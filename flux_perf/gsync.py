"""Estado de G-Sync con NVAPI (nvapi64.dll, viene con el driver de NVIDIA).

NVAPI no tiene paquete oficial para Python, así que se llama con ctypes a través de
nvapi_QueryInterface. Usamos NvAPI_Disp_GetVRRInfo, que dice si la pantalla está ahora
mismo en VRR (lo mismo que enseña el indicador de G-Sync de NVIDIA). Ver docs/api-notas.md.
"""
import ctypes
import logging
from ctypes import POINTER, byref, c_char_p, c_int, c_uint32, c_void_p

log = logging.getLogger(__name__)

# IDs de nvapi_interface.h
NVAPI_INITIALIZE = 0x0150E828
NVAPI_DISP_GET_DISPLAY_ID_BY_DISPLAY_NAME = 0xAE457190
NVAPI_DISP_GET_VRR_INFO = 0xDF8FDA57

# Bits de NV_GET_VRR_INFO, en orden
FLAGS = ("enabled", "possible", "requested", "indicator", "display_in_vrr")


class _VrrInfo(ctypes.Structure):
    _fields_ = [("version", c_uint32), ("flags", c_uint32), ("reserved", c_uint32 * 4)]


class GSyncMonitor:
    def __init__(self, display=1):
        self.available = False
        self.last = None
        try:
            nvapi = ctypes.WinDLL("nvapi64.dll")
            query = nvapi.nvapi_QueryInterface
            query.restype, query.argtypes = c_void_p, [c_uint32]

            def fn(id_, *args):
                ptr = query(id_)
                if not ptr:
                    raise OSError(f"NVAPI no tiene la función {id_:#x}")
                return ctypes.CFUNCTYPE(c_int, *args)(ptr)

            if fn(NVAPI_INITIALIZE)() != 0:
                raise OSError("NvAPI_Initialize ha fallado")
            get_id = fn(NVAPI_DISP_GET_DISPLAY_ID_BY_DISPLAY_NAME, c_char_p, POINTER(c_uint32))
            self._get_vrr = fn(NVAPI_DISP_GET_VRR_INFO, c_uint32, POINTER(_VrrInfo))
            display_id = c_uint32()
            name = "\\\\.\\DISPLAY%d" % display
            if get_id(name.encode(), byref(display_id)) != 0:
                raise OSError(f"NVAPI no encuentra {name}")
            self.display_id = display_id.value
            self.available = True
        except OSError as e:
            log.warning("G-Sync no disponible (%s)", e)

    def status(self):
        """Devuelve un dict con los bits de FLAGS, o None si NVAPI no responde."""
        if not self.available:
            return None
        info = _VrrInfo(version=ctypes.sizeof(_VrrInfo) | (1 << 16))
        if self._get_vrr(self.display_id, byref(info)) != 0:
            return None
        flags = {name: bool(info.flags >> bit & 1) for bit, name in enumerate(FLAGS)}
        if flags != self.last:
            # Para comprobar qué bit cambia al entrar en un juego con G-Sync
            log.info("G-Sync: %s", ", ".join(f"{k}={int(v)}" for k, v in flags.items()))
            self.last = flags
        return flags

    def active(self):
        """True si G-Sync está actuando ahora mismo; None si no se puede saber."""
        flags = self.status()
        return None if flags is None else flags["enabled"]
