"""Datos compartidos por las pruebas: se construyen una vez, con el mismo comando del README."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from apoyo import CONFIG, FUENTES
from base_compartida import cli


@pytest.fixture(scope="session")
def datos(tmp_path_factory) -> Path:
    """Lo que deja `make construir`: capturas de baseline y corrected, y la base cargada."""
    carpeta = tmp_path_factory.mktemp("datos")
    cli.construir(FUENTES, carpeta, CONFIG)
    return carpeta


@pytest.fixture(scope="session")
def landing(datos) -> Path:
    return datos / "landing"


@pytest.fixture(scope="session")
def completa(datos) -> Path:
    """La base con baseline y corrected cargados. Las pruebas solo la leen."""
    return datos / "base.sqlite"


@pytest.fixture
def base(tmp_path) -> Path:
    return tmp_path / "base.sqlite"


@pytest.fixture
def copia_de_landing(landing, tmp_path) -> Path:
    destino = tmp_path / "landing"
    shutil.copytree(landing, destino)
    return destino
