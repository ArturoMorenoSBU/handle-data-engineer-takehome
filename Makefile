# Requiere Python 3.11 o posterior. `verificar` usa además uv (https://docs.astral.sh/uv/).
PY ?= uv run python
export PYTHONPATH := src

.PHONY: construir respuestas rehacer verificar

construir:  ## Captura las dos aseguradoras y el book, y arma la base desde cero
	$(PY) -m base_compartida construir

respuestas:  ## Muestra las respuestas preparadas
	$(PY) -m base_compartida respuestas

rehacer:  ## Borra la base y la rehace solo desde las capturas guardadas
	$(PY) -m base_compartida rehacer

verificar:  ## Estilo y pruebas
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest
