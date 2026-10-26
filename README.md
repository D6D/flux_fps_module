# flux_perf: módulo de rendimiento para Flux Polymath

Muestra en la barra superior del teclado **Flux Polymath** un tile de **FPS** (posición 3, al lado del «Hardware Status Text» de serie):

```
FPS                                   144.0 FPS
Forza Horizon 6 · G-SYNC          1% low 98
[ gráfica de los últimos 60 s ]
```

- FPS de la ventana en primer plano (PresentMon) y su gráfica.
- Nombre del juego (título de la ventana) y **G-SYNC** cuando está actuando (NVAPI).
- **1% low**: media del 1% de frames más lentos de los últimos 10 s.
- Color verde, amarillo o rojo según los FPS (`"colors": false` para desactivarlo).

El código también admite tiles de CPU, GPU, RAM y VRAM (métricas `cpu`, `gpu`, `ram`, `vram`; hay un ejemplo en `config.4tiles.json`), pero para eso el módulo de serie se ve mejor: la API no permite una rejilla en un tile (ver [docs/api-notas.md](docs/api-notas.md)).

Usa la [API oficial de Polymath](https://github.com/FluxKeyboard/flux_api) (clonada en `..\flux_api`).

## Uso rápido

```powershell
cd C:\Users\sobremesa\proyectos\flux_perf
.venv\Scripts\python.exe -m flux_perf --dry-run   # probar las métricas en la consola
.venv\Scripts\python.exe -m flux_perf             # enviarlas al teclado
.\iniciar.bat                                     # lo mismo, en segundo plano y sin ventana
```

La primera vez, Polymath pide permiso para la aplicación «Flux Perf Monitor». Hay que aceptarlo.

## Documentación

- [docs/instalacion.md](docs/instalacion.md): puesta en marcha desde cero y arranque automático.
- [docs/configuracion.md](docs/configuracion.md): `config.json`, métricas disponibles y colores.
- [docs/api-notas.md](docs/api-notas.md): lo que hemos aprendido de la API, incluido lo que la documentación oficial no dice.
- [docs/diario.md](docs/diario.md): registro de lo que hemos ido haciendo y por qué.

## Estructura

```
flux_perf/
├── flux_perf/
│   ├── __main__.py   bucle principal, render de métricas y reconexión
│   ├── polymath.py   cliente de la API (TLS, clave, tiles)
│   ├── metrics.py    CPU/RAM (psutil) y GPU/VRAM (NVML)
│   ├── fps.py        FPS y 1% low con PresentMon
│   └── gsync.py      estado de G-Sync con NVAPI
├── config.json
├── iniciar.bat
├── requirements.txt
├── tools/            PresentMon.exe (no va en git)
└── docs/
```
