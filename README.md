# flux_perf: módulo de rendimiento para Flux Polymath

Muestra en la barra superior del teclado **Flux Polymath** cuatro gráficas en tiempo real:

| Posición | Tile | Valor | Línea secundaria |
| -------- | ---- | ----- | ---------------- |
| 0 | CPU  | carga de CPU (%) | RAM usada / total |
| 1 | GPU  | carga de GPU (%) | temperatura · consumo |
| 2 | VRAM | VRAM usada (GB) | % de la VRAM total |
| 3 | FPS  | FPS de la ventana en primer plano | nombre del juego |

El color de cada gráfica cambia a verde, amarillo o rojo según la carga. Se puede desactivar con `"colors": false`.

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
│   └── fps.py        FPS con PresentMon
├── config.json
├── iniciar.bat
├── requirements.txt
├── tools/            PresentMon.exe (no va en git)
└── docs/
```
