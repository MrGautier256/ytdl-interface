"""Fenêtre principale de YTDL Interface (interface graphique pour yt-dlp)."""
import os
import queue
import re
import subprocess
import tempfile
import threading
import urllib.request
import json as jsonmod
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import __version__
from . import command as cmdmod
from . import engine as eng
from . import i18n
from . import theme
from .binaries import (
    CREATE_NO_WINDOW, app_dir, download_ffmpeg, download_ytdlp, find_ffmpeg, find_ytdlp,
    get_version, resource_path,
)
from .config import load_settings, save_settings
from .i18n import T
from .widgets import ScrollableFrame, Tooltip, human_duration, human_size

PRESET_KEYS = ["preset.best", "preset.1080", "preset.720", "preset.mp3", "preset.m4a"]
PRESETS = {
    "preset.best": dict(
        mode="video", container="auto", vcodec="auto", recode=False,
        custom_format="", _res="best"),
    "preset.1080": dict(
        mode="video", max_res="1080", container="mp4", vcodec="auto",
        recode=False, custom_format=""),
    "preset.720": dict(
        mode="video", max_res="720", container="mp4", vcodec="auto",
        recode=False, custom_format=""),
    "preset.mp3": dict(
        mode="audio", audio_format="mp3", audio_quality="320K",
        embed_thumbnail=True, embed_metadata=True, custom_format=""),
    "preset.m4a": dict(
        mode="audio", audio_format="m4a", _aq="best",
        embed_thumbnail=True, embed_metadata=True, custom_format=""),
}

THEME_CODES = ["auto", "light", "dark"]
AUDIO_FORMATS = ("mp3", "m4a", "opus", "flac", "wav")
SUB_FORMATS = ("srt", "vtt", "ass", "lrc")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.app_dir = app_dir()
        self.settings = load_settings(self.app_dir)
        try:
            self.iconbitmap(default=resource_path("assets", "icon.ico"))
        except Exception:
            pass
        self.minsize(900, 640)
        self.geometry(self._safe_geometry(self.settings.get("_geometry", "1060x760")))

        self.ui_queue = queue.Queue()
        self.engine = eng.Engine(self.ui_queue)
        self.job_rows = {}          # job_id -> iid du Treeview
        self._preview_after = None
        self._busy_binary = False
        self._install_win = None

        self.v = {}
        self._create_vars()
        self._apply_saved_settings()

        i18n.set_lang(self.v["ui_lang"].get())
        theme.apply(self, self.v["ui_theme"].get())
        self._normalize_localized_values()
        self.title(T("app.title"))

        self._build_ui()
        self._register_traces()
        self._resolve_binaries(startup=True)
        self._update_preview()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_events)

    def _safe_geometry(self, geo):
        """Ignore une géométrie sauvegardée hors écran (ex : second écran débranché
        depuis la dernière fermeture), pour ne pas rouvrir une fenêtre inatteignable."""
        default = "1060x760"
        m = re.match(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", geo or "")
        if not m:
            return default
        w, h, x, y = (int(g) for g in m.groups())
        try:
            import ctypes
            gsm = ctypes.windll.user32.GetSystemMetrics
            vx, vy = gsm(76), gsm(77)              # SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN
            vw, vh = gsm(78), gsm(79)              # SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN
        except Exception:
            vx, vy, vw, vh = 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()
        margin = 60
        if x + w < vx + margin or x > vx + vw - margin or y + h < vy + margin or y > vy + vh - margin:
            return default
        return geo

    # ------------------------------------------------------------------ vars
    def _create_vars(self):
        defaults = {
            "ui_lang": "auto",
            "ui_theme": "auto",
            # Téléchargement
            "dest_dir": os.path.join(os.path.expanduser("~"), "Downloads"),
            "preset": "preset.1080",
            # Format
            "mode": "video",
            "max_res": "1080",
            "container": "mp4",
            "vcodec": "auto",
            "recode": False,
            "audio_format": "mp3",
            "audio_quality": "",     # normalisé vers T("aq.best") au démarrage
            "custom_format": "",
            # Sous-titres
            "write_subs": False,
            "auto_subs": False,
            "all_subs": False,
            "sub_langs": "fr,en",
            "convert_subs": "srt",
            "embed_subs": False,
            # Playlist
            "playlist_mode": "single",
            "playlist_items": "",
            "date_after": "",
            "date_before": "",
            "max_downloads": "",
            "use_archive": False,
            "archive_path": os.path.join(self.app_dir, "archive.txt"),
            "ignore_errors": True,
            "max_filesize": "",
            # Fichiers et métadonnées
            "output_template": "%(title)s.%(ext)s",
            "restrict_filenames": False,
            "no_mtime": True,
            "embed_thumbnail": False,
            "write_thumbnail": False,
            "embed_metadata": True,
            "embed_chapters": True,
            "write_description": False,
            "write_infojson": False,
            "split_chapters": False,
            "sb_mode": "non",
            "sb_cats": "sponsor",
            # Réseau
            "limit_rate": "",
            "retries": "10",
            "concurrent_fragments": "1",
            "sleep_interval": "",
            "proxy": "",
            "cookies_browser": "",   # normalisé vers T("cb.none")
            "cookies_file": "",
            "username": "",
            "password": "",
            "force_ipv4": False,
            "geo_bypass": False,
            # Avancé
            "sections": "",
            "force_keyframes": True,
            "custom_args": "",
            "simulate": False,
            "verbose": False,
            "max_concurrent": "1",
            "ytdlp_path": "",
            "ffmpeg_path": "",
            "autoscroll_log": True,
        }
        for name, value in defaults.items():
            if isinstance(value, bool):
                self.v[name] = tk.BooleanVar(value=value)
            else:
                self.v[name] = tk.StringVar(value=value)

    def _apply_saved_settings(self):
        for name, value in self.settings.items():
            if name.startswith("_") or name == "password":
                continue
            var = self.v.get(name)
            if var is None:
                continue
            try:
                var.set(value)
            except Exception:
                pass

    def _normalize_localized_values(self):
        """Ramène les libellés localisés des listes vers ceux de la langue courante."""
        v = self.v
        if not any(c.isdigit() for c in v["max_res"].get()):
            v["max_res"].set(T("res.best"))
        if not any(c.isdigit() for c in v["audio_quality"].get()):
            v["audio_quality"].set(T("aq.best"))
        if v["audio_format"].get().strip().lower() not in AUDIO_FORMATS:
            v["audio_format"].set(T("af.original"))
        if v["convert_subs"].get().strip().lower() not in SUB_FORMATS:
            v["convert_subs"].set(T("cv.no"))
        cb = v["cookies_browser"].get().strip()
        if not cb or cb.startswith("("):
            v["cookies_browser"].set(T("cb.none"))
        if v["preset"].get() not in PRESET_KEYS:
            v["preset"].set("preset.1080")
        if v["ui_theme"].get() not in THEME_CODES:
            v["ui_theme"].set("auto")

    def collect_cfg(self):
        return {name: var.get() for name, var in self.v.items()}

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        style = ttk.Style(self)
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("AppTitle.TLabel", font=("Segoe UI", 13, "bold"))

        self._build_topbar()

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(6, 0))

        self.tab_dl = ttk.Frame(self.nb)
        self.nb.add(self.tab_dl, text=" %s " % T("tab.download"))
        self._build_tab_download(self.tab_dl)

        for builder, label in (
            (self._build_tab_format, T("tab.format")),
            (self._build_tab_subs, T("tab.subs")),
            (self._build_tab_playlist, T("tab.playlist")),
            (self._build_tab_files, T("tab.files")),
            (self._build_tab_network, T("tab.network")),
            (self._build_tab_advanced, T("tab.advanced")),
        ):
            sf = ScrollableFrame(self.nb)
            self.nb.add(sf, text=" %s " % label)
            builder(sf.inner)

        self.tab_log = ttk.Frame(self.nb)
        self.nb.add(self.tab_log, text=" %s " % T("tab.log"))
        self._build_tab_log(self.tab_log)

        # Barre d'état
        bar = ttk.Frame(self)
        bar.pack(fill="x", side="bottom")
        ttk.Separator(bar).pack(fill="x")
        inner = ttk.Frame(bar, padding=(8, 3))
        inner.pack(fill="x")
        self.status_left = ttk.Label(inner, text=T("msg.init"))
        self.status_left.pack(side="left")
        self.status_right = ttk.Label(inner, text="")
        self.status_right.pack(side="right")

    def _build_topbar(self):
        top = ttk.Frame(self, padding=(12, 8, 12, 0))
        top.pack(fill="x", side="top")
        ttk.Label(top, text="YTDL Interface", style="AppTitle.TLabel").pack(side="left")
        ttk.Label(top, text="v%s" % __version__, foreground=theme.PAL["muted"]).pack(
            side="left", padx=(5, 0), pady=(5, 0))
        ttk.Label(top, text="yt-dlp", foreground=theme.PAL["muted"]).pack(side="left", padx=(10, 0), pady=(4, 0))

        # côté droit : langue puis thème (pack en ordre inverse)
        self._lang_codes = ["auto"] + [code for code, _ in i18n.LANGS]
        lang_values = [T("lang.auto")] + [name for _, name in i18n.LANGS]
        self.lang_cb = ttk.Combobox(top, state="readonly", width=14, values=lang_values)
        try:
            self.lang_cb.current(self._lang_codes.index(self.v["ui_lang"].get()))
        except ValueError:
            self.lang_cb.current(0)
        self.lang_cb.pack(side="right")
        self.lang_cb.bind("<<ComboboxSelected>>", self._on_lang_selected)
        ttk.Label(top, text=T("top.language")).pack(side="right", padx=(0, 6))

        theme_values = [T("theme.auto"), T("theme.light"), T("theme.dark")]
        self.theme_cb = ttk.Combobox(top, state="readonly", width=13, values=theme_values)
        try:
            self.theme_cb.current(THEME_CODES.index(self.v["ui_theme"].get()))
        except ValueError:
            self.theme_cb.current(0)
        self.theme_cb.pack(side="right", padx=(0, 18))
        self.theme_cb.bind("<<ComboboxSelected>>", self._on_theme_selected)
        ttk.Label(top, text=T("top.theme")).pack(side="right", padx=(0, 6))

    def _on_lang_selected(self, _event=None):
        code = self._lang_codes[self.lang_cb.current()]
        self.v["ui_lang"].set(code)
        i18n.set_lang(code)
        self.after_idle(self._rebuild_ui)

    def _on_theme_selected(self, _event=None):
        self.v["ui_theme"].set(THEME_CODES[self.theme_cb.current()])
        self.after_idle(self._rebuild_ui)

    def _rebuild_ui(self):
        """Reconstruit toute l'interface (changement de langue ou de thème)."""
        log_content = ""
        try:
            log_content = self.log_text.get("1.0", "end").rstrip()
        except Exception:
            pass
        active_tab = 0
        try:
            active_tab = self.nb.index("current")
        except Exception:
            pass
        for w in list(self.winfo_children()):
            if isinstance(w, tk.Toplevel):
                continue
            w.destroy()
        theme.apply(self, self.v["ui_theme"].get())
        self._normalize_localized_values()
        self.title(T("app.title"))
        self._build_ui()
        try:
            self.nb.select(active_tab)
        except Exception:
            pass
        if log_content:
            self._append_log([log_content])
        self.job_rows = {}
        for jid in self.engine.order:
            if jid in self.engine.jobs:
                iid = self.tree.insert("", "end", values=("", "", "", "", ""))
                self.job_rows[jid] = iid
                self._refresh_row(jid)
        self._resolve_binaries()
        self._update_preview()

    # ---- petits assistants de construction
    def _section(self, parent, text, help_text=None):
        lf = ttk.LabelFrame(parent, text=text, padding=(6, 4))
        lf.pack(fill="x", padx=8, pady=(8, 2))
        if help_text:
            lbl = ttk.Label(lf, text=help_text, foreground=theme.PAL["muted"],
                            wraplength=780, justify="left")
            lbl.pack(anchor="w", padx=4, pady=(0, 4))
        return lf

    def _check(self, parent, text, name, tip=None):
        cb = ttk.Checkbutton(parent, text=text, variable=self.v[name])
        cb.pack(anchor="w", padx=6, pady=2)
        if tip:
            Tooltip(cb, tip)
        return cb

    def _row(self, parent, label, name=None, tip=None, browse=None, width=None,
             secret=False, label_width=34):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=6, pady=3)
        lbl = ttk.Label(row, text=label, width=label_width, anchor="w")
        lbl.pack(side="left")
        widget = None
        if name is not None:
            widget = ttk.Entry(row, textvariable=self.v[name], show="*" if secret else "")
            if width:
                widget.configure(width=width)
                widget.pack(side="left")
            else:
                widget.pack(side="left", fill="x", expand=True)
            if browse == "file":
                ttk.Button(row, text=T("dl.browse"), command=lambda n=name: self._browse_file(n)).pack(side="left", padx=(4, 0))
            elif browse == "dir":
                ttk.Button(row, text=T("dl.browse"), command=lambda n=name: self._browse_dir(n)).pack(side="left", padx=(4, 0))
        if tip:
            Tooltip(lbl, tip)
            if widget is not None:
                Tooltip(widget, tip)
        return row, widget

    def _combo(self, parent, label, name, values, tip=None, width=22, label_width=34):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=6, pady=3)
        lbl = ttk.Label(row, text=label, width=label_width, anchor="w")
        lbl.pack(side="left")
        cb = ttk.Combobox(row, textvariable=self.v[name], values=values,
                          state="readonly", width=width)
        cb.pack(side="left")
        if tip:
            Tooltip(lbl, tip)
            Tooltip(cb, tip)
        return cb

    def _browse_file(self, name):
        path = filedialog.askopenfilename(parent=self)
        if path:
            self.v[name].set(path)

    def _browse_dir(self, name):
        path = filedialog.askdirectory(parent=self, initialdir=self.v[name].get() or None)
        if path:
            self.v[name].set(path)

    def _make_text(self, parent, **kwargs):
        opts = dict(
            background=theme.PAL["text_bg"], foreground=theme.PAL["text_fg"],
            insertbackground=theme.PAL["text_fg"], relief="flat",
            highlightthickness=1, highlightbackground=theme.PAL["border"],
            highlightcolor=theme.PAL["border"],
        )
        opts.update(kwargs)
        return tk.Text(parent, **opts)

    # ------------------------------------------------- onglet Téléchargement
    def _build_tab_download(self, parent):
        top = ttk.LabelFrame(parent, text=T("dl.links"), padding=4)
        top.pack(fill="x", padx=8, pady=(8, 2))
        self.url_text = self._make_text(top, height=3, font=("Segoe UI", 10), undo=True)
        self.url_text.pack(fill="x", padx=4, pady=2)
        Tooltip(self.url_text, T("dl.links.tip"))
        btns = ttk.Frame(top)
        btns.pack(fill="x", padx=4, pady=(4, 2))
        ttk.Button(btns, text=T("dl.paste"), command=self._paste_url).pack(side="left")
        ttk.Button(btns, text=T("dl.clear"), command=lambda: self.url_text.delete("1.0", "end")).pack(side="left", padx=4)
        b_ana = ttk.Button(btns, text=T("dl.analyze"), command=self._analyze)
        b_ana.pack(side="left", padx=4)
        Tooltip(b_ana, T("dl.analyze.tip"))
        ttk.Label(btns, text=T("dl.preset")).pack(side="left", padx=(24, 4))
        self.preset_cb = ttk.Combobox(btns, state="readonly", width=30,
                                      values=[T(k) for k in PRESET_KEYS])
        key = self.v["preset"].get()
        if key in PRESET_KEYS:
            self.preset_cb.current(PRESET_KEYS.index(key))
        self.preset_cb.pack(side="left")
        self.preset_cb.bind("<<ComboboxSelected>>", self._apply_preset)
        Tooltip(self.preset_cb, T("dl.preset.tip"))

        dest = ttk.Frame(parent)
        dest.pack(fill="x", padx=8, pady=4)
        ttk.Label(dest, text=T("dl.dest")).pack(side="left")
        ttk.Entry(dest, textvariable=self.v["dest_dir"]).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(dest, text=T("dl.browse"), command=lambda: self._browse_dir("dest_dir")).pack(side="left")
        ttk.Button(dest, text=T("dl.open"), command=self._open_dest).pack(side="left", padx=(4, 0))

        actions = ttk.Frame(parent)
        actions.pack(fill="x", padx=8, pady=6)
        ttk.Button(actions, text=T("dl.download"), style="Accent.TButton",
                   command=self._download_now).pack(side="left")
        b_add = ttk.Button(actions, text=T("dl.addqueue"), command=lambda: self._add_urls(start=False))
        b_add.pack(side="left", padx=6)
        Tooltip(b_add, T("dl.addqueue.tip"))

        qf = ttk.LabelFrame(parent, text=T("dl.queue"), padding=4)
        qf.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        cols = ("title", "status", "progress", "speed", "eta")
        self.tree = ttk.Treeview(qf, columns=cols, show="headings", selectmode="extended")
        headings = (("title", T("col.file"), 420), ("status", T("col.status"), 150),
                    ("progress", T("col.progress"), 90), ("speed", T("col.speed"), 100),
                    ("eta", T("col.eta"), 80))
        for col, text, width in headings:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w" if col in ("title", "status") else "center")
        vsb = ttk.Scrollbar(qf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._open_dest())
        self.tree.bind("<Button-3>", self._tree_menu)

        qbtns = ttk.Frame(parent)
        qbtns.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(qbtns, text=T("dl.start"), command=self._start_queue).pack(side="left")
        ttk.Button(qbtns, text=T("dl.cancelsel"), command=self._cancel_selected).pack(side="left", padx=4)
        ttk.Button(qbtns, text=T("dl.cancelall"), command=self._cancel_all).pack(side="left", padx=4)
        ttk.Button(qbtns, text=T("dl.removesel"), command=self._remove_selected).pack(side="left", padx=4)
        ttk.Button(qbtns, text=T("dl.removedone"), command=self._clear_finished).pack(side="left", padx=4)

    # ------------------------------------------------- onglet Format
    def _build_tab_format(self, parent):
        ttk.Label(parent, text=T("fmt.intro"), foreground=theme.PAL["muted"]).pack(anchor="w", padx=10, pady=(8, 0))

        s1 = self._section(parent, T("fmt.type"))
        for key, value in (("fmt.video", "video"), ("fmt.audio", "audio"),
                           ("fmt.videoonly", "video_only")):
            rb = ttk.Radiobutton(s1, text=T(key), value=value, variable=self.v["mode"])
            rb.pack(anchor="w", padx=6, pady=2)
            Tooltip(rb, T(key + ".tip"))

        s2 = self._section(parent, T("fmt.quality"))
        self._combo(s2, T("fmt.res"), "max_res",
                    (T("res.best"), "2160", "1440", "1080", "720", "480", "360"),
                    tip=T("fmt.res.tip"))
        self._combo(s2, T("fmt.container"), "container",
                    ("auto", "mp4", "mkv", "webm"), tip=T("fmt.container.tip"))
        self._combo(s2, T("fmt.vcodec"), "vcodec",
                    ("auto", "h264", "h265", "vp9", "av1"), tip=T("fmt.vcodec.tip"))
        self._check(s2, T("fmt.recode"), "recode", tip=T("fmt.recode.tip"))

        s3 = self._section(parent, T("fmt.audiosec"))
        self._combo(s3, T("fmt.aformat"), "audio_format",
                    (T("af.original"),) + AUDIO_FORMATS, tip=T("fmt.aformat.tip"))
        self._combo(s3, T("fmt.aquality"), "audio_quality",
                    (T("aq.best"), "320K", "256K", "192K", "128K", "96K"),
                    tip=T("fmt.aquality.tip"))

        s4 = self._section(parent, T("fmt.expert"))
        self._row(s4, T("fmt.custom"), "custom_format", tip=T("fmt.custom.tip"))

    # ------------------------------------------------- onglet Sous-titres
    def _build_tab_subs(self, parent):
        s1 = self._section(parent, T("sub.dl"))
        self._check(s1, T("sub.write"), "write_subs", tip=T("sub.write.tip"))
        self._check(s1, T("sub.auto"), "auto_subs", tip=T("sub.auto.tip"))
        self._check(s1, T("sub.all"), "all_subs", tip=T("sub.all.tip"))
        self._row(s1, T("sub.langs"), "sub_langs", width=30, tip=T("sub.langs.tip"))

        s2 = self._section(parent, T("sub.proc"))
        self._combo(s2, T("sub.convert"), "convert_subs",
                    (T("cv.no"),) + SUB_FORMATS, tip=T("sub.convert.tip"))
        self._check(s2, T("sub.embed"), "embed_subs", tip=T("sub.embed.tip"))

    # ------------------------------------------------- onglet Playlist
    def _build_tab_playlist(self, parent):
        s1 = self._section(parent, T("pl.behavior"))
        for key, value in (("pl.single", "single"), ("pl.full", "full")):
            rb = ttk.Radiobutton(s1, text=T(key), value=value, variable=self.v["playlist_mode"])
            rb.pack(anchor="w", padx=6, pady=2)
            Tooltip(rb, T(key + ".tip"))
        self._row(s1, T("pl.items"), "playlist_items", width=30, tip=T("pl.items.tip"))

        s2 = self._section(parent, T("pl.filters"))
        self._row(s2, T("pl.after"), "date_after", width=30, tip=T("pl.after.tip"))
        self._row(s2, T("pl.before"), "date_before", width=30, tip=T("pl.before.tip"))
        self._row(s2, T("pl.maxn"), "max_downloads", width=30, tip=T("pl.maxn.tip"))
        self._row(s2, T("pl.maxsize"), "max_filesize", width=30, tip=T("pl.maxsize.tip"))

        s3 = self._section(parent, T("pl.history"))
        self._check(s3, T("pl.archive"), "use_archive", tip=T("pl.archive.tip"))
        self._row(s3, T("pl.archivefile"), "archive_path", browse="file", tip=T("pl.archivefile.tip"))
        self._check(s3, T("pl.ignore"), "ignore_errors", tip=T("pl.ignore.tip"))

    # ------------------------------------------------- onglet Fichiers
    def _build_tab_files(self, parent):
        s1 = self._section(parent, T("fi.names"))
        row = ttk.Frame(s1)
        row.pack(fill="x", padx=6, pady=3)
        ttk.Label(row, text=T("fi.template"), width=34, anchor="w").pack(side="left")
        tmpl_cb = ttk.Combobox(row, textvariable=self.v["output_template"], width=52, values=(
            "%(title)s.%(ext)s",
            "%(title)s [%(id)s].%(ext)s",
            "%(uploader)s - %(title)s.%(ext)s",
            "%(uploader)s/%(title)s.%(ext)s",
            "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s",
            "%(upload_date)s - %(title)s.%(ext)s",
        ))
        tmpl_cb.pack(side="left", fill="x", expand=True)
        Tooltip(tmpl_cb, T("fi.template.tip"))
        self._check(s1, T("fi.restrict"), "restrict_filenames", tip=T("fi.restrict.tip"))
        self._check(s1, T("fi.mtime"), "no_mtime", tip=T("fi.mtime.tip"))

        s2 = self._section(parent, T("fi.meta"))
        self._check(s2, T("fi.embedmeta"), "embed_metadata", tip=T("fi.embedmeta.tip"))
        self._check(s2, T("fi.embedchapters"), "embed_chapters", tip=T("fi.embedchapters.tip"))
        self._check(s2, T("fi.embedthumb"), "embed_thumbnail", tip=T("fi.embedthumb.tip"))
        self._check(s2, T("fi.writethumb"), "write_thumbnail")
        self._check(s2, T("fi.writedesc"), "write_description")
        self._check(s2, T("fi.writejson"), "write_infojson", tip=T("fi.writejson.tip"))

        s3 = self._section(parent, T("fi.sponsor"))
        self._check(s3, T("fi.split"), "split_chapters", tip=T("fi.split.tip"))
        for key, value in (("sb.none", "non"), ("sb.mark", "mark"), ("sb.remove", "remove")):
            rb = ttk.Radiobutton(s3, text=T(key), value=value, variable=self.v["sb_mode"])
            rb.pack(anchor="w", padx=6, pady=2)
            if key != "sb.none":
                Tooltip(rb, T(key + ".tip"))
        self._row(s3, T("sb.cats"), "sb_cats", width=40, tip=T("sb.cats.tip"))

    # ------------------------------------------------- onglet Réseau
    def _build_tab_network(self, parent):
        s1 = self._section(parent, T("net.speed"))
        self._row(s1, T("net.limit"), "limit_rate", width=30, tip=T("net.limit.tip"))
        self._row(s1, T("net.retries"), "retries", width=30, tip=T("net.retries.tip"))
        self._row(s1, T("net.fragments"), "concurrent_fragments", width=30, tip=T("net.fragments.tip"))
        self._row(s1, T("net.sleep"), "sleep_interval", width=30, tip=T("net.sleep.tip"))

        s2 = self._section(parent, T("net.conn"))
        self._row(s2, T("net.proxy"), "proxy", tip=T("net.proxy.tip"))
        self._check(s2, T("net.ipv4"), "force_ipv4", tip=T("net.ipv4.tip"))
        self._check(s2, T("net.geo"), "geo_bypass", tip=T("net.geo.tip"))

        s3 = self._section(parent, T("net.accounts"), help_text=T("net.accounts.help"))
        self._combo(s3, T("net.cookiesbrowser"), "cookies_browser",
                    (T("cb.none"), "firefox", "chrome", "edge", "brave", "opera", "vivaldi", "chromium"),
                    tip=T("net.cookiesbrowser.tip"))
        self._row(s3, T("net.cookiesfile"), "cookies_file", browse="file", tip=T("net.cookiesfile.tip"))
        self._row(s3, T("net.user"), "username", width=30, tip=T("net.user.tip"))
        self._row(s3, T("net.pass"), "password", width=30, secret=True, tip=T("net.pass.tip"))

    # ------------------------------------------------- onglet Avancé
    def _build_tab_advanced(self, parent):
        s0 = self._section(parent, T("adv.sections"))
        self._row(s0, T("adv.sectionsfield"), "sections", width=40, tip=T("adv.sectionsfield.tip"))
        self._check(s0, T("adv.keyframes"), "force_keyframes", tip=T("adv.keyframes.tip"))

        s1 = self._section(parent, T("adv.queue"))
        row = ttk.Frame(s1)
        row.pack(fill="x", padx=6, pady=3)
        ttk.Label(row, text=T("adv.concurrent"), width=34, anchor="w").pack(side="left")
        sp = ttk.Spinbox(row, from_=1, to=4, textvariable=self.v["max_concurrent"], width=5, state="readonly")
        sp.pack(side="left")
        Tooltip(sp, T("adv.concurrent.tip"))

        s2 = self._section(parent, T("adv.binaries"))
        self._row(s2, T("adv.ytdlppath"), "ytdlp_path", browse="file", tip=T("adv.ytdlppath.tip"))
        self._row(s2, T("adv.ffmpegpath"), "ffmpeg_path", browse="file", tip=T("adv.ffmpegpath.tip"))
        brow = ttk.Frame(s2)
        brow.pack(fill="x", padx=6, pady=4)
        ttk.Button(brow, text=T("adv.update"), command=self._update_ytdlp).pack(side="left")
        ttk.Button(brow, text=T("adv.dlbin"), command=lambda: self._open_install_dialog(["ytdlp"])).pack(side="left", padx=4)
        ttk.Button(brow, text=T("adv.dlffmpeg"), command=lambda: self._open_install_dialog(["ffmpeg"])).pack(side="left", padx=4)

        s3 = self._section(parent, T("adv.debug"))
        self._check(s3, T("adv.simulate"), "simulate")
        self._check(s3, T("adv.verbose"), "verbose", tip=T("adv.verbose.tip"))
        self._row(s3, T("adv.custom"), "custom_args", tip=T("adv.custom.tip"))

        s4 = self._section(parent, T("adv.cmd"), help_text=T("adv.cmd.help"))
        self.preview_text = self._make_text(s4, height=5, wrap="word", font=("Consolas", 9),
                                            state="disabled",
                                            background=theme.PAL["preview_bg"])
        self.preview_text.pack(fill="x", padx=6, pady=2)
        ttk.Button(s4, text=T("adv.copy"), command=self._copy_preview).pack(anchor="w", padx=6, pady=(2, 4))

    # ------------------------------------------------- onglet Journal
    def _build_tab_log(self, parent):
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Button(bar, text=T("log.clear"), command=self._clear_log).pack(side="left")
        ttk.Checkbutton(bar, text=T("log.autoscroll"), variable=self.v["autoscroll_log"]).pack(side="left", padx=12)
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.log_text = self._make_text(frame, wrap="none", font=("Consolas", 9), state="disabled")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

    # ------------------------------------------------------------- actions
    def _paste_url(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        if text:
            self.url_text.insert("insert", text.strip() + "\n")

    def _get_urls(self):
        raw = self.url_text.get("1.0", "end")
        return [u for u in raw.split() if u.strip()]

    def _resolve_paths(self):
        ytdlp = find_ytdlp(self.v["ytdlp_path"].get())
        ffmpeg = find_ffmpeg(self.v["ffmpeg_path"].get())
        return ytdlp, ffmpeg

    def _download_now(self):
        self._add_urls(start=True)

    def _add_urls(self, start):
        urls = self._get_urls()
        if not urls:
            messagebox.showinfo("YTDL Interface", T("msg.pastefirst"), parent=self)
            return
        ytdlp, ffmpeg = self._resolve_paths()
        if not ytdlp:
            self._open_install_dialog(["ytdlp"])
            return
        cfg = self.collect_cfg()
        if not ffmpeg and cmdmod.needs_ffmpeg(cfg):
            if not messagebox.askyesno("YTDL Interface", T("msg.ffmpegneeded"), parent=self):
                self._open_install_dialog(["ffmpeg"])
                return
        dest = cfg.get("dest_dir", "").strip()
        if dest:
            try:
                os.makedirs(dest, exist_ok=True)
            except OSError:
                messagebox.showerror("YTDL Interface", "%s\n%s" % (T("msg.nodest"), dest), parent=self)
                return
        pending_urls = {j.url for j in self.engine.jobs.values() if j.status not in eng.FINAL_STATES}
        added, skipped = 0, 0
        for url in urls:
            if url in pending_urls:
                skipped += 1
                continue
            cmd = cmdmod.build_command(cfg, url, ytdlp, ffmpeg)
            job = self.engine.add_job(url, cmd, dest)
            iid = self.tree.insert("", "end", values=(job.title, T("st.pending"), "", "", ""))
            self.job_rows[job.id] = iid
            pending_urls.add(url)
            added += 1
        self.url_text.delete("1.0", "end")
        if skipped:
            self.status_right.configure(text=T("msg.duplicates_skipped").format(n=skipped))
        if start and added:
            self._start_queue()

    def _start_queue(self):
        try:
            n = int(self.v["max_concurrent"].get())
        except ValueError:
            n = 1
        self.engine.start(n)
        self.status_right.configure(text=T("msg.queueactive"))

    def _selected_job_ids(self):
        rev = {iid: jid for jid, iid in self.job_rows.items()}
        return [rev[iid] for iid in self.tree.selection() if iid in rev]

    def _cancel_selected(self):
        for jid in self._selected_job_ids():
            self.engine.cancel(jid)

    def _cancel_all(self):
        self.engine.cancel_all()

    def _remove_selected(self):
        for jid in self._selected_job_ids():
            if self.engine.remove(jid):
                iid = self.job_rows.pop(jid, None)
                if iid:
                    self.tree.delete(iid)

    def _clear_finished(self):
        for jid, iid in list(self.job_rows.items()):
            job = self.engine.jobs.get(jid)
            if job is None or job.status in eng.FINAL_STATES:
                if self.engine.remove(jid) or job is None:
                    self.job_rows.pop(jid, None)
                    try:
                        self.tree.delete(iid)
                    except tk.TclError:
                        pass

    def _tree_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label=T("menu.retry"), command=self._retry_selected)
            menu.add_command(label=T("menu.cancel"), command=self._cancel_selected)
            menu.add_command(label=T("menu.remove"), command=self._remove_selected)
            menu.add_separator()
            menu.add_command(label=T("menu.copylink"), command=self._copy_selected_url)
            menu.add_command(label=T("menu.openfolder"), command=self._open_dest)
            menu.add_separator()
            menu.add_command(label=T("menu.moveup"), command=lambda: self._move_selected(-1))
            menu.add_command(label=T("menu.movedown"), command=lambda: self._move_selected(1))
            menu.tk_popup(event.x_root, event.y_root)

    def _move_selected(self, offset):
        ids = self._selected_job_ids()
        if len(ids) != 1:
            return
        jid = ids[0]
        new_index = self.engine.move(jid, offset)
        if new_index is None:
            return
        iid = self.job_rows.get(jid)
        if iid is not None:
            self.tree.move(iid, "", new_index)

    def _retry_selected(self):
        ytdlp, ffmpeg = self._resolve_paths()
        if not ytdlp:
            self._open_install_dialog(["ytdlp"])
            return
        cfg = self.collect_cfg()
        for jid in self._selected_job_ids():
            job = self.engine.jobs.get(jid)
            if job is None or job.status not in eng.FINAL_STATES:
                continue
            url = job.url
            if self.engine.remove(jid):
                iid = self.job_rows.pop(jid, None)
                if iid:
                    self.tree.delete(iid)
            cmd = cmdmod.build_command(cfg, url, ytdlp, ffmpeg)
            new_job = self.engine.add_job(url, cmd, cfg.get("dest_dir", ""))
            new_iid = self.tree.insert("", "end", values=(new_job.title, T("st.pending"), "", "", ""))
            self.job_rows[new_job.id] = new_iid

    def _copy_selected_url(self):
        ids = self._selected_job_ids()
        urls = [self.engine.jobs[j].url for j in ids if j in self.engine.jobs]
        if urls:
            self.clipboard_clear()
            self.clipboard_append("\n".join(urls))

    def _open_dest(self):
        dest = self.v["dest_dir"].get().strip()
        if dest and os.path.isdir(dest):
            os.startfile(dest)
        else:
            messagebox.showinfo("YTDL Interface", T("msg.nodestdir"), parent=self)

    def _apply_preset(self, _event=None):
        idx = self.preset_cb.current()
        if idx < 0:
            return
        key = PRESET_KEYS[idx]
        self.v["preset"].set(key)
        preset = PRESETS[key]
        for name, value in preset.items():
            if name == "_res":
                self.v["max_res"].set(T("res.best"))
            elif name == "_aq":
                self.v["audio_quality"].set(T("aq.best"))
            else:
                var = self.v.get(name)
                if var is not None:
                    var.set(value)
        self.status_right.configure(text="%s%s" % (T("msg.presetapplied"), T(key)))

    # ---------------------------------------------------------- préviz cmd
    def _register_traces(self):
        for var in self.v.values():
            var.trace_add("write", self._schedule_preview)

    def _schedule_preview(self, *_args):
        if self._preview_after:
            try:
                self.after_cancel(self._preview_after)
            except Exception:
                pass
        self._preview_after = self.after(250, self._update_preview)

    def _update_preview(self):
        self._preview_after = None
        ytdlp, ffmpeg = self._resolve_paths()
        cfg = self.collect_cfg()
        try:
            cmd = cmdmod.build_command(cfg, "<URL>", ytdlp or "yt-dlp", ffmpeg)
            text = subprocess.list2cmdline(cmd)
        except Exception as exc:
            text = "%s %s" % (T("msg.cmderror"), exc)
        try:
            self.preview_text.configure(state="normal")
            self.preview_text.delete("1.0", "end")
            self.preview_text.insert("1.0", text)
            self.preview_text.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass

    def _copy_preview(self):
        self.clipboard_clear()
        self.clipboard_append(self.preview_text.get("1.0", "end").strip())
        self.status_right.configure(text=T("msg.copied"))

    # ---------------------------------------------------------- binaires
    def _resolve_binaries(self, startup=False):
        ytdlp, ffmpeg = self._resolve_paths()
        if startup and (not ytdlp or not ffmpeg):
            self.after(400, lambda: self._open_install_dialog())
        if not ytdlp:
            self.status_left.configure(text=T("msg.ytdlpneeded"))
            return
        ff = T("msg.ffok") if ffmpeg else T("msg.ffmissing")
        self.status_left.configure(text="%s | %s" % (T("msg.checking"), ff))

        def worker():
            version = get_version(ytdlp)
            self.ui_queue.put(("version", version, ff))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------- installation
    def _open_install_dialog(self, components=None):
        try:
            if self._install_win is not None and self._install_win.winfo_exists():
                self._install_win.lift()
                return
        except tk.TclError:
            pass
        ytdlp, ffmpeg = self._resolve_paths()
        present = {"ytdlp": bool(ytdlp), "ffmpeg": bool(ffmpeg)}
        if components is None:
            components = [c for c in ("ytdlp", "ffmpeg") if not present[c]]
        else:
            components = [c for c in components if not present.get(c)]
        if not components:
            messagebox.showinfo("YTDL Interface", T("inst.all_installed"), parent=self)
            return

        win = tk.Toplevel(self)
        win.title(T("inst.title"))
        win.resizable(False, False)
        win.transient(self)
        theme.style_toplevel(win)
        self._install_win = win

        body = ttk.Frame(win, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=T("inst.needed_intro"), font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 10))

        descs = {"ytdlp": T("inst.ytdlp_desc"), "ffmpeg": T("inst.ffmpeg_desc")}
        names = {"ytdlp": "yt-dlp", "ffmpeg": "ffmpeg"}
        rows = {}
        for comp in components:
            row = ttk.Frame(body)
            row.pack(fill="x", pady=6)
            top = ttk.Frame(row)
            top.pack(fill="x")
            ttk.Label(top, text=names[comp], font=("Segoe UI", 10, "bold")).pack(side="left")
            status_var = tk.StringVar(value=T("inst.status_waiting"))
            ttk.Label(top, textvariable=status_var, foreground=theme.PAL["muted"]).pack(side="right")
            ttk.Label(row, text=descs[comp], foreground=theme.PAL["muted"]).pack(anchor="w")
            pbar = ttk.Progressbar(row, orient="horizontal", mode="determinate", maximum=100, length=380)
            pbar.pack(fill="x", pady=(4, 0))
            rows[comp] = (pbar, status_var)
        win._rows = rows

        summary_var = tk.StringVar(value="")
        ttk.Label(body, textvariable=summary_var, wraplength=380, justify="left").pack(
            anchor="w", pady=(8, 0), fill="x")
        win._summary_var = summary_var

        def close_dialog():
            self._install_win = None
            win.destroy()

        btn_frame = ttk.Frame(body)
        btn_frame.pack(fill="x", pady=(14, 0))
        cancel_btn = ttk.Button(btn_frame, text=T("inst.btn_later"), command=close_dialog)
        cancel_btn.pack(side="right")
        install_btn = ttk.Button(btn_frame, text=T("inst.btn_install"), style="Accent.TButton",
                                 command=lambda: self._start_install(win, components))
        install_btn.pack(side="right", padx=(0, 8))
        win._install_btn = install_btn
        win._cancel_btn = cancel_btn
        win.protocol("WM_DELETE_WINDOW", close_dialog)

    def _start_install(self, win, components):
        if self._busy_binary:
            return
        self._busy_binary = True
        try:
            win._install_btn.configure(state="disabled")
            win._cancel_btn.configure(state="disabled")
            for comp in components:
                _, status_var = win._rows[comp]
                status_var.set(T("inst.status_downloading"))
        except (tk.TclError, AttributeError):
            pass
        threading.Thread(target=self._install_worker, args=(win, components), daemon=True).start()

    def _install_worker(self, win, components):
        results = {}
        for comp in components:
            try:
                if comp == "ytdlp":
                    download_ytdlp(lambda pct: self.ui_queue.put(("install_progress", win, comp, pct)))
                else:
                    download_ffmpeg(
                        progress_cb=lambda pct: self.ui_queue.put(("install_progress", win, comp, pct)),
                        status_cb=lambda phase: self.ui_queue.put(("install_status", win, comp, phase)),
                    )
                results[comp] = None
            except Exception as exc:
                results[comp] = str(exc)
            self.ui_queue.put(("install_step_done", win, comp, results[comp]))
        self.ui_queue.put(("install_all_done", win, results))

    def _install_row(self, win, comp):
        try:
            if not win.winfo_exists():
                return None
        except tk.TclError:
            return None
        return win._rows.get(comp)

    def _install_set_status(self, win, comp, phase):
        w = self._install_row(win, comp)
        if not w:
            return
        try:
            w[1].set(T("inst.status_%s" % phase))
        except tk.TclError:
            pass

    def _install_set_progress(self, win, comp, pct):
        w = self._install_row(win, comp)
        if not w:
            return
        try:
            w[0].configure(value=pct)
        except tk.TclError:
            pass

    def _install_finish_row(self, win, comp, error):
        w = self._install_row(win, comp)
        if not w:
            return
        pbar, status_var = w
        try:
            if error:
                status_var.set(T("inst.status_error"))
                pbar.configure(value=0)
            else:
                status_var.set(T("inst.status_done"))
                pbar.configure(value=100)
        except tk.TclError:
            pass

    def _install_finish_all(self, win, results):
        self._busy_binary = False
        try:
            if not win.winfo_exists():
                self._resolve_binaries()
                self._update_preview()
                return
        except tk.TclError:
            return
        failed = [c for c, err in results.items() if err]

        def close_dialog():
            self._install_win = None
            try:
                win.destroy()
            except tk.TclError:
                pass  # déjà fermée (bouton cliqué avant la fermeture auto programmée)

        try:
            if failed:
                msgs = "; ".join("%s : %s" % (c, results[c]) for c in failed)
                win._summary_var.set("%s\n%s" % (T("inst.some_failed"), msgs[:300]))
            else:
                win._summary_var.set(T("inst.all_done"))
            win._cancel_btn.configure(text=T("inst.btn_close"), state="normal", command=close_dialog)
            win.protocol("WM_DELETE_WINDOW", close_dialog)
            win._install_btn.pack_forget()
            if not failed:
                # Tout a réussi : pas besoin d'un clic, on ferme tout seul après un
                # court délai (le temps de laisser voir le message de succès).
                win.after(1200, close_dialog)
        except tk.TclError:
            pass
        self._resolve_binaries()
        self._update_preview()

    def _update_ytdlp(self):
        ytdlp, _ = self._resolve_paths()
        if not ytdlp:
            self._open_install_dialog(["ytdlp"])
            return
        if self._busy_binary:
            return
        self._busy_binary = True
        self.status_left.configure(text=T("msg.updating"))

        def worker():
            try:
                out = subprocess.run(
                    [ytdlp, "-U"], capture_output=True, text=True, timeout=300,
                    encoding="utf-8", errors="replace", creationflags=CREATE_NO_WINDOW)
                msg = (out.stdout or "") + (out.stderr or "")
            except Exception as exc:
                msg = str(exc)
            self.ui_queue.put(("binupdate", msg.strip()))

        threading.Thread(target=worker, daemon=True).start()

    # ---------------------------------------------------------- analyse
    def _analyze(self):
        urls = self._get_urls()
        if not urls:
            messagebox.showinfo("YTDL Interface", T("msg.analyzefirst"), parent=self)
            return
        ytdlp, _ = self._resolve_paths()
        if not ytdlp:
            self._open_install_dialog(["ytdlp"])
            return
        url = urls[0]
        cfg = self.collect_cfg()

        win = tk.Toplevel(self)
        win.title("%s%s" % (T("an.title"), url))
        win.geometry("960x660")
        win.transient(self)
        theme.style_toplevel(win)
        wait = ttk.Label(win, text=T("an.wait"), font=("Segoe UI", 11))
        wait.pack(pady=40)

        def worker():
            cmd = [ytdlp, "-J", "--no-warnings"]
            if cfg.get("playlist_mode") == "full":
                cmd += ["--yes-playlist", "--flat-playlist"]
            else:
                cmd += ["--no-playlist"]
            cmd += cmdmod.build_network_args(cfg)
            cmd.append(url)
            info, err = None, ""
            try:
                out = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                                     encoding="utf-8", errors="replace",
                                     creationflags=CREATE_NO_WINDOW)
                if out.returncode == 0 and out.stdout.strip():
                    info = jsonmod.loads(out.stdout)
                else:
                    err = (out.stderr or "").strip()[-800:] or T("an.nodata")
            except Exception as exc:
                err = str(exc)
            self.ui_queue.put(("analyze", win, info, err))

        threading.Thread(target=worker, daemon=True).start()

    def _populate_analysis(self, win, info, err):
        try:
            if not win.winfo_exists():
                return
        except tk.TclError:
            return
        for child in win.winfo_children():
            child.destroy()
        if info is None:
            ttk.Label(win, text=T("an.failed"), font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 4))
            txt = self._make_text(win, wrap="word", height=12)
            txt.insert("1.0", err)
            txt.configure(state="disabled")
            txt.pack(fill="both", expand=True, padx=12, pady=4)
            ttk.Button(win, text=T("an.close"), command=win.destroy).pack(pady=8)
            return
        if info.get("_type") == "playlist":
            self._populate_playlist_analysis(win, info)
        else:
            self._populate_video_analysis(win, info)

    def _populate_playlist_analysis(self, win, info):
        head = ttk.Frame(win, padding=10)
        head.pack(fill="x")
        entries = info.get("entries") or []
        ttk.Label(head, text=info.get("title") or T("an.playlist"),
                  font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(head, text=T("an.items").format(
            n=len(entries), u=info.get("uploader") or info.get("channel") or "?")).pack(anchor="w")
        cols = ("n", "title", "dur")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        tree.heading("n", text=T("an.num"))
        tree.heading("title", text=T("an.titlecol"))
        tree.heading("dur", text=T("an.dur"))
        tree.column("n", width=50, anchor="center")
        tree.column("title", width=700)
        tree.column("dur", width=80, anchor="center")
        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
        vsb.pack(side="left", fill="y", pady=(0, 10))
        for i, entry in enumerate(entries, 1):
            if not entry:
                continue
            tree.insert("", "end", values=(i, entry.get("title") or entry.get("url") or "?",
                                           human_duration(entry.get("duration"))))

    def _populate_video_analysis(self, win, info):
        head = ttk.Frame(win, padding=10)
        head.pack(fill="x")
        self._thumb_label = ttk.Label(head)
        self._thumb_label.pack(side="left", padx=(0, 12))
        meta = ttk.Frame(head)
        meta.pack(side="left", fill="x", expand=True)
        ttk.Label(meta, text=info.get("title") or "?", font=("Segoe UI", 12, "bold"),
                  wraplength=620, justify="left").pack(anchor="w")
        details = []
        if info.get("uploader") or info.get("channel"):
            details.append(T("an.channel") + str(info.get("uploader") or info.get("channel")))
        if info.get("duration"):
            details.append(T("an.duration") + human_duration(info["duration"]))
        if info.get("view_count") is not None:
            details.append(T("an.views") + f"{info['view_count']:,}".replace(",", " "))
        date = str(info.get("upload_date") or "")
        if len(date) == 8:
            details.append(T("an.published").format(d="%s/%s/%s" % (date[6:8], date[4:6], date[0:4])))
        for line in details:
            ttk.Label(meta, text=line).pack(anchor="w")
        thumb_url = info.get("thumbnail")
        if thumb_url:
            threading.Thread(target=self._fetch_thumbnail, args=(win, thumb_url), daemon=True).start()

        mid = ttk.LabelFrame(win, text=T("an.formats"), padding=4)
        mid.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        cols = ("id", "ext", "res", "fps", "vcodec", "acodec", "tbr", "size", "note")
        tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="extended", height=12)
        for col, text, width in (
            ("id", T("an.id"), 90), ("ext", T("an.ext"), 55), ("res", T("an.res"), 95),
            ("fps", T("an.fps"), 45), ("vcodec", T("an.vc"), 110), ("acodec", T("an.ac"), 100),
            ("tbr", T("an.tbr"), 70), ("size", T("an.size"), 80), ("note", T("an.note"), 130),
        ):
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(mid, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for f in reversed(info.get("formats") or []):
            size = f.get("filesize") or f.get("filesize_approx")
            tree.insert("", "end", values=(
                f.get("format_id") or "", f.get("ext") or "",
                f.get("resolution") or ("%sx%s" % (f.get("width"), f.get("height"))
                                        if f.get("width") else T("an.audio")),
                f.get("fps") or "", f.get("vcodec") or "", f.get("acodec") or "",
                ("%.0fk" % f["tbr"]) if f.get("tbr") else "",
                human_size(size), f.get("format_note") or "",
            ))
        self._analysis_tree = tree

        foot = ttk.Frame(win, padding=(10, 4))
        foot.pack(fill="x")
        b_use = ttk.Button(foot, text=T("an.use"),
                           command=lambda: self._use_selected_formats(win))
        b_use.pack(side="left")
        Tooltip(b_use, T("an.use.tip"))
        ttk.Button(foot, text=T("an.close"), command=win.destroy).pack(side="right")

    def _fetch_thumbnail(self, win, url):
        _, ffmpeg = self._resolve_paths()
        try:
            tmpdir = tempfile.mkdtemp(prefix="ytdlgui_")
            raw = os.path.join(tmpdir, "thumb_raw")
            png = os.path.join(tmpdir, "thumb.png")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp, open(raw, "wb") as f:
                f.write(resp.read())
            if not ffmpeg:
                return
            subprocess.run([ffmpeg, "-y", "-i", raw, "-vf", "scale=280:-2", png],
                           capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW)
            if os.path.isfile(png):
                self.ui_queue.put(("thumbnail", win, png))
        except Exception:
            pass

    def _use_selected_formats(self, win):
        tree = getattr(self, "_analysis_tree", None)
        if tree is None:
            return
        try:
            sel = tree.selection()
        except tk.TclError:
            return
        if not sel:
            messagebox.showinfo("YTDL Interface", T("msg.selectformat"), parent=win)
            return
        items = [(tree.set(i, "id"), tree.set(i, "vcodec")) for i in sel]
        items.sort(key=lambda x: x[1] in ("", "none"))  # vidéo d'abord, audio ensuite
        fmt = "+".join(fid for fid, _ in items if fid)
        self.v["custom_format"].set(fmt)
        self.status_right.configure(text="%s%s" % (T("msg.customformat"), fmt))
        win.destroy()

    # ---------------------------------------------------------- événements
    def _poll_events(self):
        processed = 0
        log_lines = []
        try:
            while processed < 300:
                event = self.ui_queue.get_nowait()
                processed += 1
                kind = event[0]
                if kind == "log":
                    log_lines.append("[%s] %s" % (event[1], event[2]))
                elif kind in ("status", "progress", "title"):
                    self._refresh_row(event[1])
                    if kind == "status":
                        self._update_queue_status()
                elif kind == "done":
                    self._refresh_row(event[1])
                    self._maybe_queue_done()
                elif kind == "version":
                    self.status_left.configure(text="yt-dlp %s | %s" % (event[1] or "?", event[2]))
                elif kind == "install_status":
                    self._install_set_status(event[1], event[2], event[3])
                elif kind == "install_progress":
                    self._install_set_progress(event[1], event[2], event[3])
                elif kind == "install_step_done":
                    self._install_finish_row(event[1], event[2], event[3])
                elif kind == "install_all_done":
                    self._install_finish_all(event[1], event[2])
                elif kind == "binupdate":
                    self._busy_binary = False
                    log_lines.append("[upd] %s" % event[1])
                    messagebox.showinfo(T("msg.updatetitle"), event[1][-600:] or T("msg.done"), parent=self)
                    self._resolve_binaries()
                elif kind == "analyze":
                    self._populate_analysis(event[1], event[2], event[3])
                elif kind == "thumbnail":
                    self._show_thumbnail(event[1], event[2])
        except queue.Empty:
            pass
        if log_lines:
            self._append_log(log_lines)
        self.after(100, self._poll_events)

    def _show_thumbnail(self, win, png_path):
        try:
            if not win.winfo_exists():
                return
            img = tk.PhotoImage(file=png_path)
            self._thumb_label.configure(image=img)
            self._thumb_label.image = img
        except Exception:
            pass

    def _refresh_row(self, job_id):
        job = self.engine.jobs.get(job_id)
        iid = self.job_rows.get(job_id)
        if job is None or iid is None:
            return
        status = T("st." + job.status)
        if job.status == eng.ST_RUNNING and job.item:
            status = "%s %s" % (status, job.item)
        pct = "%.1f%%" % job.percent if job.percent else ""
        try:
            self.tree.item(iid, values=(job.title, status, pct, job.speed, job.eta))
        except tk.TclError:
            pass

    def _update_queue_status(self):
        """Affiche un décompte "X/Y terminés" pendant qu'une file est active."""
        jobs = list(self.engine.jobs.values())
        if not jobs or not self.engine.running:
            return
        total = len(jobs)
        done = sum(1 for j in jobs if j.status in eng.FINAL_STATES)
        if done >= total:
            return  # _maybe_queue_done prend le relais avec le message final
        running = sum(1 for j in jobs if j.status == eng.ST_RUNNING)
        self.status_right.configure(
            text=T("msg.queueprogress").format(done=done, total=total, running=running))

    def _maybe_queue_done(self):
        jobs = list(self.engine.jobs.values())
        if jobs and all(j.status in eng.FINAL_STATES for j in jobs):
            errors = sum(1 for j in jobs if j.status == eng.ST_ERROR)
            cancelled = sum(1 for j in jobs if j.status == eng.ST_CANCELLED)
            if errors:
                self.status_right.configure(text=T("msg.queueerrors").format(n=errors))
            else:
                self.status_right.configure(text=T("msg.queuedone"))
            if cancelled < len(jobs):
                self._notify_queue_done(errors > 0)

    def _notify_queue_done(self, had_errors):
        """Petit signal (son + clignotement barre des tâches) quand une file se termine
        naturellement, utile si la fenêtre tourne en arrière-plan pendant une longue playlist."""
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONHAND if had_errors else winsound.MB_ICONASTERISK)
        except Exception:
            pass
        theme.flash_taskbar(self)

    def _append_log(self, lines):
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", "\n".join(lines) + "\n")
            if int(float(self.log_text.index("end-1c"))) > 8000:
                self.log_text.delete("1.0", "2000.0")
            if self.v["autoscroll_log"].get():
                self.log_text.see("end")
            self.log_text.configure(state="disabled")
        except (tk.TclError, AttributeError, ValueError):
            pass

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # ---------------------------------------------------------- fermeture
    def _on_close(self):
        active = any(j.status == eng.ST_RUNNING for j in self.engine.jobs.values())
        if active and not messagebox.askyesno("YTDL Interface", T("msg.quitconfirm"), parent=self):
            return
        self.engine.cancel_all()
        data = {name: var.get() for name, var in self.v.items() if name != "password"}
        data["_geometry"] = self.geometry()
        save_settings(self.app_dir, data)
        self.destroy()
