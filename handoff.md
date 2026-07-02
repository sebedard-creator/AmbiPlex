# Handoff - AmbiPlex (2 Juillet 2026)

## Ce qui a été accompli (Phase 5)
* **Synchronisation Proportionnelle (Chase Speed)** : Remplacement complet du mécanisme de "Seek" saccadé par un algorithme de suivi en temps réel (`set_speed()`). Le moteur MPV s'accélère ou ralentit dynamiquement pour s'arrimer au Plex sans aucune interruption visuelle ni perte de buffer.
* **Correction d'Immersion Letterbox** : L'algorithme NumPy de `led_engine.py` a été fondamentalement revu pour garder 100% de la hauteur physique lors du calcul des segments latéraux. L'auto-crop s'applique au contenu (Haut/Bas), tandis que les LEDs physiques situées dans la zone des "bandes noires" sont forcées au noir absolu (Zéro), garantissant un alignement spatial parfait sans effet de "décalement" ou d'étirement.
* **Sauvegarde d'Offset Intelligente** : Les configurations sont désormais mémorisées par dictionnaire dans `config.json`. Le système reconnait le profil média Plex (ex: `4kp-hevc-24pfps`) et applique automatiquement l'offset de délai associé dès le lancement d'un film.
* **Intégrité de l'UI** : Consolidation du payload JavaScript. Les formulaires (Plex vs Calibration) envoient désormais systématiquement un miroir complet de l'état, évitant l'écrasement ou la perte des configurations de luminosité.
* **Hygiène Anti-Dette Technique** : Balayage du dépôt. Les scripts de génération Python temporaires, les logs de debugging et les anciens codes orphelins concernant les "Marges Physiques" abandonnées ont été intégralement nettoyés. Seules les vidéos de calibration `.mp4` 16:9 et 21:9 ont été conservées pour l'utilisateur.

## État actuel du projet (Status)
* Le système backend (Python/MPV/Numpy/DDP) offre une stabilité sans faille et une fluidité absolue.
* L'installation matérielle (ESP32 / WS2812B / 208 LEDs) est entièrement soudée, collée sur le téléviseur et opérationnelle. 
* L'utilisateur valide présentement l'immersion visuelle et la synchro à l'aide des vidéos de calibration générées.

## Bugs / Limitations connus
* **Lissage Temporel (Smoothing)** : Le coefficient de lissage actuel est fixe par boucle. Si le *Refresh Rate* fluctue (ex: Native Refresh Rate), la vitesse de lissage perçue varie. (*Optimisation potentielle future : Lier l'`alpha` au `Delta Time`*).

## Prochaines Étapes
1. **Validation Finale** : Confirmer que l'expérience "Letterbox" est totalement immersive et naturelle sur un vrai film.
2. **Application Mobile (Phase 6 - Bonus)** : Si le système AmbiPlex est déclaré achevé et parfait par l'utilisateur, entamer la création de l'application Android native (Kotlin) pour agir comme télécommande/dashboard, évitant le besoin d'ouvrir le navigateur PC. (Rappel : La compilation de l'APK doit être gérée manuellement par l'utilisateur via Android Studio).
