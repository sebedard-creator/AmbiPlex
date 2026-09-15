# État de reprise AmbiPlex

Mise à jour : 2026-09-14.

## Nouveau lot Rover

- Interface native alignée sur le style web ; tableau ttk, recherche, filtres,
  sélection Ctrl/Shift et commandes pour sélectionner les pistes manquantes.
- `rover_batch.py` sépare scan et encodage des widgets. Scan en arrière-plan,
  insertions par groupes de 200, journal limité et événements bornés.
- Vérification des retours du processus, progression par fichier et bilan des
  erreurs. Arrêt après le fichier courant, fermeture différée, confirmation des
  remplacements et détection des sorties partagées.
- Aucun changement de `bake.py`, des couleurs, des filtres, de la configuration
  enregistrée ni du service AmbiPlex géré par PyManager.
- 57 tests Python réussis, dont 20 tests Rover ; piste générée via Rover identique
  à la commande directe sur une mire FFmpeg. Géométrie vérifiée à 1120x820 et
  880x720. Capture fournie de la fenêtre inspectée ; capture automatique Windows
  indisponible (`SetIsBorderRequired`, interface non supportée).
- `tests/preview_rover.py` ouvre un essai isolé : deux mires temporaires et un
  fichier volontairement invalide, paramètres synthétiques, aucun accès aux films
  ou au jeton Plex. La fenêtre de test peut être fermée ; lancer ensuite
  `start_rover.bat` pour l'utilisation normale. Le commit reste à faire.

## Lot Xbox précédent

- Support Xbox Series X via Remote Play : capture locale 160x90, cadence 30/60,
  lecture directe du flux, connexion maintenue sur image statique et reprise Plex.
- Interface commune aux trois pages, réglages LED regroupés et retour à Plex.
- Dépendance `websockets`, tests Python et navigateur, documentation synchronisée.
- README : annonce Xbox en tête, guide de démarrage, prérequis par source,
  validation physique et limites, gestion des services et sous-titres optionnels.

Les modifications de performance et de sélection Plex précédentes étaient déjà
commitées au début du lot Xbox. Ne pas les présenter comme de nouveaux changements
de ce commit. Aucun commit n'a été créé par l'agent; le commit reste à l'utilisateur.

## Gestion du service avec PyManager

Cette installation utilise `Y:\PyManager` pour lancer AmbiPlex. Utiliser ce
gestionnaire pour les prochains demarrages et arrets, sans lancer en parallele
`web.py` ou `start.bat`. API locale du gestionnaire : `http://127.0.0.1:8000` ;
identifiant du service : `ambiplex-1782827386887`.

L'instance lancee manuellement pendant les essais occupait le port 5777 sans
etre reconnue par PyManager, car ses arguments differaient. Les tentatives de
demarrage via le gestionnaire echouaient avec l'erreur Windows 10048 (port deja
utilise). Cette instance a ete arretee et AmbiPlex relance via PyManager.
Verification du 14 septembre : service declare actif par son API, port 5777
detecte, pages `/`, `/remote` et `/encoder` accessibles (HTTP 200).
Aucune modification du code ou de la configuration de PyManager n'a ete requise.

## Remote Play valide et interface unifiee

L'utilisateur confirme que le ruban suit le jeu sans latence perceptible apres
le correctif de capture directe. Ce retour est subjectif, pas une mesure a 0 ms.
Il a demande d'appliquer le style de cette page au reste de l'interface web.

- `style.css` partage par Plex, l'encodeur et Remote Play; `remote.css` limite
  aux dispositions specifiques. Reglages reorganises, contrats API inchanges.
- Bouton Retour a Plex sur la capture : arret explicite avant navigation.
- Tests UI des trois pages sur 1440, 768, 390 et 320 pixels, y compris les
  sauvegardes et luminosites liees/independantes, sans appareil physique.
- Les fichiers statiques et HTML sont servis sans redemarrage du serveur;
  recharger les pages pour obtenir le nouveau style. Une actualisation de la
  page Remote Play active arrete le partage et necessite une nouvelle selection.
- Les quatre captures de la galerie README ont ete remplacees le 14 septembre
  par l'interface actuelle : Remote Play, Plex, calibration WLED et encodeur.
  Pages au repos, jeton omis et adresse WLED d'exemple, sans sauvegarde des
  parametres. La vue Remote Play ne represente pas une partie en cours.

## Implementation de la capture

L'utilisateur confirme que Remote Play fonctionne avec de bonnes couleurs sur
le PC et que sa TV reste en Dolby Vision. Il a choisi de valider le delai directement
avec WLED. 720p retenu pour le premier essai; aucun parametre Xbox change par
l'agent. Les travaux precedents etaient deja commites au debut de cet ajout.

- Nouvelle page `http://localhost:5777/remote`, a ouvrir dans le meme Chrome/Edge
  que Remote Play. L'utilisateur choisit l'onglet a partager, sans audio.
- Capture navigateur RGBA8 160x90, cadence 30/60, un seul envoi en attente.
- Moteur LED et reglages existants reutilises; pas de changement de configuration.
- Plex cede la sortie WLED pendant la capture, puis reprend. Protection meme
  si la capture commence pendant le chargement asynchrone d'une piste WLEDSUB.
- Nouvelle dependance `websockets`; redemarrage du serveur requis apres mise a jour.
- Mesures dans la page limitees au PC, pas au delai complet Xbox/WLED.
- Validation physique maintenant reussie selon le retour utilisateur ci-dessus.
- Premier essai utilisateur : seule la capture AmbiPlex se coupe peu apres le
  choix de l'onglet; Xbox Remote Play reste connecte. Correctif : lecture directe
  du flux avec MediaStreamTrackProcessor, keepalive sur scene statique et delai
  reseau de quinze secondes. Recharger `/remote` pour obtenir `remote.js?v=3`.
- Validation automatisee : 37 tests Python reussis, 34 comparaisons existantes
  du simulateur identiques, tests navigateur de capture reussis sur images
  synthetiques avec DDP simule. Captures desktop/mobile inspectees.

## Changements precedents

- Calcul commun des moyennes LED dans `color_sampling.py`, utilisé par
  `led_engine.py` et `bake.py`, avec conservation des résultats RGB8.
- Vérifications WLEDSUB mises en cache, décompression par blocs hors de la boucle
  asyncio et contrôle du média après chargement.
- Libération du memmap sous Windows et nettoyage lors de l'arrêt gracieux.
- Monitoring : dernier état en attente par navigateur, événements conservés,
  cache de géométrie des numéros et mises à jour DOM limitées.
- Commandes MPV redondantes évitées en mode caché ; capture en pause conservée.
- Rover : le curseur CPU ne recrée plus les composants de la fenêtre.
- Sélection Plex stricte : session locale sans relais, nom maître respecté,
  validation conjointe du lecteur et de la clé de session, aucun repli sur un
  appareil non demandé.
- Documentation corrigée et règles Git pour les fichiers générés complétées.

## Validation

- 26 tests Python réussis lors de la validation des optimisations et du filtre local.
- 34 comparaisons exactes du canvas du simulateur sur écran large et mobile.
- Six vidéos de calibration locales comparées à la version Git d'origine.
- Essai local MPV réussi : capture 160x90, pause, recherche, vitesse et reprise.
- Calcul LED : 1,410 à 0,490 ms/image ; préencodage : 1,264 à 0,331 ms/image.
  Ces mesures excluent décodage vidéo, capture GPU et accès disque/réseau.

Les tests utilisent la référence Git
`81db0f00bcdf3cc94db47fc597fb028205fa72ab`. Conserver cet historique pour les
réexécuter. Les vidéos de calibration sont locales, ignorées par Git ; leur test
est ignoré explicitement si elles ou FFmpeg sont absents.

Commandes et détails : [tests/README.md](tests/README.md).

## Limites et prochaine vérification

L'installation Plex-to-WLED physique reste à vérifier après redémarrage :
lecture locale sur le lecteur maître, lecture distante simultanée, pause et reprise.
Aucune session Plex n'était active lors du diagnostic du filtre local.

Le nom maître correspond après normalisation des espaces, underscores et casse.
Si le nom réel diffère, AmbiPlex attend au lieu de choisir un autre appareil.
La qualification LAN dépend de Plex, notamment en présence de VPN.

Le serveur web n'a pas d'authentification applicative. Le sender DDP actuel limite
la sortie à 480 LED. FastAPI signale la dépréciation des handlers `on_event` ;
une migration vers lifespan n'a pas été incluse dans ce lot.
`stop.bat` force l'arrêt et peut contourner le nettoyage gracieux.

Le commit est laissé à l'utilisateur. Les captures PNG de documentation et les
tests sont intentionnels ; les secrets, vidéos, dépendances et caches restent locaux.
