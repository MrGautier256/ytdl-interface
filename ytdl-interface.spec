# -*- mode: python ; coding: utf-8 -*-
# Build : pyinstaller ytdl-interface.spec
# Produit un dossier portable (dist/YTDL-Interface/) contenant YTDL-Interface.exe :
# aucun installeur, settings.json et bin/ (yt-dlp, ffmpeg) sont créés à côté de l'exe,
# dans ce même dossier, au premier lancement. Le dossier est zippé tel quel pour la release.

# ytdlgui.i18n charge ytdlgui.locales.<code> via importlib.import_module() avec un nom
# construit dynamiquement : l'analyse statique de PyInstaller ne le détecte pas, d'où
# la liste explicite ci-dessous (sinon l'exe démarre mais affiche les clés de traduction
# brutes au lieu du texte, faute de pouvoir importer les modules de langue).
LOCALE_MODULES = ['ytdlgui.locales.' + code for code in
                   ('fr', 'en', 'es', 'de', 'it', 'pt', 'nl', 'pl', 'ru')]

# vendor/sv_ttk est chargé au runtime via un sys.path.insert() (cf. ytdlgui/theme.py),
# donc jamais analysé statiquement par PyInstaller : ses propres imports stdlib
# (from __future__ import ..., pathlib) ne sont alors pas embarqués et son chargement
# échoue silencieusement (theme.py bascule sur le thème de secours, moins abouti :
# plus de bouton bleu "Accent", coins moins arrondis). On les liste explicitement ici.
SVTTK_DEPS = ['__future__', 'pathlib', 'functools']

a = Analysis(
    ['main.pyw'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),   # icône (assets/icon.ico), lue via ytdlgui.binaries.resource_path()
        ('vendor', 'vendor'),   # sv_ttk vendoré : fichiers .tcl/.png non détectables par l'analyse statique
    ],
    hiddenimports=LOCALE_MODULES + SVTTK_DEPS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='YTDL-Interface',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='YTDL-Interface',
)
