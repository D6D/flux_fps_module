# Diario del proyecto

## 24-oct-2026: idea

Hacer un módulo de rendimiento para el Flux Polymath, parecido al de serie: CPU, RAM, GPU, VRAM y FPS. También se habló de mostrar el estado de G-Sync. Todavía no teníamos la API.

## 25-oct-2026: primera versión

**Hecho**

- Creada la carpeta `C:\Users\sobremesa\proyectos` y clonado `FluxKeyboard/flux_api` (solo documentación, 0,2 MB).
  - *Decisión:* los proyectos van en **C:** (Samsung 850 EVO, SSD) y no en **E:**, porque E: es un HDD mecánico (Seagate ST1000DM003) y git o las compilaciones van lentos con muchos ficheros pequeños. D: (Kingston SSD) solo tiene 69 GB libres. E: queda para cosas grandes donde la velocidad no importe.
- Revisado el equipo: Polymath 1.4.5.7 (Store) abierto pero con la **API desactivada**. No había Python. Sí hay `nvidia-smi`.
- Instalado **Python 3.13.15** (winget, solo para el usuario) y creado `.venv` con `psutil`, `nvidia-ml-py` y `keyring`.
- Descargado **PresentMon 2.6.0** (consola, firmado por Intel) en `tools\`.
- Escrito el módulo (`flux_perf/`): cliente de la API, métricas, FPS, reconexión automática y `config.json`.
- Probado `--dry-run`: CPU, RAM, GPU (RTX 4070), VRAM, temperatura y consumo leen bien.

**Decisiones**

- **Python**, como el ejemplo oficial; así reutilizamos su forma de autenticarse y de usar TLS.
- **NVML** en vez de lanzar `nvidia-smi` cada segundo: es la misma fuente de datos sin crear un proceso cada vez.
- **PresentMon** para los FPS: es el estándar (lo usan CapFrameX y el overlay de Intel) y no se inyecta en el juego, así que no da problemas con los anticheat. Los FPS son los de la **ventana en primer plano**, calculados como 1000 / media de `MsBetweenPresents` en los últimos 1,5 s.
- **4 tiles como máximo** (la API solo admite los índices 0-3) → la RAM va en la línea secundaria del tile de CPU.
- Las dudas de la API (tipo de tile, forma del PUT) se resuelven probando variantes en tiempo de ejecución. Ver [api-notas.md](api-notas.md).
- **G-Sync**: aplazado. No hay forma sencilla de leer si está activo (haría falta NVAPI, que no tiene paquete oficial para Python). Ideas para más adelante: mostrar si los FPS están por debajo de la frecuencia del monitor, o los Hz actuales.

**Pendiente**

1. Añadir el usuario al grupo «Usuarios del registro de rendimiento» y cerrar sesión (ver [instalacion.md §4](instalacion.md#4-permiso-para-presentmon-️-pendiente)). Claude Code no puede hacerlo porque es una concesión de privilegios; tiene que hacerlo el usuario.
2. Activar la API en Polymath.
3. Primera ejecución real con `-v`: resolver las dudas de [api-notas.md](api-notas.md) y ver cómo queda en el teclado.

Al cerrar la sesión, los pasos 1 y 2 seguían sin hacer. Hay que empezar por ahí la próxima vez.

## 26-oct-2026: primera prueba real con el teclado

**Hecho**

- El usuario activó la API en Polymath (puerto 52323) y se añadió al grupo «Usuarios del registro de rendimiento».
- Primera ejecución con `-v`: conecta, encuentra el certificado en la ruta MSIX y Polymath pide permiso. El usuario lo aceptó y la clave quedó guardada en el Administrador de credenciales.
- Resueltas casi todas las dudas de [api-notas.md](api-notas.md). La documentación oficial se equivoca o se queda corta en tres puntos:
  1. `type` es un entero, y la gráfica es el **`1`**, no el `0`. Al principio probamos `0` (parecía el único tipo) y se crearon tiles **en blanco** sin ID; cualquier PUT sobre ellos daba 500 sin más detalle. La pista salió de la [issue #12](https://github.com/FluxKeyboard/flux_api/issues/12) del repo oficial.
  2. `currentValue` es un número, no un texto.
  3. El PUT va plano, sin envolver, y responde 200 aunque el ID no exista (hay que mirar el `message`).
- Simplificado `polymath.py`: fuera las pruebas de variantes; ahora se envía directamente lo que funciona.
- `setup_tiles` vuelve a crear también los tiles que dan 500 (tiles rotos de ejecuciones anteriores).
- Probado durante ~30 s sin errores y lanzado con `iniciar.bat` en segundo plano.

**Pendiente**

1. Ver cómo queda en el teclado: si se ven las gráficas, si hace falta `POST /config/save` y si el `°` se muestra bien.
2. Probar FPS con un juego (el permiso de PresentMon ya está).
3. Probar qué pasa al reiniciar Polymath con el módulo en marcha.
4. Arranque automático con Windows (ver [instalacion.md](instalacion.md)).

## 26-oct-2026 (mediodía): de 4 tiles a uno solo de FPS

**Hecho**

- Probamos a meterlo todo en un tile («Performance») y a simular la rejilla del «Hardware Status Text» con saltos de línea y tabs: **no se puede**, porque cada texto del tile es de una sola línea (ver [api-notas.md](api-notas.md#cómo-pinta-polymath-un-tile-de-gráfica-visto-en-el-teclado-26-oct-2026)).
- *Decisión:* el usuario usa el **«Hardware Status Text» de serie** para CPU, GPU, memoria y VRAM, y nuestro módulo deja **un solo tile de FPS** en la posición 3. Barra: reloj · tiempo · Hardware Status Text · FPS. Quitado el código del tile «Performance».
- El tile de FPS: FPS en grande y gráfica de 60 s; arriba a la izquierda, el juego (título de la ventana, no el exe) y **G-SYNC** si está actuando; bajo el número, el **1% low** (media del 1% de frames más lentos en los últimos 10 s).
- **G-Sync** con NVAPI por ctypes (`gsync.py`). Comprobado con Forza Horizon 6.
- `/config/save` después de crear un tile (necesita `Content-Type: application/json`).
- PresentMon se relanza solo si se cae (lo tumbaban las ejecuciones de prueba que dejaban otra sesión con el mismo nombre).
- Log siempre a fichero: `%LOCALAPPDATA%\flux_perf\flux_perf.log` (con `pythonw` no había dónde verlo). Incluye qué ventana tiene el foco y qué procesos presentan frames, y cada cambio del estado de G-Sync.
- Todos los textos del teclado, en inglés.

**Pendiente**

1. Si el foco pasa a otra ventana (p. ej. el overlay de Steam) con el juego todavía pintando, el tile pone «No game». Propuesto: usar el proceso que más frames presente (sin contar dwm ni Polymath).
2. El margen inferior del tile no se ve desde la posición del usuario: no se controla por la API; probar con el **Parallax** de Polymath (`eyeHeight`, `displayOffsetY`).
3. ~~Arranque automático con Windows~~ → hecho: acceso directo «Flux Perf Monitor» en `shell:startup` (ver [instalacion.md](instalacion.md)).
4. Commit de todo lo de hoy.
5. Si el usuario quita el tile de FPS de la barra con el módulo en marcha, el módulo lo vuelve a crear en la posición 3 y lo graba en el teclado. Propuesto: respetarlo.

## 16-nov-2026: indicador de HDR

**Hecho**

- Nuevo `hdr.py`: el subtítulo del tile de FPS añade «HDR» cuando Windows tiene el HDR activado en la pantalla del juego. Va igual que «G-SYNC» (solo aparece cuando está activo) y se ve también sin juego («No game · HDR»). Ejemplo: «Forza Horizon 6 · G-SYNC · HDR».
- Probado apagándolo y encendiéndolo con Win+Alt+B (la misma combinación que la macro «HDR» de la tecla Pausa). Detalles en [api-notas.md](api-notas.md#hdr-con-displayconfig-16-nov-2026).
- Módulo reiniciado con el cambio.
- El usuario vio que, con la terminal de Claude en primer plano, el tile la tomaba por un juego (presenta frames) y el texto largo del título tapaba «HDR». Ahora se ignoran también WindowsTerminal, Explorador, Brave, Steam y Evnia Precision Center, y se pueden añadir más con `ignored_apps` en config.json.

**Pendiente**

1. Ver en el teclado si el subtítulo largo (juego · G-SYNC · HDR) cabe o se corta. Si se corta, acortar el nombre del juego.
2. `gsync.py` sigue fijo en DISPLAY1. Ahora solo hay una pantalla, pero si se vuelve a conectar el Acer habrá que usar la misma pantalla que el HDR.

## 16-nov-2026: botón de apagado bloqueado mientras se juega

**Hecho**

- Nuevo `power_guard.py`: si hay un juego abierto, cambia en el plan de energía activo la «Acción de botón de inicio/apagado» (PBUTTONACTION) a «No hacer nada». Al cerrar el juego, o al salir de flux_perf, la deja como estaba (aquí era «Apagar»). Con powercfg no hacen falta permisos de administrador; está comprobado.
- Un proceso cuenta como juego si su .exe está en `steamapps\common` o `XboxGames` (en cualquier unidad), en `game_dirs` (Battle.net\Diablo II Resurrected, E:\gog, E:\Rockstar Games, juegos de Ubisoft) o si está en `games`. Se excluyen lanzadores e instaladores.
- El valor original se guarda en `%LOCALAPPDATA%\flux_perf\power_button.json`, así que se restaura aunque flux_perf se caiga en mitad de una partida.
- Primera prueba real: BF6 abierto, botón a 0 y valor guardado. Como el antitrampas de EA no deja arrancar PresentMon con BF6 abierto, no se reinició flux_perf: para esa partida se usó un proceso aparte que restaura el botón al cerrar el juego.

**Pendiente**

1. Reiniciar flux_perf cuando no haya ningún juego abierto (o esperar al próximo arranque de Windows) para que el bloqueo funcione siempre.
2. Comprobar al cerrar BF6 que el botón vuelve a «Apagar».

## 17-nov-2026: HDR automático por juego

**Hecho**

- Nuevo `hdr_switch.py`: al abrir un juego de `hdr_games` (`D2R.exe`, `bf6.exe`) enciende el HDR en las pantallas que lo admiten y lo tienen apagado; al cerrarlo lo apaga, pero solo donde lo encendió él. Usa `DisplayConfigSetDeviceInfo` con `DISPLAYCONFIG_SET_HDR_STATE` (16, Windows 11 24H2 o posterior) y, si falla, `SET_ADVANCED_COLOR_STATE` (10). No necesita permisos de administrador.
- Las pantallas encendidas se apuntan en `%LOCALAPPDATA%\flux_perf\hdr_switch.json`: si flux_perf se cierra a mitad de partida, al volver a arrancar apaga el HDR cuando no queda ningún juego de la lista abierto. Al salir de flux_perf no lo apaga, para no cambiarlo con el juego en marcha.
- Probado con python.exe haciendo de «juego»: HDR activado → desactivado y fichero borrado. Módulo reiniciado con el cambio (18:33).
- Ampliado a petición del usuario: con `hdr_all_games: true` vale cualquier juego que detecte `power_guard` (su `_find_game` pasa a ser `find_game`, público); `hdr_exclude` para las excepciones. Los juegos sin HDR propio se ven con Auto HDR de Windows (DX11/DX12) o como SDR dentro del HDR.
- Probado con God of War Ragnarök (Steam): HDR encendido solo al abrir GoWR.exe (18:40:49).
- El subtítulo «God of War Ragnarök · G-SYNC · HDR» no cabía: ahora arriba solo va el juego y abajo «1% low N · G-SYNC · HDR» (sin juego: «No game» y debajo los indicadores). Pendiente que el usuario confirme que cabe.
- Estado visto en DISPLAY1 con HDR apagado: modo 1 (WCG), es decir, la gestión automática del color (ACM) está activa en SDR.

**Pendiente**

1. Probarlo de verdad con D2R y BF6: que el juego detecte el HDR al arrancar (se enciende a los ~2 s de aparecer el proceso). Si algún juego arranca en SDR, activar el HDR en su menú o lanzarlo con el HDR ya encendido.
