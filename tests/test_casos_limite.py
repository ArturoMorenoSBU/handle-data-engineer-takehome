"""Lo que pasa cuando la fuente no llega como en los datos de ejemplo."""

from __future__ import annotations

import pytest

from apoyo import (
    AURORA,
    BASELINE,
    BROKERS,
    CONFIG,
    ENCABEZADO_DE_RECIBOS,
    FUENTES,
    consultar,
    copia_de_config,
    entrega_de_aurora,
)
from base_compartida import captura, cli
from base_compartida.carga import cargar, rehacer, resultado
from base_compartida.config import ErrorDeConfiguracion, leer_configuracion
from base_compartida.portal import portal

COMPLETITUD = "SELECT declarado, capturado, capturas_no_leidas, completa FROM gold_completitud"
R100_ABIERTO = "alder;P-100;1;R-100;1.500,00;BRL;EM_ABERTO;10/11/2026;;1\n"


def cargar_entrega(tmp_path, base, nombre, fecha, archivos, antes=(), **manifest):
    """Captura las entregas originales que se pidan y después una armada a mano."""
    landing = tmp_path / "landing"
    for original in antes:
        captura.capturar_aurora(landing, AURORA, original)
    carpeta = entrega_de_aurora(tmp_path, nombre, fecha, archivos, **manifest)
    tanda = captura.capturar_aurora(landing, carpeta, nombre)
    cargar(base, landing, CONFIG)
    return tanda


def test_una_revision_menor_que_llega_despues_no_reemplaza_a_la_vigente(tmp_path, base):
    archivos = {"policies.csv": "", "receipts-tardio.csv": ENCABEZADO_DE_RECIBOS + R100_ABIERTO}
    cargar_entrega(
        tmp_path, base, "tardia", "2026-11-04T12:00:00-03:00", archivos, antes=["corrected"]
    )
    sql = "SELECT revision, estado, vigente, observada_desde, observada_hasta"
    sql += " FROM silver_recibo_versiones WHERE recibo_id = 'aurora|alder|R-100' ORDER BY revision"
    assert consultar(base, sql) == [
        (1, "abierto", 0, "2026-11-04T15:00:00Z", None),
        (2, "pagado", 1, "2026-11-03T15:00:00Z", None),
    ]
    sql = "SELECT abierto_conocido FROM gold_abierto_conocido WHERE broker = 'alder'"
    assert consultar(base, sql) == [("0.00",)]


def test_una_poliza_que_cambia_tiene_dos_versiones_y_una_vigente(tmp_path, base):
    polizas = (AURORA / "policies.csv").read_text(encoding="utf-8")
    cambiada = polizas.replace(
        "alder;P-100;CLI-001;AUTO;ATIVA", "alder;P-100;CLI-001;AUTO;SUSPENSA"
    )
    archivos = {"policies.csv": cambiada, "receipts-corrected.csv": ""}
    cargar_entrega(
        tmp_path, base, "cambio", "2026-11-04T12:00:00-03:00", archivos, antes=["baseline"]
    )
    sql = "SELECT version, vigente, observada_desde, observada_hasta FROM silver_poliza_versiones"
    sql += " WHERE poliza_id = 'aurora|alder|P-100' ORDER BY version"
    assert consultar(base, sql) == [
        (1, 0, "2026-11-02T15:00:00Z", "2026-11-04T15:00:00Z"),
        (2, 1, "2026-11-04T15:00:00Z", None),
    ]
    sql = "SELECT poliza_id, COUNT(*), SUM(vigente) FROM silver_poliza_versiones"
    sql += " WHERE poliza_id <> 'aurora|alder|P-100' GROUP BY poliza_id"
    assert consultar(base, sql) == [("aurora|alder|000123", 1, 1), ("aurora|birch|P-100", 1, 1)]


def test_un_archivo_que_el_manifest_lista_y_no_llega_deja_la_captura_incompleta(tmp_path, base):
    archivos = {"policies.csv": "", "receipts-perdido.csv": None}
    cargar_entrega(tmp_path, base, "incompleta", "2026-11-04T12:00:00-03:00", archivos)
    assert consultar(base, COMPLETITUD) == [(2, 1, 1, "no")]


def test_un_manifest_que_no_coincide_con_el_descriptor_no_se_lee(tmp_path, base):
    archivos = {"policies.csv": "", "receipts-baseline.csv": ""}
    cargar_entrega(
        tmp_path, base, "otra_forma", "2026-11-04T12:00:00-03:00", archivos, decimal_separator="."
    )
    sql = "SELECT DISTINCT resultado, causa LIKE '%decimal_separator%' FROM bronze_capturas"
    assert consultar(base, sql) == [("forma_no_reconocida", 1)]
    assert consultar(base, "SELECT COUNT(*) FROM silver_recibos") == [(0,)]


def test_una_fecha_de_foto_sin_huso_no_se_lee(tmp_path, base):
    archivos = {"policies.csv": "", "receipts-baseline.csv": ""}
    cargar_entrega(tmp_path, base, "sin_huso", "2026-11-04T12:00:00", archivos)
    sql = "SELECT DISTINCT resultado, causa LIKE '%huso%' FROM bronze_capturas"
    assert consultar(base, sql) == [("forma_no_reconocida", 1)]


def test_una_marca_inicial_en_el_archivo_no_mezcla_brokers(tmp_path, base):
    recibos = (AURORA / "receipts-baseline.csv").read_text(encoding="utf-8")
    archivos = {"policies.csv": "", "receipts-marca.csv": "﻿" + recibos}
    cargar_entrega(tmp_path, base, "con_marca", "2026-11-04T12:00:00-03:00", archivos)
    sql = "SELECT broker, COUNT(*) FROM silver_recibos GROUP BY broker"
    assert consultar(base, sql) == [("alder", 3), ("birch", 1)]


def test_un_encabezado_sin_un_campo_de_identidad_no_se_lee(tmp_path, base):
    recibos = (AURORA / "receipts-baseline.csv").read_text(encoding="utf-8")
    archivos = {
        "policies.csv": "",
        "receipts-renombrado.csv": recibos.replace("corretora", "corredor", 1),
    }
    cargar_entrega(tmp_path, base, "renombrada", "2026-11-04T12:00:00-03:00", archivos)
    sql = "SELECT resultado, causa FROM bronze_capturas WHERE pedido = 'receipts-renombrado.csv'"
    assert consultar(base, sql) == [
        ("forma_no_reconocida", "al encabezado le faltan campos: corretora")
    ]
    assert consultar(base, "SELECT COUNT(*) FROM silver_recibos") == [(0,)]
    assert consultar(base, "SELECT COUNT(*) FROM silver_polizas") == [(3,)]


def test_una_respuesta_sin_fecha_de_foto_no_detiene_la_carga(copia_de_landing, base):
    pagina = copia_de_landing / "brujula-0001" / "003_alder_receipts_p2.json"
    texto = pagina.read_text(encoding="utf-8")
    pagina.write_text(
        texto.replace('"source_as_of": "2026-11-02T12:00:00Z", ', ""), encoding="utf-8"
    )
    cargar(base, copia_de_landing, CONFIG, BASELINE)
    sql = COMPLETITUD + " WHERE broker = 'alder' AND tipo = 'recibos'"
    assert consultar(base, sql) == [(4, 2, 1, "no")]


def test_el_total_mira_la_ultima_captura_no_una_falla_ya_superada(tmp_path, base):
    landing = tmp_path / "landing"
    for escenario in ("failure", "baseline"):
        with portal(FUENTES, escenario) as url:
            captura.capturar_brujula(landing, url, BROKERS, "demo")
    cargar(base, landing, CONFIG)
    sql = "SELECT broker, abierto_conocido, ultima_captura_completa FROM gold_abierto_conocido"
    assert consultar(base, sql) == [("alder", "125.00", "sí"), ("birch", "80.00", "sí")]


def test_construir_solo_borra_lo_que_genera(tmp_path, capsys):
    ajeno = tmp_path / "notas.txt"
    ajeno.write_text("no es de este comando", encoding="utf-8")
    cli.construir(FUENTES, tmp_path, CONFIG)
    cli.construir(FUENTES, tmp_path, CONFIG)
    assert ajeno.exists()
    assert sorted(p.name for p in (tmp_path / "landing").iterdir()) == sorted(
        [*BASELINE, "brujula-0002", "aurora-0002"]
    )
    assert "Base construida" in capsys.readouterr().out


def test_si_rehacer_falla_la_base_anterior_se_conserva(landing, base, tmp_path):
    cargar(base, landing, CONFIG)
    antes = resultado(base)
    rota = copia_de_config(tmp_path / "config", "fuentes/aurora.toml", 'valor = ";"', 'valor = "|"')
    with pytest.raises(ErrorDeConfiguracion):
        rehacer(
            base, landing, copia_de_config(tmp_path / "c2", "reglas.toml", "aceptada", "vigente")
        )
    assert resultado(base) == antes
    # Con otro separador, Aurora deja de coincidir con su manifest: se rehace, sin sus filas.
    rehacer(base, landing, rota)
    assert consultar(base, "SELECT COUNT(*) FROM silver_recibos WHERE aseguradora = 'aurora'") == [
        (0,)
    ]


def test_una_pieza_que_el_codigo_no_sabe_cumplir_detiene_la_carga(tmp_path):
    otra = copia_de_config(
        tmp_path / "config",
        "fuentes/aurora.toml",
        'valor = "primera_linea"',
        'valor = "sin_encabezado"',
    )
    with pytest.raises(ErrorDeConfiguracion, match="AUR-E-ENC"):
        leer_configuracion(otra)


def test_dos_piezas_aceptadas_sobre_el_mismo_texto_no_se_aplican(landing, base, tmp_path):
    assert leer_configuracion(CONFIG).revisar_conflictos() == []
    # Si alguien aceptara AGENT-22 sin retirar CONTRACT-17, ninguna de las dos decide.
    aceptada = '{ id = "AGENT-22", fuente = "brujula", estado = "aceptada"'
    propuesta = '{ id = "AGENT-22", fuente = "brujula", estado = "propuesta"'
    otra = copia_de_config(tmp_path / "config", "reglas.toml", propuesta, aceptada)
    (conflicto,) = leer_configuracion(otra).revisar_conflictos()
    assert "BRU-S-TBD" in conflicto and "BRU-S-TBD-CERO" in conflicto
    cargar(base, landing, otra)
    sql = "SELECT monto_centavos, monto_disposicion FROM silver_recibo_versiones"
    sql += " WHERE recibo_id = 'brujula|alder|R-103'"
    assert consultar(base, sql) == [(None, "invalido")]


def test_una_tabla_sin_filas_se_imprime(capsys):
    cli.imprimir_tabla(["regla", "estado"], [])
    assert capsys.readouterr().out.splitlines() == ["regla  estado", "-----  ------", "(sin filas)"]
