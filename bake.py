import sys
import os
import time
import struct
import argparse
import numpy as np
import subprocess
import urllib.request
import zipfile
import re
import lz4.frame

# URL for a static FFmpeg Windows build (GPL version includes zscale for HDR tonemapping)
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

def ensure_ffmpeg():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    exe_path = os.path.join(current_dir, "ffmpeg.exe")
    
    # 1. Check local directory
    if os.path.exists(exe_path):
        return exe_path
        
    # 2. Check system PATH
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "ffmpeg"
    except FileNotFoundError:
        pass

    # 3. Download if missing
    print("========================================")
    print("FFmpeg introuvable. Téléchargement en cours...")
    print("Cela peut prendre quelques minutes (~130 Mo).")
    print("========================================")
    zip_path = os.path.join(current_dir, "ffmpeg.zip")
    
    try:
        urllib.request.urlretrieve(FFMPEG_URL, zip_path)
        print("Extraction de FFmpeg...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith('ffmpeg.exe'):
                    file_info.filename = os.path.basename(file_info.filename)
                    zip_ref.extract(file_info, current_dir)
                    break
        os.remove(zip_path)
        print("✅ FFmpeg installé avec succès !\n")
        return exe_path
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement de FFmpeg : {e}")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        sys.exit(1)

def get_video_info(ffmpeg_path, video_path):
    cmd = [ffmpeg_path, "-i", video_path]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
    
    duration_match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", result.stderr)
    fps_match = re.search(r"(\d+(?:\.\d+)?) fps", result.stderr)
    
    duration = 0.0
    if duration_match:
        h, m, s = duration_match.groups()
        duration = int(h)*3600 + int(m)*60 + float(s)
        
    fps = 24.0
    if fps_match:
        fps = float(fps_match.group(1))
        
    return duration, fps

def process_frame(frame, crop_state, leds_x, leds_y, depth=8):
    """
    Découpe une image RGB 160x90 en zones spécifiques (Haut/Bas = leds_x, Gauche/Droite = leds_y).
    Retourne exactement (leds_x*2 + leds_y*2) * 2 octets en format RGB565.
    """
    h, w, _ = frame.shape
    
    safe_margin_x = max(1, int(w * 0.10))
    gray = np.mean(frame[:, safe_margin_x:w-safe_margin_x], axis=2)
    row_brightness = np.mean(gray, axis=1)
    active_rows = np.where(row_brightness > 1.5)[0]
    
    current_top = active_rows[0] if len(active_rows) > 0 else 0
    current_bottom = active_rows[-1] if len(active_rows) > 0 else h
    
    if current_top < crop_state['top']: crop_state['top'] = current_top
    if current_bottom > crop_state['bottom']: crop_state['bottom'] = current_bottom
    
    if current_top > crop_state['top'] + 2:
        crop_state['frames_top'] += 1
        if crop_state['frames_top'] > 40:
            crop_state['top'] = current_top
            crop_state['bottom'] = h - current_top
            crop_state['frames_top'] = 0
    elif crop_state['top'] < 5 and current_bottom < crop_state['bottom'] - 2:
        crop_state['frames_bottom'] += 1
        if crop_state['frames_bottom'] > 40:
            crop_state['bottom'] = current_bottom
            crop_state['frames_bottom'] = 0

    c_top = crop_state['top']
    c_bottom = crop_state['bottom']
    
    depth_pct = depth / 100.0
    depth_y = max(1, int(h * depth_pct))
    depth_x = max(1, int(w * depth_pct))
    
    top_y_end = min(c_bottom, c_top + depth_y)
    bottom_y_start = max(c_top, c_bottom - depth_y)
    
    top_zone = frame[c_top : top_y_end, :]
    bottom_zone = frame[bottom_y_start : c_bottom, :]
    
    left_zone = frame[:, 0:depth_x].copy()
    right_zone = frame[:, w-depth_x:w].copy()
    
    if c_top > 0:
        left_zone[0:c_top, :] = [0, 0, 0]
        right_zone[0:c_top, :] = [0, 0, 0]
    if c_bottom < h:
        left_zone[c_bottom:h, :] = [0, 0, 0]
        right_zone[c_bottom:h, :] = [0, 0, 0]
        
    eff_w, eff_h = w, h
    
    top_colors, right_colors, bottom_colors, left_colors = [], [], [], []
    
    # 1. Haut (Gauche à Droite)
    segment_width = eff_w / leds_x
    for i in range(leds_x):
        start, end = int(i * segment_width), int((i + 1) * segment_width)
        segment = top_zone[:, start:end]
        top_colors.append(np.mean(segment, axis=(0, 1)) if segment.size > 0 else np.array([0,0,0]))
            
    # 2. Droite (Haut à Bas)
    segment_height = eff_h / leds_y
    for i in range(leds_y):
        start, end = int(i * segment_height), int((i + 1) * segment_height)
        segment = right_zone[start:end, :]
        right_colors.append(np.mean(segment, axis=(0, 1)) if segment.size > 0 else np.array([0,0,0]))
            
    # 3. Bas (Droite à Gauche)
    for i in range(leds_x - 1, -1, -1):
        start, end = int(i * segment_width), int((i + 1) * segment_width)
        segment = bottom_zone[:, start:end]
        bottom_colors.append(np.mean(segment, axis=(0, 1)) if segment.size > 0 else np.array([0,0,0]))
            
    # 4. Gauche (Bas à Haut)
    for i in range(leds_y - 1, -1, -1):
        start, end = int(i * segment_height), int((i + 1) * segment_height)
        segment = left_zone[start:end, :]
        left_colors.append(np.mean(segment, axis=(0, 1)) if segment.size > 0 else np.array([0,0,0]))
            
    colors = top_colors + right_colors + bottom_colors + left_colors
    target_colors = np.clip(np.array(colors), 0, 255).astype(np.uint16)
    
    # Conversion RGB888 vers RGB565 (Poids réduit de 33%)
    r = (target_colors[:, 0] >> 3) << 11
    g = (target_colors[:, 1] >> 2) << 5
    b = (target_colors[:, 2] >> 3)
    rgb565 = (r | g | b).astype(np.uint16)
    
    # Retourne exactement 480 * 2 = 960 octets
    return rgb565.tobytes()

def run_scan(ffmpeg_path, video_path, out_path, fps, total_frames, leds_x, leds_y, depth, threads, use_advanced_tonemap=True):
    # L'astuce majeure de performance :
    # On scale d'abord l'image 4K HDR à 160x90.
    # FFmpeg applique ensuite le ToneMapping complexe uniquement sur cette image minuscule.
    if use_advanced_tonemap:
        vf_filter = "scale=160:90:force_original_aspect_ratio=decrease,pad=160:90:(ow-iw)/2:(oh-ih)/2,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=rgb24"
    else:
        # Fallback ultra-basique si zscale crash
        vf_filter = "scale=160:90:force_original_aspect_ratio=decrease,pad=160:90:(ow-iw)/2:(oh-ih)/2,format=rgb24"

    cmd = [
        ffmpeg_path,
        "-hwaccel", "auto"
    ]
    
    if threads > 0:
        cmd.extend([
            "-threads", str(threads),
            "-filter_threads", str(threads),
            "-filter_complex_threads", str(threads)
        ])
        
    cmd.extend([
        "-i", video_path,
        "-vf", vf_filter,
        "-f", "image2pipe",
        "-pix_fmt", "rgb24",
        "-vcodec", "rawvideo",
        "-"
    ])

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)
    
    if threads > 0:
        # Restriction matérielle stricte (Affinity Mask) pour Windows
        # mask = 1 (core 0), mask = 3 (cores 0,1), mask = 15 (cores 0,1,2,3)
        mask = (1 << threads) - 1
        try:
            # CREATE_NO_WINDOW = 0x08000000 to hide powershell
            subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-Process -Id {process.pid}).ProcessorAffinity = {mask}"], creationflags=0x08000000)
        except Exception:
            pass

    crop_state = {'top': 0, 'bottom': 90, 'frames_top': 0, 'frames_bottom': 0}
    frame_size = 160 * 90 * 3
    start_time = time.time()
    
    i = 0
    tmp_path = out_path + ".tmp"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
        
    fallback_triggered = False
    fatal_error = False
    
    try:
        # Utilisation de LZ4 (L'algorithme de décompression le plus rapide au monde)
        with lz4.frame.open(tmp_path, mode='wb', compression_level=0) as f:
            header = struct.pack('<4s4sfIHH12x', b'WLED', b'0003', float(fps), int(total_frames), int(leds_x), int(leds_y))
            f.write(header)
            
            while True:
                raw_data = process.stdout.read(frame_size)
                
                # Vérifier si FFmpeg a planté dès la première frame (ex: zscale non supporté)
                if i == 0 and (not raw_data or len(raw_data) != frame_size):
                    if use_advanced_tonemap:
                        fallback_triggered = True
                    else:
                        fatal_error = True
                    break
                
                if not raw_data or len(raw_data) != frame_size:
                    break # Fin de la vidéo
                    
                frame = np.frombuffer(raw_data, dtype=np.uint8).reshape((90, 160, 3))
                bytes_data = process_frame(frame, crop_state, leds_x, leds_y, depth)
                f.write(bytes_data)
                
                i += 1
                if i % 50 == 0:
                    elapsed = time.time() - start_time
                    progress = (i / total_frames) * 100
                    fps_scan = i / elapsed if elapsed > 0 else 0
                    print(f"\rProgression: {progress:.2f}% ({i}/{total_frames}) - Vitesse: {fps_scan:.1f} fps", end="", flush=True)
                    
        process.terminate()
        
        if fallback_triggered:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            print("\n⚠️ Erreur de filtre avancé (zscale). Tentative de fallback basique...", flush=True)
            return False
            
        if fatal_error:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            print("\n❌ Erreur fatale: Impossible d'extraire la vidéo avec FFmpeg.", flush=True)
            sys.exit(1)
            
        print(f"\n✅ Terminé avec succès en {time.time() - start_time:.1f} secondes ! ({i} images traitées)", flush=True)
        
        # Validation atomique de succès
        if os.path.exists(out_path):
            os.remove(out_path)
        os.rename(tmp_path, out_path)
        return True
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Scan annulé par l'utilisateur.", flush=True)
        process.terminate()
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Bake a video into a .wledsub metadata file using FFmpeg.")
    parser.add_argument("video_path", help="Chemin du fichier vidéo à analyser")
    parser.add_argument("--leds-x", type=int, required=True, help="Nombre de LEDs sur la largeur (ex: 64)")
    parser.add_argument("--leds-y", type=int, required=True, help="Nombre de LEDs sur la hauteur (ex: 36)")
    parser.add_argument("--depth", type=int, default=8, help="Profondeur de la zone de scan en pourcentage (défaut: 8)")
    parser.add_argument("--threads", type=int, default=0, help="Nombre de threads FFmpeg (0 = auto, 1 = faible usage CPU)")
    args = parser.parse_args()

    video_path = args.video_path
    if not os.path.exists(video_path):
        print(f"Erreur : Le fichier {video_path} n'existe pas.")
        sys.exit(1)

    print("========================================")
    print("🎬 AmbiPlex Baker (.wledsub generator) - FFmpeg Edition")
    print("========================================")
    
    ffmpeg_path = ensure_ffmpeg()
    
    print(f"Analyse de : {os.path.basename(video_path)}")
    duration, fps = get_video_info(ffmpeg_path, video_path)
    
    if duration <= 0:
        print("Erreur : Impossible de lire la durée du fichier avec FFmpeg.")
        sys.exit(1)
        
    total_frames = int(duration * fps)
    print(f"Format  : {fps:.3f} FPS")
    print(f"Durée   : {duration:.2f} secondes")
    print(f"Trâmes  : {total_frames} images à extraire")
    
    out_path = os.path.splitext(video_path)[0] + ".wledsub.lz4"
    print(f"Sortie  : {out_path}", flush=True)
    print(f"Setup   : {args.leds_x}x{args.leds_y} ({args.leds_x*2 + args.leds_y*2} LEDs) | Profondeur: {args.depth}%", flush=True)
    print(f"CPU     : {args.threads if args.threads > 0 else 'Illimité (Auto)'} Threads", flush=True)
    print("Lancement du scan... (Ctrl+C pour annuler)", flush=True)

    success = run_scan(ffmpeg_path, video_path, out_path, fps, total_frames, args.leds_x, args.leds_y, args.depth, args.threads, use_advanced_tonemap=True)
    if not success:
        run_scan(ffmpeg_path, video_path, out_path, fps, total_frames, args.leds_x, args.leds_y, args.depth, args.threads, use_advanced_tonemap=False)

if __name__ == "__main__":
    main()
