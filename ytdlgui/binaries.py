"""Localisation et gestion des binaires yt-dlp / ffmpeg."""
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

IS_WINDOWS = os.name == "nt"
CREATE_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0
EXE_SUFFIX = ".exe" if IS_WINDOWS else ""
YTDLP_NAME = "yt-dlp" + EXE_SUFFIX
FFMPEG_NAME = "ffmpeg" + EXE_SUFFIX
FFPROBE_NAME = "ffprobe" + EXE_SUFFIX

_ARM64 = platform.machine().lower() in ("aarch64", "arm64")

# Builds autonomes officiels de yt-dlp : sous Linux, yt-dlp_linux embarque son propre
# Python (contrairement au fichier "yt-dlp" nu, qui exige python3 sur la machine).
_GH_YTDLP = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
# Build GPL statique de BtbN/FFmpeg-Builds (recommandé par yt-dlp) : hébergé sur
# GitHub, URL stable, TLS fiable (contrairement à gyan.dev dont la chaîne de
# certificats est mal servie et rejetée par le module ssl de Python malgré un
# certificat valide côté Windows/curl). Zip sous Windows, tar.xz sous Linux.
_GH_FFMPEG = "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/"
if IS_WINDOWS:
    YTDLP_RELEASE_URL = _GH_YTDLP + "yt-dlp.exe"
    FFMPEG_RELEASE_URL = _GH_FFMPEG + "ffmpeg-master-latest-win64-gpl.zip"
elif _ARM64:
    YTDLP_RELEASE_URL = _GH_YTDLP + "yt-dlp_linux_aarch64"
    FFMPEG_RELEASE_URL = _GH_FFMPEG + "ffmpeg-master-latest-linuxarm64-gpl.tar.xz"
else:
    YTDLP_RELEASE_URL = _GH_YTDLP + "yt-dlp_linux"
    FFMPEG_RELEASE_URL = _GH_FFMPEG + "ffmpeg-master-latest-linux64-gpl.tar.xz"


def app_dir():
    """Dossier de référence pour bin/ et settings.json.

    En exécutable packagé (PyInstaller), __file__ pointe vers le dossier
    d'extraction temporaire (_MEIxxxxxx), qui disparaît à la fermeture : on
    utilise alors le dossier de l'exe pour rester portable (settings et
    binaires téléchargés à côté de l'exe, persistants d'un lancement à l'autre).
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts):
    """Chemin vers une ressource embarquée en lecture seule (ex : assets/icon.ico).

    Contrairement à app_dir(), part de _MEIPASS en exécutable packagé (là où
    PyInstaller extrait les fichiers de données ajoutés au build), et du
    dossier du projet en exécution depuis les sources.
    """
    base = getattr(sys, "_MEIPASS", None) or app_dir()
    return os.path.join(base, *parts)


def bin_dir():
    d = os.path.join(app_dir(), "bin")
    os.makedirs(d, exist_ok=True)
    return d


def find_ytdlp(custom_path=""):
    """Retourne le chemin de yt-dlp : chemin perso > bin/ local > PATH."""
    custom_path = (custom_path or "").strip()
    if custom_path and os.path.isfile(custom_path):
        return custom_path
    local = os.path.join(bin_dir(), YTDLP_NAME)
    if os.path.isfile(local):
        return local
    return shutil.which("yt-dlp")


def find_ffmpeg(custom_path=""):
    custom_path = (custom_path or "").strip()
    if custom_path and os.path.isfile(custom_path):
        return custom_path
    local = os.path.join(bin_dir(), FFMPEG_NAME)
    if os.path.isfile(local):
        return local
    return shutil.which("ffmpeg")


def _make_executable(path):
    """Ajoute le droit d'exécution (Linux) : un fichier téléchargé arrive en 0644."""
    if not IS_WINDOWS:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def open_folder(path):
    """Ouvre un dossier dans l'explorateur de fichiers du système."""
    if IS_WINDOWS:
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)


def format_command(cmd):
    """Ligne de commande copiable, avec les règles de quoting du shell de la plateforme."""
    if IS_WINDOWS:
        return subprocess.list2cmdline(cmd)
    import shlex
    return shlex.join(cmd)


def download_ytdlp(progress_cb=None):
    """Télécharge la dernière version de yt-dlp (build autonome) dans bin/."""
    dest = os.path.join(bin_dir(), YTDLP_NAME)
    tmp = dest + ".part"

    def hook(blocks, bsize, total):
        if progress_cb and total > 0:
            progress_cb(min(100.0, blocks * bsize * 100.0 / total))

    urllib.request.urlretrieve(YTDLP_RELEASE_URL, tmp, reporthook=hook)
    _make_executable(tmp)
    os.replace(tmp, dest)
    return dest


def _iter_archive(path):
    """Parcourt une archive zip (Windows) ou tar.xz (Linux) en un seul passage.

    Produit des couples (chemin normalisé avec des /, flux lisible). Un tar.xz ne
    permet pas d'accès direct : relire un membre déjà dépassé obligerait à tout
    redécompresser, d'où ce parcours séquentiel unique.
    """
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                with zf.open(name) as src:
                    yield name.replace("\\", "/"), src
    else:
        with tarfile.open(path, "r:*") as tf:
            for member in tf:
                if member.isfile():
                    with tf.extractfile(member) as src:
                        yield member.name, src


def download_ffmpeg(progress_cb=None, status_cb=None):
    """Télécharge un build ffmpeg (BtbN GPL) et extrait ffmpeg/ffprobe dans bin/.

    Le téléchargement occupe 0-90% de la progression, l'extraction 90-100%.
    status_cb("extracting") est appelé juste avant l'extraction.
    """
    dest_dir = bin_dir()
    tmp_archive = os.path.join(dest_dir, "ffmpeg_download.part")

    def hook(blocks, bsize, total):
        if progress_cb and total > 0:
            progress_cb(min(100.0, blocks * bsize * 100.0 / total) * 0.9)

    try:
        urllib.request.urlretrieve(FFMPEG_RELEASE_URL, tmp_archive, reporthook=hook)
        if status_cb:
            status_cb("extracting")
        wanted = (FFMPEG_NAME, FFPROBE_NAME)
        done = set()
        for norm, src in _iter_archive(tmp_archive):
            base = norm.rsplit("/", 1)[-1]
            if base not in wanted or "/bin/" not in norm or base in done:
                continue
            out_path = os.path.join(dest_dir, base)
            tmp_out = out_path + ".part"
            with open(tmp_out, "wb") as dst:
                shutil.copyfileobj(src, dst)
            _make_executable(tmp_out)
            os.replace(tmp_out, out_path)
            done.add(base)
            if progress_cb:
                progress_cb(90.0 + len(done) / len(wanted) * 10.0)
            if len(done) == len(wanted):
                break
        if FFMPEG_NAME not in done:
            raise RuntimeError("%s introuvable dans l'archive téléchargée." % FFMPEG_NAME)
    finally:
        if os.path.isfile(tmp_archive):
            try:
                os.remove(tmp_archive)
            except OSError:
                pass
    if progress_cb:
        progress_cb(100.0)
    return os.path.join(dest_dir, FFMPEG_NAME)


def get_version(ytdlp_path):
    try:
        out = subprocess.run(
            [ytdlp_path, "--version"],
            capture_output=True, text=True, timeout=30,
            creationflags=CREATE_NO_WINDOW,
        )
        return out.stdout.strip()
    except Exception:
        return ""
