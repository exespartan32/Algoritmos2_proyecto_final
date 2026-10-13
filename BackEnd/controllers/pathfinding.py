import time
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
from BackEnd.data_structures.grafo_warehouse import GrafoWarehouse
from BackEnd.models.entities import Picker


@dataclass
class RutaResultado:
    camino_completo: List[Tuple[int, int]] = field(default_factory=list)
    nodos_explorados: List[Tuple[int, int]] = field(default_factory=list)
    distancia_total: int = 0
    aristas_recorridas: int = 0
    tiempo_ejecucion_ms: float = 0.0


class Pathfinding:
    def _dijkstra_punto_a_punto(
        self,
        grafo: GrafoWarehouse,
        origen: Tuple[int, int],
        destino: Tuple[int, int],
        paso_inicial: int = -1,
    ) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
        if origen == destino:
            return [origen], [origen]

        distancias: Dict[Tuple[int, int], float] = {origen: 0.0}
        padres: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {origen: None}
        no_visitados: List[Tuple[int, int]] = [origen]
        explorados: List[Tuple[int, int]] = []
        visitados_set = set()

        while no_visitados:
            no_visitados.sort(key=lambda n: distancias.get(n, float("inf")))
            actual = no_visitados.pop(0)

            if actual in visitados_set:
                continue
            visitados_set.add(actual)
            explorados.append(actual)

            if actual == destino:
                break

            paso_eval = (
                (paso_inicial + int(distancias[actual]) + 1)
                if paso_inicial >= 0
                else -1
            )
            for vecino in grafo.obtener_vecinos_validos(actual, paso_eval):
                nueva_dist = distancias[actual] + 1.0
                if nueva_dist < distancias.get(vecino, float("inf")):
                    distancias[vecino] = nueva_dist
                    padres[vecino] = actual
                    no_visitados.append(vecino)

        if destino not in padres:
            return [], explorados

        camino = []
        curr: Optional[Tuple[int, int]] = destino
        while curr is not None:
            camino.append(curr)
            curr = padres[curr]
        camino.reverse()
        return camino, explorados

    def calcular_estrategia_orden_pedidos(
        self,
        grafo: GrafoWarehouse,
        origen: Tuple[int, int],
        destinos: List[Tuple[int, int]],
    ) -> RutaResultado:
        t0 = time.perf_counter()
        camino_total: List[Tuple[int, int]] = [origen]
        explorados_total: List[Tuple[int, int]] = []
        actual = origen

        for dest in destinos:
            tramo, exp = self._dijkstra_punto_a_punto(grafo, actual, dest)
            explorados_total.extend(exp)
            if tramo:
                camino_total.extend(tramo[1:])
                actual = dest

        # Regreso al punto de despacho
        tramo_retorno, exp_ret = self._dijkstra_punto_a_punto(grafo, actual, origen)
        explorados_total.extend(exp_ret)
        if tramo_retorno:
            camino_total.extend(tramo_retorno[1:])

        t_ms = (time.perf_counter() - t0) * 1000.0
        aristas = max(0, len(camino_total) - 1)
        return RutaResultado(
            camino_completo=camino_total,
            nodos_explorados=explorados_total,
            distancia_total=aristas,
            aristas_recorridas=aristas,
            tiempo_ejecucion_ms=round(t_ms, 4),
        )

    def calcular_estrategia_cercania_multidestino(
        self,
        grafo: GrafoWarehouse,
        origen: Tuple[int, int],
        destinos: List[Tuple[int, int]],
    ) -> RutaResultado:
        t0 = time.perf_counter()
        pendientes = list(destinos)
        camino_total: List[Tuple[int, int]] = [origen]
        explorados_total: List[Tuple[int, int]] = []
        actual = origen

        while pendientes:
            mejor_dest = None
            mejor_tramo: List[Tuple[int, int]] = []
            menor_costo = float("inf")

            for candidato in pendientes:
                tramo, exp = self._dijkstra_punto_a_punto(grafo, actual, candidato)
                explorados_total.extend(exp)
                if tramo and len(tramo) < menor_costo:
                    menor_costo = len(tramo)
                    mejor_dest = candidato
                    mejor_tramo = tramo

            if mejor_dest is None:
                break

            camino_total.extend(mejor_tramo[1:])
            actual = mejor_dest
            pendientes.remove(mejor_dest)

        tramo_retorno, exp_ret = self._dijkstra_punto_a_punto(grafo, actual, origen)
        explorados_total.extend(exp_ret)
        if tramo_retorno:
            camino_total.extend(tramo_retorno[1:])

        t_ms = (time.perf_counter() - t0) * 1000.0
        aristas = max(0, len(camino_total) - 1)
        return RutaResultado(
            camino_completo=camino_total,
            nodos_explorados=explorados_total,
            distancia_total=aristas,
            aristas_recorridas=aristas,
            tiempo_ejecucion_ms=round(t_ms, 4),
        )

    def recalcular_evitando_obstaculo(
        self, grafo: GrafoWarehouse, picker: Picker, paso_actual: int
    ) -> List[Tuple[int, int]]:
        if not picker.ruta_asignada:
            return []
        destino_final = picker.ruta_asignada[-1]
        nuevo_camino, _ = self._dijkstra_punto_a_punto(
            grafo, picker.posicion_actual, destino_final, paso_inicial=paso_actual
        )
        return nuevo_camino
