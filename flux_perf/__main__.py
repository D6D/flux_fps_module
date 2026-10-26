"""Módulo de rendimiento para Flux Polymath.

Uso:
    python -m flux_perf              # envía las métricas al teclado
    python -m flux_perf --dry-run    # solo las muestra en la consola, sin tocar Polymath
"""
import argparse
import json
import logging
import os
import time
import urllib.error
from pathlib import Path

from .fps import FpsMonitor
from .metrics import SystemMetrics
from .polymath import ApiError, GraphTile, PolymathClient, PolymathNotReady

log = logging.getLogger("flux_perf")

PROJECT_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = Path(os.environ.get("LOCALAPPDATA", ".")) / "flux_perf" / "state.json"
RETRY_SECONDS = 5


def load_color(value, warn, crit, higher_is_worse=True):
    if value is None:
        return "Legend"
    if not higher_is_worse:
        value, warn, crit = -value, -warn, -crit
    if value >= crit:
        return "Red"
    if value >= warn:
        return "Yellow"
    return "Green"


def render(metric, m, fps):
    """Traduce una métrica a los campos de un GenericGraphUpdateRequest."""
    if metric == "cpu":
        return dict(value=m["cpu"], unit="%", sub_title="Carga CPU",
                    secondary=f"RAM {m['ram_used_gb']:.1f}/{m['ram_total_gb']:.0f} GB",
                    color=load_color(m["cpu"], 60, 85))
    if metric == "ram":
        return dict(value=m["ram_pct"], unit="%", sub_title="Memoria",
                    secondary=f"{m['ram_used_gb']:.1f}/{m['ram_total_gb']:.0f} GB",
                    color=load_color(m["ram_pct"], 70, 90))
    if metric == "gpu":
        if "gpu" not in m:
            return dict(value=0, unit="%", sub_title="Carga GPU", secondary="sin datos", color="Legend")
        return dict(value=m["gpu"], unit="%", sub_title="Carga GPU",
                    secondary=f"{m['gpu_temp']} °C · {m['gpu_power_w']:.0f} W",
                    color=load_color(m["gpu"], 80, 95))
    if metric == "vram":
        if "vram_used_gb" not in m:
            return dict(value=0, unit="GB", sub_title="VRAM", secondary="sin datos", color="Legend")
        return dict(value=m["vram_used_gb"], unit="GB", sub_title="VRAM",
                    secondary=f"{m['vram_pct']:.0f}% de {m['vram_total_gb']:.0f} GB",
                    color=load_color(m["vram_pct"], 75, 90))
    if metric == "fps":
        value, app = fps
        if value is None:
            return dict(value=0, unit="FPS", sub_title="FPS", secondary="sin juego", color="Legend")
        return dict(value=round(value), unit="FPS", sub_title="FPS",
                    secondary=app.removesuffix(".exe") if app else "",
                    color=load_color(value, 45, 30, higher_is_worse=False))
    raise ValueError(f"Métrica desconocida: {metric}")


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(tiles):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {f"{t.index}:{t.title}": t.id for t in tiles}
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def send(tile, fields, time_unit, colors):
    if not colors:
        fields = {**fields, "color": "Legend"}
    tile.update(time_unit=time_unit, **fields)


def run(config, dry_run):
    metrics = SystemMetrics()
    fps_monitor = None
    if any(t["metric"] == "fps" for t in config["tiles"]):
        fps_monitor = FpsMonitor(PROJECT_DIR / config["presentmon_path"])
        fps_monitor.start()

    client = PolymathClient()
    tiles = []
    connected = False
    next_retry = 0
    interval = config["interval_seconds"]
    time_unit = f"{config['graph_length'] * interval:.0f} s"

    try:
        while True:
            started = time.monotonic()
            m = metrics.sample()
            fps = fps_monitor.current() if fps_monitor else (None, None)
            rendered = [(t, render(t["metric"], m, fps)) for t in config["tiles"]]

            if dry_run:
                print(" | ".join(f"{t['title']}: {r['value']:.1f} {r['unit']} ({r['secondary']})" for t, r in rendered), flush=True)
            else:
                if not connected and started >= next_retry:
                    try:
                        client.connect()
                        tiles = setup_tiles(client, config)
                        connected = True
                        log.info("Conectado a Polymath; enviando métricas cada %.1f s", interval)
                    except PolymathNotReady as e:
                        log.warning("%s; reintento en %d s", e, RETRY_SECONDS)
                        next_retry = started + RETRY_SECONDS
                    except (ApiError, urllib.error.URLError, OSError) as e:
                        if isinstance(e, ApiError) and e.status == 403:
                            log.error("Polymath ha denegado el acceso a esta aplicación. Revisa la lista de bloqueadas en sus ajustes.")
                            return 1
                        log.warning("No se pudo conectar (%s); reintento en %d s", e, RETRY_SECONDS)
                        next_retry = started + RETRY_SECONDS
                if connected:
                    try:
                        for tile, (_, fields) in zip(tiles, rendered):
                            send(tile, fields, time_unit, config.get("colors", True))
                    except (ApiError, urllib.error.URLError, OSError) as e:
                        log.warning("Se perdió la conexión con Polymath (%s); reconectando", e)
                        connected = False
                        next_retry = started + RETRY_SECONDS

            time.sleep(max(0.0, interval - (time.monotonic() - started)))
    except KeyboardInterrupt:
        log.info("Parando")
        return 0
    finally:
        if fps_monitor:
            fps_monitor.stop()
        metrics.close()


def setup_tiles(client, config):
    """Reutiliza los tiles ya creados en otra ejecución; si Polymath no los conoce, los crea."""
    state = load_state()
    tiles = []
    for t in config["tiles"]:
        tile = GraphTile(client, t["title"], t["index"], config["graph_length"], state.get(f"{t['index']}:{t['title']}"))
        if tile.id:
            try:
                tile.update(0, sub_title=t["title"])
            except ApiError as e:
                if e.status not in (400, 404):
                    raise
                log.info("El tile %r ya no existe en Polymath; se crea de nuevo", tile.title)
                tile.id = None
        if not tile.id:
            tile.create()
        tiles.append(tile)
    save_state(tiles)
    return tiles


def main():
    parser = argparse.ArgumentParser(prog="flux_perf", description="Módulo de rendimiento para Flux Polymath")
    parser.add_argument("--config", type=Path, default=PROJECT_DIR / "config.json")
    parser.add_argument("--dry-run", action="store_true", help="mostrar las métricas en la consola sin enviarlas")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if len(config["tiles"]) > 4:
        parser.error("Polymath solo admite 4 tiles en la barra superior (índices 0-3)")
    return run(config, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
