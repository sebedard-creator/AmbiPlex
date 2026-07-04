import asyncio
import json
import os
import time
import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
from sync import PlexSynchronizer
from player import SlavePlayer
from led_engine import LedEngine
from wled_reader import WledSubtitleReader

app = FastAPI()

CONFIG_FILE = "config.json"
clients = [] # list of asyncio Queues for SSE
sync_task = None
sync_instance = None
player_instance = None
wled_reader_instance = None

logger = logging.getLogger("WebUI")

from typing import Dict

class ConfigModel(BaseModel):
    plex_url: str
    plex_token: str
    master_client: str
    headless: bool = True
    sync_offset_frames: int = 0
    presets: Dict[str, int] = {}
    current_preset: str = ""
    wled_ip: str = ""
    leds_top: int = 50
    leds_side: int = 30
    led_depth: int = 15
    led_smoothing: int = 30
    led_brightness_top: int = 100
    led_brightness_right: int = 100
    led_brightness_bottom: int = 100
    led_brightness_left: int = 100
    led_refresh_rate: int = 20
    led_refresh_native: bool = True
    led_corner_gap: int = 0
    led_start_pos: str = "top_left"
    led_direction: str = "clockwise"
    offset_top: int = 0
    offset_right: int = 0
    offset_bottom: int = 0
    offset_left: int = 0


    disable_autocrop: bool = False

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"plex_url": "http://127.0.0.1:32400", "plex_token": "", "master_client": "Sony Bravia", "headless": True}

def save_config(config_data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

async def background_sync_loop():
    global sync_instance
    global player_instance
    global led_engine_instance
    global wled_reader_instance
    
    led_engine_instance = LedEngine()
    wled_reader_instance = WledSubtitleReader()
    
    config = load_config()
    sync_offset_frames = int(config.get("sync_offset_frames", 0))
    sync_offset_ms = int(sync_offset_frames * (1000 / 24))
    sync_instance = PlexSynchronizer(config.get("plex_url"), config.get("plex_token"), config.get("master_client"), sync_offset_ms)
    
    player_instance = None
    
    # On laisse un peu de temps au serveur pour démarrer
    await asyncio.sleep(2)
    
    try:
        loop = asyncio.get_running_loop()
        
        def combo_logger(combo):
            async def update_combo():
                cfg = load_config()
                presets = cfg.get("presets", {})
                if combo not in presets:
                    presets[combo] = 0
                cfg["presets"] = presets
                cfg["current_preset"] = combo
                save_config(cfg)
                
                # Appliquer le nouvel offset localement
                sync_offset_frames = presets[combo]
                global sync_instance
                global player_instance
                if sync_instance:
                    new_offset_ms = int(sync_offset_frames * (1000 / 24))
                    if sync_instance.sync_offset_ms != new_offset_ms:
                        sync_instance.sync_offset_ms = new_offset_ms
                        
                await broadcast({"type": "info", "message": f"Preset actif : {combo}"})
                await broadcast({"type": "preset_changed", "combo": combo, "offset_frames": sync_offset_frames})
                
            asyncio.run_coroutine_threadsafe(update_combo(), loop)
            
        def sync_logger(level, msg):
            # Utilisez la boucle capturée ci-dessus (ligne 65) pour envoyer le broadcast thread-safe
            asyncio.run_coroutine_threadsafe(broadcast({"type": level, "message": msg}), loop)
            
        sync_instance.combo_callback = combo_logger
        sync_instance.log_callback = sync_logger

        while True:
            try:
                sync_instance.connect()
                sync_instance.start_websocket_listener()
                await broadcast({"type": "info", "message": "Connecté au serveur Plex"})
                break
            except Exception as e:
                await broadcast({"type": "error", "message": f"Erreur Plex : {e} (Nouvelle tentative dans 5s...)"})
                await asyncio.sleep(5)
    except Exception as e:
        await broadcast({"type": "error", "message": str(e)})
        return

    last_config_load = 0
    next_frame_time = time.perf_counter()
    last_playing_state = False
    
    while True:
        loop_start_time = time.perf_counter()
        try:
            current_playing_state = sync_instance.is_playing
            
            # Reload config once per second to get fresh LED/IP settings without heavy I/O
            current_time = time.time()
            if current_time - last_config_load > 1.0:
                config = load_config()
                last_config_load = current_time

            if sync_instance.is_playing:
                # --- PIVOT: VÉRIFICATION DU FICHIER WLEDSUB ---
                expected_x = int(config.get("leds_top", 50))
                expected_y = int(config.get("leds_side", 30))
                
                is_wledsub = False
                if sync_instance.current_media_path:
                    if wled_reader_instance.active_file != sync_instance.current_media_path:
                        wled_reader_instance.close()
                        
                    was_active = wled_reader_instance.is_active()
                    is_wledsub = wled_reader_instance.load_if_compatible(sync_instance.current_media_path, expected_x, expected_y)
                    
                    if is_wledsub and not was_active:
                        await broadcast({"type": "info", "message": f"✅ WLEDSUB DÉTECTÉ ET IMPORTÉ EN RAM ({expected_x}x{expected_y})"})
                        
                if current_playing_state and not last_playing_state:
                    mode = "WLEDSUB (0% CPU)" if is_wledsub else "MPV (Temps Réel)"
                    await broadcast({"type": "info", "message": f"▶️ Lancement de l'extraction LED via {mode}"})
                
                if is_wledsub:
                    # MODE ZERO CPU
                    if player_instance:
                        try: player_instance.quit()
                        except: pass
                        player_instance = None
                        
                    sync_instance.local_player_offset = sync_instance.current_view_offset
                    
                    data = {
                        "type": "monitoring",
                        "state": "playing (wledsub)",
                        "offset": sync_instance.current_view_offset,
                        "local_offset": sync_instance.local_player_offset,
                        "action": "SYNC (0% CPU)",
                        "dropped_frames": 0,
                        "loop_time_ms": int((time.perf_counter() - loop_start_time) * 1000)
                    }
                    
                    # --- EXTRACTION LEDS DEPUIS MEMMAP ---
                    raw_rgb565 = wled_reader_instance.get_colors_at_time(sync_instance.current_view_offset)
                    if raw_rgb565 is not None:
                        colors = led_engine_instance.process_prebaked_colors(raw_rgb565, config)
                        ip = config.get("wled_ip")
                        if ip and colors:
                            led_engine_instance.send_ddp(ip, colors)
                        data["colors"] = colors
                        data["crop_box"] = [0, 90]
                else:
                    # Application à MPV (Fallback)
                    if not player_instance or player_instance.current_file != sync_instance.current_media_path:
                        # Nouveau fichier : On instancie ou recrée MPV (pour éviter les bugs de contexte OpenGL écran noir)
                        if player_instance:
                            try:
                                player_instance.player.terminate()
                            except Exception:
                                pass
                        
                        try:
                            player_instance = SlavePlayer(headless=config.get("headless", True))
                            success = player_instance.load_file(sync_instance.current_media_path, sync_instance.current_view_offset)
                            if success:
                                sync_instance.local_player_offset = sync_instance.current_view_offset
                            else:
                                player_instance.quit()
                                player_instance = None
                        except Exception as e:
                            logger.error(f"Impossible de créer le lecteur MPV : {e}")
                            player_instance = None
                    elif player_instance:
                        # Mise à jour de l'offset local seulement s'il est valide
                        current_mpv_offset = player_instance.get_offset_ms()
                        if current_mpv_offset > 0:
                            sync_instance.local_player_offset = current_mpv_offset
    
                    # On calcule l'action *après* avoir mis à jour l'offset
                    action = sync_instance.compute_chase_speed(sync_instance.local_player_offset)
                    
                    if player_instance:
                        player_instance.play()
                        
                        if action:
                            player_instance.set_speed(action)
                        else:
                            # Seek brutal
                            player_instance.seek(sync_instance.current_view_offset)
                            # On triche un peu l'offset local pour éviter une boucle de seek au prochain tick
                            sync_instance.local_player_offset = sync_instance.current_view_offset
                    
                    data = {
                        "type": "monitoring",
                        "state": "playing",
                        "offset": sync_instance.current_view_offset,
                        "local_offset": sync_instance.local_player_offset,
                        "action": action if action else "SEEK",
                        "dropped_frames": player_instance.get_dropped_frames() if player_instance else 0,
                        "loop_time_ms": int((time.perf_counter() - loop_start_time) * 1000)
                    }
                    
                    # --- EXTRACTION LEDS MPV ---
                    if player_instance:
                        frame = player_instance.capture_frame()
                        if frame is not None:
                            colors = led_engine_instance.calculate_colors(frame, config)
                            ip = config.get("wled_ip")
                            if ip:
                                led_engine_instance.send_ddp(ip, colors)
                            data["colors"] = colors # Envoyer à l'UI pour la simulation
                            data["crop_box"] = [int(led_engine_instance.crop_top), int(led_engine_instance.crop_bottom)]
            else:
                if sync_instance.current_media_path is None:
                    # L'utilisateur a quitté le film (retour au menu), on libère tout
                    if player_instance:
                        try: player_instance.quit()
                        except: pass
                        player_instance = None
                    if wled_reader_instance:
                        wled_reader_instance.close()
                elif wled_reader_instance and wled_reader_instance.is_active():
                    # Pause en mode WLEDSUB
                    sync_instance.local_player_offset = sync_instance.current_view_offset
                    data = {
                        "type": "monitoring",
                        "state": "paused (wledsub)",
                        "offset": sync_instance.current_view_offset,
                        "local_offset": sync_instance.local_player_offset,
                        "action": "WAIT",
                        "dropped_frames": 0,
                        "loop_time_ms": int((time.perf_counter() - loop_start_time) * 1000)
                    }
                    raw_rgb565 = wled_reader_instance.get_colors_at_time(sync_instance.current_view_offset)
                    if raw_rgb565 is not None:
                        colors = led_engine_instance.process_prebaked_colors(raw_rgb565, config)
                        ip = config.get("wled_ip")
                        if ip and colors:
                            led_engine_instance.send_ddp(ip, colors)
                        data["colors"] = colors
                        data["crop_box"] = [0, 90]
                else:
                    # Pause en mode MPV
                    if player_instance:
                        player_instance.pause()
                        sync_instance.local_player_offset = player_instance.get_offset_ms()
                        
                    data = {
                        "type": "monitoring",
                        "state": "paused",
                        "offset": sync_instance.current_view_offset,
                        "local_offset": sync_instance.local_player_offset,
                        "action": "WAIT",
                        "dropped_frames": player_instance.get_dropped_frames() if player_instance else 0,
                        "loop_time_ms": int((time.perf_counter() - loop_start_time) * 1000)
                    }
                    
                    if player_instance:
                        frame = player_instance.capture_frame()
                        if frame is not None:
                            colors = led_engine_instance.calculate_colors(frame, config)
                            ip = config.get("wled_ip")
                            if ip:
                                led_engine_instance.send_ddp(ip, colors)
                            data["colors"] = colors
                            data["crop_box"] = [int(led_engine_instance.crop_top), int(led_engine_instance.crop_bottom)]
            
            last_playing_state = current_playing_state
            await broadcast(data)
        except Exception as e:
            import traceback
            logger.error(f"Erreur dans la boucle principale: {e}\n{traceback.format_exc()}")
            
        # Calcul du temps d'attente (Refresh Rate)
        target_fps = int(config.get("led_refresh_rate", 20))
        if config.get("led_refresh_native") and player_instance and player_instance.player:
            try:
                native_fps = player_instance.player.container_fps
                if native_fps and native_fps > 0:
                    target_fps = native_fps
            except Exception:
                pass
                
        frame_time = 1.0 / max(1, float(target_fps))
        next_frame_time += frame_time
        
        now = time.perf_counter()
        sleep_duration = next_frame_time - now
        
        if sleep_duration > 0:
            await asyncio.sleep(sleep_duration)
        else:
            await asyncio.sleep(0.001)
            next_frame_time = time.perf_counter()

async def broadcast(data: dict):
    for q in clients:
        await q.put(data)

@app.on_event("startup")
async def startup_event():
    global sync_task
    sync_task = asyncio.create_task(background_sync_loop())

from fastapi.responses import JSONResponse

@app.get("/api/config")
def get_config():
    headers = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    return JSONResponse(content=load_config(), headers=headers)

@app.post("/api/config")
async def update_config(config: ConfigModel):
    try:
        old_config = load_config()
        new_config = config.model_dump()
        save_config(new_config)
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        raise e
    
    global sync_instance
    global player_instance
    if sync_instance:
        sync_offset_frames = int(new_config.get("sync_offset_frames", 0))
        new_offset_ms = int(sync_offset_frames * (1000 / 24))
        
        # Si l'offset change, on force un seek immédiat
        if sync_instance.sync_offset_ms != new_offset_ms:
            sync_instance.sync_offset_ms = new_offset_ms
            if player_instance:
                player_instance.seek(sync_instance.current_view_offset)
                sync_instance.local_player_offset = sync_instance.current_view_offset
                sync_instance.last_seek_time = 0
                
        # Reconnecter à chaud si les identifiants ont changé
        if (old_config.get("plex_url") != new_config.get("plex_url") or
            old_config.get("plex_token") != new_config.get("plex_token") or
            old_config.get("master_client") != new_config.get("master_client")):
            sync_instance.reconnect(new_config.get("plex_url"), new_config.get("plex_token"), new_config.get("master_client"))
        
    return {"status": "success"}

# Assurez-vous que le dossier static existe
if not os.path.exists("static"):
    os.makedirs("static")
    
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/stream")
async def stream(request: Request):
    q = asyncio.Queue()
    clients.append(q)
    
    # Push immediate state so the UI log shows it even if it started earlier
    if sync_instance and sync_instance.current_title:
        await q.put({"type": "info", "message": f"Média actuel : {sync_instance.current_title} ({sync_instance.current_media_path})"})
    
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                data = await q.get()
                yield f"data: {json.dumps(data)}\n\n"
        finally:
            clients.remove(q)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run("web:app", host="0.0.0.0", port=5777, reload=False)
