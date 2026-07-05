# Journal des Modifications (Changelog) - AmbiPlex

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
- **Architecture**: Intégration d'un système de sous-titres visuels `.wledsub.lz4` pour supprimer l'utilisation CPU sur le serveur local.
- **wled_reader.py**: Création du module de décompression JIT via `lz4` et mappage direct en RAM avec `numpy.memmap`.
- **web.py**: Détection automatique des fichiers compatibles. Mode "Zéro CPU" activé (court-circuitage total de l'instance MPV).

## [Phase 7] - Encodeur Web UI & Résolution des Bugs de Mémoire
- **Encodeur Web** : Création d'une page Web `/encoder` permettant d'extraire les métadonnées `.wledsub.lz4` via l'interface graphique plutôt qu'en ligne de commande.
- **Boîte de Dialogue Système** : Remplacement de l'outil Python `tkinter` par un script natif `PowerShell` invoquant `System.Windows.Forms.OpenFileDialog` (TopMost) pour résoudre de graves problèmes de conflit asynchrone (threading) liés au backend Web.
- **Monitoring d'Extraction (SSE)** : Ajout d'une transmission en temps réel (SSE) du log de `FFmpeg` vers l'interface Web, et résolution des bogues d'affichage liés à l'encodage `cp1252` de Windows sur les emojis (`UnicodeEncodeError`).
- **Correction JIT WinError 8** : Résolution du plantage `[WinError 8]` dans `numpy.memmap`. Le système calcule désormais le nombre réel de frames directement d'après le poids du fichier sur le disque au lieu de se fier à l'entête théorique.
- **UI UX - Sécurité d'Écrasement** : Le backend vérifie l'existence préalable d'un fichier `.wledsub.lz4` lors de la sélection d'une vidéo. L'UI change dynamiquement de couleur (Jaune) et le bouton se mue en "Écraser (Ré-encoder)" pour avertir l'utilisateur et éviter le travail en double.
