"""Point d'entrée de YTDL Interface. Lancer avec pythonw (sans console) sous Windows,
python3 main.pyw sous Linux."""
import errno
import os
import sys
import traceback

APP_DIR = (os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False)
           else os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)
_VENDOR = os.path.join(APP_DIR, "vendor")
if os.path.isdir(_VENDOR):
    sys.path.insert(1, _VENDOR)

_MUTEX_NAME = "Global\\YTDLInterface_SingleInstance_Mutex"
_instance_socket = None   # Linux : gardée ouverte tant que l'app tourne


def _already_running():
    """Détecte une instance déjà lancée (évite deux process qui écrivent settings.json en même temps).

    Windows : mutex nommé. Linux : socket Unix dans l'espace de noms abstrait, propre
    à l'utilisateur ; aucun fichier créé, et le noyau la libère à la fin du process,
    même en cas de plantage (pas de verrou orphelin à nettoyer).
    """
    global _instance_socket
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
            return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
        except Exception:
            return False
    try:
        import socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    except Exception:
        return False
    try:
        sock.bind("\0YTDLInterface_SingleInstance_%d" % os.getuid())
    except OSError as exc:
        sock.close()
        return exc.errno == errno.EADDRINUSE
    _instance_socket = sock
    return False


def _restore_child_env():
    """Exécutable Linux packagé : le bootloader PyInstaller préfixe LD_LIBRARY_PATH avec
    le dossier de ses bibliothèques embarquées. yt-dlp, ffmpeg, xdg-open, gsettings...
    en hériteraient et chargeraient nos copies au lieu des leurs (plantages possibles).
    On rétablit la valeur d'origine, que le bootloader sauvegarde dans
    LD_LIBRARY_PATH_ORIG. Sans effet sur le process courant : le chargeur dynamique
    lit cette variable une seule fois, au démarrage.
    """
    if os.name == "nt" or not getattr(sys, "frozen", False):
        return
    orig = os.environ.pop("LD_LIBRARY_PATH_ORIG", None)
    if orig is not None:
        os.environ["LD_LIBRARY_PATH"] = orig
    else:
        os.environ.pop("LD_LIBRARY_PATH", None)


def main():
    _restore_child_env()
    if _already_running():
        try:
            import tkinter
            import tkinter.messagebox
            root = tkinter.Tk()
            root.withdraw()
            tkinter.messagebox.showwarning(
                "YTDL Interface",
                "YTDL Interface est déjà ouvert.\nYTDL Interface is already running.")
            root.destroy()
        except Exception:
            pass
        return
    try:
        from ytdlgui.app import App
        App().mainloop()
    except Exception:
        err = traceback.format_exc()
        try:
            with open(os.path.join(APP_DIR, "error.log"), "a", encoding="utf-8") as f:
                f.write(err + "\n")
        except OSError:
            pass
        try:
            import tkinter.messagebox
            tkinter.messagebox.showerror(
                "YTDL Interface : erreur",
                "Une erreur inattendue s'est produite (détails dans error.log) :\n\n" + err[-1200:])
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
