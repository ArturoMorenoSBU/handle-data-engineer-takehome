"""Bronze: lo que dijo cada fuente, en tablas de texto.

Una fila por aparición: un registro tal como vino en una captura y en una
posición dentro de ella. Los nombres de columna son los de la fuente y todo
valor es texto. Bronze separa registros y campos con la estructura que la
fuente declara; no interpreta montos, fechas ni estados.

Una captura que no se puede leer no detiene la carga: queda anotada como
"forma no reconocida", con su causa, y no da filas.
"""

from __future__ import annotations

import csv
import fnmatch
import io
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

from base_compartida.captura import leer_tanda
from base_compartida.config import Configuracion, ErrorDeConfiguracion
from base_compartida.valores import a_instante_utc

LEIDA, FALLO, FORMA_NO_RECONOCIDA = "leida", "fallo", "forma_no_reconocida"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS bronze_capturas (
    captura_id TEXT PRIMARY KEY,
    tanda_id TEXT NOT NULL,
    fuente TEXT NOT NULL,
    broker TEXT,
    tipo TEXT,
    pedido TEXT,
    entrega TEXT,
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

# Lo que puede salir mal al leer los bytes de una captura. No detiene la carga.
_NO_SE_PUDO_LEER = (ValueError, TypeError, KeyError, AttributeError, sqlite3.Error)


class HayQueRehacer(Exception):
    """Cambió la forma de leer una fuente que ya tiene filas en bronze."""


class FormaNoReconocida(Exception):
    """La captura llegó bien, pero no tiene la forma que su descriptor describe."""


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
        clase, leer = _LECTORES[fuente]
        if config.clase(fuente) != clase:
            raise ErrorDeConfiguracion(f"{fuente}: el código solo sabe leerla como {clase}")
        _comprobar_lectura(con, config, fuente)
        leer(con, config, leer_tanda(carpeta))
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


def _anotar(con: sqlite3.Connection, contexto: dict, resultado: str, **declarado) -> None:
    """Escribe la fila de una captura: su contexto, cómo salió y lo que la fuente declara."""
    fila = {
        "captura_id": contexto["captura_id"],
        "tanda_id": contexto["tanda_id"],
        "fuente": contexto["fuente"],
        "broker": contexto.get("broker"),
        "tipo": contexto.get("tipo"),
        "pedido": contexto.get("pedido"),
        "entrega": contexto.get("version"),
        "archivo": contexto["archivo"],
        "capturado_en": contexto["capturado_en"],
        "resultado": resultado,
        "causa": contexto.get("causa"),
        "fecha_fuente": None,
        "filas_declaradas": None,
        "archivos_declarados": None,
        **declarado,
    }
    columnas = ", ".join(fila)
    marcas = ", ".join(f":{c}" for c in fila)
    con.execute(f"INSERT INTO bronze_capturas ({columnas}) VALUES ({marcas})", fila)


def _leer_captura(
    con: sqlite3.Connection, contexto: dict, leer: Callable[[], None], **declarado
) -> None:
    """Lee una captura completa o no deja nada de ella, salvo su fila con la causa."""
    con.execute("SAVEPOINT captura")
    try:
        leer()
    except (FormaNoReconocida, *_NO_SE_PUDO_LEER) as error:
        con.execute("ROLLBACK TO captura")
        causa = str(error) or type(error).__name__
        _anotar(con, {**contexto, "causa": causa}, FORMA_NO_RECONOCIDA, **declarado)
    con.execute("RELEASE captura")


def _insertar(
    con: sqlite3.Connection, tabla: str, captura_id: str, posicion: int, registro: dict
) -> None:
    """Guarda una aparición. `_campos` lista los campos que sí vinieron en el registro:
    así se distingue un campo que no vino (no está en la lista) de uno nulo (NULL)."""
    con.execute(
        f"CREATE TABLE IF NOT EXISTS {tabla} (captura_id TEXT NOT NULL, posicion INTEGER NOT NULL,"
        " _campos TEXT NOT NULL, PRIMARY KEY (captura_id, posicion))"
    )
    presentes = {fila[1] for fila in con.execute(f"PRAGMA table_info({tabla})")}
    for campo in registro:
        if '"' in campo:
            raise FormaNoReconocida(f"nombre de campo no admitido: {campo!r}")
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
    del_sobre = config.aplicables("brujula", "respuesta:broker")
    for contexto, cuerpo in capturas:
        if contexto["resultado"] != "ok":
            _anotar(con, contexto, FALLO)
            continue
        try:
            respuesta = json.loads(cuerpo)
        except ValueError:
            respuesta = None
        sobre = respuesta if isinstance(respuesta, dict) else {}
        filas = sobre.get(campo_filas)
        declarado = {
            "fecha_fuente": _como_texto(sobre.get(campo_foto)),
            "filas_declaradas": filas if isinstance(filas, int) else None,
        }

        def leer(contexto=contexto, sobre=sobre, declarado=declarado) -> None:
            llave = config.una("brujula", "registros", contexto["tipo"]).valor
            registros = sobre.get(llave)
            if not isinstance(registros, list):
                raise FormaNoReconocida(f"la respuesta no trae sus registros en la llave '{llave}'")
            if del_sobre and sobre.get(del_sobre[0].campo) != contexto["broker"]:
                raise FormaNoReconocida("el broker que declara la respuesta no es el de la sesión")
            a_instante_utc(declarado["fecha_fuente"])  # La foto necesita una fecha legible.
            _anotar(con, contexto, LEIDA, **declarado)
            tabla = tabla_de("brujula", contexto["tipo"])
            for posicion, registro in enumerate(registros, start=1):
                textos = {campo: _como_texto(valor) for campo, valor in registro.items()}
                _insertar(con, tabla, contexto["captura_id"], posicion, textos)

        _leer_captura(con, contexto, leer, **declarado)


def _del_manifest(config: Configuracion, dato: str, entrega: dict) -> object:
    """Lee de la entrega la llave que nombra una pieza escrita como `manifest:<llave>`."""
    return entrega[config.una("aurora", dato).valor.removeprefix("manifest:")]


def _entrega_de_aurora(config: Configuracion, cuerpo: bytes, nombre: str) -> dict:
    """Lo que el manifest declara de una entrega. Solo vale si coincide con el descriptor."""
    try:
        manifest = json.loads(cuerpo)
        entrega = manifest["versions"][nombre]
        fecha = _del_manifest(config, "fecha_foto", entrega)
        a_instante_utc(fecha)
        archivos = list(_del_manifest(config, "completitud", entrega))
    except _NO_SE_PUDO_LEER as error:
        raise FormaNoReconocida(f"el manifest no se puede leer: {error}") from error
    diferencias = []
    for llave, dato in _MANIFEST_CONTRA_PIEZAS.items():
        esperado = config.una("aurora", dato).valor
        if manifest.get(llave) != esperado:
            diferencias.append(
                f"{llave}: manifest={manifest.get(llave)!r}, descriptor={esperado!r}"
            )
    if diferencias:
        raise FormaNoReconocida(
            "el manifest no coincide con el descriptor: " + "; ".join(diferencias)
        )
    return {"fecha_fuente": fecha, "archivos_declarados": json.dumps(archivos)}


def _aurora(con: sqlite3.Connection, config: Configuracion, capturas: list) -> None:
    """Una tanda de Aurora se lee solo si su manifest coincide con el descriptor."""
    manifest = next((c for ctx, c in capturas if ctx["tipo"] == "manifest"), b"")
    try:
        declarado = _entrega_de_aurora(config, manifest, capturas[0][0].get("version"))
    except FormaNoReconocida as error:
        for contexto, _ in capturas:
            _anotar(con, {**contexto, "causa": str(error)}, FORMA_NO_RECONOCIDA)
        return
    for contexto, cuerpo in capturas:
        if contexto["resultado"] != "ok":
            _anotar(con, contexto, FALLO, **declarado)
        elif contexto["tipo"] == "manifest":
            _anotar(con, contexto, LEIDA, **declarado)
        else:
            _csv(con, config, "aurora", contexto, cuerpo, declarado)


def _book(con: sqlite3.Connection, config: Configuracion, capturas: list) -> None:
    for contexto, cuerpo in capturas:
        _csv(con, config, "book", contexto, cuerpo, {})


def _tipo_de_archivo(config: Configuracion, fuente: str, nombre: str) -> str:
    for pieza in config.aplicables(fuente, "registros"):
        if fnmatch.fnmatch(nombre, pieza.valor):
            return pieza.tipo
    raise FormaNoReconocida("ninguna pieza dice qué registros trae este archivo")


def _csv(
    con: sqlite3.Connection,
    config: Configuracion,
    fuente: str,
    contexto: dict,
    cuerpo: bytes,
    declarado: dict,
) -> None:
    """Lee un archivo CSV con la codificación y el separador de las piezas de estructura."""

    def leer() -> None:
        nombre = "book.csv" if fuente == "book" else contexto["pedido"]
        tipo = _tipo_de_archivo(config, fuente, nombre)
        codificacion = config.una(fuente, "codificacion").valor
        # `utf-8-sig` es UTF-8 que además quita la marca inicial que agregan algunos programas.
        texto = cuerpo.decode("utf-8-sig" if codificacion.upper() == "UTF-8" else codificacion)
        lector = csv.reader(io.StringIO(texto), delimiter=config.una(fuente, "separador").valor)
        encabezado = next(lector, [])
        citados = {p.campo for p in config.aplicables(fuente, tipo=tipo) if p.campo}
        if faltan := sorted(citados - set(encabezado)):
            raise FormaNoReconocida(f"al encabezado le faltan campos: {', '.join(faltan)}")
        _anotar(con, {**contexto, "tipo": tipo}, LEIDA, **declarado)
        # La línea 1 es el encabezado: el primer registro está en la línea 2.
        for linea, valores in enumerate(lector, start=2):
            if not valores:
                continue
            if len(valores) != len(encabezado):
                raise FormaNoReconocida(f"la línea {linea} no tiene los campos del encabezado")
            registro = dict(zip(encabezado, valores, strict=True))
            _insertar(con, tabla_de(fuente, tipo), contexto["captura_id"], linea, registro)

    _leer_captura(con, contexto, leer, **declarado)


# La clase que el código sabe leer de cada fuente, y con qué función.
_LECTORES: dict[str, tuple[str, Callable]] = {
    "brujula": ("json", _brujula),
    "aurora": ("csv", _aurora),
    "book": ("csv", _book),
}
