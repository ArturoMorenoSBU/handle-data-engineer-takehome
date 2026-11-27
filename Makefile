# Requiere Python 3.11 o posterior. Si hay uv (https://docs.astral.sh/uv/), él consigue ese Python.
PY ?= $(shell command -v uv >/dev/null 2>&1 && echo "uv run --no-dev python" || echo python3)
export PYTHONPATH := src

E ?= failure

.PHONY: construir respuestas rehacer escenario verificar

construir:  ## Captura las dos aseguradoras y el book, y arma la base desde cero
	$(PY) -m base_compartida construir

respuestas:  ## Muestra las respuestas preparadas
	$(PY) -m base_compartida respuestas

rehacer:  ## Rehace la base solo desde las capturas guardadas
	$(PY) -m base_compartida rehacer

escenario:  ## Prueba aparte un escenario del portal: make escenario E=failure (o E=drift)
	$(PY) -m base_compartida escenario --escenario $(E)

verificar:  ## Estilo y pruebas. Necesita uv
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest
