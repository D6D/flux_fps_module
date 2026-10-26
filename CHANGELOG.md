# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-10-26

First version working on the keyboard.

### Added
- G-Sync status on the FPS tile, read from NVAPI (`NvAPI_Disp_GetVRRInfo`).
- 1% low FPS over the last 10 seconds.
- Game name from the foreground window title instead of the executable name.
- `POST /config/save` after creating a tile, so it shows up on the keyboard.
- Log file at `%LOCALAPPDATA%\flux_perf\flux_perf.log` (with `pythonw` there was no console).
- Focus and frame diagnostics in the log, to troubleshoot games whose FPS don't show.
- PresentMon is restarted automatically if it exits.
- `config.4tiles.json` with the old four-tile layout.

### Changed
- Default layout is now a single FPS tile at position 3, meant to sit next to Polymath's built-in Hardware Status Text tile.
- Polymath API calls fixed to match the real API: `type: 1` for graph tiles, flat update body, numeric `currentValue`, errors detected from `message`.
- Tiles that return HTTP 500 (broken leftovers) are recreated.
- Texts on the keyboard are in English.
- The graph's time label is just the unit (`s`), since Polymath already prints the length.

## [0.1.0] - 2026-10-25

### Added
- First version: CPU, GPU, VRAM and FPS graph tiles through the Polymath API.
- Metrics from psutil (CPU/RAM), NVML (GPU/VRAM, temperature, power) and PresentMon (FPS).
- API client with TLS certificate lookup (including the Microsoft Store install path) and API key stored in Windows Credential Manager.
- Automatic reconnection when Polymath or its API isn't available.
- `--dry-run` mode and `iniciar.bat` to run in the background.

[0.2.0]: https://github.com/D6D/flux_fps_module/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/D6D/flux_fps_module/releases/tag/v0.1.0
