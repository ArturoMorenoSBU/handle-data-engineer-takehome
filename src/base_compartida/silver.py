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
from base_compartida.config import ASEGURADORAS, Configuracion

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


def _copiar_reglas(con: sqlite3.Connection, config: Configuracion) -> None:
    for regla in config.reglas:
        con.execute(
            "INSERT INTO silver_reglas VALUES (?,?,?,?,?,?,?,?,?)", tuple(asdict(regla).values())
        )
    for pieza in config.piezas:
        fila = (pieza.id, pieza.regla, pieza.fuente, pieza.apartado, pieza.dato, pieza.tipo)
        fila += (pieza.campo, pieza.valor, pieza.etiqueta, pieza.sobre, pieza.texto)
        fila += (pieza.disposicion, int(config.es_aplicable(pieza)))
        con.execute("INSERT INTO silver_piezas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", fila)


def _apariciones(con: sqlite3.Connection, config: Configuracion, fuente: str, tipo: str):
    """Lee de bronze todas las apariciones de un tipo de registro, agrupadas por identidad."""
    tabla = tabla_de(fuente, tipo)
    grupos: dict[tuple[str, str], list[Aparicion]] = defaultdict(list)
    if not existe(con, tabla):
        return grupos
    pieza_broker = config.campo(fuente, "broker", tipo)
    nombre = "numero_poliza" if tipo == "polizas" else "numero_recibo"
    campo_numero = config.campo(fuente, nombre, tipo).campo
    consulta = (
        f"SELECT r.*, c.broker AS _sesion, c.fecha_fuente AS _foto FROM {tabla} r"
        " JOIN bronze_capturas c USING (captura_id)"
    )
    con.row_factory = sqlite3.Row
    for fila in con.execute(consulta):
        datos = dict(fila)
        sesion = pieza_broker.valor == "@sesion"
        broker = datos["_sesion"] if sesion else datos.get(pieza_broker.campo)
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
    con.row_factory = None
    return grupos


def _anotar_apariciones(con, tipo: str, registro_id: str, apariciones: list[Aparicion]) -> None:
    for a in apariciones:
        fila = (tipo, registro_id, a.contenido_id, a.captura_id, a.posicion)
        con.execute("INSERT INTO silver_apariciones VALUES (?,?,?,?,?)", fila)


def _polizas(con: sqlite3.Connection, config: Configuracion, fuente: str) -> None:
    """Una póliza no trae revisión: empieza una versión cuando cambia su contenido
    respecto de la foto anterior donde apareció. La vigente es la última observada."""
    for (broker, numero), apariciones in _apariciones(con, config, fuente, "polizas").items():
        poliza_id = f"{fuente}|{broker}|{numero}"
        con.execute(
            "INSERT INTO silver_polizas VALUES (?,?,?,?)", (poliza_id, fuente, broker, numero)
        )
        _anotar_apariciones(con, "poliza", poliza_id, apariciones)
        versiones: list[Aparicion] = []
        for aparicion in sorted(apariciones, key=lambda a: a.orden):
            if not versiones or versiones[-1].contenido_id != aparicion.contenido_id:
                versiones.append(aparicion)
        for i, primera in enumerate(versiones):
            ultima = i == len(versiones) - 1
            hasta = None if ultima else versiones[i + 1].foto
            fila = (poliza_id, i + 1, primera.contenido_id, primera.foto, hasta, int(ultima))
            fila += (primera.captura_id, primera.posicion)
            con.execute("INSERT INTO silver_poliza_versiones VALUES (?,?,?,?,?,?,?,?)", fila)


def _revision(texto: str | None) -> int:
    return int(texto) if texto and texto.isdigit() else 0


def _recibos(con: sqlite3.Connection, config: Configuracion, fuente: str) -> None:
    """Una versión de un recibo es una revisión con un contenido. Se ordenan por lo
    que declara la fuente (la revisión), no por el orden en que se cargó."""
    campo = {
        nombre: config.campo(fuente, nombre, "recibos").campo
        for nombre in ("poliza_del_recibo", "monto", "moneda", "vencimiento", "estado", "revision")
    }
    for (broker, numero), apariciones in _apariciones(con, config, fuente, "recibos").items():
        recibo_id = f"{fuente}|{broker}|{numero}"
        _anotar_apariciones(con, "recibo", recibo_id, apariciones)
        por_version: dict[tuple[int, str], list[Aparicion]] = defaultdict(list)
        for aparicion in apariciones:
            revision = _revision(aparicion.datos.get(campo["revision"]))
            por_version[(revision, aparicion.contenido_id)].append(aparicion)
        desde = {v: min(a.foto for a in grupo) for v, grupo in por_version.items()}
        ordenadas = sorted(por_version, key=lambda v: (v[0], desde[v], v[1]))
        for i, version in enumerate(ordenadas):
            referencia = min(por_version[version], key=lambda a: a.orden)
            posteriores = [desde[v] for v in ordenadas[i + 1 :]]
            vigente = i == len(ordenadas) - 1
            poliza_id = f"{fuente}|{broker}|{referencia.datos.get(campo['poliza_del_recibo'])}"
            interpretados = (
                valores.interpretar_monto(
                    config, fuente, *referencia.texto_y_presencia(campo["monto"])
                ),
                valores.interpretar_fecha(
                    config, fuente, *referencia.texto_y_presencia(campo["vencimiento"])
                ),
                valores.interpretar_estado(
                    config, fuente, *referencia.texto_y_presencia(campo["estado"])
                ),
            )
            fila = [
                recibo_id,
                version[0],
                version[1],
                poliza_id,
                referencia.datos.get(campo["moneda"]),
            ]
            for valor in interpretados:
                fila += [valor.texto, valor.interpretado, valor.disposicion, ",".join(valor.piezas)]
            fila += [desde[version], min(posteriores) if posteriores else None, int(vigente)]
            fila += [referencia.captura_id, referencia.posicion]
            marcas = ",".join("?" * len(fila))
            con.execute(f"INSERT INTO silver_recibo_versiones VALUES ({marcas})", fila)
            if vigente:
                recibo = (recibo_id, fuente, broker, numero, poliza_id)
                con.execute("INSERT INTO silver_recibos VALUES (?,?,?,?,?)", recibo)


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
    columnas = ", ".join(f'r."{config.campo("book", n, "book").campo}"' for n in nombres)
    con.execute(
        f"INSERT INTO silver_book SELECT {columnas}, r.captura_id, r.posicion FROM bronze_book r"
        " JOIN bronze_capturas c USING (captura_id) WHERE c.tanda_id = ?",
        ultima,
    )


def _completitud(con: sqlite3.Connection, config: Configuracion) -> None:
    """Dice, por tanda, si se capturó todo lo que la fuente declaró ofrecer.

    Brújula declara filas por broker; se cuentan registros distintos, no
    apariciones. Aurora declara archivos en su manifest; no declara filas.
    """
    consulta = (
        "SELECT tanda_id, broker, tipo, MAX(filas_declaradas),"
        " SUM(resultado <> 'leida'), group_concat(captura_id)"
        " FROM bronze_capturas WHERE fuente = 'brujula' GROUP BY tanda_id, broker, tipo"
    )
    for tanda, broker, tipo, declarado, no_leidas, capturas in con.execute(consulta).fetchall():
        tabla = tabla_de("brujula", tipo)
        capturado = 0
        if tipo in ("polizas", "recibos") and existe(con, tabla):
            nombre = "numero_poliza" if tipo == "polizas" else "numero_recibo"
            numero = config.campo("brujula", nombre, tipo).campo
            marcas = ",".join("?" * len(capturas.split(",")))
            contar = (
                f'SELECT COUNT(DISTINCT "{numero}") FROM {tabla} WHERE captura_id IN ({marcas})'
            )
            capturado = con.execute(contar, capturas.split(",")).fetchone()[0]
        completa = declarado is not None and capturado == declarado and not no_leidas
        fila = (tanda, "brujula", broker, tipo, "filas", declarado, capturado, no_leidas)
        con.execute(
            "INSERT INTO silver_completitud VALUES (?,?,?,?,?,?,?,?,?)", (*fila, int(completa))
        )
    consulta = (
        "SELECT tanda_id, fuente, MAX(archivos_declarados),"
        " SUM(resultado = 'leida' AND tipo <> 'manifest'), SUM(resultado <> 'leida')"
        " FROM bronze_capturas WHERE fuente <> 'brujula' GROUP BY tanda_id, fuente"
    )
    for tanda, fuente, declarados, leidos, no_leidas in con.execute(consulta).fetchall():
        declarado = len(json.loads(declarados)) if declarados else None
        completa = not no_leidas and (declarado is None or declarado == leidos)
        fila = (tanda, fuente, None, "archivos", "archivos", declarado, leidos, no_leidas)
        con.execute(
            "INSERT INTO silver_completitud VALUES (?,?,?,?,?,?,?,?,?)", (*fila, int(completa))
        )
