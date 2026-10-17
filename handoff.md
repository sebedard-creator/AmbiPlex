# État de reprise AmbiPlex

Mise à jour : 2026-10-16.

## Bouton de lancement Chiaki

- `Démarrer Chiaki` dans `/remote` en mode PlayStation avant capture. Endpoint
  `POST /api/remote/chiaki/start`, loopback + Origin identique, sans chemin client.
- `chiaki_launcher.py` : `AMBIPLEX_CHIAKI_PATH` optionnel côté environnement du
  serveur ; sinon recherche PATH, dossiers usuels et installation portable.
  Détection en lecture seule réussie sur cette installation, sans lancer Chiaki.
- Verrou concurrent, détection des instances manuelles et enfant suivi ; pas de
  doublon volontaire. Processus démarré sans shell, appels système hors asyncio.
- `remote.js?v=6` : redémarrer AmbiPlex via PyManager puis recharger `/remote`.
  Pas de second serveur lancé par l'agent. Connexion console selon les réglages
  Chiaki existants ; sélection de fenêtre Chrome toujours manuelle.
- Lancement réel à valider avec le bouton après redémarrage du service ; les tests
  automatisés substituent le lancement natif et ne démarrent pas de session console.
- Validation : 73 tests Python (11 lanceur, 16 capture/API), capture navigateur
  et 12 mises en page réussis ; captures desktop/mobile inspectées. Couleurs
  identiques dans les tests existants, pas de chemin personnel dans le code.

## Documentation réorganisée

- README désormais synthétique, avec Plex, Xbox Series X|S, PS4 et PS5 dans le
  titre ; installation commune et démarrage Plex conservés. Galerie repliable.
  README réduit d'environ deux tiers. Liens, ancres et structure du tableau
  contrôlés après le remaniement.
- `XBOX_SETUP.md` contient la procédure Xbox extraite du README. Le guide
  `PLAYSTATION_SETUP.md` reste la référence PS4/PS5 ; liens croisés entre guides.
- Series S incluse selon la documentation officielle Xbox Remote Play, sans
  essai physique revendiqué. Les résultats physiques Xbox restent Series X.
- Documentation uniquement pour ce remaniement ; aucune modification du rendu,
  du service ou de la configuration locale. Les guides restent grand public.
- Guide PlayStation : association LAN manuelle Account-ID/PIN en premier,
  authentification PSN Chiaki optionnelle pour obtenir un identifiant manquant.
  Ne pas confondre absence de connexion PSN dans le client avec absence de
  prérequis d'activation du profil console.
- L'utilisateur autorise une annexe PS4 hors ligne pour clarifier la distinction :
  procédure Apollo uniquement pour une PS4 déjà jailbreakée, repliée et séparée
  du parcours normal. README et introduction affirment qu'aucun jailbreak n'est
  nécessaire sur PS4/PS5 standard. Ne pas appliquer l'annexe aux PS5.

## État du lot PlayStation pour commit

- Guide public [PLAYSTATION_SETUP.md](PLAYSTATION_SETUP.md) : parcours normal
  PS4/PS5 standard, comptes, association Chiaki, manette sur console,
  capture Chrome. Menus en anglais,
  références officielles, aucun identifiant personnel.
- Libellé de source « PlayStation Remote Play », valeur `ps4` et anciens liens
  conservés. Aucun nouveau protocole console ni changement du traitement LED.
- L'utilisateur confirme que le passage de Firefox à Chrome a résolu le gel de
  capture PS4 ; Chiaki restait fonctionnel lors du problème Firefox. L'ancienne
  hypothèse spécifique à Chrome ne doit pas être retenue comme diagnostic établi.
- PS4 fonctionnelle, profil console dédié utilisé pour laisser la DualShock sur
  le profil de jeu principal. PS5 décrite selon l'amont, pas testée physiquement.
- Couleurs PS4 délavées et noirs gris signalés sur le ruban. Chiaki paraît correct
  à l'utilisateur ; Plex lui convient. Aucune comparaison de pixels réelle n'a
  été faite entre Chiaki et l'aperçu, donc cause précise non établie.
- Diagnostic en lecture seule : pas de gamma logiciel dans AmbiPlex ; correction
  gamma temps réel désactivée dans WLED alors que sa courbe couleur vaut 2,2.
  Le moteur conserve les primaires et produit zéro sur les 200 LED pour un noir
  numérique pur, avec les réglages locaux. Cela ne prouve pas que la capture
  réelle fournit du noir pur. Le seuil fixe d'extinction vaut 6 après luminosité.
- L'utilisateur teste l'option WLED décochée. Résultat encore inconnu ; ne pas
  déclarer les couleurs corrigées ni changer gamma/saturation/seuils dans le
  code. Un réglage WLED global doit aussi être comparé avec Plex et Xbox.
- Les fichiers personnels, configurations Chiaki, vidéos et téléchargements
  restent hors commit. Aucun commit créé par l'agent.
- Vérification du 16 octobre : 58 tests Python, capture navigateur, 12 mises en
  page et 34 comparaisons exactes du simulateur réussis. Aperçu mobile du nouveau
  libellé inspecté, 20 références locales valides. Aucun identifiant personnel
  connu ni jeton Plex réel détecté dans les fichiers à versionner ; configuration
  locale toujours ignorée. Seul nouveau fichier non ignoré : le guide PlayStation.

## Correctif de présence Remote Play

- Le serveur sonde après cinq secondes sans message, puis attend une réponse dans
  les dix secondes restantes. Le navigateur répond sur événement WebSocket, sans
  minuteur. Le délai de sécurité et la libération de la sortie Plex sont conservés.
- Aucun changement du calcul des couleurs, du recadrage, de la cadence ou du DDP.
- `remote.js?v=5` : redémarrer AmbiPlex via PyManager, puis recharger la page et
  sélectionner la fenêtre Chiaki de nouveau. Aucun second serveur à lancer.
- Test navigateur réussi : 17 secondes sans image ni minuteur de présence,
  connexion conservée et couleurs des 200 LED identiques après reprise.
  Les 12 tests Python de capture passent, dont expiration d'un client muet.
  Suite Python complète : 58 tests réussis après le correctif.

## Profil PlayStation

- `/remote` propose Xbox (onglet) et PlayStation Remote Play (fenêtre).
  Lien direct : `http://localhost:5777/remote?source=ps4`.
- Source verrouillée pendant le partage ; surface et dimensions reçues affichées.
  Capture locale, moteur LED, RGBA8 et paramètres Plex/WLED conservés.
- Le profil PS4 seul ne nécessitait pas de redémarrage. Le correctif de présence
  décrit plus haut modifie aussi le serveur et nécessite un redémarrage via PyManager.
  Recharger pendant un partage l'arrête ; il faudra sélectionner la source à nouveau.
- Essai conseillé : Chiaki sur le PC AmbiPlex, 540p/720p et haute cadence pour
  PS4, 60 images/s dans AmbiPlex, choisir sa fenêtre puis ajuster les marges.
  Ne pas confondre dimensions de fenêtre capturée et résolution du flux console.
- Fonctionnement PS4 dans Chrome confirmé ; calibration et mesures objectives
  encore ouvertes. Le guide distingue contrôleur sur PC et contrôleur sur console.
- Validations du 15 octobre : capture navigateur réussie sur les deux profils,
  couleurs exactes des 200 LED en lecture directe à 540p, repli vidéo, 12 mises en
  page et 11 tests Python de capture réussis. `/remote?source=ps4` répond HTTP 200
  avec le sélecteur et le nouveau script, via le service existant.
- Les screenshots de la galerie datent du 14 septembre et ne montrent pas encore
  le sélecteur de console. Les captures de test du 15 octobre restent temporaires.

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

Cette installation utilise PyManager pour lancer AmbiPlex. Utiliser ce
gestionnaire pour les prochains demarrages et arrets, sans lancer en parallele
`web.py` ou `start.bat`. Ne pas publier les identifiants internes du gestionnaire.

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
