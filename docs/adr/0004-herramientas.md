# ADR 0004: Herramientas y almacenamiento

- **Estado:** aceptada
- **Fecha:** 2026-11-27

## Contexto
Las capas ya están decididas (ADR 0001): archivos tal como llegaron, tablas con el texto de cada fuente, tablas con lo compartido que se recalculan completas, y vistas para consultar. Falta decidir con qué se construyen. El spec pide que otro ingeniero lo corra en local con un comando, sin cuentas ni servicios, y que las sumas sean exactas al centavo.

## Decisión

| Para qué | Qué se usa | Por qué |
|---|---|---|
| Lenguaje | Python 3.11 o posterior | Es lo que ya exige el portal de Brújula |
| Base de datos | SQLite, un solo archivo | Viene con Python: nadie instala ni arranca nada |
| Al correr | Solo la librería estándar de Python | Cero instalaciones para quien lo prueba |
| Reglas y descriptores | Archivos TOML | Se leen con la librería estándar y admiten comentarios |
| Al desarrollar | `ruff` (estilo y formato PEP 8), `pytest` (pruebas) y `uv` (versiones) | No hacen falta para correr, solo para verificar |

Módulos de la librería estándar: `urllib.request` y `http.cookiejar` para la sesión y las páginas del portal; `json` y `csv` para leer las fuentes; `sqlite3` para la base; `decimal` para leer montos sin perder centavos; `datetime` para fechas y husos horarios; `tomllib` para las reglas.

**Montos.** SQLite no tiene un tipo decimal exacto. Cada monto válido se guarda en centavos enteros, junto al texto original, y las sumas se hacen sobre los centavos.

**SQL común.** Las tablas y las vistas usan SQL que casi cualquier motor entiende. Lo propio de SQLite son unas funciones de texto de las vistas: dar formato a los montos y juntar varios orígenes en un texto. Pasar a PostgreSQL sería cambiar la conexión, esas funciones y usar su tipo `NUMERIC` para los montos.

## Alternativas descartadas
- **PostgreSQL.** Tiene decimal exacto y es un motor de producción habitual. Necesita un servidor: quien lo pruebe tendría que instalarlo o usar contenedores, y deja de ser "un comando".
- **DuckDB.** Tiene decimal exacto y lee CSV y JSON directo. Es una dependencia que instalar; SQLite cubre lo mismo aquí sin ninguna.
- **Tablas Iceberg para lo compartido.** Su historial va por el momento en que se escribió la tabla. El spec pide historial por fecha de la fuente, y esas tablas se recalculan completas en cada carga, así que no aportaría nada que se pida. Sí tiene sentido con volumen real y almacenamiento en la nube.
- **dbt para las transformaciones.** Útil cuando hay muchas tablas y un equipo. Aquí son pocas y agrega instalación y montaje.
- **YAML para las reglas.** Es lo más común para descriptores, pero necesita una dependencia.
- **`requests` y `pydantic`.** Más cómodos para HTTP y validación; la librería estándar alcanza para dos brokers y una docena de tablas.

## Consecuencias
- Se corre con Python y nada más. Para verificar hace falta `uv`, que instala `ruff` y `pytest`.
- Los montos se ven como centavos en las tablas; las vistas los muestran con dos decimales.
- SQLite admite un solo escritor a la vez. Alcanza para una carga local, no para varias en paralelo.
- Con más fuentes o más volumen, el cambio natural es PostgreSQL para lo compartido y archivos en la nube para lo que llega; las capas y las reglas no cambian.
