"""Activa el HDR de Windows al abrir ciertos juegos y lo quita al cerrarlos.

Los juegos se eligen por nombre de ejecutable en "hdr_games" de config.json, o todos los que
detecta power_guard (carpetas de juegos + "games") con "hdr_all_games": true, menos los de
"hdr_exclude". Al detectar uno,
se enciende el HDR en las pantallas que lo admiten y lo tienen apagado; al cerrarlo, se apaga
SOLO en las que encendimos nosotros (si ya lo tenías activado a mano, se respeta).

Para el cambio se usa DisplayConfigSetDeviceInfo con DISPLAYCONFIG_SET_HDR_STATE (Windows 11
24H2 o posterior), que enciende el HDR y no solo el color avanzado; en versiones anteriores,
DISPLAYCONFIG_SET_ADVANCED_COLOR_STATE. No hacen falta permisos de administrador.

Las pantallas encendidas se apuntan en `%LOCALAPPDATA%\\flux_perf\\hdr_switch.json`: si
flux_perf se cierra a mitad de partida, al volver a arrancar apaga el HDR en cuanto no haya
ningún juego de la lista abierto. Al salir de flux_perf NO se apaga (podría pillar el juego
en marcha).
"""
import ctypes
import json
import logging
import os
import time
from ctypes import byref, c_uint32, sizeof
from pathlib import Path

import psutil

from .hdr import (GET_ADVANCED_COLOR_INFO, GET_ADVANCED_COLOR_INFO_2, GET_SOURCE_NAME, COLOR_MODE_HDR,
                  _ColorInfo, _ColorInfo2, _Header, _SourceName, _active_paths, _info, _user32)

log = logging.getLogger(__name__)

STATE_FILE = Path(os.environ.get("LOCALAPPDATA", ".")) / "flux_perf" / "hdr_switch.json"
POLL_SECONDS = 2
SET_ADVANCED_COLOR_STATE = 10
SET_HDR_STATE = 16
HDR_SUPPORTED_BIT = 4      # highDynamicRangeSupported en ADVANCED_COLOR_INFO_2
ADVANCED_COLOR_SUPPORTED_BIT = 0


class _SetState(ctypes.Structure):
    _fields_ = [("header", _Header), ("value", c_uint32)]


def _key(path):
    return f"{path.target.adapter.low}:{path.target.adapter.high}:{path.target.id}"


def _name(path):
    name = _SourceName()
    return name.name if _info(name, GET_SOURCE_NAME, path) else _key(path)


def _hdr_status(path):
    """(admite HDR, HDR encendido) de una pantalla."""
    info2 = _ColorInfo2()
    if _info(info2, GET_ADVANCED_COLOR_INFO_2, path):
        return bool(info2.value >> HDR_SUPPORTED_BIT & 1), info2.mode == COLOR_MODE_HDR
    info = _ColorInfo()
    if _info(info, GET_ADVANCED_COLOR_INFO, path):
        return bool(info.value >> ADVANCED_COLOR_SUPPORTED_BIT & 1), bool(info.value >> 1 & 1)
    return False, False


def _set_hdr(path, enable):
    for kind in (SET_HDR_STATE, SET_ADVANCED_COLOR_STATE):
        packet = _SetState(value=1 if enable else 0)
        packet.header.type = kind
        packet.header.size = sizeof(packet)
        packet.header.adapter = path.target.adapter
        packet.header.id = path.target.id
        if _user32.DisplayConfigSetDeviceInfo(byref(packet)) == 0:
            return True
    return False


class HdrAutoSwitcher:
    def __init__(self, games=(), finder=None, exclude=()):
        """`finder`: función que devuelve el juego abierto (o None); si se da, se usa además de `games`."""
        self.games = {g.lower() for g in games}
        self.finder = finder
        self.exclude = {g.lower() for g in exclude}
        self.next_poll = 0.0
        # Distinto de None para que la primera pasada sin juego restaure lo pendiente de otra ejecución
        self.current_game = ""

    def _find_game(self):
        for p in psutil.process_iter(["name"]):
            name = p.info["name"] or ""
            if name.lower() in self.games:
                return name
        if self.finder:
            game = self.finder()
            if game and game.lower() not in self.exclude:
                return game
        return None

    def poll(self):
        if not (self.games or self.finder) or time.monotonic() < self.next_poll:
            return
        self.next_poll = time.monotonic() + POLL_SECONDS
        game = self._find_game()
        if game == self.current_game:
            return
        self.current_game = game
        if game:
            self._enable(game)
        else:
            self.restore()

    def _enable(self, game):
        switched = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else []
        for path in _active_paths():
            supported, on = _hdr_status(path)
            if not supported or on:
                continue
            if _set_hdr(path, True):
                switched.append(_key(path))
                log.info("%s abierto: HDR activado en %s", game, _name(path))
            else:
                log.warning("%s abierto: no se pudo activar el HDR en %s", game, _name(path))
        if switched:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(sorted(set(switched))), encoding="utf-8")

    def restore(self):
        """Apaga el HDR en las pantallas donde lo encendimos nosotros."""
        if not STATE_FILE.exists():
            return
        switched = set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
        for path in _active_paths():
            if _key(path) in switched and _hdr_status(path)[1]:
                if _set_hdr(path, False):
                    log.info("Juego cerrado: HDR desactivado en %s", _name(path))
                else:
                    log.warning("No se pudo desactivar el HDR en %s", _name(path))
        STATE_FILE.unlink()
