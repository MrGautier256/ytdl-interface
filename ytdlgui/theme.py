"""Thèmes clair/sombre : détection système, application sv-ttk, palette tk."""
import ctypes
import os
import subprocess
import sys

_VENDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor")
if os.path.isdir(_VENDOR) and _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

LIGHT = dict(
    bg="#fafafa", fg="#1c1c1c", text_bg="#ffffff", text_fg="#1c1c1c",
    muted="#6a6a6a", border="#d0d0d0", tip_bg="#ffffe1", tip_fg="#333333",
    preview_bg="#f2f2f2", select_bg="#0067c0", select_fg="#ffffff",
)
DARK = dict(
    bg="#1c1c1c", fg="#fafafa", text_bg="#2a2a2a", text_fg="#f0f0f0",
    muted="#a6a6a6", border="#3f3f3f", tip_bg="#3a3a3a", tip_fg="#f0f0f0",
    preview_bg="#242424", select_bg="#4cc2ff", select_fg="#1c1c1c",
)
PAL = dict(LIGHT)   # palette courante, mise à jour par apply()
CURRENT = "light"

# Familles de polices : Segoe UI / Consolas n'existent pas sous Linux, où fontconfig
# résout les alias génériques vers les polices du bureau (Consolas absente retomberait
# sur une police proportionnelle, illisible pour le journal et la commande).
if os.name == "nt":
    FONT_UI, FONT_MONO = "Segoe UI", "Consolas"
else:
    FONT_UI, FONT_MONO = "sans-serif", "monospace"


def system_prefers_dark():
    if os.name == "nt":
        try:
            import winreg
            key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                value, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
            return value == 0
        except Exception:
            return False
    return _linux_prefers_dark()


def _linux_prefers_dark():
    """Préférence sombre du bureau Linux : réglage GNOME (repris par la plupart des
    bureaux GTK, et par KDE via sa synchronisation GTK), puis nom du thème GTK."""
    for gkey in ("color-scheme", "gtk-theme"):
        try:
            out = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", gkey],
                capture_output=True, text=True, timeout=3).stdout
        except Exception:
            return False
        if "dark" in out.lower():
            return True
    return False


def resolve(mode):
    if mode == "dark":
        return "dark"
    if mode == "auto" and system_prefers_dark():
        return "dark"
    return "light"


def apply(root, mode):
    """Applique le thème sur la racine ; retourne 'light' ou 'dark'."""
    global CURRENT
    name = resolve(mode)
    CURRENT = name
    PAL.clear()
    PAL.update(DARK if name == "dark" else LIGHT)
    try:
        import sv_ttk
        try:
            sv_ttk.set_theme(name, root)
        except TypeError:
            sv_ttk.set_theme(name)
    except Exception:
        _fallback(root, name)
    try:
        root.configure(bg=PAL["bg"])
        root.option_add("*TCombobox*Listbox.background", PAL["text_bg"])
        root.option_add("*TCombobox*Listbox.foreground", PAL["fg"])
        root.option_add("*TCombobox*Listbox.selectBackground", PAL["select_bg"])
        root.option_add("*TCombobox*Listbox.selectForeground", PAL["select_fg"])
    except Exception:
        pass
    darken_titlebar(root, name == "dark")
    return name


def style_toplevel(window):
    """Applique fond et barre de titre du thème courant à une fenêtre secondaire."""
    try:
        window.configure(bg=PAL["bg"])
    except Exception:
        pass
    darken_titlebar(window, CURRENT == "dark")


def _fallback(root, name):
    """Sans sv-ttk : couleurs de base via le thème ttk 'clam'."""
    from tkinter import ttk
    style = ttk.Style(root)
    if name == "dark":
        try:
            style.theme_use("clam")
        except Exception:
            return
        c = DARK
        style.configure(".", background=c["bg"], foreground=c["fg"],
                        fieldbackground=c["text_bg"], bordercolor=c["border"])
        for w in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton", "TLabelframe",
                  "TLabelframe.Label", "TNotebook", "TButton", "TMenubutton", "TSpinbox"):
            style.configure(w, background=c["bg"], foreground=c["fg"])
        style.configure("TNotebook.Tab", background=c["bg"], foreground=c["fg"])
        style.map("TNotebook.Tab", background=[("selected", c["text_bg"])])
        style.configure("TEntry", fieldbackground=c["text_bg"], foreground=c["fg"])
        style.configure("TCombobox", fieldbackground=c["text_bg"], foreground=c["fg"])
        style.configure("Treeview", background=c["text_bg"],
                        fieldbackground=c["text_bg"], foreground=c["fg"])
        style.configure("Treeview.Heading", background=c["bg"], foreground=c["fg"])
    else:
        try:
            style.theme_use("vista")
        except Exception:
            pass


def flash_taskbar(window, count=5):
    """Fait clignoter l'icône de la barre des tâches (notification discrète de fin de file).

    N'agit que si la fenêtre n'a pas déjà le focus : inutile d'attirer l'attention
    sur une fenêtre que l'utilisateur regarde déjà. Windows uniquement.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("hwnd", wintypes.HWND),
                ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT),
                ("dwTimeout", wintypes.DWORD),
            ]

        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        if ctypes.windll.user32.GetForegroundWindow() == hwnd:
            return
        FLASHW_ALL = 0x00000003
        FLASHW_TIMERNOFG = 0x0000000C
        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_ALL | FLASHW_TIMERNOFG, count, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception:
        pass


def darken_titlebar(window, dark):
    """Barre de titre sombre via DWM (Windows 10 1809+). Sans effet ailleurs
    (sous Linux, la barre de titre est dessinée par le gestionnaire de fenêtres)."""
    if os.name != "nt":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE selon la version
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:
        pass
