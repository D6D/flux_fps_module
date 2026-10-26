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
