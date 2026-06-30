# Changelog

Toutes les modifications apportées au projet "AmbiPlex" sont documentées ici, par itération.

## [Phase 3] - Auto-détention et Simulateur LED (WLED)
- **Logique** : `sync.py` détecte désormais dynamiquement le combo de codec, framerate et résolution via les métadonnées de Plex.
- **Auto-génération** : Le serveur web génère automatiquement de nouveaux "presets" (ex: `1080p-h264-24p`) dans `config.json` et mémorise l'offset pour chaque profil indépendamment.
- **Extraction Vidéo** : `player.py` utilise l'API `screenshot_raw` de MPV pour capturer la mémoire vidéo et `Pillow` pour redimensionner instantanément à 160x90 à 20 FPS (extrêmement léger pour le CPU).
- **Moteur LED** : Création de `led_engine.py` responsable du calcul de la couleur moyenne des bordures (via `numpy`) et de l'envoi des paquets UDP **DDP** vers WLED.
- **Interface Web** :
  - La sÃ©lection du profil est automatisÃ©e (sÃ©lecteur grisÃ© en lecture seule).
  - Ajout du panneau **Calibration LEDs & Simulateur**.
  - IntÃ©gration d'un Canvas HTML5 dessinant en temps rÃ©el les bordures lumineuses Ã  20 FPS.
  - Sauvegarde en temps rÃ©el des paramÃ¨tres de LEDs (quantitÃ©, zone, lissage).

## [Phase 2] - IntÃ©gration du Module 2 (Lecteur MPV)
- **DÃ©pendances** : Installation de `python-mpv`.
- **Nouveau Fichier** : CrÃ©ation de `player.py` encapsulant la classe `SlavePlayer` (gestion des flags `nvdec`, `vo=gpu`, mode Headless, Seek & Speed Control).
- **Interface Web** : Ajout d'une case Ã  cocher pour le "Mode Headless" (permettant d'afficher ou cacher la fenÃªtre MPV pour dÃ©boguer). Ajout de la mÃ©trique `Offset (MPV)` sur le panneau de Live Monitoring.
- **Orchestration** : Modification de `web.py` pour instancier `SlavePlayer`. L'orchestrateur injecte dynamiquement l'action de Chase Ã‰lastique (vitesse de lecture modifiÃ©e) calculÃ©e par `sync.py` directement dans le lecteur MPV.

## [2026-06-14] - Phase 1 : Initialisation et Module de Synchronisation

### AjoutÃ©
- **Documentation** : CrÃ©ation de ce fichier `changelog.md` selon la prioritÃ© MEGA ABSOLUE #2.
- **Documentation** : Mise Ã  jour de `LED_Strip_Master_Prompt.md` pour ajouter la prioritÃ© MEGA ABSOLUE #3 : IndÃ©pendance totale du logiciel via un environnement virtuel local.
- **SystÃ¨me** : CrÃ©ation d'un environnement virtuel Python (`venv`) dans `Y:\LED Strip\venv` pour contenir toutes les dÃ©pendances locales.
- **DÃ©pendances** : Installation des bibliothÃ¨ques `plexapi` et `websocket-client` via `pip` Ã  l'intÃ©rieur de l'environnement virtuel.
- **Code** : CrÃ©ation du module `sync.py` contenant la classe `PlexSynchronizer`, la logique de connexion (WebSocket native avec `startAlertListener`) et le calcul de la vitesse "Ã©lastique" (`compute_chase_speed`).

## [2026-06-14] - Phase 2 : Interface Web de Configuration

### AjoutÃ©
- **Architecture** : DÃ©cision d'ajouter une interface web sur le port 5777 pour le paramÃ©trage et le monitoring afin de faciliter l'usage.
- **DÃ©pendances** : Installation de `fastapi` et `uvicorn` dans l'environnement virtuel.
- **Documentation** : Mise Ã  jour de `LED_Strip_Master_Prompt.md` avec le nouveau Module 5.
- **Scripts Utilitaires** : CrÃ©ation de `start.bat` et `stop.bat` pour lancer et arrÃªter facilement le serveur web sans ligne de commande.
- **Monitoring** : Ajout de la dÃ©tection du fichier en cours de lecture. `sync.py` rÃ©cupÃ¨re dÃ©sormais le titre et le chemin du fichier local via la clÃ© `ratingKey` de Plex, et l'affiche dans la console de l'interface Web.

### CorrigÃ©
- **Bug Fix (Filtres)** : `sync.py` ignorait la nature du mÃ©dia et essayait de se synchroniser avec la musique (ex: mp3). Il vÃ©rifie maintenant que `item.type` est bien une vidÃ©o.
- **Bug Fix (RÃ©seau)** : `sync.py` se synchronisait avec tous les flux du serveur. Il filtre maintenant pour ne suivre **que** le client maÃ®tre dÃ©fini en configuration, et **uniquement** si ce flux est sur le rÃ©seau local (`local=True`), bloquant ainsi les flux distants (remote).
- **AmÃ©lioration (Logs UI)** : Refactorisation complÃ¨te du systÃ¨me de logs dans `sync.py`. Les messages (dÃ©tection LAN, titre du fichier, etc.) sont dÃ©sormais poussÃ©s nativement et en temps rÃ©el vers la console Web (SSE) au lieu d'Ãªtre restreints Ã  la console PowerShell.

## [Phase 4] - Raffinements UI et Sécurité MPV Headless
- **Lecteur MPV** : Changement de la propriété `vo=gpu` vers `vo=null` lorsque le mode "Headless" est activé. Cela empêche formellement l'ouverture d'une fenêtre Windows même si une piste vidéo est détectée, tout en permettant à l'API `screenshot_raw` d'extraire la vidéo en mémoire vive.
- **Interface Web (UI)** :
  - Ajout de tooltips CSS élégants (icône "?") pour expliquer les réglages "Profondeur de Capture" et "Lissage Temporel" au survol.
  - Ajout d'un contrôle de **Luminosité Globale** (curseur de 0 à 100%) afin de pouvoir réduire la puissance envoyée aux LEDs et protéger l'alimentation.
- **Moteur LED** : `led_engine.py` applique dynamiquement un multiplicateur mathématique sur le tableau de couleurs final en fonction du pourcentage de luminosité globale défini par l'utilisateur avant d'envoyer la trame UDP DDP.

## [Phase 4] - Suite (Auto-Crop dynamique & MPV Profiling)
- **DÃ©tection des Bandes Noires (Auto-Crop)** : 
  - Abandon de l'utilisation du filtre matÃ©riel `vf=cropdetect` de MPV (incompatible avec l'extraction de la frame brute).
  - ImplÃ©mentation d'un dÃ©tecteur mathÃ©matique extrÃªmement performant en Python natif (`numpy`) directement dans `led_engine.py`.
  - Analyse de la luminositÃ© de l'image pour rogner le haut et le bas en temps rÃ©el afin de ne pas "Ã©teindre" les LEDs sur les films en 2.35:1 (Letterbox).
  - RÃ©solution du problÃ¨me des sous-titres : l'algorithme observe uniquement la stabilitÃ© de la bande noire supÃ©rieure (pendant 2 secondes) et applique une **symÃ©trie absolue** vers le bas pour ignorer totalement les sous-titres flottants ou le bruit vidÃ©o.
- **Monitoring Web (UI)** :
  - Le panneau "Live Monitoring" affiche dÃ©sormais les "Dropped Frames" du dÃ©codeur interne de MPV en temps rÃ©el via l'API `python-mpv`.
  - Ajout de l'indicateur "Auto-Crop" qui affiche les lignes actives sÃ©lectionnÃ©es par l'algorithme (`12 Ã  78` pour du 2.35:1, `0 Ã  90` pour du 16:9).
- **Simulateur Web** :
  - Ajout des nombres des LEDs incrustÃ©s visuellement sur le pourtour du canvas interactif (1, 10, 20... ainsi que les 4 coins exacts) pour guider physiquement le positionnement et le collage du ruban LED sur le tÃ©lÃ©viseur.
- **Optimisation DÃ©codage** :
  - Ajout des paramÃ¨tres secrets MPV `vd-lavc-fast=yes` et `vd-lavc-skiploopfilter=all`. Cela permet de diviser par 2 l'utilisation processeur et d'Ã©liminer les "Dropped Frames" lors du fallback logiciel (quand la carte graphique ne gÃ¨re pas les profils trÃ¨s complexes comme le Dolby Vision Profile 7).
