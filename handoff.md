# État de reprise AmbiPlex

Mise à jour : 2026-09-13.

## Changements prêts à être commités

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
