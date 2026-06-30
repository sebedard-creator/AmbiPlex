# CONTEXTE DU PROJET : PLEX-WLED HEADLESS AMBILIGHT SYNC

## 🚨 PRIORITÉ MEGA ABSOLUE : GESTION D'ÉTAT ET DOCUMENTATION 🚨
À chaque itération, modification ou ajout de code (même le plus mineur ou subtil), tu DOIS IMPÉRATIVEMENT tenir à jour ces deux fichiers :
1. **`LED_Strip_Master_Prompt.md`** : Doit être mis à jour continuellement pour refléter les nouvelles décisions architecturales, les paramètres validés ou les changements de cap.
2. **`changelog.md`** : Doit documenter précisément, étape par étape, ce qui vient d'être modifié, ajouté ou corrigé.
3. **Indépendance Totale** : Le logiciel ne doit avoir aucune dépendance externe au niveau du système. Tout doit être contenu de façon isolée dans `Y:\LED Strip` (via un environnement virtuel `venv` local).
*Il est strictement interdit de me fournir du code ou de passer à l'étape suivante sans avoir préalablement mis à jour ces deux fichiers.*

---

Agis en tant qu'architecte logiciel et expert Python. Je développe une solution "Ambilight" 100% logicielle, locale et sans latence. Le système doit analyser les bordures d'un film joué sur Plex (Sony Bravia Android TV) et envoyer les couleurs à un ESP32 (WLED) à 20 FPS. 

Le système est un script Python "Slave Player" headless tournant sur une machine avec une carte graphique Nvidia Quadro P600 (décodage matériel NVDEC). Le flux doit être ultra-léger (CPU quasi inactif).

## 🚫 CE QU'IL NE FAUT PAS FAIRE (Pistes rejetées lors de la conception)
* **Pas de matériel externe :** Pas de caméra, pas de splitter HDMI.
* **Pas de capture d'écran Android TV :** Pas de grabber sur la télé (provoque du stuttering).
* **Pas de fonction "Watch Together" de Plex :** La latence n'est pas tolérable pour de l'éclairage.
* **Pas d'OpenCV pour lire le fichier :** Le `Random Access Seek` (sauter d'une frame à l'autre) détruit le CPU à 20 FPS à cause du décodage des Keyframes (H.264/HEVC).
* **AUCUNE MANIPULATION D'IMAGE DANS PYTHON :** Interdiction d'utiliser Python (Numpy ou OpenCV) pour redimensionner l'image 4K ou pour créer des masques complexes en forme de "beigne". Le CPU doit être épargné.

## ✅ ARCHITECTURE REQUISE (Pistes validées)
Le système doit être divisé en 4 modules asynchrones/threadés interconnectés.

### 1. Module de Synchronisation (PlexAPI / WebSockets)
* Écoute le serveur Plex via WebSockets.
* Détecte quand la lecture démarre sur le client maître (Bravia) et récupère le chemin du fichier local.
* Fait un polling du `viewOffset` (timecode) du maître.
* **Logique de "Chase" élastique :** Compare le timecode maître avec le timecode du lecteur esclave local (MPV).
  * Si l'écart est < 2 secondes : Micro-ajustements de la vitesse de MPV (ex: 1.05x pour rattraper, 0.95x pour attendre). Pas de sauts brusques.
  * Si l'écart est > 2 secondes (ex: avance rapide) : Forcer un `Seek` brutal sur MPV.

### 2. Module Lecteur Esclave (python-mpv)
* Utilise `python-mpv` pour lire le fichier localement en mode *headless*.
* **Audio :** Désactivé (`--no-audio`).
* **Décodage et Downscaling matériel OBLIGATOIRE :** Utilise l'accélération de la puce NVDEC (Quadro P600).
* **Paramètres MPV exigés :** * `hwdec='auto'` ou `hwdec='nvdec'`
  * `vo='gpu'`
  * `vf='scale=128:72,cropdetect,crop'` (Délègue le downscaling à 128x72 et le retrait automatique des bandes noires directement à la carte graphique).

### 3. Module d'Extraction de Couleurs (Numpy)
* Boucle tournant à 20 Hz (20 FPS / ~50ms).
* Extrait la frame actuelle depuis le buffer mémoire de MPV (la frame est déjà à 128x72 et sans bandes noires).
* Utilise le **slicing Numpy** (lecture de mémoire rapide) pour isoler les bordures externes (ex: les 10 premières/dernières lignes et colonnes).
* Calcule la moyenne RGB pour chaque segment correspondant à la disposition physique du ruban LED.
* **Lissage temporel :** Applique une formule de transition (`Nouvelle Couleur = 70% Nouvelle Frame + 30% Ancienne Frame`) pour éviter l'effet stroboscopique.

### 4. Module Réseau (Transmetteur UDP/WLED)
* Formate les valeurs RGB extraites.
* Envoie les données en réseau local vers l'IP de l'ESP32.
* **Protocole OBLIGATOIRE :** Utiliser **DDP (Distributed Display Protocol)** ou à défaut **E1.31 (sACN)** via UDP. Pas de requêtes HTTP JSON (trop lent pour 20 FPS).

### 5. Module Web UI (FastAPI)
* Interface légère sur le port 5777 gérant la configuration et le monitoring.
* Utilise FastAPI + Uvicorn pour ne pas surcharger le processeur.
* Frontend avec design premium (Glassmorphism, Vanilla CSS).
* Fichier local `config.json` pour stocker (PLEX_URL, PLEX_TOKEN, MASTER_CLIENT).

## SPÉCIFICATIONS MATÉRIELLES VALIDÉES
* **TV** : 43x25 pouces.
* **Rubans LED** : WS2812b (60 LEDs/mètre).
* **Disposition (Vue de face)** :
  * Haut : 66 LEDs (Démarrage: LED #1 en Haut-Gauche)
  * Droite : 38 LEDs
  * Bas : 66 LEDs
  * Gauche : 38 LEDs
  * **TOTAL : 208 LEDs**

## MISSION ACTUELLE
Les Modules 1, 2, 3, 4 et 5 sont tous implémentés et fonctionnels. L'extraction des couleurs (Numpy/Pillow/MPV), le simulateur Web avec numérotation d'orientation, et l'envoi DDP vers WLED sont terminés. 
L'interface Web offre un "Live Monitoring" complet incluant la vitesse de rattrapage, le compteur de "Dropped Frames" et les limites de "l'Auto-Crop" (qui détecte les bandes noires de façon mathématique et symétrique pour ignorer les sous-titres). Le moteur MPV est optimisé pour les chutes vers le décodage processeur avec `vd-lavc-fast`.

La toute dernière étape (Priorité Mineure) sera le développement d'une **Application Compagnon Android (Kotlin)** permettant d'ajuster l'offset de synchronisation et la luminosité (`/api/config`) directement depuis un téléphone sans devoir ouvrir l'interface web sur un ordinateur.