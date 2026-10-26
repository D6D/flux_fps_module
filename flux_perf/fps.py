"""FPS de la ventana en primer plano usando PresentMon (Intel) en segundo plano.

PresentMon escribe un CSV por stdout con una fila por frame presentado. Guardamos los
tiempos entre frames de cada proceso y calculamos los FPS del proceso que tiene el foco.
Necesita permisos de administrador o pertenecer al grupo «Usuarios del registro de
rendimiento» (ver docs/instalacion.md).
"""
import csv
import ctypes
import logging
import subprocess
import threading
import time
from collections import defaultdict, deque
from ctypes import wintypes
from pathlib import Path

import psutil

log = logging.getLogger(__name__)

SESSION_NAME = "fluxperf"
# Columna con el tiempo entre frames según la versión de métricas de PresentMon
FRAME_TIME_COLUMNS = ("MsBetweenPresents", "FrameTime", "MsBetweenAppStart")
WINDOW_SECONDS = 1.5
# Ventana para el 1% low: los tirones se notan en segundos, no en un instante
LOW_WINDOW_SECONDS = 10
LOW_MIN_FRAMES = 100
IGNORED_APPS = {"dwm.exe"}
RESTART_SECONDS = 10
REPORT_SECONDS = 60

_user32 = ctypes.windll.user32


def foreground_window():
    """Devuelve (pid, título) de la ventana en primer plano, o (None, "")."""
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None, ""
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    title = ctypes.create_unicode_buffer(256)
    _user32.GetWindowTextW(hwnd, title, len(title))
    return pid.value, title.value.strip()


class FpsMonitor:
    def __init__(self, presentmon_path):
        self.path = Path(presentmon_path)
        self.proc = None
        self.started_at = 0.0
        self.last_foreground, self.last_report = None, 0.0
        self.error = None
        self.frames = defaultdict(deque)  # pid -> deque[(llegada, ms)]
        self.apps = {}  # pid -> nombre del exe
        self.lock = threading.Lock()

    def start(self):
        if not self.path.is_file():
            self.error = f"No está PresentMon en {self.path}"
            log.warning(self.error)
            return False
        cmd = [
            str(self.path), "--output_stdout", "--no_console_stats", "--stop_existing_session",
            "--session_name", SESSION_NAME, "--no_track_input",
        ]
        self.proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.started_at = time.monotonic()
        threading.Thread(target=self._read_stdout, args=(self.proc,), daemon=True).start()
        threading.Thread(target=self._read_stderr, args=(self.proc,), daemon=True).start()
        return True

    def _read_stderr(self, proc):
        for line in proc.stderr:
            line = line.strip()
            if not line:
                continue
            if "access denied" in line.lower():
                self.error = "PresentMon sin permisos (ver docs/instalacion.md)"
                log.warning(self.error)
            else:
                log.debug("PresentMon: %s", line)

    def _read_stdout(self, proc):
        reader = csv.reader(proc.stdout)
        header = next(reader, None)
        if not header:
            return
        cols = {name: i for i, name in enumerate(header)}
        ft = next((cols[c] for c in FRAME_TIME_COLUMNS if c in cols), None)
        if ft is None or "ProcessID" not in cols:
            self.error = f"Formato de PresentMon desconocido: {header}"
            log.error(self.error)
            return
        pid_col, app_col = cols["ProcessID"], cols.get("Application")
        for row in reader:
            try:
                pid = int(row[pid_col])
                ms = float(row[ft])
            except (ValueError, IndexError):
                continue
            if ms <= 0:
                continue
            now = time.monotonic()
            with self.lock:
                q = self.frames[pid]
                q.append((now, ms))
                while q and now - q[0][0] > LOW_WINDOW_SECONDS:
                    q.popleft()
                if app_col is not None and pid not in self.apps:
                    self.apps[pid] = row[app_col]

    def _report(self, pid, now):
        """Apunta en el log qué ventana tiene el foco y qué procesos presentan frames, para
        diagnosticar juegos cuyos FPS no salen (llamar con self.lock tomado)."""
        self.last_foreground, self.last_report = pid, now
        active = sorted(((sum(now - t <= WINDOW_SECONDS for t, _ in q), p) for p, q in self.frames.items()
                         if q and now - q[-1][0] <= WINDOW_SECONDS), reverse=True)
        try:
            name = psutil.Process(pid).name() if pid else None
        except psutil.Error:
            name = "?"
        log.info("FPS: primer plano %s (pid %s), %s frames suyos; procesos con frames: %s%s",
                 name, pid, "con" if pid in dict((p, n) for n, p in active) else "sin",
                 ", ".join(f"{self.apps.get(p, '?')} ({p}, {n})" for n, p in active[:5]) or "ninguno",
                 "" if self.proc and self.proc.poll() is None else " — PresentMon NO está en marcha")

    def current(self):
        """Devuelve (fps, fps_1%_low, nombre_app) de la ventana en primer plano.

        Sin juego delante devuelve (None, None, None); el 1% low es None hasta que haya
        LOW_MIN_FRAMES frames en los últimos LOW_WINDOW_SECONDS.
        """
        # PresentMon puede caerse (p. ej. si otra instancia cierra la sesión ETW con el mismo
        # nombre); lo relanzamos, como mucho una vez cada RESTART_SECONDS.
        if self.proc and self.proc.poll() is not None and time.monotonic() - self.started_at > RESTART_SECONDS:
            log.warning("PresentMon se ha cerrado (código %s); se vuelve a arrancar", self.proc.returncode)
            self.start()
        pid, title = foreground_window()
        now = time.monotonic()
        with self.lock:
            if pid != self.last_foreground or now - self.last_report > REPORT_SECONDS:
                self._report(pid, now)
            q = self.frames.get(pid)
            if not q or now - q[-1][0] > WINDOW_SECONDS:
                return None, None, None
            if self.apps.get(pid, "").lower() in IGNORED_APPS:
                return None, None, None
            # Media de los tiempos de frame, no número de filas por segundo: la salida de
            # PresentMon llega a ráfagas cuando va por una tubería.
            recent = [ms for t, ms in q if now - t <= WINDOW_SECONDS]
            avg_ms = sum(recent) / len(recent)
            # 1% low: media del 1% de frames más lentos, pasada a FPS (como CapFrameX o MSI Afterburner)
            low = None
            if len(q) >= LOW_MIN_FRAMES:
                worst = sorted((ms for _, ms in q), reverse=True)[:len(q) // 100]
                low = 1000 / (sum(worst) / len(worst))
            # El título de la ventana suele ser el nombre del juego («Forza Horizon 6»); si no
            # tiene, se usa el ejecutable sin «.exe».
            name = title or self.apps.get(pid, "").removesuffix(".exe")
            return 1000 / avg_ms, low, name

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        # Por si la sesión ETW queda colgada
        if self.path.is_file():
            subprocess.run(
                [str(self.path), "--terminate_existing_session", "--session_name", SESSION_NAME],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
            )
