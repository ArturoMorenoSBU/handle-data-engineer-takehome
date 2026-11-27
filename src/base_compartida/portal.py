"""Arranca y detiene el portal de Brújula, que vive en `fuentes/lab/`, en un escenario."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def portal(fuentes: Path, escenario: str) -> Iterator[str]:
    """Entrega la dirección del portal mientras dura el bloque `with`."""
    puerto = _puerto_libre()
    servidor = fuentes / "lab" / "server.py"
    if not servidor.exists():
        raise FileNotFoundError(f"No está el portal de Brújula en {servidor}. Revisa --fuentes.")
    orden = [sys.executable, str(servidor), "--scenario", escenario, "--port", str(puerto)]
    proceso = subprocess.Popen(orden, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        _esperar(puerto, proceso)
        yield f"http://127.0.0.1:{puerto}"
    finally:
        proceso.terminate()
        proceso.wait(timeout=5)


def _esperar(puerto: int, proceso: subprocess.Popen, segundos: float = 10.0) -> None:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if proceso.poll() is not None:
            error = proceso.stderr.read().decode("utf-8", "replace")[-300:]
            raise RuntimeError(f"El portal de Brújula no arrancó: {error}")
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", puerto)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError("El portal de Brújula no respondió a tiempo.")
