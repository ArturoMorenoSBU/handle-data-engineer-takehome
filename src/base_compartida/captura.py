"""Captura: guarda cada respuesta o archivo tal como llegó, con su contexto al lado.

Una tanda es el conjunto de capturas que se hacen de corrido contra una fuente
para copiar una foto suya. Cada tanda es una carpeta; cada captura son dos
archivos: los bytes y un `.contexto.json` con quién pidió qué, cuándo y cómo salió.
Aquí no se interpreta nada: una página que falla se guarda como falla.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from http.cookiejar import CookieJar
from pathlib import Path

SUFIJO_CONTEXTO = ".contexto.json"
_MAXIMO_DE_PAGINAS = 1000


def _ahora() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def nueva_tanda(landing: Path, fuente: str) -> Path:
    """Crea la carpeta de la siguiente tanda de una fuente: `brujula-0001`, `brujula-0002`..."""
    landing.mkdir(parents=True, exist_ok=True)
    numero = len(list(landing.glob(f"{fuente}-*"))) + 1
    carpeta = landing / f"{fuente}-{numero:04d}"
    carpeta.mkdir()
    return carpeta


def _guardar(tanda: Path, nombre: str, contenido: bytes, **contexto) -> None:
    orden = len(list(tanda.glob(f"*{SUFIJO_CONTEXTO}"))) + 1
    archivo = f"{orden:03d}_{nombre}"
    (tanda / archivo).write_bytes(contenido)
    contexto = {
        "captura_id": f"{tanda.name}/{orden:03d}",
        "tanda_id": tanda.name,
        "archivo": archivo,
        "capturado_en": _ahora(),
        **contexto,
    }
    texto = json.dumps(contexto, ensure_ascii=False, indent=2)
    (tanda / f"{archivo}{SUFIJO_CONTEXTO}").write_text(texto, encoding="utf-8")


def capturar_brujula(landing: Path, url: str, brokers: list[str], clave: str) -> str:
    """Recorre las respuestas JSON de pólizas y recibos de cada broker.

    El broker lo define la sesión, así que se inicia una sesión por broker. La
    respuesta del inicio de sesión no se guarda.
    """
    tanda = nueva_tanda(landing, "brujula")
    for broker in brokers:
        abrir = _iniciar_sesion(tanda, url, broker, clave)
        if abrir is None:
            continue
        _pedir(tanda, abrir, url, broker, "polizas", "/api/policies?page=1", "policies")
        pagina: int | None = 1
        while pagina and pagina <= _MAXIMO_DE_PAGINAS:
            pedido = f"/api/receipts?page={pagina}"
            pagina = _pedir(tanda, abrir, url, broker, "recibos", pedido, f"receipts_p{pagina}")
    return tanda.name


def _iniciar_sesion(tanda: Path, url: str, broker: str, clave: str):
    """Devuelve con qué pedir páginas ya con sesión, o None si el portal la rechaza.

    Un rechazo queda como una captura fallida sin bytes: ni la contraseña ni la
    respuesta del inicio de sesión se guardan.
    """
    abridor = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    datos = urllib.parse.urlencode({"username": broker, "password": clave}).encode()
    try:
        abridor.open(f"{url}/login", data=datos, timeout=10).close()
    except OSError as error:
        codigo = getattr(error, "code", None)
        _guardar(
            tanda,
            f"{broker}_sesion",
            b"",
            fuente="brujula",
            broker=broker,
            tipo="sesion",
            pedido="/login",
            codigo_http=codigo,
            resultado="fallo",
            causa=f"inicio de sesión rechazado (HTTP {codigo})",
        )
        return None
    return abridor.open


def _pedir(tanda: Path, abrir, url: str, broker: str, tipo: str, pedido: str, nombre: str):
    """Guarda una respuesta y devuelve la página siguiente, si la respuesta la anuncia."""
    try:
        with abrir(f"{url}{pedido}", timeout=10) as respuesta:
            codigo, cuerpo = respuesta.status, respuesta.read()
    except urllib.error.HTTPError as error:
        codigo, cuerpo = error.code, error.read()
    except OSError as error:
        codigo, cuerpo = None, str(error).encode()
    bien = codigo == 200
    causa = None if bien else f"HTTP {codigo}: {cuerpo.decode('utf-8', 'replace')[:200]}"
    _guardar(
        tanda,
        f"{broker}_{nombre}.json",
        cuerpo,
        fuente="brujula",
        broker=broker,
        tipo=tipo,
        pedido=pedido,
        codigo_http=codigo,
        resultado="ok" if bien else "fallo",
        causa=causa,
    )
    if not bien:
        return None
    try:
        return json.loads(cuerpo).get("next_page")
    except (ValueError, AttributeError):
        return None


def capturar_aurora(landing: Path, carpeta: Path, version: str) -> str:
    """Copia el manifest y los archivos que lista para una versión de la entrega."""
    tanda = nueva_tanda(landing, "aurora")
    manifest = (carpeta / "manifest.json").read_bytes()
    comun = {"fuente": "aurora", "broker": None, "version": version, "resultado": "ok"}
    _guardar(tanda, "manifest.json", manifest, tipo="manifest", pedido="manifest.json", **comun)
    for nombre in json.loads(manifest)["versions"][version]["files"]:
        archivo = carpeta / nombre
        if archivo.exists():
            _guardar(tanda, nombre, archivo.read_bytes(), tipo="archivo", pedido=nombre, **comun)
        else:
            falta = {**comun, "resultado": "fallo", "causa": "el archivo no llegó"}
            _guardar(tanda, nombre, b"", tipo="archivo", pedido=nombre, **falta)
    return tanda.name


def capturar_book(landing: Path, archivo: Path) -> str:
    """Copia el book. No trae fecha propia: vale la captura más reciente."""
    tanda = nueva_tanda(landing, "book")
    _guardar(
        tanda,
        "book.csv",
        archivo.read_bytes(),
        fuente="book",
        broker=None,
        tipo="archivo",
        pedido=archivo.name,
        resultado="ok",
    )
    return tanda.name


def leer_tanda(carpeta: Path) -> list[tuple[dict, bytes]]:
    """Devuelve las capturas de una tanda, en orden: (contexto, bytes)."""
    capturas = []
    for contexto in sorted(carpeta.glob(f"*{SUFIJO_CONTEXTO}")):
        datos = json.loads(contexto.read_text(encoding="utf-8"))
        capturas.append((datos, (carpeta / datos["archivo"]).read_bytes()))
    return capturas
