"""Localisation et gestion des binaires yt-dlp / ffmpeg."""
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

YTDLP_RELEASE_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
# Build GPL statique de BtbN/FFmpeg-Builds (recommandé par yt-dlp pour Windows) :
# hébergé sur GitHub, URL stable, TLS fiable (contrairement à gyan.dev dont la chaîne
# de certificats est mal servie et rejetée par le module ssl de Python malgré un
# certificat valide côté Windows/curl).
FFMPEG_RELEASE_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip"


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
    local = os.path.join(bin_dir(), "yt-dlp.exe")
    if os.path.isfile(local):
        return local
    return shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")


def find_ffmpeg(custom_path=""):
    custom_path = (custom_path or "").strip()
    if custom_path and os.path.isfile(custom_path):
        return custom_path
    local = os.path.join(bin_dir(), "ffmpeg.exe")
    if os.path.isfile(local):
        return local
    return shutil.which("ffmpeg")


def download_ytdlp(progress_cb=None):
    """Télécharge la dernière version de yt-dlp.exe dans bin/."""
    dest = os.path.join(bin_dir(), "yt-dlp.exe")
    tmp = dest + ".part"

    def hook(blocks, bsize, total):
        if progress_cb and total > 0:
            progress_cb(min(100.0, blocks * bsize * 100.0 / total))

    urllib.request.urlretrieve(YTDLP_RELEASE_URL, tmp, reporthook=hook)
    os.replace(tmp, dest)
    return dest


def download_ffmpeg(progress_cb=None, status_cb=None):
    """Télécharge un build ffmpeg (gyan.dev essentials) et extrait ffmpeg.exe/ffprobe.exe dans bin/.

    Le téléchargement occupe 0-90% de la progression, l'extraction 90-100%.
    status_cb("extracting") est appelé juste avant l'extraction.
    """
    dest_dir = bin_dir()
    tmp_zip = os.path.join(dest_dir, "ffmpeg_download.zip.part")

    def hook(blocks, bsize, total):
        if progress_cb and total > 0:
            progress_cb(min(100.0, blocks * bsize * 100.0 / total) * 0.9)

    try:
        urllib.request.urlretrieve(FFMPEG_RELEASE_URL, tmp_zip, reporthook=hook)
        if status_cb:
            status_cb("extracting")
        wanted = ("ffmpeg.exe", "ffprobe.exe")
        with zipfile.ZipFile(tmp_zip) as zf:
            found = {}
            for name in zf.namelist():
                norm = name.replace("\\", "/")
                base = norm.rsplit("/", 1)[-1]
                if base in wanted and "/bin/" in norm and base not in found:
                    found[base] = name
            if "ffmpeg.exe" not in found:
                raise RuntimeError("ffmpeg.exe introuvable dans l'archive téléchargée.")
            total = len(found)
            for i, (base, name) in enumerate(found.items(), 1):
                out_path = os.path.join(dest_dir, base)
                tmp_out = out_path + ".part"
                with zf.open(name) as src, open(tmp_out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                os.replace(tmp_out, out_path)
                if progress_cb:
                    progress_cb(90.0 + i / total * 10.0)
    finally:
        if os.path.isfile(tmp_zip):
            try:
                os.remove(tmp_zip)
            except OSError:
                pass
    if progress_cb:
        progress_cb(100.0)
    return os.path.join(dest_dir, "ffmpeg.exe")


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
