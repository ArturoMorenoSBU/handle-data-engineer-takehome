"""Comandos: construir desde cero, cargar, rehacer, mostrar respuestas y probar un escenario."""

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
ESCENARIOS = ["baseline", "corrected", "failure", "drift"]
SIN_VALOR = "—"


def _clave() -> str:
    """La contraseña de las cuentas de ejemplo del portal. Se puede cambiar por entorno."""
    return os.environ.get("BRUJULA_CLAVE", "demo")


def _vaciar(carpeta: Path) -> tuple[Path, Path]:
    """Borra de una carpeta de datos solo lo que estos comandos generan: capturas y base."""
    landing, base = carpeta / "landing", carpeta / "base.sqlite"
    shutil.rmtree(landing, ignore_errors=True)
    base.unlink(missing_ok=True)
    return landing, base


def construir(fuentes: Path, datos: Path, config_dir: Path) -> None:
    """Captura las dos fotos de cada aseguradora y el book, y carga todo en una base nueva."""
    landing, base = _vaciar(datos)
    for escenario in ("baseline", "corrected"):
        with portal(fuentes, escenario) as url:
            captura.capturar_brujula(landing, url, BROKERS, _clave())
        captura.capturar_aurora(landing, fuentes / "fixtures" / "aurora", escenario)
    captura.capturar_book(landing, fuentes / "reference" / "book.csv")
    tandas = cargar(base, landing, config_dir)
    print(f"Base construida en {base}.")
    print(
        f"Tandas cargadas (una tanda es una ronda de capturas de una fuente): {', '.join(tandas)}"
    )


def probar_escenario(fuentes: Path, datos: Path, config_dir: Path, escenario: str) -> None:
    """Captura Brújula en un escenario y lo carga en su propia base, aparte de la principal.

    Sirve para ver qué hace el sistema cuando el portal falla o cambia de forma.
    """
    landing, base = _vaciar(datos / escenario)
    with portal(fuentes, escenario) as url:
        captura.capturar_brujula(landing, url, BROKERS, _clave())
    cargar(base, landing, config_dir)
    print(f"Escenario '{escenario}' cargado en {base}.")
    con = sqlite3.connect(base)
    try:
        _mostrar(con, "gold_completitud")
        _mostrar(con, "gold_abierto_conocido")
        print("\n## ¿Qué capturas no se pudieron leer, y por qué?\n")
        consulta = "SELECT broker, pedido, resultado, causa FROM bronze_capturas"
        _imprimir_consulta(con, consulta + " WHERE resultado <> 'leida' ORDER BY captura_id")
    finally:
        con.close()


def respuestas(base: Path) -> None:
    """Muestra cada vista de gold bajo la pregunta que responde."""
    con = sqlite3.connect(base)
    try:
        for vista in PREGUNTAS:
            _mostrar(con, vista)
    finally:
        con.close()


def _mostrar(con: sqlite3.Connection, vista: str) -> None:
    print(f"\n## {PREGUNTAS[vista]}\n   (vista: {vista})\n")
    _imprimir_consulta(con, f"SELECT * FROM {vista}")


def _imprimir_consulta(con: sqlite3.Connection, consulta: str) -> None:
    cursor = con.execute(consulta)
    columnas = [c[0] for c in cursor.description]
    imprimir_tabla(columnas, [[SIN_VALOR if v is None else str(v) for v in f] for f in cursor])


def imprimir_tabla(columnas: list[str], filas: list[list[str]]) -> None:
    """Imprime columnas alineadas. La última no se rellena ni se corta."""
    anchos = [max([len(c), *(len(f[i]) for f in filas)]) for i, c in enumerate(columnas)]
    for fila in (columnas, ["-" * a for a in anchos], *filas):
        celdas = [v.ljust(a) for v, a in zip(fila[:-1], anchos[:-1], strict=True)]
        print("  ".join([*celdas, fila[-1]]))
    if not filas:
        print("(sin filas)")


def main() -> None:
    parser = argparse.ArgumentParser(prog="base_compartida", description=__doc__)
    comandos = ["construir", "cargar", "rehacer", "respuestas", "escenario"]
    parser.add_argument("comando", choices=comandos)
    parser.add_argument("--fuentes", type=Path, default=Path("fuentes"))
    parser.add_argument("--datos", type=Path, default=Path("datos"))
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument("--escenario", choices=ESCENARIOS, default="failure")
    args = parser.parse_args()
    base, landing = args.datos / "base.sqlite", args.datos / "landing"
    if args.comando == "construir":
        construir(args.fuentes, args.datos, args.config)
    elif args.comando == "cargar":
        print("Tandas agregadas:", ", ".join(cargar(base, landing, args.config)) or "ninguna")
    elif args.comando == "rehacer":
        tandas = rehacer(base, landing, args.config)
        print("Base rehecha desde las capturas:", ", ".join(tandas))
    elif args.comando == "escenario":
        probar_escenario(args.fuentes, args.datos, args.config, args.escenario)
    else:
        respuestas(base)


if __name__ == "__main__":
    main()
