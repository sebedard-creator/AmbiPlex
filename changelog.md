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

## [Phase 4.5] - Code Review & Refactoring
- **Interface Web (UI)** :
  - Synchronisation finale des valeurs par défaut du Frontend Javascript (`app.js`) avec le Backend Python (`web.py`) : Profondeur (15%), Lissage (30%) et Refresh Rate Natif.
  - Correction d'un bug critique où les variables de *Refresh Rate* étaient perdues lors de la sauvegarde du formulaire Plex.
- **Sécurité et Stabilité** :
  - Suppression de la journalisation inutile (Warnings) générée par les RPUs Dolby Vision dans `player.py`.
  - Fermeture formelle et propre des sockets UDP `DDP` lors de l'arrêt dans `led_engine.py` (prévention des fuites de mémoire).
  - Nettoyage des imports redondants (`time`, `logging`) dans `sync.py` et `web.py`.
- **Branding** :
  - Renommage officiel et systématique du projet sous l'appellation **AmbiPlex** dans toute la documentation (`README.md`, `architecture.md`, `changelog.md`), l'interface HTML, et les scripts batch.

## [Phase 4.6] - Audit Externe (Robustesse & Falsy Zeros)
- **Architecture de Connexion** :
  - Modification de `POST /api/config` pour déconnecter/reconnecter dynamiquement `PlexSynchronizer` à chaud si l'utilisateur modifie ses accès, évitant le besoin de redémarrer le serveur.
  - La boucle `background_sync_loop` a été blindée avec une boucle `while True` au démarrage. Si le serveur Plex est introuvable au premier lancement, l'orchestrateur retentera silencieusement au lieu d'un arrêt fatal.
- **Résilience du Lecteur (MPV)** :
  - Le lecteur valide désormais la présence physique du fichier réseau avant de s'initialiser. S'il ne trouve pas le chemin, il détruit son instance proprement (`player.quit()`), empêchant la création d'instances fantômes en boucle.
- **Logique Falsy (Le Bug du Zéro)** :
  - Refactorisation complète du `led_engine.py` pour remplacer l'opérateur `or` par `if val is not None`, autorisant l'usage réel des valeurs `0` (ex: 0% de lissage, 0 LEDs).
  - Remplacement similaire dans le Javascript (`app.js`) par la fonction `getVal(id, def)` utilisant `isNaN()`.
- **Interface Utilisateur (UI)** :
  - Le bouton **Sauvegarder** n'est plus artificiellement désactivé en attente de Plex. Il est disponible dès l'ouverture de la page.
  - Le frontend gère maintenant le flux SSE d'erreurs (`data.type === "error"`) pour l'afficher en rouge dans la console.
- **Dépendances** :
  - Génération d'un fichier `requirements.txt` contenant la liste exacte des paquets pour sceller les versions.
 
 # #   [ 2 0 2 6 - 0 7 - 0 2 ]   -   P h a s e   5   :   O f f s e t   p a r   P r o f i l   &   C a l i b r a t i o n   P a r f a i t e  
 -   * * C o n f i g u r a t i o n   P l e x * *   :   S a u v e g a r d e   i n d i v i d u e l l e   d e   l ' o f f s e t   d e   s y n c h r o n i s a t i o n   p o u r   c h a q u e   c o m b i n a i s o n   C o d e c / R � s o l u t i o n / F r a m e r a t e .   L e   b a c k e n d   ( v i a   \ w e b . p y \ )   d � t e c t e   l e   p r o f i l   a u   l a n c e m e n t   d ' u n   m � d i a   e t   r e s t a u r e   l ' o f f s e t   e x a c t   a u t o m a t i q u e m e n t   d e p u i s   l e   d i c t i o n n a i r e   d u   \ c o n f i g . j s o n \ .  
 -   * * C o r r e c t i o n   d e   R a t i o   P h y s i q u e * *   :   \ l e d _ e n g i n e . p y \   p r � s e r v e   l ' � c h e l l e   v e r t i c a l e   p h y s i q u e   d e   l a   T V   �   1 0 0 %   l o r s   d e s   f i l m s   e n   L e t t e r b o x   p o u r   � v i t e r   l e   d � c a l a g e   ( d � c a l e m e n t ) .   L e s   r u b a n s   G a u c h e   e t   D r o i t e   p r o j e t t e n t   d � s o r m a i s   u n e   c o u l e u r   n o i r e   p u r e   l o r s q u ' i l s   s o n t   p o s i t i o n n � s   e n   f a c e   d e s   b a n d e s   n o i r e s   ( A u t o - C r o p   a s y m � t r i q u e   p a r f a i t ) .  
 -   * * A n t i - D e t t e   T e c h n i q u e * *   :   S u p p r e s s i o n   d e s   t e s t s   ( P y t h o n   s c r i p t s ,   l o g s   t e m p o r a i r e s )   e t   d u   c o d e   o r p h e l i n   d e s   M a r g e s   P h y s i q u e s .  
 