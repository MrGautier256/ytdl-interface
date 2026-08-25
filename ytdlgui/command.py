"""Construction de la ligne de commande yt-dlp à partir des réglages."""
import re
import shlex


def _digits(s):
    m = re.search(r"\d+", str(s or ""))
    return m.group(0) if m else ""


def build_network_args(cfg):
    """Options réseau/authentification, réutilisées aussi pour l'analyse."""
    args = []
    proxy = cfg.get("proxy", "").strip()
    if proxy:
        args += ["--proxy", proxy]
    browser = cfg.get("cookies_browser", "").strip()
    if browser and not browser.startswith("("):
        args += ["--cookies-from-browser", browser]
    elif cfg.get("cookies_file", "").strip():
        args += ["--cookies", cfg["cookies_file"].strip()]
    if cfg.get("username", "").strip():
        args += ["--username", cfg["username"].strip()]
        if cfg.get("password", ""):
            args += ["--password", cfg["password"]]
    if cfg.get("force_ipv4"):
        args += ["--force-ipv4"]
    if cfg.get("geo_bypass"):
        args += ["--geo-bypass"]
    return args


def needs_ffmpeg(cfg):
    """Estime si les réglages actuels nécessitent ffmpeg pour aboutir sans erreur.

    Couvre les cas certains (extraction audio, embed, recode, découpage...) ainsi
    que le cas le plus courant en pratique : un mode "vidéo" sans format personnalisé
    finit presque toujours par fusionner un flux vidéo et un flux audio séparés
    (DASH), ce que yt-dlp ne peut faire sans ffmpeg.
    """
    mode = cfg.get("mode", "video")
    if mode == "audio":
        return True
    custom = cfg.get("custom_format", "").strip()
    if custom:
        if "+" in custom:
            return True
    elif mode == "video":
        return True
    if cfg.get("embed_thumbnail") or cfg.get("embed_metadata") or cfg.get("embed_chapters"):
        return True
    if cfg.get("recode"):
        return True
    cont = cfg.get("container", "auto").strip()
    if cont and cont != "auto":
        return True
    if cfg.get("split_chapters"):
        return True
    if cfg.get("sb_mode") in ("mark", "remove"):
        return True
    if cfg.get("sections", "").strip():
        return True
    if cfg.get("convert_subs", "").strip().lower() in ("srt", "vtt", "ass", "lrc"):
        return True
    if cfg.get("embed_subs"):
        return True
    return False


def build_command(cfg, url, ytdlp_path, ffmpeg_path=None):
    args = [ytdlp_path, "--newline", "--progress"]
    if ffmpeg_path:
        args += ["--ffmpeg-location", ffmpeg_path]

    # ----- Format et qualité -----
    mode = cfg.get("mode", "video")
    custom = cfg.get("custom_format", "").strip()
    if custom:
        args += ["-f", custom]
    elif mode == "video_only":
        args += ["-f", "bestvideo/best"]
    elif mode == "audio":
        args += ["-f", "bestaudio/best"]

    if mode == "audio":
        args += ["-x"]
        # Les libellés localisés ("Meilleure", "Best"...) ne sont jamais passés
        # à yt-dlp : seules les valeurs techniques connues le sont.
        af = cfg.get("audio_format", "").strip().lower()
        if af in ("mp3", "m4a", "opus", "flac", "wav", "aac", "vorbis", "alac"):
            args += ["--audio-format", af]
        aq = cfg.get("audio_quality", "").strip()
        if aq:
            args += ["--audio-quality", aq if any(c.isdigit() for c in aq) else "0"]
    else:
        sort = []
        res = _digits(cfg.get("max_res", ""))
        if res:
            sort.append("res:%s" % res)
        vc = cfg.get("vcodec", "auto").strip()
        if vc and vc != "auto":
            sort.append("vcodec:%s" % vc)
        if sort:
            args += ["-S", ",".join(sort)]
        cont = cfg.get("container", "auto").strip()
        if cont and cont != "auto":
            args += ["--recode-video" if cfg.get("recode") else "--remux-video", cont]

    # ----- Sous-titres -----
    if cfg.get("write_subs"):
        args += ["--write-subs"]
    if cfg.get("auto_subs"):
        args += ["--write-auto-subs"]
    if cfg.get("write_subs") or cfg.get("auto_subs") or cfg.get("embed_subs"):
        langs = "all" if cfg.get("all_subs") else cfg.get("sub_langs", "").strip()
        if langs:
            args += ["--sub-langs", langs]
    cs = cfg.get("convert_subs", "").strip().lower()
    if cs in ("srt", "vtt", "ass", "lrc"):
        args += ["--convert-subs", cs]
    if cfg.get("embed_subs"):
        args += ["--embed-subs"]

    # ----- Playlist et filtres -----
    if cfg.get("playlist_mode", "single") == "single":
        args += ["--no-playlist"]
    else:
        args += ["--yes-playlist"]
    for key, flag in (
        ("playlist_items", "--playlist-items"),
        ("date_after", "--dateafter"),
        ("date_before", "--datebefore"),
        ("max_filesize", "--max-filesize"),
    ):
        v = cfg.get(key, "").strip()
        if v:
            args += [flag, v]
    md = cfg.get("max_downloads", "").strip()
    if md.isdigit() and int(md) > 0:
        args += ["--max-downloads", md]
    if cfg.get("use_archive"):
        ap = cfg.get("archive_path", "").strip() or "archive.txt"
        args += ["--download-archive", ap]
    if cfg.get("ignore_errors"):
        args += ["--ignore-errors"]

    # ----- Fichiers et métadonnées -----
    dest = cfg.get("dest_dir", "").strip()
    if dest:
        args += ["-P", dest]
    tmpl = cfg.get("output_template", "").strip() or "%(title)s.%(ext)s"
    args += ["-o", tmpl]
    if cfg.get("restrict_filenames"):
        args += ["--restrict-filenames"]
    if cfg.get("no_mtime"):
        args += ["--no-mtime"]
    for key, flag in (
        ("embed_thumbnail", "--embed-thumbnail"),
        ("write_thumbnail", "--write-thumbnail"),
        ("embed_metadata", "--embed-metadata"),
        ("embed_chapters", "--embed-chapters"),
        ("write_description", "--write-description"),
        ("write_infojson", "--write-info-json"),
        ("split_chapters", "--split-chapters"),
    ):
        if cfg.get(key):
            args += [flag]
    sb = cfg.get("sb_mode", "non")
    if sb in ("mark", "remove"):
        cats = cfg.get("sb_cats", "").strip() or "sponsor"
        args += ["--sponsorblock-mark" if sb == "mark" else "--sponsorblock-remove", cats]

    # ----- Réseau et performances -----
    lr = cfg.get("limit_rate", "").strip()
    if lr:
        args += ["--limit-rate", lr]
    rt = cfg.get("retries", "").strip()
    if rt.isdigit():
        args += ["--retries", rt]
    ncf = cfg.get("concurrent_fragments", "").strip()
    if ncf.isdigit() and int(ncf) > 1:
        args += ["--concurrent-fragments", ncf]
    si = cfg.get("sleep_interval", "").strip()
    if si:
        try:
            float(si)
            args += ["--sleep-interval", si]
        except ValueError:
            pass
    args += build_network_args(cfg)

    # ----- Avancé -----
    sec = cfg.get("sections", "").strip()
    if sec:
        args += ["--download-sections", sec]
        if cfg.get("force_keyframes"):
            args += ["--force-keyframes-at-cuts"]
    if cfg.get("simulate"):
        args += ["--simulate"]
    if cfg.get("verbose"):
        args += ["--verbose"]
    extra = cfg.get("custom_args", "").strip()
    if extra:
        try:
            args += [t.strip('"') for t in shlex.split(extra, posix=False)]
        except ValueError:
            args += extra.split()

    args.append(url)
    return args
