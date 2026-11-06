"""Punto de entrada de la interfaz gráfica de Wave Picking."""

import argparse
from pathlib import Path
import pygame


def main():
    parser = argparse.ArgumentParser(description="Interfaz gráfica de Wave Picking")
    parser.add_argument(
        "--escenario", type=Path, help="Abrir un archivo JSON directamente"
    )
    parser.add_argument(
        "--biblioteca", type=Path, help="Carpeta personalizada de escenarios"
    )
    parser.add_argument(
        "--cuadros",
        type=int,
        help="Cerrar tras N cuadros (útil para pruebas de arranque)",
    )
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
