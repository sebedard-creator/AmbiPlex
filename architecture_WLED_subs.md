# Architecture WLED Subtitles

État implémenté au 2026-09-13. Ce document remplace les propositions initiales.

## Objectif

Précalculer les couleurs d'une vidéo pour éviter son décodage par MPV à chaque
lecture. La piste est spécifique aux dimensions LED et à la profondeur de capture
choisies. Elle ne constitue pas un format indépendant du matériel.

Le fichier final `.wledsub.lz4` est compressé avec LZ4. Le cache de lecture est
décompressé sur disque puis mappé avec NumPy. La décompression, le routage, le
lissage et les communications consomment toujours des ressources.

## Format version 0003

Le flux décompressé commence par un en-tête de 32 octets, encodé avec
`struct.pack('<4s4sfIHH12x', ...)` :

| Champ | Taille | Valeur |
| --- | --- | --- |
| Signature | 4 octets | `WLED` |
| Version | 4 octets | `0003` |
| Fréquence | 4 octets | float32 |
| Nombre théorique de trames | 4 octets | uint32 |
| LED horizontales X | 2 octets | uint16 |
| LED verticales Y | 2 octets | uint16 |
| Réserve | 12 octets | zéros |

Chaque trame contient `2 * (X + Y)` valeurs RGB565 de 16 bits, dans l'ordre
haut gauche-droite, droite haut-bas, bas droite-gauche, gauche bas-haut.
Le code actuel écrit/lit le payload en `np.uint16` natif, little-endian sur la
plateforme Windows utilisée ; il ne faut pas présumer sa portabilité big-endian.

Pour 64x36 LED, une trame représente 400 octets. Deux heures à 24 images/s
représentent 69 120 000 octets de payload décompressé. La taille LZ4 dépend du contenu.

Le RGB565 réduit la précision par rapport au RGB888 : rouge et bleu sur 5 bits,
vert sur 6 bits. La lecture restitue ces valeurs par décalage de bits, conformément
au moteur existant. L'optimisation des moyennes ne change pas cette conversion.

## Création

```powershell
venv\Scripts\python.exe bake.py "D:\Movies\Film.mkv" --leds-x 64 --leds-y 36 --depth 8 --threads 0
```

- `bake.py` cherche FFmpeg localement, puis dans PATH, puis télécharge un binaire
  Windows si aucun n'est disponible.
- FFmpeg réduit les images à 160x90 avec conservation du ratio et ajout de bandes.
  Le traitement HDR utilise zscale et tonemap ; un échec initial peut déclencher
  le filtre de repli sans ce traitement.
- La profondeur est un paramètre, 8 % par défaut en CLI. Le recadrage est précalculé.
- `color_sampling.py` calcule les moyennes de segments avant conversion RGB565.
- Le résultat est écrit dans `Film.wledsub.lz4.tmp`, puis renommé en fichier final.
  Le code supprime d'abord un ancien fichier final : ce remplacement n'est donc
  pas une transaction atomique garantie en cas d'interruption.

La limitation des threads et l'affinité CPU concernent le processus FFmpeg.
Les calculs Python du préencodage restent également à prendre en compte.

## Lecture et cache

1. Chercher la piste portant le même nom que la vidéo, avec l'extension
   `.wledsub.lz4`. Aucun chemin alternatif basé sur le RatingKey n'est implémenté.
2. Vérifier signature, version et dimensions LED. En cas d'absence ou
   d'incompatibilité, utiliser le rendu MPV en temps réel.
3. Décompresser le payload par blocs de 1 MiB vers `cache/active_movie.wledsub_raw`,
   hors de la boucle asyncio du serveur.
4. Calculer le nombre réel de trames d'après la taille du payload, puis créer
   le memmap. L'en-tête théorique ne détermine pas la taille du mapping.
5. Lire `int(temps_ms / 1000 * fps)`, borné à la première ou dernière trame.
   Une copie de cette petite trame permet de libérer le mapping sous Windows
   lors du changement de film.
6. Convertir en RGB888, appliquer les réglages dynamiques et envoyer en DDP.

Les vérifications sont mises en cache par média et dimensions. Taille et dates
du fichier sont revérifiées environ une fois par seconde pendant la lecture.
Un fichier absent ou incompatible peut donc être détecté après sa création ou
son remplacement, sans être rouvert à chaque image.

Le serveur attend le résultat du chargement avant de reprendre le rendu et vérifie
que le média et les réglages n'ont pas changé pendant l'attente. L'interface web
reste disponible durant la décompression. Une annulation attend la fin du worker
avant le nettoyage du lecteur.

## Réglages dynamiques

Luminosité par côté, lissage, point de départ, sens et décalages restent appliqués
à chaque cycle. Les décalages de côté insèrent du noir ; ce ne sont pas des
rotations circulaires. Profondeur de capture et recadrage nécessitent un nouveau
préencodage pour changer les couleurs stockées.

Le rafraîchissement WLEDSUB suit actuellement le réglage de fréquence de l'application,
pas automatiquement la fréquence stockée dans la piste. Le format DDP courant
limite la sortie à 480 LED par paquet.

Voir [les tests de non-régression](tests/README.md) pour les vérifications de
conversion, de rendu et de cycle de vie.
