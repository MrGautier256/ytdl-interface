"""Widgets utilitaires : infobulles, cadre défilant, formatage."""
import tkinter as tk
from tkinter import ttk

from . import theme


class Tooltip:
    """Infobulle affichée au survol d'un widget."""

    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after_id = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._tip or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            self._tip = tk.Toplevel(self.widget)
            self._tip.wm_overrideredirect(True)
            self._tip.wm_geometry("+%d+%d" % (x, y))
            lbl = tk.Label(
                self._tip, text=self.text, justify="left",
                background=theme.PAL["tip_bg"], foreground=theme.PAL["tip_fg"],
                relief="solid", borderwidth=1, wraplength=380,
                font=(theme.FONT_UI, 9), padx=6, pady=4,
            )
            lbl.pack()
        except Exception:
            self._tip = None

    def _hide(self, _event=None):
        self._cancel()
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


class ScrollableFrame(ttk.Frame):
    """Cadre avec ascenseur vertical ; placer le contenu dans .inner."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0,
                                 background=theme.PAL["bg"])
        vsb = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self.inner = ttk.Frame(self._canvas)
        self._win = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self._canvas.configure(yscrollcommand=vsb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<Enter>", self._bind_wheel)
        self._canvas.bind("<Leave>", self._unbind_wheel)

    def _on_inner_configure(self, _event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfigure(self._win, width=event.width)

    # Linux (X11, Tk 8.6) : la molette arrive en clics Button-4 (haut) / Button-5 (bas)
    # et non en événements <MouseWheel>.
    _WHEEL_EVENTS = ("<MouseWheel>", "<Button-4>", "<Button-5>")

    def _bind_wheel(self, _event=None):
        for seq in self._WHEEL_EVENTS:
            self._canvas.bind_all(seq, self._on_wheel)

    def _unbind_wheel(self, _event=None):
        for seq in self._WHEEL_EVENTS:
            self._canvas.unbind_all(seq)

    def _on_wheel(self, event):
        if event.num == 4:
            step = -1
        elif event.num == 5:
            step = 1
        else:
            step = int(-event.delta / 120)
        try:
            if self._canvas.bbox("all")[3] > self._canvas.winfo_height():
                self._canvas.yview_scroll(step, "units")
        except Exception:
            pass


def human_size(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return ("%d %s" if unit == "B" else "%.1f %s") % (n, unit)
        n /= 1024
    return "%.1f PB" % n


def human_duration(seconds):
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return ""
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%d:%02d" % (m, s)
