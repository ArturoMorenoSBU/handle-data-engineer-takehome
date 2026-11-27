"""Carga: de las capturas guardadas a la base, en un solo paso que no deja nada a medias.

Orden: se leen las reglas y se comprueban; se agregan a bronze las tandas que
faltan; se recalcula silver completa; se rehacen las vistas de gold. Si algo
falla, la base queda como estaba.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from base_compartida import bronze, gold, silver
from base_compartida.config import leer_configuracion

# Tablas que definen el resultado. La hora de captura no está en ninguna.
_TABLAS_DEL_RESULTADO = (
    "silver_polizas",
    "silver_poliza_versiones",
    "silver_recibos",
    "silver_recibo_versiones",
    "silver_book",
    "gold_abierto_conocido",
    "gold_book",
)


def cargar(base: Path, landing: Path, config_dir: Path, tandas: list[str] | None = None) -> list:
    """Agrega a la base las tandas de la carpeta que aún no tiene. Devuelve cuáles."""
    config = leer_configuracion(config_dir)
    base.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(base, isolation_level=None)
    try:
        con.execute("BEGIN")
        agregadas = bronze.agregar_tandas(con, landing, config, tandas)
        silver.recalcular(con, config)
        gold.crear_vistas(con, config)
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    return agregadas


def rehacer(base: Path, landing: Path, config_dir: Path) -> list:
    """Rehace todo lo derivado solo desde las capturas, sin tocar la fuente.

    Arma la base nueva aparte y reemplaza la anterior solo si salió bien.
    """
    nueva = base.with_suffix(".nueva")
    nueva.unlink(missing_ok=True)
    try:
        tandas = cargar(nueva, landing, config_dir)
    except BaseException:
        nueva.unlink(missing_ok=True)
        raise
    os.replace(nueva, base)
    return tandas


def resultado(base: Path) -> dict[str, list[tuple]]:
    """El contenido de las tablas que definen el resultado, para comparar dos bases."""
    con = sqlite3.connect(base)
    try:
        return {
            tabla: sorted(con.execute(f"SELECT * FROM {tabla}").fetchall(), key=repr)
            for tabla in _TABLAS_DEL_RESULTADO
        }
    finally:
        con.close()
