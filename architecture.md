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
* `/web.py` : Serveur FastAPI, point d'entrée principal. Maintient la boucle asynchrone `while True` (blindée contre les déconnexions réseau) qui coordonne les modules. Gère le redémarrage à chaud des connexions si les paramètres changent.
* `/player.py` : Classe `SlavePlayer` encapsulant `libmpv`. Gère les chargements de médias locaux, les sauts (seek) initiaux, l'ajustement dynamique de la vitesse (`set_speed`) pour la synchronisation douce, et l'extraction `screenshot_raw`.
* `/sync.py` : Classe `PlexSynchronizer`. Maintient la websocket avec le serveur Plex pour capter les statuts de lecture du `master_client`. Dispose d'une méthode `reconnect()` pour le rechargement à chaud. Calcule la `chase_speed` (Synchronisation Proportionnelle) au lieu de forcer des seeks continus.
* `/led_engine.py` : Classe `LedEngine`. Cerveau mathématique (Numpy) qui détecte automatiquement les bandes noires (Auto-Crop asymétrique), conserve l'échelle verticale physique pour les rubans de côté, découpe l'image en 4 segments matériels (Top, Right, Bottom, Left), calcule la moyenne des couleurs, applique le lissage temporel, et envoie les paquets DDP. Gère de manière sécurisée les valeurs extrêmes ("Falsy" = 0%).
* `/config.json` : Fichier de persistance des paramètres utilisateurs modifiés via l'UI.
* `/static/` : Interface utilisateur frontend (index.html, app.js, styles).
* `/changelog.md` : Journal chronologique des avancées.
* `/LED_Strip_Master_Prompt.md` : Cerveau de la documentation matérielle et objectifs projet.

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
