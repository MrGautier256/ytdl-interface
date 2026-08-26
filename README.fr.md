[English](README.md) · **Français**

# YTDL Interface

Interface graphique complète pour [yt-dlp](https://github.com/yt-dlp/yt-dlp), le successeur maintenu de youtube-dl. Compatible YouTube et plus de 1000 autres sites.

## Lancement

**Version prête à l'emploi (recommandé) :** téléchargez le dernier `YTDL-Interface.zip` depuis la page [Releases](../../releases), extrayez-le où vous voulez, puis lancez `YTDL-Interface.exe` dans le dossier extrait. Aucune installation, aucun prérequis.

**Depuis les sources :** double-cliquer sur `main.pyw` (nécessite Python 3, avec Tkinter, inclus par défaut sur Windows).

Dans les deux cas, si yt-dlp et/ou ffmpeg sont absents de la machine, l'application le détecte au démarrage et propose une fenêtre d'installation avec barre de progression par composant ; l'installation se fait en arrière-plan, sans quitter l'app. Accessible aussi à tout moment depuis l'onglet Avancé ("Télécharger yt-dlp" / "Installer ffmpeg" / "Mettre à jour yt-dlp"). Les réglages et les binaires sont enregistrés dans ce même dossier (`settings.json`, `bin/`), à côté de l'exécutable, pas dans un dossier système : gardez le dossier entier ensemble.

## Langue et thème

En haut de la fenêtre :
- **Langue** : 9 langues disponibles (français, anglais, espagnol, allemand, italien, portugais, néerlandais, polonais, russe). "Auto" suit la langue de Windows.
- **Thème** : clair ou sombre (habillage moderne Sun Valley, bibliothèque sv-ttk embarquée dans `vendor/`). "Auto" suit le thème de Windows, barre de titre comprise.

## Utilisation rapide

1. Coller un ou plusieurs liens (un par ligne) dans l'onglet **Téléchargement**.
2. Choisir un préréglage (Vidéo 1080p MP4, Audio MP3...) ou affiner dans les onglets.
3. Cliquer sur **Télécharger**. La file affiche progression, vitesse et temps restant.

Le bouton **Analyser la vidéo** affiche titre, durée, miniature et la liste complète des formats disponibles ; on peut y choisir manuellement un format vidéo + un format audio précis.

## Les onglets

- **Téléchargement** : liens, destination, préréglages, file d'attente.
- **Format et qualité** : vidéo/audio seul, résolution max, conteneur (mp4/mkv/webm), codec, format audio (mp3, m4a, opus, flac...), qualité, sélecteur `-f` personnalisé.
- **Sous-titres** : officiels ou automatiques, langues, conversion srt, incrustation.
- **Playlist et filtres** : playlist entière ou vidéo seule, sélection d'éléments, filtres par date et taille, archive anti-doublons, tolérance aux erreurs.
- **Fichiers et métadonnées** : modèle de nom (avec sous-dossiers), miniature, métadonnées, chapitres, description, découpage par chapitres, SponsorBlock (marquer ou supprimer les pubs intégrées).
- **Réseau et comptes** : limite de vitesse, fragments parallèles (accélération), proxy, IPv4, cookies du navigateur (vidéos privées ou avec limite d'âge), identifiants.
- **Avancé** : téléchargement partiel par sections de temps, téléchargements simultanés, chemins des binaires, mise à jour de yt-dlp, simulation, arguments libres, et l'aperçu en direct de la commande yt-dlp générée (copiable).
- **Journal** : sortie complète de yt-dlp, pour le diagnostic.

Chaque option a une infobulle d'explication au survol.

## Notes

- Les réglages sont mémorisés dans `settings.json`, à côté de l'exécutable (le mot de passe n'est jamais enregistré).
- En cas d'erreur "Sign in to confirm you're not a bot" sur YouTube : onglet Réseau et comptes, sélectionner son navigateur dans "Utiliser les cookies du navigateur".
- Toute option yt-dlp absente de l'interface peut être passée via "Arguments supplémentaires" (onglet Avancé).

## Avertissement

Cet outil télécharge du contenu depuis des sites tiers. À utiliser dans le respect des conditions d'utilisation de ces sites et des droits des ayants droit (usage personnel, contenus libres de droits ou dont vous détenez les droits).

## Licence et crédits

YTDL Interface est distribué sous licence MIT (voir [LICENSE](LICENSE)).

Au premier lancement, l'application télécharge pour son propre fonctionnement :
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (licence Unlicense / domaine public)
- [ffmpeg](https://github.com/BtbN/FFmpeg-Builds) (build GPL de BtbN)

Le thème visuel Sun Valley ([sv-ttk](https://github.com/rdbende/Sun-Valley-ttk-theme), licence MIT) est embarqué dans `vendor/`.
