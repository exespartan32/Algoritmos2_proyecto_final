import time
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Set
from BackEnd.data_structures.grafo_warehouse import GrafoWarehouse
from BackEnd.models.entities import Picker


class _MinHeapNodos:
    """Cola de prioridad mínima (Min-Heap) propia para ejecutar Dijkstra en O((V+E) log V)."""

    def __init__(self) -> None:
        self._heap: List[Tuple[float, Tuple[int, int]]] = []

    def insertar(self, distancia: float, nodo: Tuple[int, int]) -> None:
        self._heap.append((distancia, nodo))
        self._flotar(len(self._heap) - 1)

    def extraer_minimo(self) -> Tuple[float, Tuple[int, int]]:
        if len(self._heap) == 1:
            return self._heap.pop()
        minimo = self._heap[0]
        self._heap[0] = self._heap.pop()
        self._hundir(0)
        return minimo

    def esta_vacio(self) -> bool:
        return len(self._heap) == 0

    def _flotar(self, idx: int) -> None:
        while idx > 0:
            padre = (idx - 1) // 2
            if self._heap[idx][0] < self._heap[padre][0]:
                self._heap[idx], self._heap[padre] = self._heap[padre], self._heap[idx]
                idx = padre
            else:
                break

    def _hundir(self, idx: int) -> None:
        n = len(self._heap)
        while True:
            izq = 2 * idx + 1
            der = 2 * idx + 2
            menor = idx
            if izq < n and self._heap[izq][0] < self._heap[menor][0]:
                menor = izq
            if der < n and self._heap[der][0] < self._heap[menor][0]:
                menor = der
            if menor != idx:
                self._heap[idx], self._heap[menor] = self._heap[menor], self._heap[idx]
                idx = menor
            else:
                break


@dataclass
class RutaResultado:
    camino_completo: List[Tuple[int, int]] = field(default_factory=list)
    nodos_explorados: List[Tuple[int, int]] = field(default_factory=list)
    distancia_total: int = 0
    aristas_recorridas: int = 0
    tiempo_ejecucion_ms: float = 0.0


class Pathfinding:
    def _reconstruir_camino(
        self,
        padres: Dict[Tuple[int, int], Optional[Tuple[int, int]]],
        destino: Tuple[int, int],
    ) -> List[Tuple[int, int]]:
        if destino not in padres:
            return []
        camino: List[Tuple[int, int]] = []
        curr: Optional[Tuple[int, int]] = destino
        while curr is not None:
            camino.append(curr)
            curr = padres[curr]
        camino.reverse()
        return camino

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
        cola = _MinHeapNodos()
        cola.insertar(0.0, origen)
        explorados: List[Tuple[int, int]] = []
        visitados_set: Set[Tuple[int, int]] = set()

        while not cola.esta_vacio():
            dist_actual, actual = cola.extraer_minimo()

            if actual in visitados_set:
                continue
            visitados_set.add(actual)
            explorados.append(actual)

            if actual == destino:
                break

            paso_eval = (
                (paso_inicial + int(dist_actual) + 1)
                if paso_inicial >= 0
                else -1
            )
            for vecino in grafo.obtener_vecinos_validos(actual, paso_eval):
                if vecino in visitados_set:
                    continue
                nueva_dist = dist_actual + 1.0
                if nueva_dist < distancias.get(vecino, float("inf")):
                    distancias[vecino] = nueva_dist
                    padres[vecino] = actual
                    cola.insertar(nueva_dist, vecino)

        return self._reconstruir_camino(padres, destino), explorados

    def _dijkstra_al_mas_cercano(
        self,
        grafo: GrafoWarehouse,
        origen: Tuple[int, int],
        candidatos: Set[Tuple[int, int]],
    ) -> Tuple[Optional[Tuple[int, int]], List[Tuple[int, int]], List[Tuple[int, int]]]:
        """Encuentra el destino más cercano en una sola pasada de Dijkstra."""
        if origen in candidatos:
            return origen, [origen], [origen]

        distancias: Dict[Tuple[int, int], float] = {origen: 0.0}
        padres: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {origen: None}
        cola = _MinHeapNodos()
        cola.insertar(0.0, origen)
        explorados: List[Tuple[int, int]] = []
        visitados_set: Set[Tuple[int, int]] = set()
        mejor_destino: Optional[Tuple[int, int]] = None

        while not cola.esta_vacio():
            dist_actual, actual = cola.extraer_minimo()

            if actual in visitados_set:
                continue
            visitados_set.add(actual)
            explorados.append(actual)

            if actual in candidatos:
                mejor_destino = actual
                break

            for vecino in grafo.obtener_vecinos_validos(actual, -1):
                if vecino in visitados_set:
                    continue
                nueva_dist = dist_actual + 1.0
                if nueva_dist < distancias.get(vecino, float("inf")):
                    distancias[vecino] = nueva_dist
                    padres[vecino] = actual
                    cola.insertar(nueva_dist, vecino)

        if mejor_destino is None:
            return None, [], explorados

        return mejor_destino, self._reconstruir_camino(padres, mejor_destino), explorados

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
            if actual == dest:
                continue
            tramo, exp = self._dijkstra_punto_a_punto(grafo, actual, dest)
            explorados_total.extend(exp)
            if tramo:
                camino_total.extend(tramo[1:])
                actual = dest

        # Regreso al punto de despacho
        if actual != origen:
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
        pendientes: Set[Tuple[int, int]] = set(destinos)
        pendientes.discard(origen)

        camino_total: List[Tuple[int, int]] = [origen]
        explorados_total: List[Tuple[int, int]] = []
        actual = origen

        while pendientes:
            mejor_dest, mejor_tramo, exp = self._dijkstra_al_mas_cercano(
                grafo, actual, pendientes
            )
            explorados_total.extend(exp)

            if mejor_dest is None or not mejor_tramo:
                break

            camino_total.extend(mejor_tramo[1:])
            actual = mejor_dest
            pendientes.remove(mejor_dest)

        if actual != origen:
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
        """
        Recalcula un desvío local evitando la celda bloqueada en picker.ruta_asignada[0]
        y reconectando con los siguientes pasos de picker.ruta_asignada para no perder
        las paradas de productos intermedias.
        """
        if not picker.ruta_asignada:
            return []

        # Intentamos esquivar el obstáculo reconectando con algún punto cercano más adelante en la ruta
        for idx_reconexion in range(1, min(len(picker.ruta_asignada), 6)):
            objetivo = picker.ruta_asignada[idx_reconexion]
            if objetivo == picker.ruta_asignada[0]:
                continue
            desvio, _ = self._dijkstra_punto_a_punto(
                grafo, picker.posicion_actual, objetivo, paso_inicial=paso_actual
            )
            if desvio and len(desvio) > 1:
                # Retornamos los pasos del desvío (sin repetir posicion_actual) + el resto de la ruta original
                return desvio[1:] + picker.ruta_asignada[idx_reconexion + 1 :]

        # Si está en un pasillo estrecho sin desvío posible, espera 1 turno en su posición actual
        return [picker.posicion_actual] + list(picker.ruta_asignada)