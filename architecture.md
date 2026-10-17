# Architecture du projet AmbiPlex

Mise à jour : 2026-10-16.

## Vue d'ensemble

AmbiPlex synchronise un ruban WLED avec deux sources : une session vidéo Plex
locale ou une capture Remote Play choisie dans le navigateur. La source
Xbox Series X a été validée sur l'installation de l'utilisateur, sans retard
perceptible et avec le téléviseur restant en Dolby Vision. Ce retour ne constitue
pas une mesure de latence ni une garantie pour toutes les installations.

- **Xbox Remote Play** : capture d'un onglet, lecture directe des images, calcul
  des couleurs et envoi DDP. Parcours Xbox Series X|S, avec essai physique sur
  Series X uniquement. Aucun préencodage ni carte de capture HDMI.
- **PlayStation Remote Play** : capture de la fenêtre Chiaki-ng, fonctionnement
  PS4 confirmé dans Chrome. PS5 documentée, non testée ici ; calibration des
  couleurs PS4 encore en cours. Voir [le guide dédié](PLAYSTATION_SETUP.md).
- **Plex temps réel** : capture d'une fenêtre MPV cachée, puis extraction des couleurs.
- **Plex avec WLEDSUB (optionnel)** : lecture d'une piste de couleurs précalculées,
  sans décodage vidéo MPV pendant la lecture.

Ces chemins partagent le même moteur de routage LED. Le mode Xbox ne dépend
pas d'une session Plex active; les composants MPV restent toutefois importés
par l'application et font encore partie de ses dépendances d'installation.

Le mode précalculé réduit fortement le travail CPU/GPU ; il ne signifie pas une
consommation littéralement nulle ni une synchronisation sans latence.

## Modules

| Fichier | Responsabilité |
| --- | --- |
| `web.py` | FastAPI, configuration, boucle LED, encodeur web et flux SSE. |
| `sync.py` | Sélection de la session locale, événements Plex et correction de synchronisation. |
| `player.py` | MPV, capture 160x90, lecture, pause, recherche et vitesse. |
| `led_engine.py` | Recadrage, luminosité, routage, lissage, seuil de noir et envoi DDP. |
| `color_sampling.py` | Moyennes de segments communes au temps réel et au préencodage. |
| `wled_reader.py` | Validation, cache, décompression LZ4 et accès memmap. |
| `monitoring.py` | Dernier état de simulation en attente et file séparée pour les événements. |
| `remote_capture.py` | Capture navigateur locale, WebSocket RGBA8 et exclusion de la sortie Plex. |
| `chiaki_launcher.py` | Détection et lancement local de Chiaki, sans commande fournie par le navigateur. |
| `bake.py` | Décodage FFmpeg et création des pistes RGB565 compressées. |
| `rover.py` | Interface Windows d'encodage par lots. |
| `static/` | Tableau de bord, simulateur et interface de l'encodeur. |
| `tests/` | Tests de rendu, de session locale et de cycle de vie. |

Les trois pages web partagent `static/style.css` : palette charbon, controles
compacts et sections non encadrees. `static/remote.css` conserve uniquement la
disposition de la capture. Les formulaires Plex/WLED gardent leurs contrats API.
La liaison de luminosite utilise une case a cocher; la calibration confirme
l'enregistrement sur son propre bouton. Le retour a Plex ferme explicitement
la capture avant la navigation normale, sans arreter Xbox Remote Play.

`config.json`, le cache, les vidéos et les dépendances binaires restent locaux
et sont ignorés par Git. Les captures PNG versionnées servent à la documentation.

## Sources de lecture

### Capture Remote Play (Xbox / PlayStation)

Le sélecteur de source propose Xbox (préférence `displaySurface: 'browser'`) ou
PlayStation (préférence `displaySurface: 'window'`). `/remote?source=ps4`
présélectionne ce profil commun PS4/PS5 ; la valeur interne `ps4` est conservée
pour les anciens liens. Le type de console se règle dans Chiaki, pas AmbiPlex.
Tout autre paramètre conserve Xbox par défaut. Le navigateur décide
des choix disponibles et l'utilisateur confirme la source. Le sélecteur est
verrouillé pendant la capture, puis réactivé à l'arrêt ou en cas d'erreur.

La surface rapportée par `track.getSettings()` et les dimensions réelles des
images reçues sont affichées sans publier le titre de la fenêtre. Ces dimensions
incluent les éventuelles décorations et ne mesurent pas la résolution du flux
console. Celle-ci se règle dans Chiaki (540p/720p pour le premier essai PS4).
Le profil ne fixe aucune contrainte de largeur/hauteur ni aucun recadrage propre
à une application : les marges manuelles s'appliquent avant le centrage 16:9.
Audio désactivé pour les deux sources. Aucun accès aux identifiants PlayStation.

Le bouton « Démarrer Chiaki », visible pour PlayStation avant le partage, appelle
`POST /api/remote/chiaki/start`. Contrôle loopback et Origin identique (hôte,
port, protocole), GET et clients distants refusés. Aucun chemin ni argument n'est
accepté du client. Une variable d'environnement serveur `AMBIPLEX_CHIAKI_PATH`
peut préciser l'exécutable ; sinon PATH, dossiers usuels et layout portable sont
examinés. Seuls les exécutables locaux nommés `chiaki.exe`/`chiaki-ng.exe` sont admis.
L'inventaire Windows évite aussi les doublons ouverts manuellement ; un verrou
sérialise les clics concurrents. Appels système hors boucle asyncio, lancement
sans shell. Aucun changement de source, d'identifiants, de rendu ou de partage.
Un redémarrage via le gestionnaire habituel est requis après cette mise à jour.

`/remote` utilise `getDisplayMedia` apres une action de l'utilisateur, puis
`MediaStreamTrackProcessor` dans Chrome/Edge (buffer d'une image), avec repli
`requestVideoFrameCallback` si l'API directe est absente. Chaque VideoFrame est
fermee apres traitement, meme si elle est ignoree. La capture directe ne depend
pas des rappels d'affichage du lecteur video. L'image est reduite a 160x90 sRGB dans
un canvas. Une seule trame RGBA8 (57 600 octets) peut attendre son acquittement
sur `/api/remote/frames`; les images intermediaires sont ignorees. Aucun nouvel
encodage video avec pertes. Cadence cible 30 ou 60 images/s, independante de Plex.

Le serveur accepte uniquement un client loopback avec une Origin locale de meme
hote/port/protocole. Un seul proprietaire est admis. Taille, type et inactivite
des messages sont controles; le delai d'inactivite reseau est de quinze secondes.
Un ping applicatif chaque seconde sans image en attente maintient la connexion
sur une scene statique. Apres cinq secondes sans message, le serveur envoie aussi
un ping : le navigateur repond sur l'evenement WebSocket, sans minuteur JavaScript.
Il reste dix secondes pour recevoir une reponse avant liberation de la capture.
Cela couvre les minuteurs ralentis en arriere-plan, pas une page gelee ou detruite.
Les ping/pong ne declenchent aucun envoi DDP. Les fermetures
sont journalisees avec leur code et le nombre d'images, sans contenu capture.
Le moteur LED de cette source possede son propre etat de lissage et de crop.
Il relit les reglages locaux au maximum une fois par seconde, sans les modifier.

La boucle Plex suspend son traitement et met MPV en pause pendant la capture.
Tous ses envois DDP passent aussi par une verification sans await du proprietaire,
y compris apres le chargement asynchrone d'un WLEDSUB. Les evenements Plex restent
suivis. A la reprise, l'historique de lissage Plex est reinitialise et la correction
de synchronisation normale reprend. La connexion initiale Plex se fait dans un
thread pour ne pas bloquer la reception Remote Play quand Plex est indisponible.

La fermeture, une erreur ou une annulation ferme le moteur et libere le
proprietaire. Aucun effacement force du ruban n'est envoye a l'arret. Les mesures
affichees ne sont pas une mesure de latence console-vers-LED. La capture depend du
partage navigateur, du cadrage choisi et de sa cadence, notamment en arriere-plan.

Le 15 octobre, les tests navigateur vérifient une fenêtre synthétique 960x540,
une fenêtre 960x600 avec une barre de 60 pixels retirée par la marge haute,
le repli vidéo, les erreurs de capture et le retour à Plex. Les 200 couleurs LED
sont identiques à la référence en lecture directe. Le repli vidéo conserve les
couleurs des zones unies, mais le rendu navigateur peut interpoler les frontières.
Le retour utilisateur du 16 octobre confirme la capture PS4 dans Chrome après
un gel prolongé dans Firefox, Chiaki restant actif. Le montage avec utilisateur
console dédié évite le conflit de manette. Ce retour n'est ni une mesure de
latence ni une calibration : saturation et niveaux de noir restent en examen.
Le repli vidéo Firefox reste présent, mais n'est pas recommandé pour ce parcours.
PS5 n'a pas été testée physiquement ; seul le chemin générique de capture de
fenêtre est commun. Le guide décrit le parcours PlayStation standard.

Le moteur AmbiPlex n'applique actuellement aucun gamma logiciel. WLED peut
corriger les couleurs temps réel, sauf si son option de désactivation est cochée.
Un test A/B est en cours, sans changement de code ni résultat confirmé. Ce
réglage appartient à WLED et affecte toutes les sources, pas uniquement PS4.

### Session Plex locale

Le listener Plex tourne dans son propre thread. Sur les notifications de lecture,
il rafraîchit un instantané de sessions au maximum une fois par seconde.

Une session admissible est une vidéo dont `Player.local` vaut vrai, sans relais,
et dont la localisation, si fournie, vaut `lan`. Une adresse IP privée ne remplace
pas cette validation. Si un nom maître est configuré, il doit correspondre après
normalisation de la casse, des espaces et des underscores. Aucun autre appareil
n'est choisi en remplacement. Le nom vide autorise la sélection locale automatique.

Les notifications doivent correspondre à la fois à l'identifiant du lecteur et
à la clé de session. Une session arrêtée, disparue ou devenue distante libère la
sélection. La classification dépend des informations fournies par Plex.

## Boucle de rendu

1. Charger périodiquement les réglages et lire l'état de synchronisation.
2. Vérifier la piste WLEDSUB du média. Les vérifications et la décompression
   s'exécutent hors de la boucle asyncio principale.
3. Après une attente de chargement, revérifier le média, l'état de lecture et les
   dimensions LED avant d'utiliser le résultat.
4. Lire la trame précalculée ou capturer MPV. En mode caché, MPV utilise
   `vo=gpu` dans une fenêtre native 160x90 ; `vo=null` est le repli si sa création échoue.
5. Appliquer luminosité par côté, décalages, ordre du ruban, lissage et seuil de noir.
6. Envoyer le paquet DDP et publier l'état de monitoring, puis attendre la prochaine échéance.

La pause continue de capturer/traiter les images et d'envoyer les couleurs pour
préserver les mises à jour du lecteur et le lissage. Les commandes MPV redondantes
sont évitées en mode caché grâce à l'observation des propriétés ; le mode visible
et l'échec d'observation conservent les commandes systématiques.

## Calcul et monitoring

Pour les images RGB8, les sommes cumulées entières remplacent les moyennes
individuelles par LED. Les limites de segments, arrondis et traitements visuels
restent identiques. Les autres types d'image gardent le calcul NumPy classique.

Chaque navigateur conserve au maximum un état de monitoring en attente ; les
logs et événements de preset gardent leur ordre. Le cache des positions et mesures
des numéros du simulateur est invalidé si sa géométrie ou les polices changent.
La mesure de durée de boucle inclut désormais le calcul des couleurs et l'envoi DDP.

## Matériel et limites

Les dimensions LED sont configurables ; les mesures de septembre utilisent
64 LED horizontales et 36 verticales, soit 200 LED. Ce n'est pas une constante du code.

Le contrôleur cible est compatible WLED/DDP, par exemple un QuinLED Dig-Uno avec
ruban WS2812B. Le paquet DDP actuel est limité à 480 LED. Le rafraîchissement natif
est suivi en mode MPV ; le mode WLEDSUB utilise la fréquence configurée.

La configuration et certains appels MPV/Plex restent synchrones. Le déplacement
du chargement WLEDSUB hors de la boucle ne rend pas tous les accès non bloquants.
La fermeture gracieuse libère les ressources ; un arrêt forcé peut laisser un cache.

## Exploitation du service

Le serveur écoute sur le port 5777. Sur cette installation, PyManager gère le
processus avec le Python du venv AmbiPlex et le dossier du projet comme répertoire
de travail. Ne pas lancer une seconde instance indépendante : elle échoue à
occuper le port et peut ne pas être reconnue par le gestionnaire si ses arguments
diffèrent. Les changements Python nécessitent un redémarrage via le gestionnaire;
les changements HTML/CSS/JS nécessitent une actualisation du navigateur.

Le code et la configuration de PyManager n'ont pas été modifiés. Les détails de
l'installation locale et du conflit de port résolu sont dans [handoff.md](handoff.md).

## Documents associés

- [Utilisation et installation](README.md)
- [Configuration Xbox Series X|S](XBOX_SETUP.md)
- [Configuration PlayStation PS4 / PS5](PLAYSTATION_SETUP.md)
- [Format et lecture WLEDSUB](architecture_WLED_subs.md)
- [Tests et résultats](tests/README.md)
- [Journal des modifications](changelog.md)
- [État de reprise](handoff.md)
