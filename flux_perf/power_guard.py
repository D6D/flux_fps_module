"""Desactiva el botón físico de apagado del PC mientras hay un juego abierto.

Cambia en el plan de energía activo la «Acción de botón de inicio/apagado» (PBUTTONACTION)
a «No hacer nada» y, al cerrar el juego, deja el valor que hubiera. Con powercfg no hacen
falta permisos de administrador.

Un proceso cuenta como juego si su .exe está dentro de una carpeta de juegos (Steam, Xbox,
GOG, Battle.net...; ver GAME_DIR_MARKERS y "game_dirs" en config.json) o si su nombre está
en "games". El valor original se guarda en `%LOCALAPPDATA%\\flux_perf\\power_button.json`:
si flux_perf se cierra a mitad de partida, al volver a arrancar lo restaura en cuanto no
haya ningún juego abierto.

Lo que NO se puede evitar desde Windows: mantener pulsado el botón 4 s apaga el PC por
hardware.
"""
import json
import logging
import os
import subprocess
import time
from pathlib import Path

import psutil

log = logging.getLogger(__name__)

STATE_FILE = Path(os.environ.get("LOCALAPPDATA", ".")) / "flux_perf" / "power_button.json"
POLL_SECONDS = 3
# Trozos de ruta (en minúsculas) que identifican carpetas de juegos en cualquier unidad
GAME_DIR_MARKERS = ("\\steamapps\\common\\", "\\xboxgames\\")
# Ejecutables dentro de esas carpetas que no son juegos (instaladores, lanzadores)
NOT_GAMES = {"steam.exe", "steamwebhelper.exe", "battle.net.exe", "battle.net launcher.exe",
             "dxsetup.exe", "vc_redist.x64.exe", "vc_redist.x86.exe", "installer.exe",
             "launcher.exe", "launcherpatcher.exe", "rockstarservice.exe", "socialclubhelper.exe"}
ACTION_NAMES = {0: "No hacer nada", 1: "Suspender", 2: "Hibernar", 3: "Apagar", 4: "Apagar la pantalla"}
NO_WINDOW = subprocess.CREATE_NO_WINDOW


def _powercfg(*args):
    return subprocess.run(["powercfg", *args], capture_output=True, text=True, check=True,
                          creationflags=NO_WINDOW).stdout


def _active_scheme():
    # «GUID de plan de energía: 8c5e7fda-...  (Alto rendimiento)»: el GUID es el único token con 4 guiones
    return next(t for t in _powercfg("/getactivescheme").split() if t.count("-") == 4)


def _current_action(scheme):
    """Devuelve (corriente alterna, batería) de PBUTTONACTION en el plan indicado."""
    # Solo las líneas del valor actual (alterna y batería) acaban en «: 0x...». Se busca eso y
    # no el texto, que depende del idioma y de la página de códigos de la consola.
    values = [int(line.rsplit(":", 1)[1], 16)
              for line in _powercfg("/qh", scheme, "SUB_BUTTONS", "PBUTTONACTION").splitlines()
              if line.rsplit(":", 1)[-1].strip().startswith("0x")]
    if len(values) != 2:
        raise RuntimeError("No se pudo leer la acción del botón de apagado")
    return values


def _set_action(scheme, ac, dc):
    _powercfg("/setacvalueindex", scheme, "SUB_BUTTONS", "PBUTTONACTION", str(ac))
    _powercfg("/setdcvalueindex", scheme, "SUB_BUTTONS", "PBUTTONACTION", str(dc))
    if scheme == _active_scheme():
        _powercfg("/setactive", scheme)


class PowerButtonGuard:
    def __init__(self, game_dirs=(), games=()):
        self.prefixes = tuple(os.path.normcase(os.path.join(d, "")) for d in game_dirs)
        self.games = {g.lower() for g in games}
        self.next_poll = 0.0
        self.current_game = None

    def find_game(self):
        """Nombre del primer juego abierto (también lo usa hdr_switch), o None."""
        for p in psutil.process_iter(["name", "exe"]):
            name = (p.info["name"] or "").lower()
            if name in self.games:
                return p.info["name"]
            exe = os.path.normcase(p.info["exe"] or "")
            if not exe or name in NOT_GAMES:
                continue
            if any(m in exe for m in GAME_DIR_MARKERS) or exe.startswith(self.prefixes):
                return p.info["name"]
        return None

    @property
    def guarding(self):
        return STATE_FILE.exists()

    def poll(self):
        if time.monotonic() < self.next_poll:
            return
        self.next_poll = time.monotonic() + POLL_SECONDS
        game = self.find_game()
        if game != self.current_game:
            log.info("Juego abierto: %s", game or "ninguno")
            self.current_game = game
        if game and not self.guarding:
            scheme = _active_scheme()
            ac, dc = _current_action(scheme)
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps({"scheme": scheme, "ac": ac, "dc": dc, "game": game}), encoding="utf-8")
            _set_action(scheme, 0, 0)
            log.info("%s abierto: botón de apagado desactivado (antes: %s)", game, ACTION_NAMES.get(ac, ac))
        elif not game and self.guarding:
            self.restore()

    def restore(self):
        """Vuelve a dejar el botón como estaba (al cerrar el juego o al salir de flux_perf)."""
        if not self.guarding:
            return
        saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        _set_action(saved["scheme"], saved["ac"], saved["dc"])
        STATE_FILE.unlink()
        log.info("Botón de apagado restaurado: %s", ACTION_NAMES.get(saved["ac"], saved["ac"]))
