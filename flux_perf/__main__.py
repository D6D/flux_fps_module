"""Módulo de rendimiento para Flux Polymath.

Uso:
    python -m flux_perf              # envía las métricas al teclado
    python -m flux_perf --dry-run    # solo las muestra en la consola, sin tocar Polymath
"""
import argparse
import json
import logging
import logging.handlers
import os
import sys
import time
import urllib.error
from pathlib import Path

from .fps import FpsMonitor
from .gsync import GSyncMonitor
from .hdr import HdrMonitor
from .hdr_switch import HdrAutoSwitcher
from .metrics import SystemMetrics
from .mosaic_switch import MosaicSwitcher
from .power_guard import PowerButtonGuard
from .polymath import ApiError, GraphTile, PolymathClient, PolymathNotReady

log = logging.getLogger("flux_perf")

PROJECT_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = Path(os.environ.get("LOCALAPPDATA", ".")) / "flux_perf" / "state.json"
LOG_FILE = STATE_FILE.with_name("flux_perf.log")
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
        return dict(value=m["cpu"], unit="%", sub_title="CPU load",
                    secondary=f"RAM {m['ram_used_gb']:.1f}/{m['ram_total_gb']:.0f} GB",
                    color=load_color(m["cpu"], 60, 85))
    if metric == "ram":
        return dict(value=m["ram_pct"], unit="%", sub_title="Memory",
                    secondary=f"{m['ram_used_gb']:.1f}/{m['ram_total_gb']:.0f} GB",
                    color=load_color(m["ram_pct"], 70, 90))
    if metric == "gpu":
        if "gpu" not in m:
            return dict(value=0, unit="%", sub_title="GPU load", secondary="no data", color="Legend")
        return dict(value=m["gpu"], unit="%", sub_title="GPU load",
                    secondary=f"{m['gpu_temp']} °C · {m['gpu_power_w']:.0f} W",
                    color=load_color(m["gpu"], 80, 95))
    if metric == "vram":
        if "vram_used_gb" not in m:
            return dict(value=0, unit="GB", sub_title="VRAM", secondary="no data", color="Legend")
        return dict(value=m["vram_used_gb"], unit="GB", sub_title="VRAM",
                    secondary=f"{m['vram_pct']:.0f}% of {m['vram_total_gb']:.0f} GB",
                    color=load_color(m["vram_pct"], 75, 90))
    if metric == "fps":
        value, low, app, gsync, hdr = fps
        # El título del tile ya dice «FPS». Arriba solo va el juego (con G-SYNC y HDR al lado no
        # cabía: «God of War Ragnarök · G-SYNC · HDR»); abajo, el 1% low y los indicadores.
        # HDR se muestra también sin juego: depende de Windows, no del juego.
        flags = " · ".join(f for f, on in (("G-SYNC", gsync and value is not None), ("HDR", hdr)) if on)
        if value is None:
            return dict(value=0, unit="FPS", sub_title="No game", secondary=flags, color="Legend")
        low_txt = f"1% low {low:.0f}" if low is not None else ""
        return dict(value=round(value), unit="FPS", sub_title=app or "",
                    secondary=" · ".join(x for x in (low_txt, flags) if x),
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
    fps_monitor = gsync = hdr = None
    if any(t["metric"] == "fps" for t in config["tiles"]):
        fps_monitor = FpsMonitor(PROJECT_DIR / config["presentmon_path"], config.get("ignored_apps", []))
        fps_monitor.start()
        gsync = GSyncMonitor()
        hdr = HdrMonitor()

    client = PolymathClient()
    switcher = MosaicSwitcher(config.get("mosaic_rules", []))
    guard = None
    if config.get("block_power_button", True):
        guard = PowerButtonGuard(config.get("game_dirs", []), config.get("games", []))
    finder = None
    if config.get("hdr_all_games"):
        finder = (guard or PowerButtonGuard(config.get("game_dirs", []), config.get("games", []))).find_game
    hdr_switch = HdrAutoSwitcher(config.get("hdr_games", []), finder, config.get("hdr_exclude", []))
    tiles = []
    connected = False
    next_retry = 0
    interval = config["interval_seconds"]
    # Polymath pinta «<length> <timeUnit>» bajo la gráfica, así que solo hace falta la unidad.
    time_unit = "s" if interval == 1 else f"× {interval:g} s"

    try:
        while True:
            started = time.monotonic()
            m = metrics.sample()
            fps = (*fps_monitor.current(), gsync.active(), hdr.active()) if fps_monitor else (None,) * 5
            rendered = [(t, render(t["metric"], m, fps)) for t in config["tiles"]]
            if guard:
                try:
                    guard.poll()
                except Exception:
                    log.exception("Error con el botón de apagado")
            try:
                hdr_switch.poll()
            except Exception:
                log.exception("Error cambiando el HDR")

            if dry_run:
                print(" | ".join(f"{t['title']}: {r['value']:.1f} {r['unit']} ({r['secondary']})" for t, r in rendered), flush=True)
            else:
                try:
                    if switcher.poll():
                        connected, next_retry = False, 0
                except Exception:
                    log.exception("Error cambiando los módulos de Polymath")
                # En modo juego los módulos los fija el switcher: no se crean ni se actualizan tiles.
                if switcher.game_mode:
                    connected = False
                elif not connected and started >= next_retry:
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
                            log.error("Polymath ha denegado el acceso (%s). Revisa la lista de bloqueadas en sus ajustes.", e)
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
        if guard:
            try:
                guard.restore()
            except Exception:
                log.exception("No se pudo restaurar el botón de apagado")
        if fps_monitor:
            fps_monitor.stop()
        metrics.close()


def setup_tiles(client, config):
    """Reutiliza los tiles ya creados en otra ejecución; si Polymath no los conoce, los crea."""
    state = load_state()
    tiles = []
    created = False
    for t in config["tiles"]:
        tile = GraphTile(client, t["title"], t["index"], config["graph_length"], state.get(f"{t['index']}:{t['title']}"))
        if tile.id:
            try:
                tile.update(0, sub_title=t["title"])
            except ApiError as e:
                if e.status not in (400, 404, 500):
                    raise
                log.info("El tile %r no existe o está roto en Polymath (%s); se crea de nuevo", tile.title, e)
                tile.id = None
        if not tile.id:
            tile.create()
            created = True
        tiles.append(tile)
    save_state(tiles)
    if created:
        # Un tile nuevo no aparece en el teclado hasta que se graba la configuración. Aunque no
        # lleva cuerpo, Polymath exige Content-Type JSON (si no, 403), así que se manda {}.
        log.info("Grabando la configuración en el teclado: %s", client.post("/config/save", {}, timeout=60))
    return tiles


def main():
    parser = argparse.ArgumentParser(prog="flux_perf", description="Módulo de rendimiento para Flux Polymath")
    parser.add_argument("--config", type=Path, default=PROJECT_DIR / "config.json")
    parser.add_argument("--dry-run", action="store_true", help="mostrar las métricas en la consola sin enviarlas")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    # Con pythonw (iniciar.bat) no hay consola, así que el log va siempre también a un fichero.
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handlers = [logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=1, encoding="utf-8")]
    if sys.stderr:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if len(config["tiles"]) > 4:
        parser.error("Polymath solo admite 4 tiles en la barra superior (índices 0-3)")
    return run(config, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
