"""Rutas, tandas y ayudas que comparten las pruebas."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FUENTES = RAIZ / "fuentes"
AURORA = FUENTES / "fixtures" / "aurora"
CONFIG = RAIZ / "config"
BROKERS = ["alder", "birch"]

# Tandas que deja `construir`, que captura primero baseline y después corrected.
BASELINE = ["brujula-0001", "aurora-0001", "book-0001"]
CORRECTED = ["brujula-0002", "aurora-0002"]

ENCABEZADO_DE_RECIBOS = (
    "corretora;numero_apolice;numero_parcela;id_cobranca;valor_parcela;moeda;"
    "status_cobranca;vencimento;data_pagamento;revisao\n"
)


def consultar(base: Path, sql: str, *parametros) -> list[tuple]:
    con = sqlite3.connect(base)
    try:
        return con.execute(sql, parametros).fetchall()
    finally:
        con.close()


def entrega_de_aurora(
    carpeta: Path, nombre: str, fecha: str, archivos: dict[str, str | None], **manifest
) -> Path:
    """Arma una entrega de Aurora a mano, para casos que los datos de ejemplo no traen.

    `archivos` dice qué lista el manifest: un texto reemplaza el archivo, `None` lo
    lista sin entregarlo, y un nombre que ya existe en la entrega original se usa tal cual.
    """
    destino = carpeta / f"aurora_{nombre}"
    shutil.copytree(AURORA, destino)
    declarado = json.loads((destino / "manifest.json").read_text(encoding="utf-8"))
    declarado["versions"][nombre] = {"source_as_of": fecha, "files": list(archivos)}
    declarado.update(manifest)
    (destino / "manifest.json").write_text(json.dumps(declarado), encoding="utf-8")
    for archivo, texto in archivos.items():
        if texto is None:
            (destino / archivo).unlink(missing_ok=True)
        elif texto:
            (destino / archivo).write_text(texto, encoding="utf-8")
    return destino


def copia_de_config(destino: Path, archivo: str, viejo: str, nuevo: str) -> Path:
    """Una copia de la configuración con un texto cambiado en uno de sus archivos."""
    shutil.copytree(CONFIG, destino)
    ruta = destino / archivo
    texto = ruta.read_text(encoding="utf-8")
    assert viejo in texto
    ruta.write_text(texto.replace(viejo, nuevo), encoding="utf-8")
    return destino
