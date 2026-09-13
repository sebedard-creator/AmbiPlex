# Journal des Modifications (Changelog) - AmbiPlex

## 2026-09-13 - Performances et sélection locale

- Moyennes de couleurs regroupées dans `color_sampling.py`, communes au rendu
  temps réel et au préencodage. Résultats RGB8 identiques dans les comparaisons.
- Calcul LED mesuré de 1,410 à 0,490 ms/image ; calcul de préencodage de 1,264 à
  0,331 ms/image sur 200 LED. Décodage, capture GPU et réseau exclus de ces mesures.
- Cache des vérifications WLEDSUB et décompression par blocs de 1 MiB hors de la
  boucle asyncio. Revérification du média et des dimensions après chargement.
- Copie des petites trames memmap pour permettre la libération du fichier sous
  Windows ; nettoyage lors de l'arrêt gracieux du serveur.
- Un état de monitoring en attente par navigateur, avec conservation séparée des
  logs et presets. Cache des mesures/positions des numéros du simulateur.
- Réduction des commandes MPV redondantes en mode caché. Capture et traitement
  en pause conservés pour préserver le comportement visuel.
- Correction du curseur CPU de Rover, qui recréait les composants de la fenêtre.
- Sessions distantes ou relayées exclues. Le nom du lecteur maître doit
  correspondre ; suppression du repli vers un autre appareil. Validation du
  lecteur et de la clé de session, avec rafraîchissement des sessions limité.
- 26 tests Python et 34 comparaisons exactes du canvas réussis. Essai MPV local
  réussi ; validation physique Plex/WLED encore à effectuer après redémarrage.
- Documentation actualisée et exclusions Git complétées pour les fichiers générés.

Les phases ci-dessous conservent l'historique du projet. L'architecture actuelle
est décrite dans [architecture.md](architecture.md), avec les limites et résultats
de validation dans [tests/README.md](tests/README.md).

## [Phase 1 & 2] - Fondations
- Création du projet.
- Implémentation du backend FastAPI.
- Intégration de libmpv (SlavePlayer).
- Développement du moteur LED (détection des couleurs, mapping physique).

## [Phase 3] - Refonte du Protocole
- Passage du protocole E1.31 au DDP (Distributed Display Protocol).
- Implémentation de la capture de fenêtre cachée (Headless) `screenshot_raw`.

## [Phase 4] - Raffinements UI et Sécurité MPV Headless
- **Lecteur MPV** : Changement de la propriété `vo=gpu` vers `vo=null` lorsque le mode "Headless" est activé.
- **Auto-Crop dynamique** : Abandon du filtre `vf=cropdetect` de MPV pour un détecteur mathématique Numpy ultra-performant, gérant parfaitement les sous-titres via une symétrie asymétrique.
- **Monitoring Web** : Ajout du compteur de Dropped Frames.

## [Phase 5] - Offset par Profil & Calibration Parfaite
- **Configuration Plex** : Sauvegarde individuelle de l'offset de synchronisation pour chaque combinaison Codec/Résolution/Framerate. Le backend restaure l'offset exact automatiquement.
- **Correction de Ratio Physique** : `led_engine.py` préserve l'échelle verticale physique à 100% lors des films en Letterbox.

## [Phase 6] - Zero CPU Mode (WLED Subtitles JIT)
- **Architecture**: Intégration de pistes `.wledsub.lz4` pour éviter le décodage vidéo pendant la lecture et réduire le travail CPU/GPU.
- **wled_reader.py**: Décompression JIT via `lz4` vers un cache disque, puis accès avec `numpy.memmap`.
- **web.py**: Détection automatique des fichiers compatibles. Mode "Zéro CPU" activé (court-circuitage total de l'instance MPV).

## [Phase 7] - Encodeur Web UI & Résolution des Bugs de Mémoire
- **Encodeur Web** : Création d'une page Web `/encoder` permettant d'extraire les métadonnées `.wledsub.lz4` via l'interface graphique plutôt qu'en ligne de commande.
- **Boîte de Dialogue Système** : Résolution du blocage (Focus Stealing Prevention) de Windows. Le backend invoque désormais un micro-script C# via PowerShell utilisant `user32.dll SetForegroundWindow` pour imposer la fenêtre de sélection de fichier au premier plan, par-dessus le navigateur web.
- **Monitoring d'Extraction (SSE)** : Ajout d'une transmission en temps réel (SSE) du log de `FFmpeg` vers l'interface Web, et résolution des bogues d'affichage liés à l'encodage `cp1252` de Windows sur les emojis (`UnicodeEncodeError`).
- **Correction JIT WinError 8** : Résolution du plantage `[WinError 8]` dans `numpy.memmap`. Le système calcule désormais le nombre réel de frames directement d'après le poids du fichier sur le disque au lieu de se fier à l'entête théorique.
- **UI UX - Sécurité d'Écrasement** : Le backend vérifie l'existence préalable d'un fichier `.wledsub.lz4` lors de la sélection d'une vidéo. L'UI change dynamiquement de couleur (Jaune) et le bouton se mue en "Écraser (Ré-encoder)" pour avertir l'utilisateur et éviter le travail en double.
- **Affinité Matérielle (CPU Masking)** : Le script `bake.py` bride physiquement l'utilisation processeur de FFmpeg (et ZScale) via un masque d'affinité Windows (`ProcessorAffinity`) pour empêcher l'emballement du ventilateur du PC, limitant l'accès strict au nombre de cœurs choisis dans l'UI.

## [Phase 8] - AmbiPlex Rover (Batch Encoder)
- **Logiciel Autonome** : Création de `rover.py`, un mini-logiciel Windows indépendant basé sur `customtkinter`.
- **Analyse de Dossier Récursive** : Scan un répertoire et tous ses sous-dossiers (`os.walk`), et identifie visuellement (couleur verte) les films possédant déjà un `.wledsub.lz4`.
- **Sélection Ergonomique** : Implémentation du Shift-Click permettant de sélectionner ou désélectionner rapidement des dizaines de films d'un coup.
- **Écriture temporaire** : `bake.py` écrit dans un fichier `.tmp` avant de le renommer. Le remplacement supprime préalablement l'ancien fichier final ; il ne garantit pas une transaction atomique en cas d'interruption.
- **Configuration CPU** : Intégration d'un Slider interactif dans l'interface du Rover permettant de brider manuellement les cœurs du processeur alloués à FFmpeg.
- **Encodage en Lot (Batch)** : Permet de sélectionner plusieurs films et de lancer `bake.py` séquentiellement.
- **Correction Windows File Lock** : Résolution du `[WinError 32]` lors du fallback de FFmpeg (`zscale`) en déplaçant la suppression du `.tmp` hors du contexte de compression LZ4.
- **Correction UTF-8 (Rover)** : Injection stricte de l'encodage `UTF-8` dans le tuyau de communication (`subprocess.Popen`) entre le Rover et `bake.py` pour empêcher le crash silencieux lié à l'émoji `🎬` sous l'encodage `cp1252` par défaut de Windows.
