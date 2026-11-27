"""Capturas compartidas por las pruebas: se hacen una vez contra el portal del lab."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from base_compartida import captura
from base_compartida.carga import cargar
from base_compartida.portal import portal

RAIZ = Path(__file__).resolve().parents[1]
FUENTES = RAIZ / "fuentes"
CONFIG = RAIZ / "config"
BROKERS = ["alder", "birch"]

# Tandas que deja la captura, en el orden en que se hacen.
BASELINE = ["brujula-0001", "aurora-0001", "book-0001"]
CORRECTED = ["brujula-0002", "aurora-0002"]


def capturar_todo(landing: Path) -> None:
    for escenario in ("baseline", "corrected"):
        with portal(FUENTES, escenario) as url:
            captura.capturar_brujula(landing, url, BROKERS, "demo")
        captura.capturar_aurora(landing, FUENTES / "fixtures" / "aurora", escenario)
    captura.capturar_book(landing, FUENTES / "reference" / "book.csv")


def consultar(base: Path, sql: str, *parametros) -> list[tuple]:
    con = sqlite3.connect(base)
    try:
        return con.execute(sql, parametros).fetchall()
    finally:
        con.close()


@pytest.fixture(scope="session")
def landing(tmp_path_factory) -> Path:
    carpeta = tmp_path_factory.mktemp("landing")
    capturar_todo(carpeta)
    return carpeta


@pytest.fixture(scope="session")
def completa(landing, tmp_path_factory) -> Path:
    """Una base con baseline y corrected cargados."""
    base = tmp_path_factory.mktemp("completa") / "base.sqlite"
    cargar(base, landing, CONFIG)
    return base


@pytest.fixture
def base(tmp_path) -> Path:
    return tmp_path / "base.sqlite"


@pytest.fixture
def copia_de_landing(landing, tmp_path) -> Path:
    destino = tmp_path / "landing"
    shutil.copytree(landing, destino)
    return destino
