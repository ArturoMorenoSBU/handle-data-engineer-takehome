"""Silver: lo compartido entre aseguradoras, recalculado completo en cada carga.

Aquí se identifica cada póliza y cada recibo, se arman sus versiones y se
interpreta cada valor con las piezas aplicables. Nada de silver sobrevive de
una carga a la siguiente: se rehace leyendo todo bronze.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass

from base_compartida import valores
from base_compartida.bronze import LEIDA, ejecutar_esquema, existe, tabla_de
from base_compartida.config import ASEGURADORAS, NOMBRES_COMUNES_DEL_RECIBO, Configuracion

_ESQUEMA = """
CREATE TABLE silver_reglas (
    id TEXT PRIMARY KEY, fuente TEXT, estado TEXT, origen TEXT, fecha TEXT,
    propuesta_por TEXT, decidida_por TEXT, nota TEXT, dice TEXT
);
CREATE TABLE silver_piezas (
    id TEXT PRIMARY KEY, regla TEXT, fuente TEXT, apartado TEXT, dato TEXT, tipo TEXT,
    campo TEXT, valor TEXT, etiqueta TEXT, sobre TEXT, texto TEXT, disposicion TEXT,
    aplicable INTEGER
);
CREATE TABLE silver_polizas (
    poliza_id TEXT PRIMARY KEY, aseguradora TEXT, broker TEXT, numero_poliza TEXT
);
CREATE TABLE silver_poliza_versiones (
    poliza_id TEXT, version INTEGER, contenido_id TEXT,
    observada_desde TEXT, observada_hasta TEXT, vigente INTEGER,
    ref_captura_id TEXT, ref_posicion INTEGER,
    PRIMARY KEY (poliza_id, version)
);
CREATE TABLE silver_recibos (
    recibo_id TEXT PRIMARY KEY, aseguradora TEXT, broker TEXT, numero_recibo TEXT,
    poliza_id TEXT
);
CREATE TABLE silver_recibo_versiones (
    recibo_id TEXT, revision INTEGER, contenido_id TEXT, poliza_id TEXT, moneda TEXT,
    monto_texto TEXT, monto_centavos INTEGER, monto_disposicion TEXT, monto_piezas TEXT,
    vencimiento_texto TEXT, vencimiento TEXT, vencimiento_disposicion TEXT,
    vencimiento_piezas TEXT,
    estado_texto TEXT, estado TEXT, estado_disposicion TEXT, estado_piezas TEXT,
    observada_desde TEXT, observada_hasta TEXT, vigente INTEGER,
    ref_captura_id TEXT, ref_posicion INTEGER,
    PRIMARY KEY (recibo_id, revision, contenido_id)
);
CREATE TABLE silver_apariciones (
    tipo TEXT, registro_id TEXT, contenido_id TEXT, captura_id TEXT, posicion INTEGER,
    PRIMARY KEY (tipo, captura_id, posicion)
);
CREATE TABLE silver_book (
    aseguradora TEXT, broker TEXT, numero_poliza TEXT, referencia_cliente TEXT,
    captura_id TEXT, posicion INTEGER
);
CREATE TABLE silver_completitud (
    tanda_id TEXT, fuente TEXT, broker TEXT, tipo TEXT, unidad TEXT,
    declarado INTEGER, capturado INTEGER, capturas_no_leidas INTEGER, completa INTEGER
);
"""


@dataclass
class Aparicion:
    """Un registro tal como vino en una captura y en una posición dentro de ella."""

    captura_id: str
    posicion: int
    foto: str
    broker: str
    numero: str
    datos: dict
    campos: list

    @property
    def contenido_id(self) -> str:
        """Huella del texto de todos los campos que vinieron. No incluye posición ni foto."""
        texto = json.dumps({c: self.datos.get(c) for c in sorted(self.campos)}, ensure_ascii=False)
        return hashlib.sha1(texto.encode()).hexdigest()[:12]

    @property
    def orden(self) -> tuple:
        return (self.foto, self.captura_id, self.posicion)

    def texto_y_presencia(self, campo: str) -> tuple[str | None, str]:
        if campo not in self.campos:
            return None, valores.AUSENTE
        texto = self.datos.get(campo)
        if texto is None:
            return None, valores.NULO
        return texto, valores.VACIO if texto == "" else valores.CON_VALOR


def recalcular(con: sqlite3.Connection, config: Configuracion) -> None:
    """Borra silver y la rehace desde bronze con las piezas aplicables de hoy."""
    tablas = con.execute("SELECT name FROM sqlite_master WHERE name LIKE 'silver_%'").fetchall()
    for (tabla,) in tablas:
        con.execute(f"DROP TABLE {tabla}")
    ejecutar_esquema(con, _ESQUEMA)
    _copiar_reglas(con, config)
    for fuente in ASEGURADORAS:
        _polizas(con, config, fuente)
        _recibos(con, config, fuente)
    _book(con, config)
    _completitud(con, config)


def _guardar(con: sqlite3.Connection, tabla: str, fila: dict) -> None:
    """Inserta una fila nombrando cada columna, para no depender de su orden."""
    columnas = ", ".join(fila)
    marcas = ", ".join(f":{c}" for c in fila)
    con.execute(f"INSERT INTO {tabla} ({columnas}) VALUES ({marcas})", fila)


def _copiar_reglas(con: sqlite3.Connection, config: Configuracion) -> None:
    """Deja en silver la lista y los descriptores con que se calculó esta carga."""
    for regla in config.reglas:
        _guardar(con, "silver_reglas", asdict(regla))
    for pieza in config.piezas:
        aplicable = int(config.es_aplicable(pieza))
        _guardar(con, "silver_piezas", {**asdict(pieza), "aplicable": aplicable})


def _apariciones(
    con: sqlite3.Connection, config: Configuracion, fuente: str, tipo: str
) -> dict[tuple[str, str], list[Aparicion]]:
    """Lee de bronze todas las apariciones de un tipo de registro, agrupadas por identidad."""
    tabla = tabla_de(fuente, tipo)
    grupos: dict[tuple[str, str], list[Aparicion]] = defaultdict(list)
    if not existe(con, tabla):
        return grupos
    pieza_broker = config.campo(fuente, "broker", tipo)
    nombre = "numero_poliza" if tipo == "polizas" else "numero_recibo"
    campo_numero = config.campo(fuente, nombre, tipo).campo
    cursor = con.cursor()
    cursor.row_factory = sqlite3.Row
    consulta = (
        f"SELECT r.*, c.broker AS _sesion, c.fecha_fuente AS _foto FROM {tabla} r"
        " JOIN bronze_capturas c ON c.captura_id = r.captura_id"
    )
    for fila in cursor.execute(consulta):
        datos = dict(fila)
        de_la_sesion = pieza_broker.valor == "@sesion"
        broker = datos["_sesion"] if de_la_sesion else datos[pieza_broker.campo]
        aparicion = Aparicion(
            captura_id=datos["captura_id"],
            posicion=datos["posicion"],
            foto=valores.a_instante_utc(datos["_foto"]),
            broker=broker,
            numero=datos.get(campo_numero),
            datos=datos,
            campos=json.loads(datos["_campos"]),
        )
        grupos[(broker, aparicion.numero)].append(aparicion)
    return grupos


def _anotar_apariciones(
    con: sqlite3.Connection, tipo: str, registro_id: str, apariciones: list[Aparicion]
) -> None:
    for a in apariciones:
        fila = {"tipo": tipo, "registro_id": registro_id, "contenido_id": a.contenido_id}
        _guardar(
            con, "silver_apariciones", {**fila, "captura_id": a.captura_id, "posicion": a.posicion}
        )


def _polizas(con: sqlite3.Connection, config: Configuracion, fuente: str) -> None:
    """Una póliza no trae revisión: empieza una versión cuando cambia su contenido
    respecto de la foto anterior donde apareció. La vigente es la última observada."""
    for (broker, numero), apariciones in _apariciones(con, config, fuente, "polizas").items():
        poliza_id = f"{fuente}|{broker}|{numero}"
        poliza = {"poliza_id": poliza_id, "aseguradora": fuente, "broker": broker}
        _guardar(con, "silver_polizas", {**poliza, "numero_poliza": numero})
        _anotar_apariciones(con, "poliza", poliza_id, apariciones)
        primeras: list[Aparicion] = []
        for aparicion in sorted(apariciones, key=lambda a: a.orden):
            if not primeras or primeras[-1].contenido_id != aparicion.contenido_id:
                primeras.append(aparicion)
        for i, primera in enumerate(primeras):
            es_la_ultima = i == len(primeras) - 1
            version = {
                "poliza_id": poliza_id,
                "version": i + 1,
                "contenido_id": primera.contenido_id,
                "observada_desde": primera.foto,
                "observada_hasta": None if es_la_ultima else primeras[i + 1].foto,
                "vigente": int(es_la_ultima),
                "ref_captura_id": primera.captura_id,
                "ref_posicion": primera.posicion,
            }
            _guardar(con, "silver_poliza_versiones", version)


def _revision(texto: str | None) -> int:
    """La revisión como número, para ordenar. Una que no es un entero se ordena como 0."""
    return int(texto) if texto and texto.isdigit() else 0


def _valores_del_recibo(
    config: Configuracion, fuente: str, campo: dict, referencia: Aparicion
) -> dict:
    """Texto, valor interpretado, disposición y piezas del monto, el vencimiento y el estado."""
    interpretados = {
        "monto": (valores.interpretar_monto, "monto_centavos"),
        "vencimiento": (valores.interpretar_fecha, "vencimiento"),
        "estado": (valores.interpretar_estado, "estado"),
    }
    columnas = {}
    for nombre, (interpretar, columna) in interpretados.items():
        valor = interpretar(config, fuente, *referencia.texto_y_presencia(campo[nombre]))
        columnas[f"{nombre}_texto"] = valor.texto
        columnas[columna] = valor.interpretado
        columnas[f"{nombre}_disposicion"] = valor.disposicion
        columnas[f"{nombre}_piezas"] = ",".join(valor.piezas)
    return columnas


def _recibos(con: sqlite3.Connection, config: Configuracion, fuente: str) -> None:
    """Una versión de un recibo es una revisión con un contenido. Se ordenan por lo
    que declara la fuente (la revisión), no por el orden en que se cargó."""
    campo = {n: config.campo(fuente, n, "recibos").campo for n in NOMBRES_COMUNES_DEL_RECIBO}
    for (broker, numero), apariciones in _apariciones(con, config, fuente, "recibos").items():
        recibo_id = f"{fuente}|{broker}|{numero}"
        _anotar_apariciones(con, "recibo", recibo_id, apariciones)
        por_version: dict[tuple[int, str], list[Aparicion]] = defaultdict(list)
        for aparicion in apariciones:
            revision = _revision(aparicion.datos.get(campo["revision"]))
            por_version[(revision, aparicion.contenido_id)].append(aparicion)
        desde = {v: min(a.foto for a in grupo) for v, grupo in por_version.items()}
        ordenadas = sorted(por_version, key=lambda v: (v[0], desde[v], v[1]))
        for i, (revision, contenido_id) in enumerate(ordenadas):
            llave = (revision, contenido_id)
            referencia = min(por_version[llave], key=lambda a: a.orden)
            # Una revisión menor puede llegar en una foto posterior: entonces no hay
            # una foto en que se la haya visto reemplazada, y el final queda vacío.
            despues = [desde[v] for v in ordenadas[i + 1 :] if desde[v] > desde[llave]]
            vigente = i == len(ordenadas) - 1
            poliza_id = f"{fuente}|{broker}|{referencia.datos.get(campo['poliza_del_recibo'])}"
            version = {
                "recibo_id": recibo_id,
                "revision": revision,
                "contenido_id": contenido_id,
                "poliza_id": poliza_id,
                "moneda": referencia.datos.get(campo["moneda"]),
                **_valores_del_recibo(config, fuente, campo, referencia),
                "observada_desde": desde[llave],
                "observada_hasta": min(despues) if despues else None,
                "vigente": int(vigente),
                "ref_captura_id": referencia.captura_id,
                "ref_posicion": referencia.posicion,
            }
            _guardar(con, "silver_recibo_versiones", version)
            if vigente:
                recibo = {"recibo_id": recibo_id, "aseguradora": fuente, "broker": broker}
                _guardar(
                    con,
                    "silver_recibos",
                    {**recibo, "numero_recibo": numero, "poliza_id": poliza_id},
                )


def _book(con: sqlite3.Connection, config: Configuracion) -> None:
    """El book no trae fecha propia: vale la tanda capturada más tarde."""
    if not existe(con, "bronze_book"):
        return
    ultima = con.execute(
        "SELECT tanda_id FROM bronze_capturas WHERE fuente = 'book' AND resultado = ?"
        " ORDER BY capturado_en DESC, tanda_id DESC LIMIT 1",
        (LEIDA,),
    ).fetchone()
    if ultima is None:
        return
    nombres = ("aseguradora", "broker", "numero_poliza", "referencia_cliente")
    origen = ", ".join(f'r."{config.campo("book", n, "book").campo}"' for n in nombres)
    con.execute(
        f"INSERT INTO silver_book ({', '.join(nombres)}, captura_id, posicion)"
        f" SELECT {origen}, r.captura_id, r.posicion FROM bronze_book r"
        " JOIN bronze_capturas c ON c.captura_id = r.captura_id WHERE c.tanda_id = ?",
        ultima,
    )


def _registros_distintos(
    con: sqlite3.Connection, config: Configuracion, tanda: str, broker: str, tipo: str
) -> int:
    """Cuántos registros distintos de un broker dejó una tanda de Brújula. No cuenta apariciones."""
    tabla = tabla_de("brujula", tipo)
    if tipo not in ("polizas", "recibos") or not existe(con, tabla):
        return 0
    nombre = "numero_poliza" if tipo == "polizas" else "numero_recibo"
    numero = config.campo("brujula", nombre, tipo).campo
    consulta = (
        f'SELECT COUNT(DISTINCT r."{numero}") FROM {tabla} r'
        " JOIN bronze_capturas c ON c.captura_id = r.captura_id"
        " WHERE c.tanda_id = ? AND c.broker = ?"
    )
    return con.execute(consulta, (tanda, broker)).fetchone()[0]


def _completitud(con: sqlite3.Connection, config: Configuracion) -> None:
    """Dice, por tanda, si se capturó todo lo que la fuente declaró ofrecer.

    Brújula declara filas por broker. Aurora declara archivos en su manifest; no
    declara filas. El book no declara nada: está completo si su archivo se leyó.
    """
    no_leidas = "SUM(CASE WHEN resultado <> 'leida' THEN 1 ELSE 0 END)"
    consulta = (
        f"SELECT tanda_id, broker, tipo, MAX(filas_declaradas), {no_leidas}"
        " FROM bronze_capturas WHERE fuente = 'brujula' GROUP BY tanda_id, broker, tipo"
    )
    for tanda, broker, tipo, declarado, fallidas in con.execute(consulta).fetchall():
        capturado = _registros_distintos(con, config, tanda, broker, tipo)
        completa = declarado is not None and capturado == declarado and not fallidas
        fila = {"tanda_id": tanda, "fuente": "brujula", "broker": broker, "tipo": tipo}
        fila |= {"unidad": "filas", "declarado": declarado, "capturado": capturado}
        _guardar(
            con,
            "silver_completitud",
            {**fila, "capturas_no_leidas": fallidas, "completa": int(completa)},
        )
    leidos = "SUM(CASE WHEN resultado = 'leida' AND tipo <> 'manifest' THEN 1 ELSE 0 END)"
    consulta = (
        f"SELECT tanda_id, fuente, MAX(archivos_declarados), {leidos}, {no_leidas}"
        " FROM bronze_capturas WHERE fuente <> 'brujula' GROUP BY tanda_id, fuente"
    )
    for tanda, fuente, declarados, capturado, fallidas in con.execute(consulta).fetchall():
        declarado = len(json.loads(declarados)) if declarados else None
        completa = not fallidas and declarado in (None, capturado)
        fila = {"tanda_id": tanda, "fuente": fuente, "broker": None, "tipo": "archivos"}
        fila |= {"unidad": "archivos", "declarado": declarado, "capturado": capturado}
        _guardar(
            con,
            "silver_completitud",
            {**fila, "capturas_no_leidas": fallidas, "completa": int(completa)},
        )
