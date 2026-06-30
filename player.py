import os
import sys

# On s'assure que Python trouve le DLL mpv dans le dossier actuel
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = current_dir + os.pathsep + os.environ.get("PATH", "")
if hasattr(os, 'add_dll_directory'):
    try:
        os.add_dll_directory(current_dir)
    except Exception:
        pass

import mpv
import logging

logger = logging.getLogger("SlavePlayer")

class SlavePlayer:
    def __init__(self, headless=True):
        self.headless = headless
        self.current_file = None
        
        # Options strictes requises par l'architecture
        kwargs = {
            'hwdec': 'auto-copy', # Utiliser auto-copy pour rapatrier l'image en RAM
            'ao': 'null',         # Bypass complet de l'audio
            'hr-seek': 'yes',     # Forcer la recherche à la frame exacte
            'vd-lavc-fast': 'yes', # Accélérer le décodage CPU (si le GPU n'est pas supporté)
            'vd-lavc-skiploopfilter': 'all', # Ignorer les filtres de deblocking (énorme gain CPU, invisible en 160x90)
            'log_handler': self._mpv_log
        }
        
        if headless:
            kwargs['vo'] = 'null'
            kwargs['force_window'] = 'no'
        else:
            kwargs['vo'] = 'gpu'
            kwargs['force_window'] = 'yes'
            kwargs['geometry'] = '50%' # Fenêtre visible de taille moyenne

        try:
            self.player = mpv.MPV(**kwargs)
            logger.info(f"Lecteur MPV initialisé avec succès (Headless: {headless})")
        except Exception as e:
            logger.error(f"Erreur fatale d'initialisation MPV. Le fichier mpv-2.dll est-il présent dans le dossier ? Erreur : {e}")
            raise

    def _mpv_log(self, loglevel, component, message):
        if loglevel in ['warn', 'error', 'fatal']:
            logger.warning(f"[MPV] {component}: {message}")

    def load_file(self, filepath: str, start_time_ms: int = 0):
        if not filepath or not os.path.exists(filepath):
            logger.error(f"Fichier vidéo local introuvable : {filepath}")
            return

        self.current_file = filepath
        logger.info(f"Chargement dans MPV : {filepath} à {start_time_ms}ms")
        self.player.play(filepath)
        self.player.wait_until_playing()
        
        if start_time_ms > 0:
            self.seek(start_time_ms)
            
    def play(self):
        self.player.pause = False

    def pause(self):
        self.player.pause = True

    def capture_frame(self, width=160, height=90):
        try:
            from PIL import Image
            import numpy as np
            # Capture la frame brute
            img = self.player.screenshot_raw()
            if img:
                # Resize très rapide
                small = img.resize((width, height), Image.Resampling.NEAREST)
                return np.array(small)
        except Exception:
            pass
        return None

    def seek(self, time_ms: int):
        try:
            self.player.time_pos = time_ms / 1000.0
        except Exception as e:
            logger.warning(f"Erreur seek MPV: {e}")

    def set_speed(self, speed: float):
        if speed and 0.5 <= speed <= 2.0:
            self.player.speed = speed

    def get_offset_ms(self) -> int:
        if self.player.time_pos is not None:
            return int(self.player.time_pos * 1000)
        return 0

    def get_dropped_frames(self) -> int:
        drops = 0
        try:
            drops += int(self.player.decoder_frame_drop_count or 0)
        except Exception:
            pass
            
        try:
            drops += int(self.player.frame_drop_count or 0)
        except Exception:
            pass
            
        return drops

    def quit(self):
        self.player.terminate()
