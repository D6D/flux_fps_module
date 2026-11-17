"""Estado de HDR de Windows con la API DisplayConfig (user32), sin dependencias.

Se mira la pantalla donde está la ventana en primer plano (el juego), o la principal si
no hay ninguna. En Windows 11 24H2 o posterior se usa DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO_2
(`activeColorMode`), que distingue HDR de la gestión automática del color (WCG); en
versiones anteriores, el bit `advancedColorEnabled` de la versión 1. Ver docs/api-notas.md.
"""
import ctypes
import logging
from ctypes import byref, c_int32, c_uint32, c_uint64, c_wchar, sizeof, wintypes

log = logging.getLogger(__name__)

QDC_ONLY_ACTIVE_PATHS = 0x2
GET_SOURCE_NAME = 1
GET_ADVANCED_COLOR_INFO = 9
GET_ADVANCED_COLOR_INFO_2 = 15
COLOR_MODE_HDR = 2
MONITOR_DEFAULTTOPRIMARY = 1


class _Luid(ctypes.Structure):
    _fields_ = [("low", c_uint32), ("high", c_int32)]


class _Header(ctypes.Structure):
    _fields_ = [("type", c_uint32), ("size", c_uint32), ("adapter", _Luid), ("id", c_uint32)]


class _SourceInfo(ctypes.Structure):
    _fields_ = [("adapter", _Luid), ("id", c_uint32), ("mode_idx", c_uint32), ("status", c_uint32)]


class _TargetInfo(ctypes.Structure):
    _fields_ = [("adapter", _Luid), ("id", c_uint32), ("mode_idx", c_uint32), ("output_tech", c_uint32),
                ("rotation", c_uint32), ("scaling", c_uint32), ("refresh_num", c_uint32),
                ("refresh_den", c_uint32), ("scanline", c_uint32), ("available", c_int32),
                ("status", c_uint32)]


class _PathInfo(ctypes.Structure):
    _fields_ = [("source", _SourceInfo), ("target", _TargetInfo), ("flags", c_uint32)]


class _ModeInfo(ctypes.Structure):
    # El contenido no nos interesa, solo el tamaño (64 bytes) para que QueryDisplayConfig no falle
    _fields_ = [("type", c_uint32), ("id", c_uint32), ("adapter", _Luid), ("data", c_uint64 * 6)]


class _SourceName(ctypes.Structure):
    _fields_ = [("header", _Header), ("name", c_wchar * 32)]


class _ColorInfo(ctypes.Structure):
    _fields_ = [("header", _Header), ("value", c_uint32), ("encoding", c_uint32), ("bpc", c_uint32)]


class _ColorInfo2(ctypes.Structure):
    _fields_ = [("header", _Header), ("value", c_uint32), ("encoding", c_uint32), ("bpc", c_uint32),
                ("mode", c_uint32)]


class _MonitorInfoEx(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT), ("work", wintypes.RECT),
                ("flags", wintypes.DWORD), ("device", c_wchar * 32)]


_user32 = ctypes.windll.user32
_user32.MonitorFromWindow.restype = wintypes.HMONITOR
_user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
_user32.GetForegroundWindow.restype = wintypes.HWND


def _info(packet, kind, path):
    packet.header.type = kind
    packet.header.size = sizeof(packet)
    packet.header.adapter = path.target.adapter if kind != GET_SOURCE_NAME else path.source.adapter
    packet.header.id = path.target.id if kind != GET_SOURCE_NAME else path.source.id
    return _user32.DisplayConfigGetDeviceInfo(byref(packet)) == 0


def _active_paths():
    n_paths, n_modes = c_uint32(), c_uint32()
    if _user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, byref(n_paths), byref(n_modes)):
        return []
    paths, modes = (_PathInfo * n_paths.value)(), (_ModeInfo * n_modes.value)()
    if _user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, byref(n_paths), paths, byref(n_modes), modes, None):
        return []
    return paths[:n_paths.value]


def _foreground_display():
    """Nombre GDI (\\\\.\\DISPLAYn) de la pantalla con la ventana activa, o de la principal."""
    hmon = _user32.MonitorFromWindow(_user32.GetForegroundWindow(), MONITOR_DEFAULTTOPRIMARY)
    info = _MonitorInfoEx(size=sizeof(_MonitorInfoEx))
    return info.device if hmon and _user32.GetMonitorInfoW(hmon, byref(info)) else None


class HdrMonitor:
    def __init__(self):
        self.last = None

    def _state(self, path):
        info2 = _ColorInfo2()
        if _info(info2, GET_ADVANCED_COLOR_INFO_2, path):
            return info2.mode == COLOR_MODE_HDR
        info = _ColorInfo()
        if _info(info, GET_ADVANCED_COLOR_INFO, path):
            return bool(info.value >> 1 & 1)  # advancedColorEnabled
        return None

    def active(self):
        """True si la pantalla del juego está en HDR; None si no se puede saber."""
        display = None
        try:
            display = _foreground_display()
            paths = _active_paths()
            path = next((p for p in paths if _info(name := _SourceName(), GET_SOURCE_NAME, p)
                         and name.name == display), paths[0] if paths else None)
            state = None if path is None else self._state(path)
        except OSError as e:
            log.debug("No se pudo leer el estado de HDR (%s)", e)
            state = None
        if state != self.last:
            log.info("HDR en %s: %s", display, {True: "activado", False: "desactivado", None: "desconocido"}[state])
            self.last = state
        return state
