import time
from collections import deque
from typing import Tuple, List, Dict, Optional
from BackEnd.models.warehouse import Digrafo

Coord = Tuple[int, int]

class ResultadoCamino:
    def __init__(
        self,
        camino: List[Coord],
        nodos_explorados: List[Coord],
        aristas_recorridas: int,
        tiempo_ms: float
    ):
        self.secuencia_pasos = camino
        # La distancia es la cantidad de movimientos realizados (longitud del camino - 1)
        self.distancia_total = max(0, len(camino) - 1)
        self.nodos_explorados_orden = nodos_explorados
        self.cantidad_nodos_visitados = len(nodos_explorados)
        self.cantidad_aristas_recorridas = aristas_recorridas
        self.tiempo_ejecucion_ms = tiempo_ms

class BuscadorBFS:
    @staticmethod
    def buscar_camino(grafo: Digrafo, origen: Coord, destino: Coord) -> Optional[ResultadoCamino]:
        inicio_t = time.perf_counter()

        if origen not in grafo.nodos or destino not in grafo.nodos:
            return None

        cola = deque([origen])
        # Diccionario padre para reconstruir el camino y evitar visitar dos veces el mismo nodo
        padre: Dict[Coord, Optional[Coord]] = {origen: None}
        nodos_explorados: List[Coord] = []
        aristas_evaluadas = 0

        encontrado = False

        while cola:
            actual = cola.popleft()
            nodos_explorados.append(actual)

            if actual == destino:
                encontrado = True
                break

            for vecino in grafo.obtener_vecinos(actual):
                aristas_evaluadas += 1
                if vecino not in padre:
                    padre[vecino] = actual
                    cola.append(vecino)

        fin_t = time.perf_counter()
        tiempo_ms = (fin_t - inicio_t) * 1000.0

        if not encontrado:
            return None

        # Reconstrucción del camino de destino a origen
        camino: List[Coord] = []
        paso: Optional[Coord] = destino
        while paso is not None:
            camino.append(paso)
            paso = padre[paso]
        camino.reverse()

        return ResultadoCamino(
            camino=camino,
            nodos_explorados=nodos_explorados,
            aristas_recorridas=aristas_evaluadas,
            tiempo_ms=tiempo_ms
        )