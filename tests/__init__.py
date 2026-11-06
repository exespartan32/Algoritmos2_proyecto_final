import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

try:  # Con pygame instalado se prueba la interfaz real (sin ventana visible).
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame  # noqa: F401
except ImportError:  # Sin pygame se usa un sustituto que verifica las llamadas.
    from tests import pygame_falso  # noqa: E402

    pygame_falso.instalar()
