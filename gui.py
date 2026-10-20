"""Entrada gráfica independiente del programa de consola del equipo."""

import argparse
from pathlib import Path
import pygame


def main():
    parser = argparse.ArgumentParser(description="Interfaz de Wave Picking")
    parser.add_argument("--escenario", type=Path, help="Abrir un JSON directamente")
    parser.add_argument(
        "--biblioteca", type=Path, help="Carpeta de escenarios del usuario"
    )
    parser.add_argument(
        "--frames", type=int, help="Cerrar tras N cuadros (prueba de arranque)"
    )
    args = parser.parse_args()
    from FrontEnd.views.pygame_engine import App

    try:
        app = App(args.biblioteca)
        if args.escenario:
            app.load(args.escenario)
        app.run(args.frames)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
