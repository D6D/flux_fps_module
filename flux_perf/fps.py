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

log = logging.getLogger(__name__)

SESSION_NAME = "fluxperf"
# Columna con el tiempo entre frames según la versión de métricas de PresentMon
FRAME_TIME_COLUMNS = ("MsBetweenPresents", "FrameTime", "MsBetweenAppStart")
WINDOW_SECONDS = 1.5
IGNORED_APPS = {"dwm.exe"}

_user32 = ctypes.windll.user32


def foreground_pid():
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


class FpsMonitor:
    def __init__(self, presentmon_path):
        self.path = Path(presentmon_path)
        self.proc = None
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
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        return True

    def _read_stderr(self):
        for line in self.proc.stderr:
            line = line.strip()
            if not line:
                continue
            if "access denied" in line.lower():
                self.error = "PresentMon sin permisos (ver docs/instalacion.md)"
                log.warning(self.error)
            else:
                log.debug("PresentMon: %s", line)

    def _read_stdout(self):
        reader = csv.reader(self.proc.stdout)
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
                while q and now - q[0][0] > WINDOW_SECONDS:
                    q.popleft()
                if app_col is not None and pid not in self.apps:
                    self.apps[pid] = row[app_col]

    def current(self):
        """Devuelve (fps, nombre_app) de la ventana en primer plano, o (None, None)."""
        pid = foreground_pid()
        now = time.monotonic()
        with self.lock:
            q = self.frames.get(pid)
            if not q or now - q[-1][0] > WINDOW_SECONDS:
                return None, None
            if self.apps.get(pid, "").lower() in IGNORED_APPS:
                return None, None
            # Media de los tiempos de frame, no número de filas por segundo: la salida de
            # PresentMon llega a ráfagas cuando va por una tubería.
            avg_ms = sum(ms for _, ms in q) / len(q)
            return 1000 / avg_ms, self.apps.get(pid)

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
