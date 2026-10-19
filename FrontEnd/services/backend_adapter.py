"""Adaptaciones de lectura para consumir el backend sin modificar sus archivos."""

import importlib.util
import sys
import types
from BackEnd.controllers.pathfinding import Pathfinding


class AdaptadorGrafo:
    """Traduce la API de Digrafo y permite excluir pickers estacionados."""

    def __init__(self, grafo, bloqueados=()):
        self.grafo = grafo
        self.bloqueados = set(bloqueados)

    def obtener_vecinos_validos(self, coordenada, paso_tiempo=0):
        return [
            v
            for v in self.grafo.obtener_vecinos(coordenada)
            if v not in self.bloqueados
        ]


class BuscadorBFS:
    @staticmethod
    def buscar_camino(grafo, origen, destino):
        ruta, _ = Pathfinding.calcular_ruta_dijkstra(
            origen, destino, AdaptadorGrafo(grafo)
        )
        return ruta or None


def generator_class():
    """Puente temporal para el import obsoleto del generador en integracion.

    Sólo se registra si el módulo no existe. No escribe archivos ni reemplaza
    implementaciones del grupo. Quitar el puente cuando reparen ese import.
    La función generar_escenario_dict no utiliza el buscador.
    """
    name = "BackEnd.controllers.bfs"
    if name not in sys.modules and importlib.util.find_spec(name) is None:
        compatibility = types.ModuleType(name)
        compatibility.BuscadorBFS = BuscadorBFS
        sys.modules[name] = compatibility
    from BackEnd.utils.scenario_generator import ScenarioGenerator

    return ScenarioGenerator
