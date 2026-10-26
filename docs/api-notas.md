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
  - `PUT /config/updateGenericTile` con un `GenericGraphUpdateRequest`: `id, subTitle, unit, secondarySubtitle, timeUnit, currentValue (string, se trunca a 2 decimales), color, leading, ending`.
  - Colores: `Legend, Red, Orange, Yellow, Lime, Green, Cyan, Blue, Purple, Pink, White`. Un color no válido usa el del tema.

## Lo que la documentación NO aclara (y cómo lo resolvemos)

| Duda | Qué hace el código | Estado |
| ---- | ------------------ | ------ |
| Valores de `GenericModuleType`: no hay página de ese modelo | prueba `graph`, `Graph`, `GRAPH`, `genericGraph` y `GenericGraph` hasta que uno no da 400/422, y lo registra en el log | ❓ pendiente de probar con la API activa |
| ¿El cuerpo del PUT va envuelto en `{"GenericGraphUpdateRequest": {...}}` o es plano? | prueba primero envuelto y después plano; recuerda el que funciona y lo registra | ❓ pendiente |
| Formato del `message` de creación: ¿el ID a secas o una frase? | si es un único token, lo usa como ID; si no, usa el título | ❓ pendiente |
| ¿Los tiles persisten al reiniciar Polymath? ¿Qué pasa al crear uno que ya existe? | guarda los IDs en `state.json`; al arrancar intenta actualizarlos y, si da 400/404, los vuelve a crear | ❓ pendiente |
| ¿Hace falta `POST /config/save` para que se vean en el teclado? | de momento no se llama | ❓ pendiente |
| ¿Se ve bien el carácter `°` en la pantalla del teclado? | se envía tal cual | ❓ pendiente |

Cuando la API esté activa, lanzar `python -m flux_perf -v` y apuntar aquí lo que salga en el log.

## Trampa: Polymath de la Microsoft Store (MSIX)

El ejemplo oficial busca el certificado en `%APPDATA%\com.fluxkeyboard\polymath\tls\cert.pem`. Pero una app MSIX tiene `%APPDATA%` **redirigido** a:

```
%LOCALAPPDATA%\Packages\FluxGroup.FluxPolymath_42m5gadgr7drm\LocalCache\Roaming\com.fluxkeyboard\polymath\
```

Allí están ya `flutter_secure_storage.dat` y `shared_preferences.json` (Polymath está hecho con Flutter). `polymath.find_cert()` busca primero en `publicKeyLocation` (puede ser el fichero o la carpeta), luego en la ruta del ejemplo y por último en la ruta MSIX.

`Documents\flux\config\` **no** está redirigida: es una carpeta real y es donde lee el ejemplo.

## Otros procesos de Polymath

Polymath trae sus propios «bridges» como procesos aparte: `FluxPolymathHardwareMonitoringBridge.exe` (su módulo de rendimiento de serie) y `FluxPolymathActiveMediaBridge.exe`. No interactuamos con ellos.
