"""File de téléchargement : exécution de yt-dlp et suivi de progression."""
import os
import re
import subprocess
import threading

from .binaries import CREATE_NO_WINDOW

# Codes internes ; la traduction pour l'affichage se fait dans app.py (st.*)
ST_PENDING = "pending"
ST_RUNNING = "running"
ST_DONE = "done"
ST_ERROR = "error"
ST_CANCELLED = "cancelled"

FINAL_STATES = (ST_DONE, ST_ERROR, ST_CANCELLED)

RE_PROGRESS = re.compile(
    r"\[download\]\s+(?P<pct>[\d.]+)%"
    r"(?:\s+of\s+~?\s*(?P<size>\S+))?"
    r"(?:\s+at\s+(?P<speed>\S+))?"
    r"(?:\s+ETA\s+(?P<eta>\S+))?"
)
RE_ITEM = re.compile(r"\[download\][^\S\n]*Downloading item (\d+) of (\d+)")
RE_DEST = re.compile(r"\[(?:download|ExtractAudio)\] Destination: (.+)")
RE_MERGE = re.compile(r'\[Merger\] Merging formats into "(.+)"')
RE_ALREADY = re.compile(r"\[download\] (.+) has already been downloaded")


class Job:
    _next_id = 1

    def __init__(self, url, cmd, dest_dir):
        self.id = Job._next_id
        Job._next_id += 1
        self.url = url
        self.cmd = cmd
        self.dest_dir = dest_dir
        self.title = url
        self.status = ST_PENDING
        self.percent = 0.0
        self.speed = ""
        self.eta = ""
        self.item = ""      # "2/10" pour les playlists
        self.proc = None
        self.cancelled = False
        self.log = []


class Engine:
    """Gère la file : démarre les jobs, lit la sortie, publie des événements.

    Événements postés dans ui_queue (tuples) :
      ("status", job_id), ("progress", job_id), ("title", job_id),
      ("log", job_id, ligne), ("done", job_id, code_retour)
    """

    def __init__(self, ui_queue):
        self.ui_queue = ui_queue
        self.jobs = {}
        self.order = []
        self.lock = threading.Lock()
        self.max_concurrent = 1
        self.running = False

    def _post(self, *event):
        self.ui_queue.put(event)

    def add_job(self, url, cmd, dest_dir):
        job = Job(url, cmd, dest_dir)
        with self.lock:
            self.jobs[job.id] = job
            self.order.append(job.id)
        if self.running:
            self._fill_slots()
        return job

    def start(self, max_concurrent=1):
        self.max_concurrent = max(1, int(max_concurrent))
        self.running = True
        self._fill_slots()

    def _active_count(self):
        return sum(1 for j in self.jobs.values() if j.status == ST_RUNNING)

    def _fill_slots(self):
        to_start = []
        with self.lock:
            if not self.running:
                return
            free = self.max_concurrent - self._active_count()
            for jid in self.order:
                if free <= 0:
                    break
                job = self.jobs[jid]
                if job.status == ST_PENDING and not job.cancelled:
                    job.status = ST_RUNNING
                    to_start.append(job)
                    free -= 1
        for job in to_start:
            self._post("status", job.id)
            threading.Thread(target=self._run, args=(job,), daemon=True).start()

    def _run(self, job):
        try:
            job.proc = subprocess.Popen(
                job.cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True, encoding="utf-8", errors="replace",
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception as exc:
            job.status = ST_ERROR
            self._post("log", job.id, "Impossible de lancer yt-dlp : %s" % exc)
            self._post("status", job.id)
            self._post("done", job.id, -1)
            self._fill_slots()
            return

        try:
            for line in job.proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                job.log.append(line)
                self._post("log", job.id, line)
                self._parse_line(job, line)
        except Exception as exc:
            self._post("log", job.id, "Erreur de lecture de la sortie de yt-dlp : %s" % exc)

        rc = job.proc.wait()
        if job.cancelled:
            job.status = ST_CANCELLED
        elif rc == 0 or rc == 101:  # 101 = --max-downloads atteint
            job.status = ST_DONE
            job.percent = 100.0
            job.speed = ""
            job.eta = ""
        else:
            job.status = ST_ERROR
        self._post("status", job.id)
        self._post("done", job.id, rc)
        self._fill_slots()

    def _parse_line(self, job, line):
        m = RE_PROGRESS.match(line)
        if m:
            try:
                job.percent = float(m.group("pct"))
            except ValueError:
                pass
            job.speed = m.group("speed") or ""
            job.eta = m.group("eta") or ""
            self._post("progress", job.id)
            return
        m = RE_ITEM.search(line)
        if m:
            job.item = "%s/%s" % (m.group(1), m.group(2))
            self._post("status", job.id)
            return
        m = RE_DEST.search(line) or RE_MERGE.search(line) or RE_ALREADY.search(line)
        if m:
            job.title = os.path.basename(m.group(1).strip())
            self._post("title", job.id)

    def cancel(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job.status in FINAL_STATES:
                return
            job.cancelled = True
            if job.status == ST_PENDING:
                job.status = ST_CANCELLED
                self._post("status", job.id)
                return
            proc = job.proc
        if proc and proc.poll() is None:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True, creationflags=CREATE_NO_WINDOW,
                )
            except Exception:
                pass

    def cancel_all(self):
        self.running = False
        for jid in list(self.order):
            self.cancel(jid)

    def move(self, job_id, offset):
        """Déplace un job de `offset` positions dans l'ordre de la file (réordonnancement manuel).

        Retourne le nouvel index, ou None si le déplacement est impossible
        (job inconnu ou déjà en bout de file).
        """
        with self.lock:
            if job_id not in self.order:
                return None
            i = self.order.index(job_id)
            j = i + offset
            if j < 0 or j >= len(self.order):
                return None
            self.order[i], self.order[j] = self.order[j], self.order[i]
            return j

    def remove(self, job_id):
        """Retire un job non actif de la file. Retourne True si retiré."""
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job.status == ST_RUNNING:
                return False
            self.jobs.pop(job_id, None)
            if job_id in self.order:
                self.order.remove(job_id)
        return True
