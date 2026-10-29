"""Interfaz gráfica del sistema de Wave Picking.

Uso:
    python gui.py                         # abre la biblioteca de escenarios
    python gui.py --escenario archivo.json
"""

import argparse
from pathlib import Path

import pygame


def main():
    parser = argparse.ArgumentParser(description="Interfaz de Wave Picking")
    parser.add_argument("--escenario", type=Path, help="Abrir un JSON directamente")
    parser.add_argument("--biblioteca", type=Path, help="Carpeta de escenarios del usuario")
    parser.add_argument("--cuadros", type=int, help="Cerrar tras N cuadros (prueba de arranque)")
    args = parser.parse_args()
    from FrontEnd.views.pygame_engine import App

    try:
        app = App(args.biblioteca)
        if args.escenario:
            app.cargar(args.escenario)
        app.run(args.cuadros)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
