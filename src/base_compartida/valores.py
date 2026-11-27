"""Interpretación de un valor: el texto que llegó, lo que significa y si se pudo usar.

Cada función devuelve las tres cosas juntas, más las piezas que lo decidieron.
Nunca rellena un valor desde otro campo ni repara uno que no cumple su formato.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from base_compartida.config import FORMATOS_DE_FECHA, Configuracion

VALIDO = "valido"
NO_SUMINISTRADO = "no_suministrado"
NULO_EXPLICITO = "nulo_explicito"
NO_UTILIZABLE = "no_utilizable"
INVALIDO = "invalido"

ESTADO_INDETERMINADO = "indeterminado"

# Cómo llegó un campo dentro de su registro.
CON_VALOR, VACIO, NULO, AUSENTE = "valor", "vacio", "nulo", "ausente"


@dataclass(frozen=True)
class Valor:
    texto: str | None
    interpretado: int | str | None
    disposicion: str
    piezas: tuple[str, ...] = ()


def _sin_valor(
    config: Configuracion, fuente: str, texto: str | None, presencia: str
) -> Valor | None:
    """Un campo que no vino, vino vacío o vino nulo. Devuelve None si sí trae valor."""
    if presencia == CON_VALOR:
        return None
    if presencia == VACIO:
        return Valor(texto, None, NO_SUMINISTRADO)
    # Solo una fuente JSON distingue "no vino" de "nulo": lo dice su pieza de estructura.
    pieza = config.aplicables(fuente, "ausente_y_nulo")
    disposicion = NULO_EXPLICITO if presencia == NULO else NO_SUMINISTRADO
    return Valor(None, None, disposicion, tuple(p.id for p in pieza))


def interpretar_monto(
    config: Configuracion, fuente: str, texto: str | None, presencia: str
) -> Valor:
    """Devuelve el monto en centavos enteros, para que las sumas sean exactas."""
    if (faltante := _sin_valor(config, fuente, texto, presencia)) is not None:
        return faltante
    especial = config.textos_especiales(fuente, "monto").get(texto)
    if especial is not None:
        centavos = _a_centavos(especial.valor, ".", "") if especial.valor else None
        return Valor(texto, centavos, especial.disposicion, (especial.id,))
    decimal = config.formato(fuente, "monto_decimal")
    miles = config.formato(fuente, "monto_miles")
    centavos = _a_centavos(texto, decimal.valor, miles.valor)
    disposicion = VALIDO if centavos is not None else INVALIDO
    return Valor(texto, centavos, disposicion, (decimal.id, miles.id))


def _a_centavos(texto: str, decimal: str, miles: str) -> int | None:
    # El separador de miles es opcional: "1.500,00" y "1500,00" son el mismo monto.
    con_miles = rf"\d{{1,3}}(?:{re.escape(miles)}\d{{3}})+|\d+"
    entero = f"(?:{con_miles})" if miles else r"\d+"
    if not re.fullmatch(rf"{entero}(?:{re.escape(decimal)}\d{{1,2}})?", texto):
        return None
    limpio = texto.replace(miles, "") if miles else texto
    return int(Decimal(limpio.replace(decimal, ".")) * 100)


def interpretar_fecha(
    config: Configuracion, fuente: str, texto: str | None, presencia: str
) -> Valor:
    """Devuelve la fecha como año-mes-día. Una fecha que no existe queda inválida."""
    if (faltante := _sin_valor(config, fuente, texto, presencia)) is not None:
        return faltante
    pieza = config.formato(fuente, "vencimiento")
    try:
        fecha: date = datetime.strptime(texto, FORMATOS_DE_FECHA[pieza.valor]).date()
    except (KeyError, ValueError):
        return Valor(texto, None, INVALIDO, (pieza.id,))
    return Valor(texto, fecha.isoformat(), VALIDO, (pieza.id,))


def interpretar_estado(
    config: Configuracion, fuente: str, texto: str | None, presencia: str
) -> Valor:
    """Traduce la etiqueta de la fuente a abierto, pagado o indeterminado.

    Indeterminado es un valor, no una disposición: una etiqueta sin regla llega
    bien (disposición válida) y aun así no se sabe qué significa.
    """
    if (faltante := _sin_valor(config, fuente, texto, presencia)) is not None:
        return Valor(faltante.texto, ESTADO_INDETERMINADO, faltante.disposicion, faltante.piezas)
    pieza = config.mapa_de_estados(fuente).get(texto)
    if pieza is None:
        return Valor(texto, ESTADO_INDETERMINADO, VALIDO)
    return Valor(texto, pieza.valor, VALIDO, (pieza.id,))


def a_instante_utc(texto: str) -> str:
    """Lee una fecha con huso horario y la devuelve en UTC, para comparar instantes.

    Una fecha sin huso no se acepta: leerla dependería de la zona de cada máquina.
    """
    instante = datetime.fromisoformat(texto)
    if instante.tzinfo is None:
        raise ValueError(f"la fecha {texto!r} no trae huso horario")
    return instante.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
