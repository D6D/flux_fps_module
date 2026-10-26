# Notas sobre la API de Polymath

Fuente: https://github.com/FluxKeyboard/flux_api (clonado en `C:\Users\sobremesa\proyectos\flux_api`). Polymath instalado: **1.4.5.7** (Microsoft Store).

## Lo que dice la documentación

- API REST local en `https://localhost:<puerto>/v1`. Intenta usar el puerto 52323; el real está en `Documents\flux\config\keys.json` → `openPort`, y `apiActive` indica si está encendida.
- TLS con un certificado **autofirmado** que se regenera cuando caduca o cambia la IP. Su ruta está en `keys.json` → `publicKeyLocation`.
- Autenticación: `POST /authentication/register` (sin clave; el usuario tiene que aceptarlo en Polymath) devuelve la clave en `message`. Después, `Authorization: Bearer <clave>` en cada petición. `GET /authentication/check` valida la clave.
- Todas las peticiones llevan `User-Agent` con el nombre de la aplicación.
- Errores relevantes: 401 = clave no válida (pedir otra); 403 = el usuario ha denegado o bloqueado la app.
- **Generic tiles**, lo que usamos para el módulo:
  - `POST /config/addGenericTile` con `{title, type, index (0-3), length (solo en gráficas, ≤ 100 000)}`. Devuelve `message` «con el ID del nuevo tile». La documentación añade que *«the ID will be directly comparable to the title»*.
  - `PUT /config/updateGenericTile` con un `GenericGraphUpdateRequest`: `id, subTitle, unit, secondarySubtitle, timeUnit, currentValue (string, se trunca a 2 decimales), color, leading, ending`. **En la práctica, `currentValue` tiene que ser un número; ver más abajo.**
  - Colores: `Legend, Red, Orange, Yellow, Lime, Green, Cyan, Blue, Purple, Pink, White`. Un color no válido usa el del tema.

## Lo que la documentación NO aclara o dice mal (comprobado el 26-oct-2026 con Polymath 1.4.5.7)

| Duda | Respuesta real | Estado |
| ---- | -------------- | ------ |
| Valores de `GenericModuleType` | Es un **entero**: `0` = tile **en blanco**, `1` = **gráfica**. Con texto da `400 "type must be an int"`; fuera de rango, `400 "type must be between 0 and 1"`. Lo confirmó el mantenedor en la [issue #12](https://github.com/FluxKeyboard/flux_api/issues/12). ⚠️ Con `0` el tile se crea pero queda **sin ID ni título**, y cualquier PUT sobre él da **500**. | ✅ |
| ¿El PUT va envuelto en `GenericGraphUpdateRequest` o plano? | **Plano**. Envuelto da `400 "Request body must contain a \"id\" key"`. | ✅ |
| Tipo de `currentValue` | La documentación dice String, pero la API exige un **número**: con texto da `400 "currentValue must be an double"`. | ✅ |
| Respuesta del PUT con un ID que no existe | **HTTP 200** con `{"message": "Module ID does not exist. Have you added it yet?"}`. Hay que mirar el `message`; el código lo convierte en un 404. | ✅ |
| Formato del `message` de creación | El ID a secas, igual al título (`"CPU"`). | ✅ |
| ¿Qué pasa al crear un tile en una posición ocupada? | Lo sustituye. Si el tile anterior era de otro tipo (p. ej. el tiempo), la configuración puede quedar mezclada; ver más abajo. | ✅ |
| ¿Los tiles persisten al reiniciar Polymath? | Se guardan en `Documents\flux\config\mosaic.json`. El código guarda los IDs en `state.json`; al arrancar intenta actualizarlos y, si da 400/404/500, los vuelve a crear. | ✅ (falta probar un reinicio de Polymath) |
| ¿Hace falta `POST /config/save` para que se vean en el teclado? | De momento no se llama. | ❓ pendiente de ver en el teclado |
| ¿Se ve bien el carácter `°` en la pantalla del teclado? | Se envía tal cual. | ❓ pendiente de ver en el teclado |
| Creación lenta | Cada `addGenericTile` tarda ~2-4 s. | ℹ️ |

### Cómo guarda Polymath los tiles (`mosaic.json`)

```json
{"tileTypes":[18,18,18,18],
 "tileConfigs":[{"identifier":18,"title":"CPU","subTitle":"","unit":"","secondarySubtutle":"",
                 "length":"60","selectedColor":"Legend","color":null,"id":"CPU","type":1}, ...]}
```

`18` es el tipo «generic tile» de la barra. Ojo con la errata de Polymath, `secondarySubtutle`: es su formato interno y no afecta a la API, donde la clave sigue siendo `secondarySubtitle`.

### Depuración

Cuando el servidor da 500, Polymath intenta escribir la excepción en una consola que no existe, así que solo queda un `polymath_crash_*.log` en `Documents\flux\logs` con `FileSystemException: writeFrom failed` y sin la causa real. Un 500 en `updateGenericTile` casi siempre significa que el tile existe pero está mal creado (con `type: 0`).

## Trampa: Polymath de la Microsoft Store (MSIX)

El ejemplo oficial busca el certificado en `%APPDATA%\com.fluxkeyboard\polymath\tls\cert.pem`. Pero una app MSIX tiene `%APPDATA%` **redirigido** a:

```
%LOCALAPPDATA%\Packages\FluxGroup.FluxPolymath_42m5gadgr7drm\LocalCache\Roaming\com.fluxkeyboard\polymath\
```

Allí están ya `flutter_secure_storage.dat` y `shared_preferences.json` (Polymath está hecho con Flutter). `polymath.find_cert()` busca primero en `publicKeyLocation` (puede ser el fichero o la carpeta), luego en la ruta del ejemplo y por último en la ruta MSIX.

`Documents\flux\config\` **no** está redirigida: es una carpeta real y es donde lee el ejemplo.

## Otros procesos de Polymath

Polymath trae sus propios «bridges» como procesos aparte: `FluxPolymathHardwareMonitoringBridge.exe` (su módulo de rendimiento de serie) y `FluxPolymathActiveMediaBridge.exe`. No interactuamos con ellos.

## Cómo pinta Polymath un tile de gráfica (visto en el teclado, 26-oct-2026)

```
┌──────────────────────────────────────────┐
│ <title>                  <leading><currentValue> <unit><ending> │
│ <subTitle>                       <secondarySubtitle>            │
│ [ gráfica de <length> puntos ]                                  │
│ <length> <timeUnit>                                             │
└──────────────────────────────────────────┘
```

- Cada texto ocupa **una sola línea**: los `\n` y lo que venga detrás se descartan, y los tabs se convierten en espacios. **No se puede simular una rejilla** como la del «Hardware Status Text» de serie.
- El `title` no se puede cambiar después de crear el tile (es el ID).
- Bajo la gráfica se pinta `<length> <timeUnit>`, así que `timeUnit` tiene que ser solo la unidad (`s`).
- Con `length: 1` la gráfica queda vacía, solo con las líneas guía.
- El `color` que pedimos no se respetó en las pruebas (pedimos cian y salió el del tema). Pendiente de confirmar.
- El número grande siempre sale con un decimal (`99.0`).
- `POST /config/save` (grabar en el teclado) exige `Content-Type: application/json` aunque no lleve cuerpo; sin él da **403**. Hace falta llamarlo después de crear un tile para que aparezca en el teclado; las actualizaciones (PUT) se ven sin grabar.

## G-Sync con NVAPI

`NvAPI_Disp_GetVRRInfo` (ID `0xDF8FDA57`) con el displayId de `\.\DISPLAY1` (`NvAPI_DISP_GetDisplayIdByDisplayName`, `0xAE457190`). Comprobado con Forza Horizon 6:

| Bit | Sin juego | Jugando con G-Sync |
| --- | --------- | ------------------ |
| `bIsVRREnabled` | 0 | **1** ← el que usamos |
| `bIsVRRPossible` | 1 | 1 |
| `bIsVRRRequested` | 0 | 1 |
| `bIsVRRIndicatorEnabled` | 1 | 1 (es el ajuste del indicador de NVIDIA) |
| `bIsDisplayInVRRMode` | 1 | 1 (G-Sync configurado en la pantalla) |

Al pasar el foco a otra ventana (p. ej. Steam), `enabled` vuelve a 0: el driver solo aplica G-Sync a la ventana activa.
