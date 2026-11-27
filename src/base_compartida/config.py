"""Lo que se sabe de cada fuente: la lista de reglas y las piezas de cada descriptor.

Una regla dice qué se sabe y con qué autoridad. Una pieza es una instrucción
concreta que la carga ejecuta y que cita una regla. Solo corren las piezas de
reglas aceptadas: aquí está ese filtro, y nada más abajo lo vuelve a decidir.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ESTADOS_DE_REGLA = ("propuesta", "aceptada", "rechazada")
ASEGURADORAS = ("brujula", "aurora")
FUENTES = (*ASEGURADORAS, "book")
TIPOS = {"brujula": ("polizas", "recibos"), "aurora": ("polizas", "recibos"), "book": ("book",)}

# Datos que la carga necesita sí o sí. Cada uno pide exactamente una pieza aplicable.
NOMBRES_COMUNES_DEL_RECIBO = (
    "poliza_del_recibo",
    "monto",
    "moneda",
    "vencimiento",
    "estado",
    "revision",
)
_FORMATOS = ("monto_decimal", "monto_miles", "vencimiento", "revision", "fecha_foto")
FORMATOS_DE_FECHA = {"YYYY-MM-DD": "%Y-%m-%d", "DD/MM/YYYY": "%d/%m/%Y"}

# Valores que el código sabe ejecutar. Una pieza que pide otro detiene la carga:
# así ninguna pieza queda escrita sin que algo la cumpla.
_VALORES_ADMITIDOS = {
    "clase": {"csv", "json"},
    "encabezado": {"primera_linea"},
    "ausente_y_nulo": {"distintos"},
    "formato:revision": {"entero"},
    "formato:fecha_foto": {"iso8601"},
    "formato:vencimiento": set(FORMATOS_DE_FECHA),
}


class ErrorDeConfiguracion(Exception):
    """La lista de reglas o un descriptor no permiten leer una fuente."""


@dataclass(frozen=True)
class Regla:
    id: str
    fuente: str
    estado: str
    origen: str
    fecha: str
    propuesta_por: str
    decidida_por: str
    nota: str
    dice: str


@dataclass(frozen=True)
class Pieza:
    id: str
    regla: str
    fuente: str
    apartado: str
    dato: str
    tipo: str = ""
    campo: str = ""
    valor: str = ""
    etiqueta: str = ""
    sobre: str = ""
    texto: str = ""
    disposicion: str = ""


@dataclass
class Configuracion:
    reglas: list[Regla]
    piezas: list[Pieza]
    conflictos: list[str] = field(default_factory=list)

    def es_aplicable(self, pieza: Pieza) -> bool:
        estados = {r.id: r.estado for r in self.reglas}
        return estados[pieza.regla] == "aceptada"

    def aplicables(self, fuente: str, dato: str | None = None, tipo: str = "") -> list[Pieza]:
        return [
            p
            for p in self.piezas
            if p.fuente == fuente
            and self.es_aplicable(p)
            and (dato is None or p.dato == dato)
            and (not tipo or p.tipo in ("", tipo))
        ]

    def una(self, fuente: str, dato: str, tipo: str = "") -> Pieza:
        """La única pieza aplicable de un dato obligatorio. Si no hay una sola, es error."""
        halladas = self.aplicables(fuente, dato, tipo)
        if len(halladas) != 1:
            ids = ", ".join(p.id for p in halladas) or "ninguna"
            sufijo = f" ({tipo})" if tipo else ""
            raise ErrorDeConfiguracion(
                f"{fuente}: el dato '{dato}'{sufijo} necesita una pieza aplicable y tiene: {ids}"
            )
        return halladas[0]

    def campo(self, fuente: str, nombre: str, tipo: str) -> Pieza:
        return self.una(fuente, f"campo:{nombre}", tipo)

    def formato(self, fuente: str, nombre: str) -> Pieza:
        return self.una(fuente, f"formato:{nombre}")

    def mapa_de_estados(self, fuente: str) -> dict[str, Pieza]:
        return self._sin_repetidos(fuente, "estado", lambda p: p.etiqueta)

    def textos_especiales(self, fuente: str, sobre: str) -> dict[str, Pieza]:
        piezas = self._sin_repetidos(fuente, "texto_especial", lambda p: (p.sobre, p.texto))
        return {texto: p for (campo, texto), p in piezas.items() if campo == sobre}

    def _sin_repetidos(self, fuente: str, dato: str, llave) -> dict:
        """Si dos piezas aplicables cubren lo mismo, no se aplica ninguna.

        El choque queda en `conflictos`; `revisar_conflictos` los junta todos.
        """
        vistas: dict = {}
        repetidas = set()
        for pieza in self.aplicables(fuente, dato):
            k = llave(pieza)
            if k in vistas:
                repetidas.add(k)
                aviso = f"{fuente}: {vistas[k].id} y {pieza.id} cubren lo mismo ({k})"
                if aviso not in self.conflictos:
                    self.conflictos.append(aviso)
            vistas[k] = pieza
        return {k: p for k, p in vistas.items() if k not in repetidas}

    def clase(self, fuente: str) -> str:
        return self.una(fuente, "clase").valor

    def comprobar(self) -> None:
        """Termina con error, antes de escribir nada, si falta o sobra una pieza obligatoria."""
        for fuente in FUENTES:
            for dato, tipo in _obligatorios(fuente, self.clase(fuente)):
                pieza = self.una(fuente, dato, tipo)
                admitidos = _VALORES_ADMITIDOS.get(dato)
                if admitidos and pieza.valor not in admitidos:
                    raise ErrorDeConfiguracion(
                        f"{pieza.id}: el código no sabe leer '{dato}' como '{pieza.valor}'"
                    )

    def revisar_conflictos(self) -> list[str]:
        """Piezas aplicables que cubren la misma etiqueta o el mismo texto especial."""
        for fuente in ASEGURADORAS:
            self.mapa_de_estados(fuente)
            self._sin_repetidos(fuente, "texto_especial", lambda p: (p.sobre, p.texto))
        return self.conflictos

    def firma_de_lectura(self, fuente: str) -> str:
        """Lo que bronze usa para leer una fuente. Si cambia, hay que rehacer la base."""
        leidas = [p for p in self.aplicables(fuente) if p.apartado == "estructura"]
        if fuente == "aurora":
            leidas += [self.formato(fuente, n) for n in _FORMATOS[:3]]
        return "|".join(sorted(f"{p.dato}/{p.tipo}/{p.campo}/{p.valor}" for p in leidas))


def _obligatorios(fuente: str, clase: str) -> list[tuple[str, str]]:
    datos = [("clase", "")] + [("registros", t) for t in TIPOS[fuente]]
    if clase == "csv":
        datos += [("codificacion", ""), ("separador", ""), ("encabezado", "")]
    if clase == "json":
        datos += [("ausente_y_nulo", "")]
    if fuente == "book":
        nombres = ("aseguradora", "broker", "numero_poliza", "referencia_cliente")
        return datos + [(f"campo:{n}", "book") for n in nombres]
    datos += [("campo:broker", "polizas"), ("campo:broker", "recibos")]
    datos += [("campo:numero_poliza", "polizas"), ("campo:numero_recibo", "recibos")]
    datos += [("fecha_foto", ""), ("completitud", "")]
    datos += [(f"campo:{n}", "recibos") for n in NOMBRES_COMUNES_DEL_RECIBO]
    return datos + [(f"formato:{n}", "") for n in _FORMATOS]


def leer_configuracion(carpeta: Path) -> Configuracion:
    """Lee `reglas.toml` y `fuentes/*.toml` de la carpeta de configuración."""
    crudo = tomllib.loads((carpeta / "reglas.toml").read_text(encoding="utf-8"))
    reglas = [Regla(**r) for r in crudo["regla"]]
    conocidas = {r.id for r in reglas}
    for regla in reglas:
        if regla.estado not in ESTADOS_DE_REGLA:
            raise ErrorDeConfiguracion(f"{regla.id}: estado desconocido '{regla.estado}'")
    piezas = []
    for archivo in sorted((carpeta / "fuentes").glob("*.toml")):
        descriptor = tomllib.loads(archivo.read_text(encoding="utf-8"))
        for p in descriptor["pieza"]:
            pieza = Pieza(fuente=descriptor["fuente"], **p)
            if pieza.regla not in conocidas:
                raise ErrorDeConfiguracion(f"{pieza.id}: cita una regla que no existe")
            piezas.append(pieza)
    configuracion = Configuracion(reglas=reglas, piezas=piezas)
    configuracion.comprobar()
    return configuracion
