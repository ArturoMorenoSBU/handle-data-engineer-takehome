# Base compartida de aseguradoras

Un broker necesita saber qué pólizas y cobros le muestra cada aseguradora y contrastarlo con lo que él dice tener. Este repo reúne en una base de datos local las pólizas y los recibos de dos aseguradoras de ejemplo, Brújula (un portal web, en USD) y Aurora (archivos CSV, en BRL), sin perder lo que dijo cada una ni de dónde salió.

Es una prueba de concepto: dos fuentes y pocos datos, todos ficticios.

## Cómo probarlo

Hace falta Python 3.11 o posterior. No se instala nada más para correrlo.

```bash
make construir     # captura las dos aseguradoras y el book, y arma la base en datos/
make respuestas    # muestra las siete respuestas preparadas
make verificar     # estilo y pruebas; este sí necesita uv (https://docs.astral.sh/uv/)
```

Sin `uv`, los dos primeros corren con el Python que tengas: `make construir PY=python3`.

`make construir` arranca el portal de Brújula en tu máquina dos veces, con los datos iniciales y con una corrección, y lee las dos entregas de Aurora. Tarda menos de un segundo.

## Qué responde

| Pregunta | Vista |
|---|---|
| ¿Cuánto está abierto y qué quedó fuera de la suma? | `gold_abierto_conocido` |
| ¿Cuál es el historial de cada recibo? | `gold_historial_recibos` |
| ¿Qué pólizas están en el book, en la fuente o en los dos? | `gold_book` |
| ¿Qué reglas tiene cada fuente y en qué estado? | `gold_reglas` |
| ¿Qué valores no se pudieron usar, y por qué? | `gold_valores_no_validos` |
| ¿De qué campo de cada fuente sale cada nombre común? | `gold_diccionario` |
| ¿Quedó completa cada captura? | `gold_completitud` |

La salida completa está en [docs/evidencia/respuestas.txt](docs/evidencia/respuestas.txt), y la de las pruebas en [docs/evidencia/verificar.txt](docs/evidencia/verificar.txt).

Para escribir tus propias consultas, la base es un archivo SQLite:

```bash
sqlite3 -header -column datos/base.sqlite "SELECT * FROM gold_abierto_conocido"
```

Las tablas `bronze_*` tienen lo que dijo cada fuente, como texto. Las `silver_*`, lo compartido: pólizas, recibos y sus versiones. Las `gold_*` son las vistas de arriba.

## Tres cosas que se ven en los datos

- **Un valor que no se sabe no se inventa.** El recibo `R-103` llega con monto `TBD`. Queda fuera del total y el total lo dice: 130.00 USD abiertos, más un recibo abierto sin monto utilizable.
- **Una corrección no borra lo anterior.** `R-102` pasó de 25.00 a 30.00. Quedan las dos versiones, cada una con la respuesta de donde salió, y una sola vigente.
- **Una propuesta no cambia el resultado.** Una nota sin verificar propone leer `TBD` como cero. Está registrada como propuesta y no se aplica: solo corren las reglas aceptadas.

## Cómo está hecho

| Carpeta | Qué hay |
|---|---|
| `fuentes/` | El portal de Brújula, los archivos de Aurora, el book y las notas de cada fuente, sin modificar |
| `config/` | Lo que se sabe de cada fuente: la lista de reglas y un descriptor por fuente |
| `src/base_compartida/` | El código: captura, carga y vistas |
| `tests/` | Una prueba por comprobación del spec |
| `specs/0001-base-compartida/` | Qué debe cumplir (spec) y cómo se construyó (plan) |
| `docs/adr/` | Las cuatro decisiones de diseño, una página cada una |

Decisiones: [capas](docs/adr/0001-capas-de-la-base.md), [dónde vive lo que se sabe de cada fuente](docs/adr/0002-reglas-de-cada-fuente.md), [cómo se captura el portal](docs/adr/0003-captura-del-portal-de-brujula.md) y [herramientas](docs/adr/0004-herramientas.md).

## Límites

- No convierte monedas ni une registros de aseguradoras distintas: los datos no traen tipo de cambio ni una tabla que diga cuáles son el mismo. Todo total sale por aseguradora, broker y moneda.
- El historial tiene la resolución de las fotos capturadas: si la fuente cambia dos veces entre dos capturas, se ve solo el último valor.
- Lo compartido se recalcula completo en cada carga. Es simple y no deja mezclas, pero no escala; el ADR de capas dice cuál es el paso siguiente.
- No reintenta una página que falla: la registra y marca la captura como incompleta.
