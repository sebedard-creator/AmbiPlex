import socket
import numpy as np
import time

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
        gray = np.mean(frame, axis=2)
        row_brightness = np.mean(gray, axis=1)
        # Seuil très bas (8/255) pour filtrer le noir absolu et le bruit de compression
        active_rows = np.where(row_brightness > 8)[0]
        
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

        # On rogne la frame en mémoire !
        frame = frame[self.crop_top:self.crop_bottom+1, :, :]
        
        # On recalcule la hauteur réelle utile
        h, w, _ = frame.shape
        leds_top = int(config.get("leds_top", 50) or 50)
        leds_side = int(config.get("leds_side", 30) or 30)
        depth_pct = float(config.get("led_depth", 10) or 10) / 100.0
        smoothing = float(config.get("led_smoothing", 50) or 50) / 100.0
        
        depth_y = max(1, int(h * depth_pct))
        depth_x = max(1, int(w * depth_pct))
        
        # Découpage des zones
        top_zone = frame[0:depth_y, :]
        bottom_zone = frame[h-depth_y:h, :]
        left_zone = frame[:, 0:depth_x]
        right_zone = frame[:, w-depth_x:w]
        
        colors = []
        
        # 1. Haut (Gauche vers Droite)
        if leds_top > 0:
            segment_width = w / leds_top
            for i in range(leds_top):
                start = int(i * segment_width)
                end = int((i + 1) * segment_width)
                segment = top_zone[:, start:end]
                if segment.size > 0:
                    color = np.mean(segment, axis=(0, 1))
                else:
                    color = np.array([0,0,0])
                colors.append(color)
                
        # 2. Droite (Haut vers Bas)
        if leds_side > 0:
            segment_height = h / leds_side
            for i in range(leds_side):
                start = int(i * segment_height)
                end = int((i + 1) * segment_height)
                segment = right_zone[start:end, :]
                if segment.size > 0:
                    color = np.mean(segment, axis=(0, 1))
                else:
                    color = np.array([0,0,0])
                colors.append(color)
                
        # 3. Bas (Droite vers Gauche pour suivre le ruban)
        if leds_top > 0:
            segment_width = w / leds_top
            for i in range(leds_top - 1, -1, -1):
                start = int(i * segment_width)
                end = int((i + 1) * segment_width)
                segment = bottom_zone[:, start:end]
                if segment.size > 0:
                    color = np.mean(segment, axis=(0, 1))
                else:
                    color = np.array([0,0,0])
                colors.append(color)
                
        # 4. Gauche (Bas vers Haut)
        if leds_side > 0:
            segment_height = h / leds_side
            for i in range(leds_side - 1, -1, -1):
                start = int(i * segment_height)
                end = int((i + 1) * segment_height)
                segment = left_zone[start:end, :]
                if segment.size > 0:
                    color = np.mean(segment, axis=(0, 1))
                else:
                    color = np.array([0,0,0])
                colors.append(color)
                
        # Formatage RGB entier
        target_colors = np.array(colors, dtype=np.float32)
        
        # Luminosité globale
        brightness = config.get("led_brightness", 80) / 100.0
        target_colors = target_colors * brightness
        
        # Smoothing (Lissage temporel)
        if self.last_colors is not None and len(self.last_colors) == len(target_colors):
            # smoothing=1.0 signifie figé, smoothing=0.0 signifie immédiat
            # Mais souvent le user le voit comme 100% = très lisse, 0% = brusque.
            alpha = 1.0 - (smoothing * 0.9) # Empêche d'atteindre 1.0 qui gèlerait l'image
            target_colors = self.last_colors * (1.0 - alpha) + target_colors * alpha
            
        self.last_colors = target_colors
        return np.clip(target_colors, 0, 255).astype(np.uint8).tolist()

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
