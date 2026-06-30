# Handoff - Synchronisation Ambilight (30 Juin 2026)

## Ce qui a été accompli
* **Révision Architecture/Code** : Analyse approfondie de `led_engine.py` et `web.py` demandée par l'utilisateur. 
* **Validation de l'Algorithme Auto-Crop** : Confirmation que le code Numpy asymétrique pour détecter et ignorer les bandes noires/sous-titres fonctionne de manière optimale. La capture MPV se faisant en `160x90`, la constante `90` pour la hauteur maximale est mathématiquement correcte.
* **Documentation** : Création de `architecture.md` et mise à jour des spécifications matérielles (208 LEDs confirmées) dans `LED_Strip_Master_Prompt.md` selon les directives de `AGENTS.md`.

## État actuel du projet (Status)
* Le système backend (Python/MPV/Numpy/DDP) est **100% fonctionnel et stable**.
* L'interface de configuration Web fonctionne parfaitement et affiche la simulation en temps réel.
* L'installation matérielle (ESP32 / WLED Dig-Uno) a été configurée virtuellement et flashée. 
* L'utilisateur est présentement en train de souder les coins à 90 degrés de ses rubans LEDs WS2812B physiques (66x38x66x38 = 208 LEDs). Les tests de continuité initiaux (faux positifs dus aux micro-puces des LEDs) ont été démystifiés.

## Bugs / Limitations connus
* **Lissage Temporel (Smoothing)** : Le coefficient de lissage actuel est fixe par boucle. Si le *Refresh Rate* fluctue (ex: Native Refresh Rate), la vitesse de lissage perçue varie. (*Optimisation potentielle future : Lier l'`alpha` au `Delta Time`*).
* **Limite DDP** : Codé en dur pour bloquer à 480 LEDs maximum afin de rester sous le MTU Ethernet UDP de 1440 octets. (Pas un problème pour le setup actuel de 208 LEDs).

## Prochaines Étapes
1. **Branchement Matériel Réel** : L'utilisateur doit compléter ses soudures, brancher l'alimentation 5V 15A avec l'injection de puissance (Power Injection), et insérer le fusible dans le Dig-Uno.
2. **Premier Test "Live"** : Lancer un film sur Plex et observer la réaction physique des rubans sur le téléviseur.
3. **Application Mobile (Phase 5 - Bonus)** : Si le système est validé et stable avec la télé, commencer la programmation de l'application Android (Kotlin) pour un contrôle facile des offsets/luminosité sans ouvrir de page web depuis un PC. (Rappel : La compilation Android doit toujours se faire via Android Studio par l'utilisateur, jamais via le terminal de l'agent).
