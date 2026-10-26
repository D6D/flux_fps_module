"""Recogida de métricas: CPU y RAM con psutil, GPU y VRAM con NVML (driver de NVIDIA)."""
import logging

import psutil

log = logging.getLogger(__name__)

try:
    import pynvml
except ImportError:  # nvidia-ml-py no instalado
    pynvml = None


class SystemMetrics:
    def __init__(self, gpu_index=0):
        psutil.cpu_percent(None)  # la primera llamada siempre devuelve 0; la descartamos
        self.gpu = None
        if pynvml:
            try:
                pynvml.nvmlInit()
                self.gpu = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
                self.gpu_name = pynvml.nvmlDeviceGetName(self.gpu)
                log.info("GPU: %s", self.gpu_name)
            except pynvml.NVMLError as e:
                log.warning("NVML no disponible (%s); sin métricas de GPU", e)

    def sample(self):
        vm = psutil.virtual_memory()
        m = {
            "cpu": psutil.cpu_percent(None),
            "ram_pct": vm.percent,
            "ram_used_gb": (vm.total - vm.available) / 2**30,
            "ram_total_gb": vm.total / 2**30,
        }
        if self.gpu:
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(self.gpu)
                mem = pynvml.nvmlDeviceGetMemoryInfo(self.gpu)
                m.update(
                    gpu=util.gpu,
                    vram_used_gb=mem.used / 2**30,
                    vram_total_gb=mem.total / 2**30,
                    vram_pct=100 * mem.used / mem.total,
                    gpu_temp=pynvml.nvmlDeviceGetTemperature(self.gpu, pynvml.NVML_TEMPERATURE_GPU),
                    gpu_power_w=pynvml.nvmlDeviceGetPowerUsage(self.gpu) / 1000,
                )
            except pynvml.NVMLError as e:
                log.debug("Error leyendo la GPU: %s", e)
        return m

    def close(self):
        if self.gpu:
            pynvml.nvmlShutdown()
