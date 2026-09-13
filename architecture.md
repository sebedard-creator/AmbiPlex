# Architecture du projet AmbiPlex

Mise à jour : 2026-09-13.

## Vue d'ensemble

AmbiPlex suit une session vidéo Plex locale et transmet les couleurs correspondantes
à un contrôleur WLED en UDP. Deux chemins de lecture partagent le même routage LED :

- **WLEDSUB** : lecture d'une piste de couleurs précalculées, sans décodage vidéo MPV.
- **Temps réel** : capture d'une fenêtre MPV cachée, puis extraction des couleurs.

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
| `bake.py` | Décodage FFmpeg et création des pistes RGB565 compressées. |
| `rover.py` | Interface Windows d'encodage par lots. |
| `static/` | Tableau de bord, simulateur et interface de l'encodeur. |
| `tests/` | Tests de rendu, de session locale et de cycle de vie. |

`config.json`, le cache, les vidéos et les dépendances binaires restent locaux
et sont ignorés par Git. Les captures PNG versionnées servent à la documentation.

## Sélection Plex

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

## Documents associés

- [Utilisation et installation](README.md)
- [Format et lecture WLEDSUB](architecture_WLED_subs.md)
- [Tests et résultats](tests/README.md)
- [Journal des modifications](changelog.md)
- [État de reprise](handoff.md)
