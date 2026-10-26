# Instalación

Pasos para dejarlo funcionando en un Windows recién instalado. En el PC de sobremesa están todos hechos (25 y 26-oct-2026).

## 1. Python

```powershell
winget install --id Python.Python.3.13 -e --scope user
```

Se instala en `%LOCALAPPDATA%\Programs\Python\Python313\`. Ojo: si no está instalado, el comando `python` abre la Microsoft Store (es un alias de Windows), así que no sirve para comprobar si hay Python.

## 2. Entorno virtual y dependencias

```powershell
cd C:\Users\sobremesa\proyectos\flux_perf
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

| Paquete | Para qué |
| ------- | -------- |
| `psutil` | carga de CPU y uso de RAM |
| `nvidia-ml-py` | GPU, VRAM, temperatura y consumo mediante NVML, la librería del driver de NVIDIA (no hace falta abrir `nvidia-smi`) |
| `keyring` | guardar la clave de la API en el Administrador de credenciales de Windows |

## 3. PresentMon (para los FPS)

Es la herramienta de Intel para medir los frames presentados (código abierto, firmada por Intel Corporation). Usamos la versión de consola:

```powershell
$rel = Invoke-RestMethod https://api.github.com/repos/GameTechDev/PresentMon/releases/latest
# buscar el asset PresentMon-<versión>-x64.exe y guardarlo como tools\PresentMon.exe
```

Instalada: **v2.6.0** (21-sep-2026).

## 4. Permiso para PresentMon

PresentMon lee eventos ETW del sistema. Para eso necesita **o bien ejecutarse como administrador, o bien que el usuario esté en el grupo «Usuarios del registro de rendimiento»** (*Performance Log Users*, SID `S-1-5-32-559`). Sin esto, el tile de FPS muestra «sin juego» y el log avisa con `PresentMon sin permisos`.

Recomendamos la opción del grupo: se hace una vez y el módulo puede funcionar sin privilegios. En un PowerShell **como administrador**:

```powershell
Add-LocalGroupMember -SID 'S-1-5-32-559' -Member "$env:USERDOMAIN\$env:USERNAME"
```

Después hay que **cerrar sesión y volver a entrar**, porque la pertenencia a grupos solo se aplica al iniciar sesión.

## 5. Activar la API en Polymath

En Polymath → Ajustes → API: activarla. Al hacerlo, Polymath:

- pone `apiActive: true` y el puerto (normalmente el 52323) en `Documents\flux\config\keys.json`;
- genera el certificado TLS autofirmado.

La primera vez que se ejecute el módulo, Polymath mostrará una solicitud de acceso para «Flux Perf Monitor». Si la aceptas, la clave se guarda en el Administrador de credenciales (servicio `com.sobremesa.fluxperf`). Si la rechazas, la app queda bloqueada y hay que quitarla de la lista de bloqueadas en los ajustes de Polymath.

## 6. Arranque automático (opcional)

Para que se inicie al entrar en Windows hay un acceso directo **«Flux Perf Monitor»** en la carpeta de inicio (`Win+R` → `shell:startup`), configurado el 26-oct-2026. Apunta directamente a `.venv\Scripts\pythonw.exe -m flux_perf` con la carpeta del proyecto como directorio de trabajo, en vez de a `iniciar.bat`, para que no aparezca ni un instante la ventana de consola. El módulo espera solo a que Polymath y su API estén disponibles: lo reintenta cada 5 s.

Para quitar el arranque automático, borra ese acceso directo.
