"""Casos que no ocurren en los datos del lab y que el spec define igual."""

from __future__ import annotations

import shutil

import pytest

from apoyo import CONFIG
from base_compartida import valores
from base_compartida.config import ErrorDeConfiguracion, leer_configuracion


@pytest.fixture(scope="module")
def config():
    return leer_configuracion(CONFIG)


def test_una_etiqueta_sin_regla_es_indeterminado_con_disposicion_valida(config):
    valor = valores.interpretar_estado(config, "aurora", "EM_ANALISE", valores.CON_VALOR)
    assert (valor.texto, valor.interpretado, valor.disposicion) == (
        "EM_ANALISE",
        "indeterminado",
        "valido",
    )


def test_un_estado_que_no_llega_es_indeterminado_y_no_suministrado(config):
    valor = valores.interpretar_estado(config, "aurora", "", valores.VACIO)
    assert (valor.interpretado, valor.disposicion) == ("indeterminado", "no_suministrado")


def test_tbd_solo_es_texto_especial_en_la_fuente_que_tiene_esa_regla(config):
    assert (
        valores.interpretar_monto(config, "brujula", "TBD", "valor").disposicion == "no_utilizable"
    )
    assert valores.interpretar_monto(config, "aurora", "TBD", "valor").disposicion == "invalido"


@pytest.mark.parametrize(
    ("fuente", "texto", "centavos"),
    [
        ("aurora", "2.400,50", 240050),
        ("aurora", "150,00", 15000),
        ("aurora", "1.500", 150000),
        ("aurora", "1500,00", 150000),
        ("aurora", "15.00,00", None),
        ("aurora", "1500.00", None),
        ("brujula", "100.00", 10000),
        ("brujula", "1,500.00", None),
    ],
)
def test_cada_fuente_se_lee_con_su_propio_formato_de_monto(config, fuente, texto, centavos):
    assert valores.interpretar_monto(config, fuente, texto, "valor").interpretado == centavos


def test_los_instantes_se_comparan_en_utc():
    assert valores.a_instante_utc("2026-11-02T12:00:00-03:00") == "2026-11-02T15:00:00Z"
    assert valores.a_instante_utc("2026-11-02T12:00:00Z") == "2026-11-02T12:00:00Z"
    # Sin huso, el resultado dependería de la zona de la máquina: no se acepta.
    with pytest.raises(ValueError, match="huso"):
        valores.a_instante_utc("2026-11-02T12:00:00")


def test_sin_una_pieza_obligatoria_la_configuracion_no_se_acepta(tmp_path):
    otra = tmp_path / "config"
    shutil.copytree(CONFIG, otra)
    descriptor = otra / "fuentes" / "aurora.toml"
    lineas = descriptor.read_text(encoding="utf-8").splitlines()
    descriptor.write_text("\n".join(x for x in lineas if "AUR-E-SEP" not in x), encoding="utf-8")
    with pytest.raises(ErrorDeConfiguracion, match="separador"):
        leer_configuracion(otra)
