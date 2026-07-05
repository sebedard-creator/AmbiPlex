# Architecture du Projet - AmbiPlex

## 1. Vue d'Ensemble
AmbiPlex est un pont réseau local permettant de synchroniser un ruban LED (piloté par un contrôleur ESP32 / WLED) avec le flux vidéo en cours de lecture sur un client Plex.
Le système agit en "Man-in-the-Middle" : il écoute les évènements de lecture du serveur Plex, lance une instance invisible de lecteur vidéo (MPV) parfaitement synchronisée, extrait les couleurs des bordures de l'image en mémoire vive, et les transmet en UDP au contrôleur LED sans aucun retard perceptif.

## 2. Stack Technique
* **Langage Principal** : Python 3.10+
* **Interface Web** : FastAPI + Uvicorn, Vanilla JS / CSS (Architecture Glassmorphism), SSE (Server-Sent Events) pour le temps réel.
* **Moteur Vidéo** : `python-mpv` (libmpv) configuré en `headless` (`vo=null` ou lecture matérielle NVDEC). L'extraction d'image se fait via `screenshot_raw` en 160x90.
* **Traitement d'Image** : `Pillow` (downscaling immédiat) + `Numpy` (slicing matriciel ultra-rapide et détection de letterbox).
* **Protocole Réseau LED** : DDP (Distributed Display Protocol) envoyé via UDP Socket (Port 4048) au module ESP32 (WLED).
* **Communication Plex** : Websockets natifs (`plexapi` ou appels websockets directs) pour écouter les ticks `playing`, `paused`, `seek`.

## 3. Structure des Dossiers et Fichiers Clés
* `/start.bat` / `/stop.bat` : Scripts de lancement de l'application sous Windows (Virtual Env).
* `/web.py` : Serveur FastAPI, point d'entrée principal. Maintient la boucle asynchrone `while True` (blindée contre les déconnexions réseau) qui coordonne les modules. Héberge également les routes Web et SSE de l'encodeur WLED Subtitles.
* `/player.py` : Classe `SlavePlayer` encapsulant `libmpv`. Agit en tant que fallback de lecture en temps réel si aucun métadonnée n'est pré-calculée.
* `/wled_reader.py` : Lecteur JIT. Décompresse les fichiers `.wledsub.lz4` à la volée vers le cache, puis les mappe virtuellement en mémoire RAM via `numpy.memmap`, permettant un mode de lecture avec littéralement Zéro CPU en court-circuitant le lecteur MPV complet.
* `/bake.py` : Outil CLI/Backend FFmpeg appelé par l'UI web pour pré-calculer les couleurs vidéo et générer les fichiers métadonnées de sous-titres visuels.
* `/sync.py` : Classe `PlexSynchronizer`. Écoute Plex et calcule l'offset pour la synchronisation proportionnelle.
* `/led_engine.py` : Classe `LedEngine`. Cerveau mathématique (Numpy) détectant les bandes noires et applicant l'Auto-Crop asymétrique. Gère l'envoi des paquets UDP DDP.
* `/config.json` : Fichier de persistance des paramètres.
* `/static/` : Interface utilisateur frontend (Dashboard, Encodeur, Simulateur LED).
* `/changelog.md` : Journal chronologique des avancées.
* `/handoff.md` : Bilan quotidien de la session en cours.

## 4. Spécifications Matérielles
* **Cible** : QuinLED Dig-Uno V3 (ESP32) avec module Ethernet.
* **Microgiciel** : WLED (Profil QuinLED-ESP32-Ethernet).
* **LEDs** : WS2812b 5V (60 leds/m). Total : 208 LEDs (66 Haut, 38 Droite, 66 Bas, 38 Gauche). Démarrage en Haut-Gauche.

## 5. Conventions de Code
* Le backend Python DOIT minimiser l'usage CPU. Privilégier `Numpy` pour les opérations sur de grands tableaux.
* Les communications avec le frontend doivent utiliser les Server-Sent Events (SSE) pour le flux vidéo (Simulateur RGB) et les logs, pas de polling agressif HTTP.
* Ne jamais bloquer la Main Event Loop asynchrone outre mesure.
* L'architecture doit rester compatible Windows / Headless.
* Aucun secret (Token Plex, etc.) codé en dur dans le dépôt, toujours utiliser `config.json`.
