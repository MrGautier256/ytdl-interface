# -*- mode: python ; coding: utf-8 -*-
# Build : pyinstaller ytdl-interface.spec
# Produit un exe unique portable (dist/YTDL-Interface.exe) : aucun installeur,
# settings.json et bin/ (yt-dlp, ffmpeg) sont créés à côté de l'exe au premier lancement.

# ytdlgui.i18n charge ytdlgui.locales.<code> via importlib.import_module() avec un nom
# construit dynamiquement : l'analyse statique de PyInstaller ne le détecte pas, d'où
# la liste explicite ci-dessous (sinon l'exe démarre mais affiche les clés de traduction
# brutes au lieu du texte, faute de pouvoir importer les modules de langue).
LOCALE_MODULES = ['ytdlgui.locales.' + code for code in
                   ('fr', 'en', 'es', 'de', 'it', 'pt', 'nl', 'pl', 'ru')]

a = Analysis(
    ['main.pyw'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),   # icône (assets/icon.ico), lue via ytdlgui.binaries.resource_path()
        ('vendor', 'vendor'),   # sv_ttk vendoré : fichiers .tcl/.png non détectables par l'analyse statique
    ],
    hiddenimports=LOCALE_MODULES,
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
    a.binaries,
    a.datas,
    [],
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
