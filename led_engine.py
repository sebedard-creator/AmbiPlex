import socket
import numpy as np

class LedEngine:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.last_colors = None
        
        # Détection des bandes noires (Crop)
        self.crop_top = 0
        self.crop_bottom = 90
        self.frames_with_new_crop = 0
        self.candidate_crop = (0, 90)

    def calculate_colors(self, frame, config):
        """
        frame: numpy array de forme (height, width, 3) RGB
        config: dict avec leds_top, leds_side, led_depth, led_smoothing
        Retourne une liste de triplets (R, G, B) pour chaque LED dans l'ordre (Haut -> Droite -> Bas -> Gauche)
        """
        if frame is None:
            return []
            
        h, w, _ = frame.shape
        
        # --- DÉTECTION AUTO DES BANDES NOIRES (LETTERBOX) ---
        disable_autocrop = config.get("disable_autocrop", False)
        
        if disable_autocrop:
            self.crop_top = 0
            self.crop_bottom = h
        else:
            # Auto-crop logic based on brightness variance to detect black bars
            # On ignore les 10% de chaque bord (gauche/droite) pour éviter que 
            # les artefacts de compression MP4 (ringing) sur les bords extrêmes ne faussent le crop
            safe_margin_x = max(1, int(w * 0.10))
            gray = np.mean(frame[:, safe_margin_x:w-safe_margin_x], axis=2)
            row_brightness = np.mean(gray, axis=1)
            
            # A threshold of 1.5 out of 255 to distinguish pure black from content
            active_rows = np.where(row_brightness > 1.5)[0]
            
            if len(active_rows) > 0:
                current_top = active_rows[0]
                current_bottom = active_rows[-1]
                
                # Si l'image devient PLUS GRANDE (IMAX ou 16:9 plein écran), on agrandit tout de suite
                if current_top < self.crop_top:
                    self.crop_top = current_top
                if current_bottom > self.crop_bottom:
                    self.crop_bottom = current_bottom
                    
                # Si l'image semble PLUS PETITE (Nouveau film en 2.35:1)
                # On vérifie uniquement le HAUT (top) pour la stabilité, car le BAS est souvent pollué par les sous-titres !
                if current_top > self.crop_top + 2:
                    if abs(current_top - self.candidate_crop[0]) < 2:
                        self.frames_with_new_crop += 1
                    else:
                        self.candidate_crop = (current_top, current_bottom)
                        self.frames_with_new_crop = 0
                        
                    if self.frames_with_new_crop > 40: # ~2 secondes de stabilité à 20 FPS
                        self.crop_top = current_top
                        # On force la symétrie absolue pour le bas (pour ignorer les sous-titres qui pourraient fausser la détection)
                        self.crop_bottom = 90 - current_top
                        self.frames_with_new_crop = 0
                
                # Si le haut est stable mais qu'on a juste une scène sombre sans bandes noires,
                # on permet au bottom de remonter s'il n'y a pas de bandes noires en haut
                elif self.crop_top < 5 and current_bottom < self.crop_bottom - 2:
                     if abs(current_bottom - self.candidate_crop[1]) < 2:
                        self.frames_with_new_crop += 1
                     else:
                        self.candidate_crop = (current_top, current_bottom)
                        self.frames_with_new_crop = 0
                        
                     if self.frames_with_new_crop > 40:
                        self.crop_bottom = current_bottom
                        self.frames_with_new_crop = 0

        # On ne rogne PLUS la frame complète en mémoire pour garder le ratio vertical physique !
        # frame = frame[self.crop_top:self.crop_bottom, :, :]
        
        # On utilise la hauteur réelle de l'écran pour garder l'alignement physique
        h, w, _ = frame.shape
        cfg_top = config.get("leds_top")
        leds_top = int(cfg_top if cfg_top is not None else 50)
        
        cfg_side = config.get("leds_side")
        leds_side = int(cfg_side if cfg_side is not None else 30)
        
        cfg_depth = config.get("led_depth")
        depth_pct = float(cfg_depth if cfg_depth is not None else 10) / 100.0
        
        cfg_smooth = config.get("led_smoothing")
        smoothing = float(cfg_smooth if cfg_smooth is not None else 50) / 100.0
        
        depth_y = max(1, int(h * depth_pct))
        depth_x = max(1, int(w * depth_pct))
        
        # Découpage des zones
        # Le ruban Haut/Bas doit lire la VRAIE image (sans le noir)
        top_y_end = min(self.crop_bottom, self.crop_top + depth_y)
        bottom_y_start = max(self.crop_top, self.crop_bottom - depth_y)
        
        top_zone = frame[self.crop_top : top_y_end, :]
        bottom_zone = frame[bottom_y_start : self.crop_bottom, :]
        
        # Les rubans de côté gardent la pleine hauteur physique, mais on force les bandes noires à être 100% éteintes
        left_zone = frame[:, 0:depth_x].copy()
        right_zone = frame[:, w-depth_x:w].copy()
        
        if self.crop_top > 0:
            left_zone[0:self.crop_top, :] = [0, 0, 0]
            right_zone[0:self.crop_top, :] = [0, 0, 0]
        if self.crop_bottom < h:
            left_zone[self.crop_bottom:h, :] = [0, 0, 0]
            right_zone[self.crop_bottom:h, :] = [0, 0, 0]
        
        top_colors = []
        right_colors = []
        bottom_colors = []
        left_colors = []
        
        corner_gap_pct = float(config.get("led_corner_gap", 0)) / 100.0
        gap_x = int(w * corner_gap_pct)
        gap_y = int(h * corner_gap_pct)
        eff_w = max(1, w - 2 * gap_x)
        eff_h = max(1, h - 2 * gap_y)

        # 1. Haut (Gauche vers Droite)
        if leds_top > 0:
            segment_width = eff_w / leds_top
            for i in range(leds_top):
                start = gap_x + int(i * segment_width)
                end = gap_x + int((i + 1) * segment_width)
                segment = top_zone[:, start:end]
                if segment.size > 0:
                    color = np.mean(segment, axis=(0, 1))
                else:
                    color = np.array([0,0,0])
                top_colors.append(color)
                
        # 2. Droite (Haut vers Bas)
        if leds_side > 0:
            segment_height = eff_h / leds_side
            for i in range(leds_side):
                start = gap_y + int(i * segment_height)
                end = gap_y + int((i + 1) * segment_height)
                segment = right_zone[start:end, :]
                if segment.size > 0:
                    color = np.mean(segment, axis=(0, 1))
                else:
                    color = np.array([0,0,0])
                right_colors.append(color)
                
        # 3. Bas (Droite vers Gauche pour suivre le ruban horaire)
        if leds_top > 0:
            segment_width = eff_w / leds_top
            for i in range(leds_top - 1, -1, -1):
                start = gap_x + int(i * segment_width)
                end = gap_x + int((i + 1) * segment_width)
                segment = bottom_zone[:, start:end]
                if segment.size > 0:
                    color = np.mean(segment, axis=(0, 1))
                else:
                    color = np.array([0,0,0])
                bottom_colors.append(color)
                
        # 4. Gauche (Bas vers Haut pour suivre le ruban horaire)
        if leds_side > 0:
            segment_height = eff_h / leds_side
            for i in range(leds_side - 1, -1, -1):
                start = gap_y + int(i * segment_height)
                end = gap_y + int((i + 1) * segment_height)
                segment = left_zone[start:end, :]
                if segment.size > 0:
                    color = np.mean(segment, axis=(0, 1))
                else:
                    color = np.array([0,0,0])
                left_colors.append(color)

        return self._apply_routing(top_colors, right_colors, bottom_colors, left_colors, config)

    def _apply_routing(self, top_colors, right_colors, bottom_colors, left_colors, config):
        # Routage et Décalage
        def apply_shift(arr, offset):
            if offset == 0 or len(arr) == 0:
                return arr
            black = np.array([0, 0, 0])
            if offset > 0:
                return [black] * min(offset, len(arr)) + arr[:-offset]
            else:
                return arr[-offset:] + [black] * min(-offset, len(arr))
                
        top_colors = apply_shift(top_colors, int(config.get("offset_top", 0)))
        right_colors = apply_shift(right_colors, int(config.get("offset_right", 0)))
        bottom_colors = apply_shift(bottom_colors, int(config.get("offset_bottom", 0)))
        left_colors = apply_shift(left_colors, int(config.get("offset_left", 0)))
        
        b_top = float(config.get("led_brightness_top", 100)) / 100.0
        b_right = float(config.get("led_brightness_right", 100)) / 100.0
        b_bottom = float(config.get("led_brightness_bottom", 100)) / 100.0
        b_left = float(config.get("led_brightness_left", 100)) / 100.0
        
        top_colors = [c * b_top for c in top_colors]
        right_colors = [c * b_right for c in right_colors]
        bottom_colors = [c * b_bottom for c in bottom_colors]
        left_colors = [c * b_left for c in left_colors]
        
        start_pos = config.get("led_start_pos", "top_left")
        direction = config.get("led_direction", "clockwise")
        
        if start_pos == "top_right":
            colors = right_colors + bottom_colors + left_colors + top_colors
        elif start_pos == "bottom_right":
            colors = bottom_colors + left_colors + top_colors + right_colors
        elif start_pos == "bottom_left":
            colors = left_colors + top_colors + right_colors + bottom_colors
        else: # top_left
            colors = top_colors + right_colors + bottom_colors + left_colors
            
        if direction == "counter_clockwise":
            colors.reverse()
                
        # Formatage RGB entier
        target_colors = np.array(colors, dtype=np.float32)
        
        # Smoothing (Lissage temporel)
        cfg_smooth = config.get("led_smoothing")
        smoothing = float(cfg_smooth if cfg_smooth is not None else 50) / 100.0
        
        if self.last_colors is not None and len(self.last_colors) == len(target_colors):
            alpha = 1.0 - (smoothing * 0.9)
            target_colors = self.last_colors * (1.0 - alpha) + target_colors * alpha
            
        self.last_colors = target_colors
        return np.clip(target_colors, 0, 255).astype(np.uint8).tolist()

    def process_prebaked_colors(self, rgb565_array, config):
        """
        Prend un tableau RGB565 (uint16) brut extrait du fichier .wledsub,
        le convertit en RGB888, le découpe en 4 zones et applique le routage dynamique.
        """
        cfg_top = config.get("leds_top")
        leds_top = int(cfg_top if cfg_top is not None else 50)
        
        cfg_side = config.get("leds_side")
        leds_side = int(cfg_side if cfg_side is not None else 30)
        
        expected_len = leds_top * 2 + leds_side * 2
        if len(rgb565_array) != expected_len:
            return [] # Incompatible
            
        # Conversion rapide Numpy RGB565 -> RGB888
        r = ((rgb565_array >> 11) & 0x1F) << 3
        g = ((rgb565_array >> 5) & 0x3F) << 2
        b = (rgb565_array & 0x1F) << 3
        
        rgb888_array = np.column_stack((r, g, b))
        
        idx = 0
        top_colors = list(rgb888_array[idx : idx + leds_top])
        idx += leds_top
        right_colors = list(rgb888_array[idx : idx + leds_side])
        idx += leds_side
        bottom_colors = list(rgb888_array[idx : idx + leds_top])
        idx += leds_top
        left_colors = list(rgb888_array[idx : idx + leds_side])
        
        return self._apply_routing(top_colors, right_colors, bottom_colors, left_colors, config)

    def send_ddp(self, ip, colors):
        """Envoie les couleurs en UDP via le protocole DDP (WLED)"""
        if not ip or not colors:
            return
            
        # Un seul paquet DDP pour simplifier (max ~480 LEDs par paquet)
        length = len(colors) * 3
        if length > 1440:
            length = 1440 # Truncate to fit in standard MTU if too many LEDs
            
        header = bytearray(10)
        header[0] = 0x41 # Flags: V1
        header[1] = 0x00 # Sequence (on s'en fout en DDP)
        header[2] = 0x01 # Type: RGB
        header[3] = 0x01 # ID: 1
        header[4] = 0x00 # Offset
        header[5] = 0x00
        header[6] = 0x00
        header[7] = 0x00
        header[8] = (length >> 8) & 0xFF
        header[9] = length & 0xFF
        
        payload = bytearray()
        for i in range(min(len(colors), 480)):
            r, g, b = colors[i]
            payload.append(r)
            payload.append(g)
            payload.append(b)
            
        packet = header + payload
        try:
            self.sock.sendto(packet, (ip, 4048))
        except Exception:
            pass

    def close(self):
        """Ferme proprement le socket UDP"""
        try:
            self.sock.close()
        except Exception:
            pass
