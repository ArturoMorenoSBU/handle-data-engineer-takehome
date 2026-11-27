"""Bronze: lo que dijo cada fuente, en tablas de texto.

Una fila por aparición: un registro tal como vino en una captura y en una
posición dentro de ella. Los nombres de columna son los de la fuente y todo
valor es texto. Bronze separa registros y campos con la estructura que la
fuente declara; no interpreta montos, fechas ni estados.
"""

from __future__ import annotations

import csv
import fnmatch
import io
import json
import sqlite3
from pathlib import Path

from base_compartida.captura import leer_tanda
from base_compartida.config import Configuracion

LEIDA, FALLO, FORMA_NO_RECONOCIDA = "leida", "fallo", "forma_no_reconocida"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS bronze_capturas (
    captura_id TEXT PRIMARY KEY,
    tanda_id TEXT NOT NULL,
    fuente TEXT NOT NULL,
    broker TEXT,
    tipo TEXT,
    pedido TEXT,
    version TEXT,
    archivo TEXT,
    capturado_en TEXT,
    resultado TEXT NOT NULL,
    causa TEXT,
    fecha_fuente TEXT,
    filas_declaradas INTEGER,
    archivos_declarados TEXT
);
CREATE TABLE IF NOT EXISTS bronze_lectura (fuente TEXT PRIMARY KEY, firma TEXT NOT NULL);
"""

# Llaves del manifest de Aurora y la pieza del descriptor con la que deben coincidir.
_MANIFEST_CONTRA_PIEZAS = {
    "delimiter": "separador",
    "encoding": "codificacion",
    "date_format": "formato:vencimiento",
    "decimal_separator": "formato:monto_decimal",
    "thousands_separator": "formato:monto_miles",
}


class HayQueRehacer(Exception):
    """Cambió la forma de leer una fuente que ya tiene filas en bronze."""


def tabla_de(fuente: str, tipo: str) -> str:
    return "bronze_book" if fuente == "book" else f"bronze_{fuente}_{tipo}"


def ejecutar_esquema(con: sqlite3.Connection, esquema: str) -> None:
    """Ejecuta varias sentencias sin cerrar la transacción abierta."""
    for sentencia in esquema.split(";"):
        if sentencia.strip():
            con.execute(sentencia)


def existe(con: sqlite3.Connection, tabla: str) -> bool:
    consulta = "SELECT 1 FROM sqlite_master WHERE name = ?"
    return con.execute(consulta, (tabla,)).fetchone() is not None


def agregar_tandas(
    con: sqlite3.Connection,
    landing: Path,
    config: Configuracion,
    tandas: list[str] | None = None,
) -> list[str]:
    """Agrega a bronze las tandas de la carpeta que todavía no tiene. Devuelve cuáles."""
    ejecutar_esquema(con, _ESQUEMA)
    ya = {fila[0] for fila in con.execute("SELECT DISTINCT tanda_id FROM bronze_capturas")}
    pendientes = [c for c in sorted(landing.iterdir()) if c.is_dir() and c.name not in ya]
    if tandas is not None:
        pendientes = [c for c in pendientes if c.name in tandas]
    for carpeta in pendientes:
        fuente = carpeta.name.rsplit("-", 1)[0]
        _comprobar_lectura(con, config, fuente)
        capturas = leer_tanda(carpeta)
        {"brujula": _brujula, "aurora": _aurora, "book": _book}[fuente](con, config, capturas)
    return [c.name for c in pendientes]


def _comprobar_lectura(con: sqlite3.Connection, config: Configuracion, fuente: str) -> None:
    firma = config.firma_de_lectura(fuente)
    previa = con.execute("SELECT firma FROM bronze_lectura WHERE fuente = ?", (fuente,)).fetchone()
    if previa and previa[0] != firma:
        raise HayQueRehacer(
            f"Cambió cómo se lee {fuente} y bronze ya tiene filas leídas con la forma anterior. "
            "Hay que borrar la base y volver a cargar."
        )
    con.execute("INSERT OR REPLACE INTO bronze_lectura VALUES (?, ?)", (fuente, firma))


def _anotar(con: sqlite3.Connection, contexto: dict, resultado: str, **extra) -> None:
    fila = {
        "captura_id": contexto["captura_id"],
        "tanda_id": contexto["tanda_id"],
        "fuente": contexto["fuente"],
        "broker": contexto.get("broker"),
        "tipo": contexto.get("tipo"),
        "pedido": contexto.get("pedido"),
        "version": contexto.get("version"),
        "archivo": contexto["archivo"],
        "capturado_en": contexto["capturado_en"],
        "resultado": resultado,
        "causa": contexto.get("causa"),
        "fecha_fuente": None,
        "filas_declaradas": None,
        "archivos_declarados": None,
        **extra,
    }
    columnas = ", ".join(fila)
    marcas = ", ".join(f":{c}" for c in fila)
    con.execute(f"INSERT INTO bronze_capturas ({columnas}) VALUES ({marcas})", fila)


def _insertar(con: sqlite3.Connection, tabla: str, captura_id: str, posicion: int, registro: dict):
    """Guarda una aparición. `_campos` lista los campos que sí vinieron en el registro:
    así se distingue un campo que no vino (no está en la lista) de uno nulo (NULL)."""
    con.execute(
        f"CREATE TABLE IF NOT EXISTS {tabla} (captura_id TEXT NOT NULL, posicion INTEGER NOT NULL,"
        " _campos TEXT NOT NULL, PRIMARY KEY (captura_id, posicion))"
    )
    presentes = {fila[1] for fila in con.execute(f"PRAGMA table_info({tabla})")}
    for campo in registro:
        if '"' in campo:
            raise ValueError(f"Nombre de campo no admitido: {campo!r}")
        if campo not in presentes:
            con.execute(f'ALTER TABLE {tabla} ADD COLUMN "{campo}" TEXT')
    columnas = "".join(f', "{c}"' for c in registro)
    marcas = ", ?" * len(registro)
    con.execute(
        f"INSERT INTO {tabla} (captura_id, posicion, _campos{columnas}) VALUES (?, ?, ?{marcas})",
        (captura_id, posicion, json.dumps(list(registro)), *registro.values()),
    )


def _como_texto(valor: object) -> str | None:
    if valor is None or isinstance(valor, str):
        return valor
    return json.dumps(valor, ensure_ascii=False)


def _brujula(con: sqlite3.Connection, config: Configuracion, capturas: list) -> None:
    campo_foto = config.una("brujula", "fecha_foto").campo
    campo_filas = config.una("brujula", "completitud").campo
    sobre = config.aplicables("brujula", "sobre:broker")
    for contexto, cuerpo in capturas:
        if contexto["resultado"] != "ok":
            _anotar(con, contexto, FALLO)
            continue
        llave = config.una("brujula", "registros", contexto["tipo"]).valor
        try:
            respuesta = json.loads(cuerpo)
        except ValueError:
            respuesta = None
        declarado = respuesta if isinstance(respuesta, dict) else {}
        extra = {
            "fecha_fuente": declarado.get(campo_foto),
            "filas_declaradas": declarado.get(campo_filas),
        }
        registros = declarado.get(llave)
        causa = None
        if not isinstance(registros, list):
            causa = f"la respuesta no trae sus registros en la llave '{llave}'"
        elif sobre and declarado.get(sobre[0].campo) != contexto["broker"]:
            causa = "el broker que declara la respuesta no es el de la sesión"
        if causa:
            _anotar(con, {**contexto, "causa": causa}, FORMA_NO_RECONOCIDA, **extra)
            continue
        _anotar(con, contexto, LEIDA, **extra)
        tabla = tabla_de("brujula", contexto["tipo"])
        for posicion, registro in enumerate(registros, start=1):
            textos = {campo: _como_texto(valor) for campo, valor in registro.items()}
            _insertar(con, tabla, contexto["captura_id"], posicion, textos)


def _diferencias_con_manifest(config: Configuracion, manifest: object) -> list[str]:
    if not isinstance(manifest, dict):
        return ["el manifest no se puede leer"]
    diferencias = []
    for llave, dato in _MANIFEST_CONTRA_PIEZAS.items():
        esperado = config.una("aurora", dato).valor
        if manifest.get(llave) != esperado:
            diferencias.append(f"{llave}: manifest={manifest.get(llave)!r}, pieza={esperado!r}")
    return diferencias


def _aurora(con: sqlite3.Connection, config: Configuracion, capturas: list) -> None:
    cuerpo_manifest = next((c for ctx, c in capturas if ctx["tipo"] == "manifest"), b"")
    try:
        manifest = json.loads(cuerpo_manifest)
    except ValueError:
        manifest = None
    diferencias = _diferencias_con_manifest(config, manifest)
    for contexto, cuerpo in capturas:
        if diferencias:
            causa = "el manifest no coincide con el descriptor: " + "; ".join(diferencias)
            _anotar(con, {**contexto, "causa": causa}, FORMA_NO_RECONOCIDA)
            continue
        version = manifest["versions"][contexto["version"]]
        extra = {
            "fecha_fuente": version["source_as_of"],
            "archivos_declarados": json.dumps(version["files"]),
        }
        if contexto["resultado"] != "ok":
            _anotar(con, contexto, FALLO, **extra)
        elif contexto["tipo"] == "manifest":
            _anotar(con, contexto, LEIDA, **extra)
        else:
            _csv(con, config, "aurora", contexto, cuerpo, extra)


def _book(con: sqlite3.Connection, config: Configuracion, capturas: list) -> None:
    for contexto, cuerpo in capturas:
        _csv(con, config, "book", contexto, cuerpo, {})


def _csv(con, config: Configuracion, fuente: str, contexto: dict, cuerpo: bytes, extra: dict):
    """Lee un archivo CSV con la codificación y el separador de las piezas de estructura."""
    tipos = {p.tipo: p.valor for p in config.aplicables(fuente, "registros")}
    nombre = "book.csv" if fuente == "book" else contexto["pedido"]
    tipo = next((t for t, patron in tipos.items() if fnmatch.fnmatch(nombre, patron)), None)
    if tipo is None:
        causa = "ninguna pieza dice qué registros trae este archivo"
        _anotar(con, {**contexto, "causa": causa}, FORMA_NO_RECONOCIDA, **extra)
        return
    texto = cuerpo.decode(config.una(fuente, "codificacion").valor)
    lector = csv.reader(io.StringIO(texto), delimiter=config.una(fuente, "separador").valor)
    encabezado = next(lector, [])
    _anotar(con, {**contexto, "tipo": tipo}, LEIDA, **extra)
    # La línea 1 es el encabezado: el primer registro está en la línea 2.
    for linea, valores in enumerate(lector, start=2):
        if valores:
            registro = dict(zip(encabezado, valores, strict=False))
            _insertar(con, tabla_de(fuente, tipo), contexto["captura_id"], linea, registro)
