"""Gold: una vista por cada pregunta preparada. No guarda datos: se calcula al consultar.

Las vistas leen de silver lo compartido y de bronze las capturas y los datos
propios de cada fuente. Los montos se suman en centavos y se muestran con dos
decimales. Ninguna vista suma monedas distintas: siempre agrupan por moneda.
"""

from __future__ import annotations

import sqlite3

from base_compartida.bronze import existe, tabla_de
from base_compartida.config import ASEGURADORAS, Configuracion

SOLO_EN_EL_BOOK = "el book la afirma, la fuente no la muestra"

# Pregunta que responde cada vista, en el orden en que se muestran.
PREGUNTAS = {
    "gold_abierto_conocido": "¿Cuánto está abierto y qué quedó fuera de la suma?",
    "gold_historial_recibos": "¿Cuál es el historial de cada recibo?",
    "gold_book": "¿Qué pólizas están en el book, en la fuente o en los dos?",
    "gold_reglas": "¿Qué reglas tiene cada fuente y en qué estado?",
    "gold_valores_no_validos": "¿Qué valores tienen una disposición distinta de válido?",
    "gold_diccionario": "¿De qué campo de cada fuente sale cada nombre común?",
    "gold_completitud": "¿Quedó completa cada captura?",
}


def _dinero(centavos: str) -> str:
    return f"printf('%d.%02d', ({centavos}) / 100, ({centavos}) % 100)"


def _suma(condicion: str) -> str:
    return f"SUM(CASE WHEN {condicion} THEN v.monto_centavos ELSE 0 END)"


_ABIERTO = "v.estado = 'abierto' AND v.monto_disposicion = 'valido'"
_INDETERMINADO = "v.estado = 'indeterminado' AND v.monto_disposicion = 'valido'"

_VISTAS = {
    "gold_abierto_conocido": f"""
        SELECT r.aseguradora, r.broker, v.moneda,
            {_dinero(_suma(_ABIERTO))} AS abierto_conocido,
            SUM(v.estado = 'abierto' AND v.monto_disposicion <> 'valido')
                AS abiertos_sin_monto_utilizable,
            SUM(v.estado = 'indeterminado') AS con_estado_indeterminado,
            {_dinero(_suma(_INDETERMINADO))} AS monto_indeterminado,
            CASE WHEN EXISTS (
                SELECT 1 FROM silver_completitud k
                WHERE k.fuente = r.aseguradora AND k.completa = 0
                    AND (k.broker IS NULL OR k.broker = r.broker)
            ) THEN 'no' ELSE 'sí' END AS capturas_completas,
            {_suma(_ABIERTO)} AS abierto_centavos
        FROM silver_recibos r
        JOIN silver_recibo_versiones v ON v.recibo_id = r.recibo_id AND v.vigente = 1
        GROUP BY r.aseguradora, r.broker, v.moneda
        ORDER BY r.aseguradora, r.broker, v.moneda""",
    "gold_historial_recibos": """
        SELECT r.aseguradora, r.broker, r.numero_recibo, v.revision,
            v.monto_texto AS monto, v.moneda, v.estado_texto AS estado_fuente, v.estado,
            v.vencimiento_texto AS vencimiento, v.observada_desde, v.observada_hasta,
            v.vigente, COUNT(*) AS apariciones,
            group_concat(c.tanda_id || ' ' || c.pedido || ' posición ' || a.posicion, '; ')
                AS origen
        FROM silver_recibos r
        JOIN silver_recibo_versiones v ON v.recibo_id = r.recibo_id
        JOIN silver_apariciones a ON a.tipo = 'recibo' AND a.registro_id = v.recibo_id
            AND a.contenido_id = v.contenido_id
        JOIN bronze_capturas c ON c.captura_id = a.captura_id
        GROUP BY v.recibo_id, v.revision, v.contenido_id
        ORDER BY r.aseguradora, r.broker, r.numero_recibo, v.revision, v.observada_desde""",
    "gold_book": f"""
        SELECT b.aseguradora, b.broker, b.numero_poliza,
            CASE WHEN p.poliza_id IS NULL THEN '{SOLO_EN_EL_BOOK}'
                 ELSE 'en el book y en la fuente' END AS situacion,
            b.referencia_cliente AS referencia_en_el_book,
            p.referencia_cliente AS referencia_en_la_fuente
        FROM silver_book b
        LEFT JOIN gold_polizas p ON p.aseguradora = b.aseguradora AND p.broker = b.broker
            AND p.numero_poliza = b.numero_poliza
        UNION ALL
        SELECT p.aseguradora, p.broker, p.numero_poliza, 'solo en la fuente', NULL,
            p.referencia_cliente
        FROM gold_polizas p
        LEFT JOIN silver_book b ON p.aseguradora = b.aseguradora AND p.broker = b.broker
            AND p.numero_poliza = b.numero_poliza
        WHERE b.numero_poliza IS NULL
        ORDER BY 1, 2, 3""",
    "gold_reglas": """
        SELECT r.id AS regla, r.fuente, r.estado, r.origen, r.fecha, r.propuesta_por,
            r.decidida_por, r.nota, COUNT(p.id) AS piezas,
            COALESCE(SUM(p.aplicable), 0) AS piezas_que_se_aplican, r.dice
        FROM silver_reglas r LEFT JOIN silver_piezas p ON p.regla = r.id
        GROUP BY r.id ORDER BY r.fuente, r.id""",
    "gold_valores_no_validos": """
        SELECT r.aseguradora, r.broker, r.numero_recibo, x.revision, x.campo, x.texto,
            x.disposicion, x.piezas,
            (SELECT group_concat(DISTINCT p.regla) FROM silver_piezas p
             WHERE instr(',' || x.piezas || ',', ',' || p.id || ',') > 0) AS reglas
        FROM (
            SELECT recibo_id, revision, 'monto' AS campo, monto_texto AS texto,
                monto_disposicion AS disposicion, monto_piezas AS piezas
            FROM silver_recibo_versiones
            UNION ALL
            SELECT recibo_id, revision, 'vencimiento', vencimiento_texto,
                vencimiento_disposicion, vencimiento_piezas FROM silver_recibo_versiones
            UNION ALL
            SELECT recibo_id, revision, 'estado', estado_texto, estado_disposicion,
                estado_piezas FROM silver_recibo_versiones
        ) x JOIN silver_recibos r ON r.recibo_id = x.recibo_id
        WHERE x.disposicion <> 'valido'
        ORDER BY r.aseguradora, r.broker, r.numero_recibo, x.revision, x.campo""",
    "gold_diccionario": """
        SELECT substr(dato, 7) AS nombre_comun, fuente, tipo AS tipo_de_registro,
            CASE WHEN valor = '@sesion' THEN 'la sesión con la que se consultó'
                 ELSE campo END AS campo_de_la_fuente,
            regla, id AS pieza
        FROM silver_piezas
        WHERE aplicable = 1 AND dato LIKE 'campo:%'
        ORDER BY nombre_comun, fuente, tipo""",
    "gold_completitud": """
        SELECT tanda_id, fuente, broker, tipo, declarado, capturado, unidad,
            capturas_no_leidas, CASE completa WHEN 1 THEN 'sí' ELSE 'no' END AS completa
        FROM silver_completitud ORDER BY tanda_id, broker, tipo""",
}


def _vista_de_polizas(con: sqlite3.Connection, config: Configuracion) -> str:
    """La versión vigente de cada póliza, con los datos propios de su fuente tal como
    llegaron. Cada aseguradora los nombra distinto: el nombre sale de sus piezas."""
    ramas = []
    for fuente in ASEGURADORAS:
        tabla = tabla_de(fuente, "polizas")
        if not existe(con, tabla):
            continue
        referencia = config.una(fuente, "propio:referencia_cliente", "polizas").campo
        ramas.append(
            f"""SELECT p.poliza_id, p.aseguradora, p.broker, p.numero_poliza,
                b."{referencia}" AS referencia_cliente, v.observada_desde
            FROM silver_polizas p
            JOIN silver_poliza_versiones v ON v.poliza_id = p.poliza_id AND v.vigente = 1
            JOIN {tabla} b ON b.captura_id = v.ref_captura_id AND b.posicion = v.ref_posicion
            WHERE p.aseguradora = '{fuente}'"""
        )
    vacia = "SELECT NULL AS poliza_id, NULL AS aseguradora, NULL AS broker, NULL AS numero_poliza,"
    vacia += " NULL AS referencia_cliente, NULL AS observada_desde WHERE 0"
    return " UNION ALL ".join(ramas) or vacia


def crear_vistas(con: sqlite3.Connection, config: Configuracion) -> None:
    vistas = {"gold_polizas": _vista_de_polizas(con, config), **_VISTAS}
    for nombre in reversed(list(vistas)):
        con.execute(f"DROP VIEW IF EXISTS {nombre}")
    for nombre, consulta in vistas.items():
        con.execute(f"CREATE VIEW {nombre} AS {consulta}")
