"""Point d'entrée de YTDL Interface. Lancer avec pythonw (sans console)."""
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


def _already_running():
    """Détecte une instance déjà lancée via un mutex nommé Windows (évite deux process qui écrivent settings.json en même temps)."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return False


def main():
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
