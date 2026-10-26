# flux_fps_module

Adds an **FPS tile** to the top bar of the [Flux keyboard](https://fluxkeyboard.com) through the official [Polymath API](https://github.com/FluxKeyboard/flux_api). It shows the current FPS, the game you're playing, FPS lows (1% low) and whether G-Sync is active:

```
FPS                                   144.0 FPS
Forza Horizon 6 · G-SYNC          1% low 98
[ FPS graph, last 60 s ]
```

- **FPS** of the foreground window, measured with [PresentMon](https://github.com/GameTechDev/PresentMon) (Intel). It doesn't inject anything into the game, so it's safe with anti-cheat.
- **Game name**, taken from the window title.
- **G-SYNC** when the driver is actually applying it, read from NVAPI (same thing the NVIDIA G-Sync indicator shows).
- **1% low**: average of the slowest 1% of frames over the last 10 s, the usual way to spot stutter.
- Colour changes with FPS: green, yellow below 45, red below 30.

It's meant to sit next to Polymath's built-in **Hardware Status Text** tile, which already covers CPU, GPU, memory and VRAM.

## Requirements

- Windows 10/11 and a Flux keyboard with **Polymath** (tested with 1.4.5.7, Microsoft Store version).
- An **NVIDIA** GPU for G-Sync (FPS works with any GPU).
- **Python 3.13**.
- **PresentMon** console build (tested with 2.6.0).

## Setup

```powershell
git clone https://github.com/D6D/flux_fps_module.git
cd flux_fps_module
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

1. **PresentMon:** download `PresentMon-<version>-x64.exe` from its [releases](https://github.com/GameTechDev/PresentMon/releases) and save it as `tools\PresentMon.exe`.
2. **Permission for PresentMon:** it reads system ETW events, so your user must be in the *Performance Log Users* group. In an **admin** PowerShell, then sign out and back in:
   ```powershell
   Add-LocalGroupMember -SID 'S-1-5-32-559' -Member "$env:USERDOMAIN\$env:USERNAME"
   ```
3. **Enable the API** in Polymath's settings.
4. **Run it:**
   ```powershell
   .venv\Scripts\python.exe -m flux_perf --dry-run   # print metrics to the console only
   .venv\Scripts\python.exe -m flux_perf -v          # send them to the keyboard, verbose
   .\iniciar.bat                                     # run in the background, no window
   ```
   The first time, Polymath asks you to allow **"Flux Perf Monitor"**. The API key is stored in Windows Credential Manager.
5. **Start with Windows (optional):** put a shortcut in `shell:startup` pointing to `.venv\Scripts\pythonw.exe` with arguments `-m flux_perf` and the project folder as "Start in".

The log goes to `%LOCALAPPDATA%\flux_perf\flux_perf.log`.

## Configuration

`config.json`:

```json
{
  "interval_seconds": 1.0,
  "graph_length": 60,
  "presentmon_path": "tools/PresentMon.exe",
  "colors": true,
  "tiles": [
    { "index": 3, "title": "FPS", "metric": "fps" }
  ]
}
```

`index` is the position in the top bar (0–3). The code can also draw `cpu`, `gpu`, `ram` and `vram` tiles (see `config.4tiles.json`), although the built-in tile looks better for those.

## Polymath API: things the docs don't tell you

Found by testing against Polymath 1.4.5.7 (details in [docs/api-notas.md](docs/api-notas.md), in Spanish):

- `addGenericTile`: `type` is an **int**, and **`1` is the graph** (`0` is a blank tile you can't update).
- `updateGenericTile`: the body is **flat** (not wrapped in `GenericGraphUpdateRequest`) and `currentValue` must be a **number** (a double: `60.0`, not `60`).
- An unknown tile ID returns **HTTP 200** with `"Module ID does not exist…"` in `message`.
- New tiles only show up on the keyboard after `POST /config/save`, which needs `Content-Type: application/json` even with no body (otherwise **403**).
- Every text field is rendered on **one line**: newlines and tabs are dropped, so a multi-value grid inside a tile isn't possible.

## Project layout

```
flux_perf/
├── __main__.py   main loop, tile rendering, reconnection
├── polymath.py   Polymath API client (TLS, key, tiles)
├── fps.py        FPS and 1% low with PresentMon
├── gsync.py      G-Sync status with NVAPI
└── metrics.py    CPU/RAM (psutil) and GPU/VRAM (NVML)
docs/             notes, setup and dev journal (Spanish)
```

See [CHANGELOG.md](CHANGELOG.md) for the history.

## License

[PolyForm Noncommercial 1.0.0](LICENSE.md): free to use, modify and share for **noncommercial** purposes. Selling it or using it in a commercial product is not allowed. PresentMon and the Polymath API have their own terms.
