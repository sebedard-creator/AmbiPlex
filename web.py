import asyncio
import json
import os
import time
import logging
import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
from sync import PlexSynchronizer
from player import SlavePlayer
from led_engine import LedEngine

app = FastAPI()

CONFIG_FILE = "config.json"
clients = [] # list of asyncio Queues for SSE
sync_task = None
sync_instance = None
player_instance = None

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
    led_brightness: int = 80
    led_refresh_rate: int = 20
    led_refresh_native: bool = True

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
    
    led_engine_instance = LedEngine()
    
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

        sync_instance.connect()
        sync_instance.start_websocket_listener()
        await broadcast({"type": "info", "message": "Connecté au serveur Plex"})
    except Exception as e:
        await broadcast({"type": "error", "message": str(e)})
        return

    last_config_load = 0
    while True:
        try:
            # Reload config once per second to get fresh LED/IP settings without heavy I/O
            current_time = time.time()
            if current_time - last_config_load > 1.0:
                config = load_config()
                last_config_load = current_time

            if sync_instance.is_playing:
                # Application à MPV
                if not player_instance or player_instance.current_file != sync_instance.current_media_path:
                    # Nouveau fichier : On instancie ou recrée MPV (pour éviter les bugs de contexte OpenGL écran noir)
                    if player_instance:
                        try:
                            player_instance.player.terminate()
                        except Exception:
                            pass
                    
                    try:
                        player_instance = SlavePlayer(headless=config.get("headless", True))
                        player_instance.load_file(sync_instance.current_media_path, sync_instance.current_view_offset)
                        sync_instance.local_player_offset = sync_instance.current_view_offset
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
                    "dropped_frames": player_instance.get_dropped_frames() if player_instance else 0
                }
                
                # --- EXTRACTION LEDS ---
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
                if player_instance:
                    player_instance.pause()
                    sync_instance.local_player_offset = player_instance.get_offset_ms()
                    
                data = {
                    "type": "monitoring",
                    "state": "paused",
                    "offset": sync_instance.current_view_offset,
                    "local_offset": sync_instance.local_player_offset,
                    "action": "WAIT",
                    "dropped_frames": player_instance.get_dropped_frames() if player_instance else 0
                }
                
                # --- EXTRACTION LEDS MEME EN PAUSE ---
                if player_instance:
                    frame = player_instance.capture_frame()
                    if frame is not None:
                        colors = led_engine_instance.calculate_colors(frame, config)
                        ip = config.get("wled_ip")
                        if ip:
                            led_engine_instance.send_ddp(ip, colors)
                        data["colors"] = colors
                        data["crop_box"] = [int(led_engine_instance.crop_top), int(led_engine_instance.crop_bottom)]
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
                
        sleep_time = 1.0 / max(1, float(target_fps))
        await asyncio.sleep(sleep_time)

async def broadcast(data: dict):
    for q in clients:
        await q.put(data)

@app.on_event("startup")
async def startup_event():
    global sync_task
    sync_task = asyncio.create_task(background_sync_loop())

@app.get("/api/config")
def get_config():
    return load_config()

@app.post("/api/config")
async def update_config(config: ConfigModel):
    save_config(config.model_dump())
    
    global sync_instance
    global player_instance
    if sync_instance:
        sync_offset_frames = int(config.model_dump().get("sync_offset_frames", 0))
        new_offset_ms = int(sync_offset_frames * (1000 / 24))
        
        # Si l'offset change, on force un seek immédiat pour que l'utilisateur voie la différence tout de suite
        if sync_instance.sync_offset_ms != new_offset_ms:
            sync_instance.sync_offset_ms = new_offset_ms
            if player_instance:
                # Force le seek
                player_instance.seek(sync_instance.current_view_offset)
                sync_instance.local_player_offset = sync_instance.current_view_offset
                sync_instance.last_seek_time = 0
        
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
