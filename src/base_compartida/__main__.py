import sys

if sys.version_info < (3, 11):  # noqa: UP036 (el aviso es para quien lo corre con un Python viejo)
    sys.exit("Hace falta Python 3.11 o posterior. Prueba con `make construir PY=python3.11`.")

from base_compartida.cli import main  # noqa: E402

main()
