"""Una prueba por comprobación de la sección 8 del spec, con los datos del lab."""

from __future__ import annotations

import shutil

import pytest

from apoyo import BASELINE, BROKERS, CONFIG, CORRECTED, FUENTES, consultar
from base_compartida import captura, cli
from base_compartida.bronze import HayQueRehacer
from base_compartida.carga import cargar, rehacer, resultado
from base_compartida.portal import portal

TOTALES = "SELECT aseguradora, broker, moneda, abierto_conocido, abiertos_sin_monto_utilizable,"
TOTALES += " con_estado_indeterminado, monto_indeterminado FROM gold_abierto_conocido"


def versiones(base, aseguradora, broker, recibo):
    sql = "SELECT revision, monto, estado_fuente, vigente, apariciones, origen"
    sql += " FROM gold_historial_recibos WHERE aseguradora=? AND broker=? AND numero_recibo=?"
    return consultar(base, sql, aseguradora, broker, recibo)


def test_01_totales_con_baseline_y_despues_con_corrected(landing, base):
    cargar(base, landing, CONFIG, BASELINE)
    assert consultar(base, TOTALES) == [
        ("aurora", "alder", "BRL", "1500.00", 0, 1, "2400.50"),
        ("aurora", "birch", "BRL", "800.00", 0, 0, "0.00"),
        ("brujula", "alder", "USD", "125.00", 1, 0, "0.00"),
        ("brujula", "birch", "USD", "80.00", 0, 0, "0.00"),
    ]
    cargar(base, landing, CONFIG, CORRECTED)
    assert consultar(base, TOTALES) == [
        ("aurora", "alder", "BRL", "0.00", 0, 1, "2400.50"),
        ("aurora", "birch", "BRL", "800.00", 0, 0, "0.00"),
        ("brujula", "alder", "USD", "130.00", 1, 0, "0.00"),
        ("brujula", "birch", "USD", "80.00", 0, 0, "0.00"),
    ]


def test_02_identidad_por_aseguradora_broker_y_numero(completa):
    sql = "SELECT COUNT(*) FROM silver_recibos WHERE numero_recibo = 'R-100'"
    assert consultar(completa, sql) == [(4,)]
    sql = "SELECT COUNT(*) FROM silver_polizas WHERE numero_poliza = 'P-100'"
    assert consultar(completa, sql) == [(4,)]
    sql = "SELECT numero_poliza FROM silver_polizas WHERE poliza_id = 'aurora|alder|000123'"
    assert consultar(completa, sql) == [("000123",)]


def test_03_cada_recibo_pertenece_a_una_poliza_de_su_aseguradora_y_broker(completa):
    sql = "SELECT numero_recibo, poliza_id FROM silver_recibos"
    sql += " WHERE aseguradora='brujula' AND broker='alder' AND numero_recibo IN ('R-102','R-103')"
    assert sorted(consultar(completa, sql)) == [
        ("R-102", "brujula|alder|P-200"),
        ("R-103", "brujula|alder|P-200"),
    ]
    sql = "SELECT COUNT(*) FROM silver_recibos"
    sql += " WHERE poliza_id NOT LIKE aseguradora || '|' || broker || '|%'"
    assert consultar(completa, sql) == [(0,)]
    sql = "SELECT COUNT(*) FROM silver_recibos r"
    sql += " LEFT JOIN silver_polizas p USING (poliza_id) WHERE p.poliza_id IS NULL"
    assert consultar(completa, sql) == [(0,)]


def test_04_texto_valor_y_disposicion(completa):
    sql = "SELECT DISTINCT aseguradora, broker, numero_recibo, campo, texto, disposicion, reglas"
    sql += " FROM gold_valores_no_validos"
    assert sorted(consultar(completa, sql), key=repr) == sorted(
        [
            ("aurora", "alder", "R-102", "vencimiento", "31/11/2026", "invalido", "AUR-01"),
            ("brujula", "alder", "R-101", "vencimiento", None, "nulo_explicito", "BRU-PORTAL"),
            ("brujula", "alder", "R-102", "vencimiento", None, "no_suministrado", "BRU-PORTAL"),
            ("brujula", "alder", "R-103", "monto", "TBD", "no_utilizable", "CONTRACT-17"),
        ],
        key=repr,
    )
    # Un valor que no es válido queda vacío: no se repara ni se rellena desde otro campo.
    sql = "SELECT COUNT(*) FROM silver_recibo_versiones WHERE"
    sql += " (monto_disposicion <> 'valido' AND monto_centavos IS NOT NULL)"
    sql += " OR (vencimiento_disposicion <> 'valido' AND vencimiento IS NOT NULL)"
    assert consultar(completa, sql) == [(0,)]
    # Los que sí son válidos se leen con el formato que declara cada fuente.
    sql = "SELECT monto_texto, monto_centavos, vencimiento_texto, vencimiento"
    sql += " FROM silver_recibo_versiones WHERE recibo_id = 'aurora|alder|R-100' AND vigente = 1"
    assert consultar(completa, sql) == [("1.500,00", 150000, "10/11/2026", "2026-11-10")]


def test_05_nombres_comunes_y_datos_propios_de_cada_fuente(completa):
    sql = "SELECT nombre_comun, fuente, campo_de_la_fuente FROM gold_diccionario"
    sql += " WHERE tipo_de_registro = 'recibos' OR nombre_comun = 'numero_poliza'"
    diccionario = {(n, f): c for n, f, c in consultar(completa, sql) if f != "book"}
    esperado = {
        "broker": ("la sesión con la que se consultó", "corretora"),
        "numero_poliza": ("policy_number", "numero_apolice"),
        "numero_recibo": ("receipt_number", "id_cobranca"),
        "monto": ("amount", "valor_parcela"),
        "moneda": ("currency", "moeda"),
        "vencimiento": ("due_date", "vencimento"),
        "estado": ("status", "status_cobranca"),
        "revision": ("revision", "revisao"),
    }
    for nombre, (brujula, aurora) in esperado.items():
        assert diccionario[(nombre, "brujula")] == brujula
        assert diccionario[(nombre, "aurora")] == aurora
    # Lo propio de Aurora se conserva con su texto original y se puede consultar.
    sql = "SELECT DISTINCT inicio_vigencia, fim_vigencia, premio_total, ramo, situacao"
    sql += " FROM bronze_aurora_polizas WHERE corretora='alder' AND numero_apolice='P-100'"
    assert consultar(completa, sql) == [("01/01/2026", "31/12/2026", "1.500,00", "AUTO", "ATIVA")]
    sql = "SELECT DISTINCT data_pagamento, numero_parcela FROM bronze_aurora_recibos"
    sql += " WHERE corretora='alder' AND id_cobranca='R-100' AND revisao='2'"
    assert consultar(completa, sql) == [("03/11/2026", "1")]


def test_06_cargar_otra_vez_la_misma_foto_no_cambia_nada(copia_de_landing, base):
    cargar(base, copia_de_landing, CONFIG)
    antes = resultado(base)
    assert cargar(base, copia_de_landing, CONFIG) == []
    assert resultado(base) == antes
    # La misma foto de Aurora, capturada de nuevo en otra tanda.
    captura.capturar_aurora(copia_de_landing, FUENTES / "fixtures" / "aurora", "baseline")
    assert cargar(base, copia_de_landing, CONFIG) == ["aurora-0003"]
    assert resultado(base) == antes


def test_07_la_fila_repetida_es_un_solo_recibo_y_queda_registrada(landing, base):
    cargar(base, landing, CONFIG, BASELINE)
    sql = "SELECT COUNT(*) FROM silver_recibos WHERE recibo_id = 'aurora|alder|R-100'"
    assert consultar(base, sql) == [(1,)]
    ((revision, _, _, _, apariciones, origen),) = versiones(base, "aurora", "alder", "R-100")
    assert (revision, apariciones) == (1, 2)
    assert "receipts-baseline.csv posición 2" in origen
    assert "receipts-baseline.csv posición 5" in origen


def test_08_historial_con_una_sola_version_vigente(completa):
    historial = [fila[:4] for fila in versiones(completa, "brujula", "alder", "R-102")]
    assert historial == [(1, "25.00", "outstanding", 0), (2, "30.00", "outstanding", 1)]
    historial = [fila[:4] for fila in versiones(completa, "aurora", "alder", "R-100")]
    assert historial == [(1, "1.500,00", "EM_ABERTO", 0), (2, "1.500,00", "LIQUIDADO", 1)]
    for aseguradora in ("brujula", "aurora"):
        assert len(versiones(completa, aseguradora, "birch", "R-100")) == 1
    for tabla, llave in (("recibo", "recibo_id"), ("poliza", "poliza_id")):
        sql = f"SELECT COUNT(*) FROM (SELECT {llave} FROM silver_{tabla}_versiones"
        sql += f" GROUP BY {llave} HAVING SUM(vigente) <> 1)"
        assert consultar(completa, sql) == [(0,)]


def test_09_el_orden_de_carga_no_cambia_el_resultado(landing, completa, base):
    cargar(base, landing, CONFIG, CORRECTED)
    cargar(base, landing, CONFIG, BASELINE)
    assert resultado(base) == resultado(completa)


def test_10_rehacer_desde_las_capturas_da_el_mismo_resultado(copia_de_landing, base):
    cargar(base, copia_de_landing, CONFIG, BASELINE)
    cargar(base, copia_de_landing, CONFIG, CORRECTED)
    antes = resultado(base)
    assert sorted(rehacer(base, copia_de_landing, CONFIG)) == sorted(BASELINE + CORRECTED)
    assert resultado(base) == antes


def test_11_procedencia_y_contexto_de_cada_captura(completa):
    origenes = [fila[5] for fila in versiones(completa, "brujula", "alder", "R-102")]
    assert origenes == [
        "brujula-0001 /api/receipts?page=2 posición 1",
        "brujula-0002 /api/receipts?page=2 posición 1",
    ]
    corregido = versiones(completa, "aurora", "alder", "R-100")[1][5]
    assert corregido == "aurora-0002 receipts-corrected.csv posición 2"
    sql = "SELECT COUNT(*) FROM bronze_capturas WHERE tanda_id IS NULL OR pedido IS NULL"
    sql += " OR capturado_en IS NULL OR resultado IS NULL OR archivo IS NULL"
    sql += " OR (fuente = 'brujula' AND broker IS NULL)"
    sql += " OR (fuente <> 'book' AND resultado = 'leida' AND fecha_fuente IS NULL)"
    assert consultar(completa, sql) == [(0,)]


def test_12_completitud_de_cada_captura(completa):
    sql = "SELECT broker, tipo, declarado, capturado, completa FROM gold_completitud"
    sql += " WHERE tanda_id = 'brujula-0001'"
    assert consultar(completa, sql) == [
        ("alder", "polizas", 2, 2, "sí"),
        ("alder", "recibos", 4, 4, "sí"),
        ("birch", "polizas", 1, 1, "sí"),
        ("birch", "recibos", 1, 1, "sí"),
    ]
    sql = "SELECT tanda_id, declarado, capturado, completa FROM gold_completitud"
    sql += " WHERE fuente = 'aurora'"
    assert consultar(completa, sql) == [("aurora-0001", 2, 2, "sí"), ("aurora-0002", 2, 2, "sí")]


def test_13_la_prima_no_entra_a_ninguna_suma(landing, base):
    cargar(base, landing, CONFIG, BASELINE)
    # Prima de alder/P-100: 1500.00. Sus recibos: 1500.00 abierto y 150.00 pagado.
    sql = "SELECT abierto_centavos FROM gold_abierto_conocido"
    sql += " WHERE aseguradora = 'aurora' AND broker = 'alder'"
    assert consultar(base, sql) == [(150000,)]
    columnas = {fila[1] for fila in consultar(base, "PRAGMA table_info(silver_recibo_versiones)")}
    assert not {c for c in columnas if "prima" in c or "premio" in c}


def test_14_solo_se_aplican_las_reglas_aceptadas(landing, completa, base, tmp_path):
    sql = "SELECT regla, estado, fecha, piezas_que_se_aplican FROM gold_reglas"
    sql += " WHERE regla IN ('CONTRACT-17', 'AGENT-22') ORDER BY regla"
    (agent, estado_a, fecha_a, aplica_a), (contrato, estado_c, fecha_c, aplica_c) = consultar(
        completa, sql
    )
    assert (agent, estado_a, aplica_a) == ("AGENT-22", "propuesta", 0)
    assert (contrato, estado_c, aplica_c) == ("CONTRACT-17", "aceptada", 1)
    assert fecha_a > fecha_c  # La propuesta es más reciente: la fecha no decide.
    sql = "SELECT COUNT(*) FROM silver_reglas WHERE '' IN (id, fuente, estado, origen, fecha,"
    sql += " propuesta_por, nota) OR (estado <> 'propuesta' AND decidida_por = '')"
    assert consultar(completa, sql) == [(0,)]
    # El mismo resultado con AGENT-22 registrada y sin ella.
    sin_agente = tmp_path / "config"
    shutil.copytree(CONFIG, sin_agente)
    for archivo in (sin_agente / "reglas.toml", sin_agente / "fuentes" / "brujula.toml"):
        lineas = archivo.read_text(encoding="utf-8").splitlines()
        archivo.write_text("\n".join(x for x in lineas if "AGENT-22" not in x), encoding="utf-8")
    cargar(base, landing, sin_agente)
    assert consultar(base, "SELECT COUNT(*) FROM silver_reglas WHERE id = 'AGENT-22'") == [(0,)]
    assert resultado(base) == resultado(completa)
    # Y el sistema dice qué regla decidió el monto de R-103.
    sql = "SELECT monto_disposicion, monto_centavos, p.regla FROM silver_recibo_versiones v"
    sql += " JOIN silver_piezas p ON p.id = v.monto_piezas WHERE recibo_id = 'brujula|alder|R-103'"
    assert consultar(completa, sql) == [("no_utilizable", None, "CONTRACT-17")]


def test_15_comparacion_con_el_book(completa):
    solo_en_el_book = "el book la afirma, la fuente no la muestra"
    sql = "SELECT situacion, COUNT(*) FROM gold_book GROUP BY situacion"
    situaciones = dict(consultar(completa, sql))
    assert situaciones == {"en el book y en la fuente": 6, solo_en_el_book: 2}
    assert not [s for s in situaciones if "cancel" in s.lower()]
    sql = "SELECT aseguradora, broker, numero_poliza FROM gold_book WHERE situacion = ?"
    assert consultar(completa, sql, solo_en_el_book) == [
        ("aurora", "alder", "000999"),
        ("brujula", "alder", "P-300"),
    ]
    sql = "SELECT aseguradora, SUM(referencia_en_el_book = referencia_en_la_fuente), COUNT(*)"
    sql += " FROM gold_book WHERE referencia_en_la_fuente IS NOT NULL GROUP BY aseguradora"
    assert consultar(completa, sql) == [("aurora", 0, 3), ("brujula", 3, 3)]


def test_16_el_comando_de_respuestas_trae_una_seccion_por_pregunta(completa, capsys):
    cli.respuestas(completa)
    salida = capsys.readouterr().out
    vistas = (
        "gold_abierto_conocido",
        "gold_historial_recibos",
        "gold_book",
        "gold_reglas",
        "gold_valores_no_validos",
        "gold_diccionario",
        "gold_completitud",
    )
    for vista in vistas:
        assert f"(vista: {vista})" in salida
    assert salida.count("\n## ¿") == 7
    # El origen se imprime entero: la fila repetida de Aurora muestra sus dos líneas.
    assert (
        "receipts-baseline.csv posición 2; aurora-0001 receipts-baseline.csv posición 5" in salida
    )


@pytest.mark.parametrize(
    ("escenario", "resultado_de_la_pagina"),
    [("failure", "fallo"), ("drift", "forma_no_reconocida")],
)
def test_una_pagina_que_falla_o_cambia_de_forma_no_es_una_pagina_vacia(
    escenario, resultado_de_la_pagina, tmp_path, base
):
    landing = tmp_path / "landing"
    with portal(FUENTES, escenario) as url:
        captura.capturar_brujula(landing, url, BROKERS, "demo")
    cargar(base, landing, CONFIG)
    sql = "SELECT declarado, capturado, capturas_no_leidas, completa FROM gold_completitud"
    sql += " WHERE broker = 'alder' AND tipo = 'recibos'"
    assert consultar(base, sql) == [(4, 2, 1, "no")]
    sql = "SELECT resultado, causa IS NOT NULL FROM bronze_capturas"
    sql += " WHERE broker = 'alder' AND pedido = '/api/receipts?page=2'"
    assert consultar(base, sql) == [(resultado_de_la_pagina, 1)]
    sql = "SELECT completa FROM gold_completitud WHERE broker = 'birch' AND tipo = 'recibos'"
    assert consultar(base, sql) == [("sí",)]
    # El total de alder sale más bajo, y al lado dice que la captura no está completa.
    sql = "SELECT broker, abierto_conocido, ultima_captura_completa FROM gold_abierto_conocido"
    assert consultar(base, sql) == [("alder", "100.00", "no"), ("birch", "80.00", "sí")]


def test_una_sesion_rechazada_queda_como_captura_fallida(tmp_path, base):
    landing = tmp_path / "landing"
    with portal(FUENTES, "baseline") as url:
        captura.capturar_brujula(landing, url, ["alder"], "clave-equivocada")
    cargar(base, landing, CONFIG)
    sql = "SELECT pedido, resultado, causa FROM bronze_capturas"
    assert consultar(base, sql) == [("/login", "fallo", "inicio de sesión rechazado (HTTP 401)")]
    sql = "SELECT tipo, completa FROM gold_completitud"
    assert consultar(base, sql) == [("sesion", "no")]


def test_cambiar_como_se_lee_una_fuente_obliga_a_rehacer(landing, base, tmp_path):
    cargar(base, landing, CONFIG, BASELINE)
    otra = tmp_path / "config"
    shutil.copytree(CONFIG, otra)
    descriptor = otra / "fuentes" / "brujula.toml"
    cambiado = descriptor.read_text(encoding="utf-8").replace(
        'valor = "receipts"', 'valor = "items"'
    )
    descriptor.write_text(cambiado, encoding="utf-8")
    antes = resultado(base)
    with pytest.raises(HayQueRehacer):
        cargar(base, landing, otra, CORRECTED)
    assert resultado(base) == antes  # Una carga que termina con error no cambia nada.
    assert consultar(base, "SELECT COUNT(*) FROM bronze_capturas") == [(9,)]
