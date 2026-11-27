"""Comandos: construir todo desde cero, cargar, rehacer y mostrar las respuestas preparadas."""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from pathlib import Path

from base_compartida import captura
from base_compartida.carga import cargar, rehacer
from base_compartida.gold import PREGUNTAS
from base_compartida.portal import portal

BROKERS = ["alder", "birch"]


def construir(fuentes: Path, datos: Path, config_dir: Path) -> None:
    """Captura las dos fotos de cada aseguradora y el book, y carga todo en una base nueva."""
    landing = datos / "landing"
    shutil.rmtree(datos, ignore_errors=True)
    clave = os.environ.get("BRUJULA_CLAVE", "demo")
    for escenario in ("baseline", "corrected"):
        with portal(fuentes, escenario) as url:
            captura.capturar_brujula(landing, url, BROKERS, clave)
        captura.capturar_aurora(landing, fuentes / "fixtures" / "aurora", escenario)
    captura.capturar_book(landing, fuentes / "reference" / "book.csv")
    tandas = cargar(datos / "base.sqlite", landing, config_dir)
    print(
        f"Base construida en {datos / 'base.sqlite'} con {len(tandas)} tandas: {', '.join(tandas)}"
    )


def respuestas(base: Path) -> None:
    """Muestra cada vista de gold bajo la pregunta que responde."""
    con = sqlite3.connect(base)
    try:
        for vista, pregunta in PREGUNTAS.items():
            cursor = con.execute(f"SELECT * FROM {vista}")
            columnas = [c[0] for c in cursor.description]
            filas = [["" if v is None else str(v) for v in fila] for fila in cursor]
            print(f"\n## {pregunta}\n   (vista: {vista})\n")
            _tabla(columnas, filas)
    finally:
        con.close()


def _tabla(columnas: list[str], filas: list[list[str]]) -> None:
    anchos = [min(60, max(len(c), *(len(f[i]) for f in filas))) for i, c in enumerate(columnas)]
    for fila in (columnas, ["-" * a for a in anchos], *filas):
        print("  ".join(v[:60].ljust(a) for v, a in zip(fila, anchos, strict=True)).rstrip())
    if not filas:
        print("(sin filas)")


def main() -> None:
    parser = argparse.ArgumentParser(prog="base_compartida", description=__doc__)
    parser.add_argument("comando", choices=["construir", "cargar", "rehacer", "respuestas"])
    parser.add_argument("--fuentes", type=Path, default=Path("fuentes"))
    parser.add_argument("--datos", type=Path, default=Path("datos"))
    parser.add_argument("--config", type=Path, default=Path("config"))
    args = parser.parse_args()
    base, landing = args.datos / "base.sqlite", args.datos / "landing"
    if args.comando == "construir":
        construir(args.fuentes, args.datos, args.config)
    elif args.comando == "cargar":
        print("Tandas agregadas:", cargar(base, landing, args.config) or "ninguna")
    elif args.comando == "rehacer":
        print("Base rehecha desde las capturas:", rehacer(base, landing, args.config))
    else:
        respuestas(base)


if __name__ == "__main__":
    main()
