"""Cambia los módulos de la barra superior mientras un juego concreto está abierto.

Polymath no permite módulos por perfil y la API no deja quitarlos, así que esto es un
parche (ver flux_game_profiles/docs/peticiones-flux.md):

1. Polymath solo lee `mosaic.json` al arrancar y lo reescribe al cerrarse. Hay que
   cerrarlo, cambiar el fichero y volver a abrirlo.
2. El teclado guarda su propia copia de los módulos: después hay que grabar la
   configuración (`POST /config/save`).

Se activa al ABRIRSE el proceso del juego, no al ponerse en primer plano: así un Alt+Tab
no reinicia Polymath. Mientras dura, la disposición normal se guarda en
`%LOCALAPPDATA%\\flux_perf\\mosaic_normal.json`; que ese fichero exista significa «modo
juego aplicado», y así se recupera aunque flux_perf se reinicie a mitad de partida.
"""
import ctypes
import json
import logging
import uuid
from ctypes import wintypes
import os
import shutil
import subprocess
import time
from pathlib import Path

import psutil

from .polymath import CONFIG_DIR, ApiError, PolymathClient, PolymathNotReady

log = logging.getLogger(__name__)

MOSAIC_FILE = CONFIG_DIR / "mosaic.json"
NORMAL_FILE = Path(os.environ.get("LOCALAPPDATA", ".")) / "flux_perf" / "mosaic_normal.json"
POLYMATH_EXE = "polymath.exe"
POLYMATH_AUMID = "FluxGroup.FluxPolymath_42m5gadgr7drm!polymath"
POLYMATH_APP_ID = "shell:AppsFolder\\" + POLYMATH_AUMID
POLL_SECONDS = 3
CLOSE_TIMEOUT = 5
START_TIMEOUT = 90


def _guid(text):
    g = (ctypes.c_byte * 16)()
    ctypes.memmove(g, uuid.UUID(text).bytes_le, 16)
    return g


def _activate_app(aumid, arguments):
    """Lanza una app empaquetada con argumentos (IApplicationActivationManager).

    Abrirla con shell:AppsFolder no deja pasar parámetros. Devuelve el PID.
    """
    ole32 = ctypes.OleDLL("ole32")
    ole32.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED; si ya estaba iniciado no pasa nada
    manager = ctypes.c_void_p()
    ole32.CoCreateInstance(ctypes.byref(_guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")), None, 4,
                           ctypes.byref(_guid("2E941141-7F97-4756-BA1D-9DECDE894A3D")), ctypes.byref(manager))
    vtbl = ctypes.cast(ctypes.cast(manager, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    activate = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                  ctypes.c_int, ctypes.POINTER(wintypes.DWORD))(vtbl[3])
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])
    pid = wintypes.DWORD()
    try:
        activate(manager, aumid, arguments, 0, ctypes.byref(pid))
    finally:
        release(manager)
    return pid.value


class MosaicSwitcher:
    def __init__(self, rules):
        """rules: lista de {"process": "D2R.exe", "tile_types": [11]} (11 = reloj)."""
        self.rules = {r["process"].lower(): r["tile_types"] for r in rules}
        self.next_poll = 0.0

    @property
    def game_mode(self):
        return NORMAL_FILE.exists()

    def poll(self):
        """Comprueba los procesos y cambia los módulos si hace falta.

        Devuelve True si ha reiniciado Polymath (el llamador debe reconectarse).
        """
        if not self.rules or time.monotonic() < self.next_poll:
            return False
        self.next_poll = time.monotonic() + POLL_SECONDS
        running = {p.info["name"].lower() for p in psutil.process_iter(["name"]) if p.info["name"]}
        game = next((name for name in self.rules if name in running), None)
        if game and not self.game_mode:
            log.info("%s abierto: dejando solo los módulos %s", game, self.rules[game])
            self._switch(self.rules[game])
            return True
        if not game and self.game_mode:
            log.info("Juego cerrado: restaurando los módulos normales")
            self._switch(None)
            return True
        return False

    def _switch(self, tile_types):
        """tile_types None = volver a la disposición normal."""
        self._close_polymath()
        if tile_types is not None:
            NORMAL_FILE.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(MOSAIC_FILE, NORMAL_FILE)
            mosaic = json.loads(NORMAL_FILE.read_text(encoding="utf-8"))
            mosaic["tileTypes"] = tile_types
            MOSAIC_FILE.write_text(json.dumps(mosaic, separators=(",", ":")), encoding="utf-8")
        else:
            shutil.copyfile(NORMAL_FILE, MOSAIC_FILE)
            NORMAL_FILE.unlink()
        self._start_polymath_and_save()

    def _close_polymath(self):
        procs = [p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == POLYMATH_EXE]
        if not procs:
            return
        # Primero educadamente (WM_CLOSE), para que termine de escribir su configuración. Con
        # Polymath 1.4.5.7 no basta (se queda en la bandeja) y acaba cerrándose a la fuerza.
        subprocess.run(["taskkill", "/IM", POLYMATH_EXE], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        _, alive = psutil.wait_procs(procs, timeout=CLOSE_TIMEOUT)
        for p in alive:
            log.warning("Polymath no se cierra; forzando (pid %d)", p.pid)
            p.kill()
        psutil.wait_procs(alive, timeout=5)

    def _start_polymath_and_save(self):
        # Con «--hidden» (lo que usa su propia tarea de inicio) arranca en la bandeja y no le
        # roba el foco al juego. Si la activación falla, lo abrimos como antes.
        try:
            _activate_app(POLYMATH_AUMID, "--hidden")
        except OSError as e:
            log.warning("No se pudo lanzar Polymath oculto (%s); abriéndolo normal", e)
            subprocess.Popen(["explorer.exe", POLYMATH_APP_ID])
        client = PolymathClient()
        deadline = time.monotonic() + START_TIMEOUT
        while True:
            try:
                client.connect()
                break
            except (PolymathNotReady, ApiError, OSError) as e:
                if time.monotonic() > deadline:
                    log.error("Polymath no responde tras reiniciarlo (%s); los módulos del teclado no se han grabado", e)
                    return
                time.sleep(2)
        log.info("Grabando los módulos en el teclado: %s", client.post("/config/save", {}, timeout=90))
