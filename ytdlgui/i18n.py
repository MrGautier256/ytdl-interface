"""Internationalisation : langues disponibles, détection système, T(clé)."""
import importlib
import locale

# (code, nom natif) ; "auto" est ajouté en tête par l'interface
LANGS = [
    ("fr", "Français"),
    ("en", "English"),
    ("es", "Español"),
    ("de", "Deutsch"),
    ("it", "Italiano"),
    ("pt", "Português"),
    ("nl", "Nederlands"),
    ("pl", "Polski"),
    ("ru", "Русский"),
]

_SUPPORTED = [code for code, _ in LANGS]
_current = "fr"
_tables = {}


def _load(lang):
    if lang not in _tables:
        try:
            mod = importlib.import_module(".locales.%s" % lang, package="ytdlgui")
            _tables[lang] = getattr(mod, "S", {})
        except Exception:
            _tables[lang] = {}
    return _tables[lang]


def system_lang():
    """Code langue de l'interface Windows (fr, en...), 'en' par défaut."""
    try:
        import ctypes
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        code = locale.windows_locale.get(lcid, "en")
        return code.split("_")[0].lower()
    except Exception:
        try:
            code = (locale.getlocale()[0] or "en")
            return code.split("_")[0].lower()
        except Exception:
            return "en"


def set_lang(code):
    global _current
    if code == "auto":
        code = system_lang()
    _current = code if code in _SUPPORTED else "en"


def get_lang():
    return _current


def T(key):
    table = _load(_current)
    if key in table:
        return table[key]
    for fallback in ("en", "fr"):
        value = _load(fallback).get(key)
        if value is not None:
            return value
    return key
