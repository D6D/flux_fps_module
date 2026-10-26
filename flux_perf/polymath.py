"""Cliente para la API local de Flux Polymath.

Basado en el ejemplo oficial (flux_api/Examples/BlenderShortcutContextSwitcher), con dos
cambios: localiza el certificado aunque Polymath esté instalado desde la Microsoft Store
(MSIX redirige %APPDATA%) y prueba las variantes de payload que la documentación no aclara.
"""
import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path

import keyring

log = logging.getLogger(__name__)

USER_AGENT = "Flux Perf Monitor"
KEYRING_SERVICE = "com.sobremesa.fluxperf"
KEYRING_ACCOUNT = "com.fluxkeyboard.polymath"

CONFIG_DIR = Path.home() / "Documents" / "flux" / "config"
MSIX_ROAMING = Path(os.environ.get("LOCALAPPDATA", "")) / "Packages" / "FluxGroup.FluxPolymath_42m5gadgr7drm" / "LocalCache" / "Roaming"


class ApiError(Exception):
    def __init__(self, status, body=""):
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.body = body


class PolymathNotReady(Exception):
    """La API está desactivada, Polymath no está abierto o falta el certificado."""


def read_keys_json():
    try:
        with open(CONFIG_DIR / "keys.json", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return None


def find_cert(keys):
    # La documentación dice que la ruta está en keys.json -> publicKeyLocation; puede ser
    # el fichero o la carpeta. Si no viene, probamos la ruta del ejemplo y la de la Store.
    candidates = []
    location = (keys or {}).get("publicKeyLocation")
    if location:
        p = Path(location)
        candidates += [p, p / "cert.pem"]
    for base in (Path(os.environ.get("APPDATA", "")), MSIX_ROAMING):
        candidates.append(base / "com.fluxkeyboard" / "polymath" / "tls" / "cert.pem")
    for c in candidates:
        if c.is_file():
            return c
    return None


class PolymathClient:
    def __init__(self):
        self.port = None
        self.api_key = None
        self.ssl_context = None

    def connect(self):
        keys = read_keys_json()
        if not keys:
            raise PolymathNotReady(f"No se puede leer {CONFIG_DIR / 'keys.json'}; ¿está instalado Polymath?")
        if not keys.get("apiActive") or not keys.get("openPort"):
            raise PolymathNotReady("La API de Polymath está desactivada (actívala en los ajustes de Polymath)")
        cert = find_cert(keys)
        if not cert:
            raise PolymathNotReady("No se encuentra el certificado TLS de Polymath")
        self.port = keys["openPort"]
        self.ssl_context = ssl.create_default_context(cafile=str(cert))
        log.debug("Puerto %s, certificado %s", self.port, cert)

        self.get("/docs")  # ping sin autenticación
        self._authenticate()

    def _authenticate(self):
        self.api_key = keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        if self.api_key:
            try:
                self.get("/authentication/check")
                return
            except ApiError as e:
                if e.status != 401:
                    raise
                log.info("La clave guardada ya no vale; pidiendo una nueva")
                self.api_key = None
        log.info("Pidiendo acceso a Polymath: acepta la solicitud en la ventana de Polymath")
        result = self.post("/authentication/register", {}, timeout=120)
        self.api_key = result["message"]
        keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, self.api_key)
        log.info("Acceso concedido; clave guardada en el Administrador de credenciales de Windows")

    def get(self, path):
        return self._request("GET", path)

    def post(self, path, payload, timeout=10):
        return self._request("POST", path, payload, timeout)

    def put(self, path, payload):
        return self._request("PUT", path, payload)

    def _request(self, method, path, payload=None, timeout=10):
        url = f"https://localhost:{self.port}/v1{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("User-Agent", USER_AGENT)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(req, context=self.ssl_context, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raise ApiError(e.code, e.read().decode("utf-8", "replace")) from None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw


class GraphTile:
    """Un tile de gráfica en la barra superior del Polymath (índices 0-3).

    Comprobado contra Polymath 1.4.5.7 (ver docs/api-notas.md): type es un entero (0 = tile en
    blanco, 1 = gráfica), el PUT va plano y Polymath responde 200 aunque el ID no exista.
    """

    TYPE_GRAPH = 1

    def __init__(self, client, title, index, length, tile_id=None):
        self.client = client
        self.title = title
        self.index = index
        self.length = length
        self.id = tile_id

    def create(self):
        body = {"title": self.title, "type": self.TYPE_GRAPH, "index": self.index, "length": self.length}
        result = self.client.post("/config/addGenericTile", body)
        message = result.get("message", "") if isinstance(result, dict) else str(result)
        # El mensaje es el ID, que coincide con el título.
        self.id = message or self.title
        log.info("Tile %r creado en la posición %d (id=%r)", self.title, self.index, self.id)

    def update(self, value, sub_title=None, secondary=None, unit=None, time_unit=None, color=None, leading=None, ending=None):
        fields = {
            "id": self.id,
            # La documentación dice String, pero la API exige un número ("currentValue must be an double").
            "currentValue": round(float(value), 2),
            "subTitle": sub_title,
            "secondarySubtitle": secondary,
            "unit": unit,
            "timeUnit": time_unit,
            "color": color,
            "leading": leading,
            "ending": ending,
        }
        fields = {k: v for k, v in fields.items() if v is not None}
        result = self.client.put("/config/updateGenericTile", fields)
        message = result.get("message", "") if isinstance(result, dict) else str(result)
        if "does not exist" in message:
            raise ApiError(404, message)
