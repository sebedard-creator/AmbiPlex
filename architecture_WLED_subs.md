# Architecture : WLED Subtitles (Pistes de Métadonnées LED)

## 1. Concept Général
Le projet évolue d'un paradigme de "Capture d'écran en Temps Réel" (CPU/GPU intensif, synchronisation élastique difficile) vers un système de **Piste de Métadonnées Pré-calculées**. 
Le concept est de scanner le film hors-ligne une seule fois pour produire un fichier ultra-léger contenant les couleurs pré-rendues. À la lecture, le serveur se contente de lire les octets correspondants au *timestamp* Plex et de les envoyer via UDP.

### Avantages :
- **0% utilisation CPU/GPU** lors de la lecture.
- **Synchronisation absolue (O(1))** : Accès direct au bon moment, sans élasticité.
- **Indépendance de la plateforme** : Le lecteur n'a plus besoin d'accélération matérielle.

---

## 2. Le Format de Fichier Universel (`.wledsub.lz4`)
Le fichier DOIT être "Future-Proof" et indépendant du nombre physique de LEDs de l'utilisateur.

### 2.1 La Résolution Spécifique au Matériel (Hardware-Specific)
Le fichier n'est pas universel. Il est encodé ("Baked") avec les dimensions physiques exactes de la télévision de l'utilisateur.
Exemple pour une configuration 64x36 :
- **Haut / Bas** : 64 zones (chacun)
- **Gauche / Droite** : 36 zones (chacun)
Total = 200 LEDs.

### 2.2 Structure Binaire (Raw `uint16` - RGB565)
Pour permettre une lecture instantanée (zéro charge mémoire, utilisation de `numpy.memmap`), le fichier N'EST PAS compressé. Afin d'économiser 33% d'espace disque sans perte visible, les couleurs utilisent le format RGB565 (16-bit) au lieu du format RGB888 (24-bit).

- **Entête (Header)** : 32 octets.
  - `[4 octets]` Signature (WLED)
  - `[4 octets]` Version (0003)
  - `[4 octets]` FPS du film (float)
  - `[4 octets]` Total Frames (uint32)
  - `[2 octets]` LEDs X (Largeur)
  - `[2 octets]` LEDs Y (Hauteur)
  - `[12 octets]` Padding
- **Corps (Payload)** : Séquence continue d'octets.
  - Chaque trame (frame) = `(X*2 + Y*2) * 2 octets (RGB565)`. Pour 64x36 = **400 octets**.
  - Si le film est à 24 FPS : 1 seconde = 9 600 octets.
  - Film de 2 heures = **~69 Mo** (Non-compressé).

---

## 3. Le Processus de Création ("Le Bake")
Un nouveau script autonome (`bake.py`) sera créé.

### Étapes du Bake :
1. L'utilisateur lance `python bake.py "MonFilm.mkv"`.
2. Le script télécharge automatiquement `ffmpeg.exe` (si manquant) et l'utilise en arrière-plan (via des pipes mémoire) pour décoder le film à vitesse maximale (Tone-Mapping HDR via zscale).
3. Le paramètre de profondeur (`led_depth`) est **figé à 10%** (le "sweet spot" Ambilight).
4. L'auto-crop dynamique détecte les bandes noires et est "baked in".
5. Les couleurs des zones sont écrites séquentiellement dans `MonFilm.wledsub.lz4` avec une compression LZ4. LZ4 est l'algorithme le plus rapide au monde en décompression (vitesse de 3 à 5 Go/s), ce qui garantit une extraction Juste-à-Temps instantanée (en dépit d'une efficacité de compression un peu moindre que GZIP).
   - **Taille Finale (LZ4)** : Entre 15 et 25 Mo au total !

---

## 4. Le Processus de Lecture (Intégration `web.py`)
La boucle principale `background_sync_loop` de `web.py` subira un refactoring hybride.

### 4.1 Logique de bascule et Extraction "Juste-à-Temps" (JIT)
Quand Plex signale la lecture de `MonFilm.mkv` :
1. Le serveur cherche `MonFilm.wledsub.lz4` (ou utilise le `RatingKey` Plex comme nom de cache, ex: `cache/12345.wledsub.lz4`).
2. **Handshake de Sécurité** : Le serveur lit les 32 octets de l'entête. Si `leds_x` et `leds_y` ne correspondent pas aux paramètres actuels de l'UI Web, il refuse le fichier et retourne en Temps Réel.
3. **S'il existe et est compatible** : Le serveur décompresse instantanément le fichier LZ4 (vitesse ~4000 Mo/s) vers un fichier cache non-compressé `Y:\AmbiPlex\cache\active_movie.wledsub_raw`. 
4. *Note Caching* : Il ne conserve qu'un seul fichier non compressé à la fois. Si un nouveau film est demandé, le fichier `active_movie.wledsub_raw` est simplement écrasé.
5. Mode "Subtitle" : Le fichier Raw décompressé est mappé en mémoire via `numpy.memmap`.
6. **S'il n'existe pas ou est incompatible** : Mode "Temps Réel". Le système classique avec MPV prend le relais.

### 4.2 La Lecture Instantanée (Memmap)
En mode "Subtitle" (sur le fichier temporaire Raw) :
```python
# 1. Obtenir le temps de Plex
temps_ms = sync_instance.current_view_offset
# 2. Calculer l'index de la trame
frame_index = int((temps_ms / 1000.0) * FPS)
# 3. Extraire les 480 couleurs instantanément depuis le disque
couleurs_virtuelles = memmap_array[frame_index]
```

### 4.3 Fin du Downscaling
Puisque le fichier est créé sur-mesure pour la TV physique, le serveur n'a plus à faire de calculs Numpy de redimensionnement (`downscale`). Il extrait la trame et la pousse en UDP vers WLED. Les paramètres `offset` et `direction` peuvent toujours être gérés, car ils ne font qu'appliquer une simple rotation circulaire (`np.roll`) sur le tableau final sans en changer la taille.

---

## 5. Résumé des Nouveaux Fichiers / Modifications
- `[NEW] bake.py` : Script CLI autonome (utilisant FFmpeg) pour analyser un film et générer le `.wledsub.lz4`.
- `[MODIFY] led_engine.py` : Ajout d'une fonction `downscale_virtual_to_physical(virtual_colors, config)`.
- `[MODIFY] web.py` : Implémentation du lecteur `Memmap` et de la condition `if has_wled_file()`.
