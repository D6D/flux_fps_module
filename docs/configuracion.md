# Configuración (`config.json`)

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

Por defecto hay un solo tile de FPS en la posición 3, al lado del «Hardware Status Text» de serie de Polymath. La configuración antigua de cuatro tiles (CPU, GPU, VRAM y FPS) está en `config.4tiles.json`.

| Clave | Significado |
| ----- | ----------- |
| `interval_seconds` | cada cuánto se envía un valor nuevo |
| `graph_length` | puntos del eje X de cada gráfica (máximo 100 000 según la API). Con 60 puntos y 1 s de intervalo, la gráfica cubre el último minuto |
| `presentmon_path` | ruta a PresentMon, relativa a la carpeta del proyecto |
| `colors` | `true`: verde/amarillo/rojo según la carga; `false`: el color del tema del perfil (`Legend`) |
| `tiles` | máximo 4: la barra superior del Polymath solo tiene las posiciones 0 a 3 |
| `ignored_apps` | (opcional) ejecutables que no cuentan como juego aunque presenten frames, p. ej. `["Discord.exe"]`. Se suman a los de serie: terminal, Explorador, Brave, Steam, Evnia Precision Center, Polymath y dwm |
| `block_power_button` | `true` (por defecto): mientras hay un juego abierto, el botón físico de apagado del PC no hace nada; al cerrarlo vuelve a lo que tenía. Mantenerlo pulsado 4 s sigue apagando el PC (eso va por hardware) |
| `game_dirs` | carpetas cuyos .exe cuentan como juego, además de cualquier `steamapps\common` y `XboxGames` |
| `games` | nombres de ejecutables que cuentan como juego estén donde estén, p. ej. `["D2R.exe"]` |
| `hdr_games` | ejecutables que encienden el HDR de Windows al abrirse, p. ej. `["D2R.exe", "bf6.exe"]`. Al cerrarlos se apaga solo en las pantallas donde lo encendió flux_perf (si ya estaba activado a mano, se deja). Lista vacía = desactivado |
| `hdr_all_games` | `true`: además de `hdr_games`, enciende el HDR con cualquier juego que detecte el bloqueo del botón de apagado (carpetas de Steam/Xbox, `game_dirs` y `games`) |
| `hdr_exclude` | ejecutables que nunca encienden el HDR aunque se detecten como juego, p. ej. uno que se vea mal en HDR |

## Métricas

| `metric` | Valor | Línea secundaria | Amarillo / rojo a partir de |
| -------- | ----- | ---------------- | --------------------------- |
| `cpu` | carga CPU % | RAM usada/total | 60 % / 85 % |
| `ram` | RAM % | GB usados/total | 70 % / 90 % |
| `gpu` | carga GPU % | °C · W | 80 % / 95 % |
| `vram` | GB usados | % del total | 75 % / 90 % |
| `fps` | FPS de la ventana activa | arriba: juego (título de la ventana), «G-SYNC» si está actuando y «HDR» si Windows tiene el HDR activado en esa pantalla (también sin juego: «No game · HDR»); bajo el número: 1% low | por debajo de 45 / 30 FPS |

En la configuración de cuatro tiles la RAM va en la línea secundaria del tile de CPU, porque solo caben 4 tiles y hay 5 métricas.

Los umbrales están en la función `render()` de `flux_perf/__main__.py`.

## Ficheros que genera

- `%LOCALAPPDATA%\flux_perf\state.json`: los IDs de los tiles creados, para no crearlos repetidos en cada arranque. Si cambias `index` o `title`, se crea un tile nuevo (puede que haya que borrar el antiguo a mano en Polymath).
- La clave de la API, en el Administrador de credenciales de Windows (servicio `com.sobremesa.fluxperf`).
