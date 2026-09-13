import os
import struct
import numpy as np
import lz4.frame
import logging
import asyncio
import time

logger = logging.getLogger("WledReader")

class WledSubtitleReader:
    def __init__(self, cache_dir="cache"):
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
        self.active_file = None
        self.memmap_array = None
        
        self.fps = 24.0
        self.total_frames = 0
        self.leds_x = 0
        self.leds_y = 0
        self._checked_key = None
        self._checked_signature = None
        self._next_check = 0.0
        self._raw_path = None

    def needs_check(self, video_path, expected_x, expected_y):
        return (self._checked_key != (video_path, expected_x, expected_y)
                or time.monotonic() >= self._next_check)

    async def ensure_compatible(self, video_path, expected_x, expected_y):
        if not self.needs_check(video_path, expected_x, expected_y):
            return self.is_active()
        # One caller owns the reader. Finish its worker before allowing cleanup.
        task = asyncio.create_task(asyncio.to_thread(
            self.load_if_compatible, video_path, expected_x, expected_y))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            finally:
                self.close()
            raise
        
    def load_if_compatible(self, video_path, expected_x, expected_y):
        """
        Cherche le fichier .wledsub.lz4. S'il existe, l'extrait dans le cache
        et le mappe en mémoire SI la configuration matérielle correspond.
        """
        if not video_path:
            self.close()
            return False

        key = (video_path, expected_x, expected_y)
        if not self.needs_check(*key):
            return self.is_active()
        wled_path = os.path.splitext(video_path)[0] + ".wledsub.lz4"
        signature = None
        try:
            try:
                stat = os.stat(wled_path)
                signature = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            except FileNotFoundError:
                pass
            if key == self._checked_key and signature == self._checked_signature:
                return self.is_active()
            self.close()
            if signature is None:
                return False
            with lz4.frame.open(wled_path, 'rb') as f:
                header = f.read(32)
                if len(header) < 32:
                    return False
                    
                magic, version, fps, total_frames, leds_x, leds_y = struct.unpack('<4s4sfIHH', header[:20])
                
                if magic != b'WLED' or version != b'0003':
                    logger.warning(f"Version incompatible du fichier .wledsub.lz4: {version}")
                    return False
                    
                if int(leds_x) != expected_x or int(leds_y) != expected_y:
                    logger.warning(f"Fichier incompatible: {int(leds_x)}x{int(leds_y)} au lieu de {expected_x}x{expected_y}")
                    return False
                    
                self.fps = float(fps)
                self.total_frames = int(total_frames)
                self.leds_x = int(leds_x)
                self.leds_y = int(leds_y)
                
                # Extraction JIT
                raw_path = os.path.join(self.cache_dir, "active_movie.wledsub_raw")
                logger.info(f"Décompression JIT LZ4 vers {raw_path}...")
                
                # Nombre d'éléments par frame (1 element uint16 par LED)
                frame_elements = self.leds_x * 2 + self.leds_y * 2
                
                with open(raw_path, 'wb') as raw_file:
                    self._raw_path = raw_path
                    while chunk := f.read(1024 * 1024):
                        raw_file.write(chunk)
                    
            # Calculate actual frames to avoid WinError 8 if FFmpeg extracted fewer frames than the theoretical header value
            file_size = os.path.getsize(raw_path)
            actual_frames = file_size // (frame_elements * 2)
            self.total_frames = actual_frames
            
            # Mapper le cache en mémoire (0 RAM utilisée avant accès)
            self.memmap_array = np.memmap(raw_path, dtype=np.uint16, mode='r', shape=(self.total_frames, frame_elements))
            
            self.active_file = video_path
            logger.info(f"Fichier WLEDSUB LZ4 chargé avec succès : {self.total_frames} images")
            return True
                
        except Exception as e:
            import traceback
            logger.error(f"Erreur lors du chargement de {wled_path}: {e}\n{traceback.format_exc()}")
            self.close()
            signature = None  # Retry transient read/decompression errors.
            return False
        finally:
            self._checked_key = key
            self._checked_signature = signature
            self._next_check = time.monotonic() + 1.0
            
    def is_active(self):
        return self.memmap_array is not None
        
    def close(self):
        self.memmap_array = None
        self.active_file = None
        self._checked_key = None
        self._checked_signature = None
        self._next_check = 0.0
        if self._raw_path is not None:
            try:
                os.remove(self._raw_path)
            except FileNotFoundError:
                pass
            except OSError as e:
                logger.warning(f"Impossible de supprimer le cache {self._raw_path}: {e}")
            self._raw_path = None
        
    def get_colors_at_time(self, time_ms):
        if not self.is_active():
            return None
            
        frame_index = int((time_ms / 1000.0) * self.fps)
        if frame_index < 0:
            frame_index = 0
        if frame_index >= self.total_frames:
            frame_index = self.total_frames - 1
            
        # A tiny owned frame lets Windows release the mapping on movie changes.
        return self.memmap_array[frame_index].copy()
