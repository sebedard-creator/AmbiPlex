## Date: 2026-07-04
### Accomplissements (Phase 7 & 8)
- Création d'une interface web dédiée (`/encoder`) pour l'extraction WLED Subtitles.
- Implémentation du script PowerShell de dialogue de fichiers natif avec injection C# (user32.dll `SetForegroundWindow`) pour by-passer de force la protection "Focus Stealing" de Windows.
- Résolution complète du bug de l'encodage `cp1252` sur Windows qui corrompait la console web lors de la réception de symboles ou tracebacks.
- Résolution du `[WinError 8]` dans `wled_reader.py` lors du mappage mémoire. Le fichier s'adapte désormais dynamiquement au poids exact du fichier brut généré par FFmpeg au lieu de la durée mathématique, empêchant tout crash de mémoire.
- Ajout d'une fonctionnalité UX de sécurité d'écrasement : l'interface web avertit l'utilisateur (Boîte de texte jaune + "Écraser") si un fichier .wledsub existe déjà pour le film sélectionné.
- Restriction matérielle absolue (Masque d'affinité CPU Windows) de FFmpeg dans `bake.py` pour garantir la limitation du ventilateur et des ressources processeur selon le choix de l'utilisateur.
- Traduction du README.md en anglais, nettoyage final du projet.
- Création du mini-logiciel autonome `rover.py` (Phase 8) basé sur CustomTkinter pour l'encodage par lot de fichiers multiples au sein d'un répertoire donné.
- Implémentation du moteur de scan récursif (os.walk) pour identifier les vidéos dans tous les sous-dossiers.
- Implémentation de la sélection multiple par plage (Shift-Click) dans l'interface UI du Rover.
- Implémentation de l'écriture atomique via extension `.tmp` dans `bake.py` garantissant l'intégrité absolue (Zéro corruption) des fichiers de sous-titres encodés.

### État Actuel
- Le projet est stable, le mode WLEDSUB fonctionne parfaitement sans crash depuis l'interface Web ou via FFmpeg CLI. Aucun bug connu.
- Le backend et l'architecture respectent intégralement les règles de développement, sans secrets en dur et avec un code nettoyé.

### Prochaines étapes exactes
- L'utilisateur est prêt à créer un commit sur son dépôt Git.
- Reprise standard du projet ou perfectionnement (ex: profilage, filtres avancés) si de nouveaux besoins matériels sont soulevés.
