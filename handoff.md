## Date: 2026-07-04
### Accomplissements (Phase 7)
- Création d'une interface web dédiée (`/encoder`) pour l'extraction WLED Subtitles.
- Implémentation du script PowerShell de dialogue de fichiers natif, résolvant les crashs de l'ancienne approche (Tkinter bloquant la boucle asyncio).
- Résolution complète du bug de l'encodage `cp1252` sur Windows qui corrompait la console web lors de la réception de symboles ou tracebacks.
- Résolution du `[WinError 8]` dans `wled_reader.py` lors du mappage mémoire. Le fichier s'adapte désormais dynamiquement au poids exact du fichier brut généré par FFmpeg au lieu de la durée mathématique, empêchant tout crash de mémoire.
- Ajout d'une fonctionnalité UX de sécurité d'écrasement : l'interface web avertit l'utilisateur (Boîte de texte jaune + "Écraser") si un fichier .wledsub existe déjà pour le film sélectionné.
- Traduction du README.md en anglais, nettoyage final du projet.

### État Actuel
- Le projet est stable, le mode WLEDSUB fonctionne parfaitement sans crash depuis l'interface Web ou via FFmpeg CLI. Aucun bug connu.
- Le backend et l'architecture respectent intégralement les règles de développement, sans secrets en dur et avec un code nettoyé.

### Prochaines étapes exactes
- L'utilisateur est prêt à créer un commit sur son dépôt Git.
- Reprise standard du projet ou perfectionnement (ex: profilage, filtres avancés) si de nouveaux besoins matériels sont soulevés.
