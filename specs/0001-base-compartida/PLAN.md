# Plan: Base compartida para Brújula y Aurora

Cita: `SPEC.md` y los ADRs 0001 (capas), 0002 (reglas de cada fuente), 0003 (extracción de Brújula) y 0004 (herramientas).

## Enfoque
Se construyen los 35 criterios obligatorios (CA-01 a CA-35). Los deseables (CD-01 a CD-09) quedan como siguiente incremento. La comprobación de cada rebanada es `make verificar`.

## Archivos a crear o cambiar
- `fuentes/`: el paquete con el portal de Brújula, los archivos de Aurora, el book y las notas de cada fuente, sin modificar.
- `config/reglas.toml` y `config/fuentes/*.toml`: la lista de reglas y el descriptor de cada fuente.
- `src/base_compartida/`: un módulo por responsabilidad.

| Módulo | Qué hace |
|---|---|
| `captura.py` | Guarda cada respuesta o archivo tal como llegó, con su contexto |
| `portal.py` | Arranca y detiene el portal de Brújula en un escenario |
| `config.py` | Lee reglas y descriptores y deja solo las piezas de reglas aceptadas |
| `bronze.py` | Pasa las capturas a tablas de texto, una fila por aparición |
| `valores.py` | Interpreta monto, fecha y estado, y les da una disposición |
| `silver.py` | Recalcula pólizas, recibos, versiones y el book |
| `gold.py` | Define las vistas que responden las preguntas preparadas |
| `carga.py` | Une los pasos en una carga que no deja nada a medias, y rehace la base |
| `cli.py` | Comandos: construir, cargar, rehacer y respuestas |

- `tests/`: una prueba por comprobación de la sección 8 del spec.
- `Makefile`, `pyproject.toml` y `README.md`.

## Configuración concreta
- Datos generados en `datos/` (capturas y base); git los ignora, porque se rehacen con un comando.
- `make construir` arranca el portal en `baseline` y en `corrected`, captura las dos aseguradoras y el book, y carga.
- `make respuestas` muestra las siete respuestas preparadas. `make verificar` corre `ruff` y `pytest`.

## Rebanadas
- [x] 1. Bala trazadora: un recibo de cada aseguradora, de la captura a una vista — comprobación: el total abierto de birch sale 80.00 USD y 800.00 BRL.
- [x] 2. Captura completa con contexto y completitud — comprobación: alder 4 de 4 recibos; `failure` deja 2 de 4.
- [x] 3. Reglas, valores y disposiciones — comprobación: `R-103` queda *no utilizable* por CONTRACT-17, con y sin AGENT-22.
- [x] 4. Versiones e historial — comprobación: `R-102` y `R-100` tienen dos versiones y una vigente, en cualquier orden de carga.
- [x] 5. Book y respuestas preparadas — comprobación: seis pólizas en los dos lados, dos solo en el book.
- [x] 6. README y evidencia — comprobación: otro ingeniero lo corre siguiendo el README.

## Dependencias o servicios nuevos
Al correr, ninguna. Al desarrollar: `ruff`, `pytest` y `uv` (ADR 0004).
