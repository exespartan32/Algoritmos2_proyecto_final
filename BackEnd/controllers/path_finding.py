import time
import heapq
from typing import List, Tuple, Set, Dict, Optional, Any

CoordXY = Tuple[int, int]


class RutaResultado:
    def __init__(
        self,
        camino_completo: List[CoordXY],
        nodos_explorados: List[CoordXY],
        tiempo_ejecucion_ms: float,
        destinos_inalcanzables: Optional[List[CoordXY]] = None,
        expansiones: int = 0,
        orden_exploracion: Optional[List[CoordXY]] = None,
    ) -> None:
        self.camino_completo = camino_completo
        self.nodos_explorados = nodos_explorados
        self.distancia_total = len(camino_completo) - 1 if camino_completo else 0
        self.aristas_recorridas = self.distancia_total
        self.tiempo_ejecucion_ms = tiempo_ejecucion_ms
        self.destinos_inalcanzables = destinos_inalcanzables or []
        # Suma de nodos que sacó de la cola cada búsqueda (trabajo total).
        self.expansiones = expansiones
        # Celdas en el orden en que Dijkstra las sacó de la cola (para animar).
        self.orden_exploracion = orden_exploracion or []


class Pathfinding:
    NORTE_AUMENTA_Y: bool = True

    @staticmethod
    def es_movimiento_permitido_digrafo(
        origen: CoordXY,
        destino: CoordXY,
        sentido_origen: str,
        sentido_destino: str = "AMBOS",
        norte_aumenta_y: Optional[bool] = None,
    ) -> bool:
        usar_norte_positivo = (
            Pathfinding.NORTE_AUMENTA_Y if norte_aumenta_y is None else norte_aumenta_y
        )
        dx = destino[0] - origen[0]
        dy = destino[1] - origen[1]
        if abs(dx) + abs(dy) != 1:
            return False

        s_orig = (
            sentido_origen.value
            if hasattr(sentido_origen, "value")
            else str(sentido_origen).upper()
        )
        s_dest = (
            sentido_destino.value
            if hasattr(sentido_destino, "value")
            else str(sentido_destino).upper()
        )

        if s_orig == "NINGUNO" or s_dest == "NINGUNO":
            return False

        if dx == 1:
            opuesto_paso = "O"
        elif dx == -1:
            opuesto_paso = "E"
        elif dy == 1:
            opuesto_paso = "S" if usar_norte_positivo else "N"
        else:
            opuesto_paso = "N" if usar_norte_positivo else "S"

        if s_orig == opuesto_paso or s_dest == opuesto_paso:
            return False
        return True

    @staticmethod
    def _es_celda_pasillo_en_grafo(coord: CoordXY, grafo: Any) -> bool:
        if grafo is None:
            return False
        if hasattr(grafo, "nodos") and isinstance(grafo.nodos, dict):
            return coord in grafo.nodos
        if hasattr(grafo, "lista_adyacencia") and isinstance(
            grafo.lista_adyacencia, dict
        ):
            return coord in grafo.lista_adyacencia
        return False

    @staticmethod
    def obtener_celda_acceso_pasillo(
        coord_xy: CoordXY,
        grafo: Any,
        warehouse: Any = None,
    ) -> CoordXY:
        if warehouse is not None and hasattr(warehouse, "obtener_celda_acceso_pasillo"):
            acceso = warehouse.obtener_celda_acceso_pasillo(coord_xy[0], coord_xy[1])
            if acceso is not None:
                return acceso

        if Pathfinding._es_celda_pasillo_en_grafo(coord_xy, grafo):
            return coord_xy

        rx, ry = coord_xy
        for cand in [(rx - 1, ry), (rx + 1, ry), (rx, ry - 1), (rx, ry + 1)]:
            if Pathfinding._es_celda_pasillo_en_grafo(cand, grafo):
                return cand
        return coord_xy

    @staticmethod
    def calcular_estrategia_orden_pedidos(
        grafo: Any,
        origen: CoordXY,
        destinos: List[CoordXY],
        destino_retorno: Optional[CoordXY] = None,
        warehouse: Any = None,
    ) -> RutaResultado:
        tiempo_inicio = time.perf_counter()
        nodos_explorados_totales: Set[CoordXY] = set()
        destinos_inalcanzables: List[CoordXY] = []
        expansiones = 0
        orden: List[CoordXY] = []

        origen_pasillo = Pathfinding.obtener_celda_acceso_pasillo(
            origen, grafo, warehouse
        )
        cierre_pasillo = (
            Pathfinding.obtener_celda_acceso_pasillo(destino_retorno, grafo, warehouse)
            if destino_retorno is not None
            else origen_pasillo
        )

        if not destinos:
            tiempo_ms = (time.perf_counter() - tiempo_inicio) * 1000
            return RutaResultado([origen_pasillo], [], tiempo_ms)

        ruta_total: List[CoordXY] = [origen_pasillo]
        posicion_actual = origen_pasillo

        for destino_raw in destinos:
            destino = Pathfinding.obtener_celda_acceso_pasillo(
                destino_raw, grafo, warehouse
            )
            if destino == posicion_actual:
                continue

            ruta_tramo, explorados_tramo = Pathfinding.calcular_ruta_dijkstra(
                posicion_actual, destino, grafo, orden_exploracion=orden
            )
            nodos_explorados_totales.update(explorados_tramo)
            expansiones += len(explorados_tramo)

            if not ruta_tramo:
                destinos_inalcanzables.append(destino_raw)
                continue

            ruta_total.extend(ruta_tramo[1:])
            posicion_actual = destino

        if posicion_actual != cierre_pasillo:
            ruta_regreso, explorados_regreso = Pathfinding.calcular_ruta_dijkstra(
                posicion_actual, cierre_pasillo, grafo, orden_exploracion=orden
            )
            nodos_explorados_totales.update(explorados_regreso)
            expansiones += len(explorados_regreso)
            if ruta_regreso:
                ruta_total.extend(ruta_regreso[1:])
            else:
                destinos_inalcanzables.append(cierre_pasillo)

        tiempo_ms = (time.perf_counter() - tiempo_inicio) * 1000
        return RutaResultado(
            ruta_total,
            list(nodos_explorados_totales),
            tiempo_ms,
            destinos_inalcanzables,
            expansiones,
            orden,
        )

    @staticmethod
    def calcular_estrategia_cercania_multidestino(
        grafo: Any,
        origen: CoordXY,
        destinos_pendientes: List[CoordXY],
        destino_retorno: Optional[CoordXY] = None,
        warehouse: Any = None,
    ) -> RutaResultado:
        tiempo_inicio = time.perf_counter()
        nodos_explorados_totales: Set[CoordXY] = set()
        destinos_inalcanzables: List[CoordXY] = []
        expansiones = 0
        orden: List[CoordXY] = []

        origen_pasillo = Pathfinding.obtener_celda_acceso_pasillo(
            origen, grafo, warehouse
        )
        cierre_pasillo = (
            Pathfinding.obtener_celda_acceso_pasillo(destino_retorno, grafo, warehouse)
            if destino_retorno is not None
            else origen_pasillo
        )

        if not destinos_pendientes:
            tiempo_ms = (time.perf_counter() - tiempo_inicio) * 1000
            return RutaResultado([origen_pasillo], [], tiempo_ms)

        ruta_total: List[CoordXY] = [origen_pasillo]
        posicion_actual = origen_pasillo

        pendientes: Set[CoordXY] = {
            Pathfinding.obtener_celda_acceso_pasillo(d, grafo, warehouse)
            for d in destinos_pendientes
        }
        pendientes.discard(origen_pasillo)

        while pendientes:
            ruta_tramo, destino_alcanzado, explorados_tramo = (
                Pathfinding.calcular_ruta_greedy(
                    posicion_actual, pendientes, grafo, orden_exploracion=orden
                )
            )
            nodos_explorados_totales.update(explorados_tramo)
            expansiones += len(explorados_tramo)

            if not destino_alcanzado or not ruta_tramo:
                destinos_inalcanzables.extend(pendientes)
                break

            ruta_total.extend(ruta_tramo[1:])
            posicion_actual = destino_alcanzado
            pendientes.discard(destino_alcanzado)

        if posicion_actual != cierre_pasillo:
            ruta_regreso, explorados_regreso = Pathfinding.calcular_ruta_dijkstra(
                posicion_actual, cierre_pasillo, grafo, orden_exploracion=orden
            )
            nodos_explorados_totales.update(explorados_regreso)
            expansiones += len(explorados_regreso)
            if ruta_regreso:
                ruta_total.extend(ruta_regreso[1:])
            else:
                destinos_inalcanzables.append(cierre_pasillo)

        tiempo_ms = (time.perf_counter() - tiempo_inicio) * 1000
        return RutaResultado(
            ruta_total,
            list(nodos_explorados_totales),
            tiempo_ms,
            destinos_inalcanzables,
            expansiones,
            orden,
        )

    @staticmethod
    def _obtener_vecinos(
        grafo: Any,
        nodo_actual: CoordXY,
        paso_tiempo: int = 0,
        picker_id: Optional[str] = None,
    ) -> List[CoordXY]:
        if hasattr(grafo, "obtener_vecinos_validos"):
            try:
                return grafo.obtener_vecinos_validos(
                    nodo_actual,
                    paso_tiempo=paso_tiempo,
                    picker_id_solicitante=picker_id,
                )
            except TypeError:
                return grafo.obtener_vecinos_validos(
                    nodo_actual, paso_tiempo=paso_tiempo
                )
        if hasattr(grafo, "lista_adyacencia") and isinstance(
            grafo.lista_adyacencia, dict
        ):
            return grafo.lista_adyacencia.get(nodo_actual, [])
        return []

    @staticmethod
    def calcular_ruta_dijkstra(
        origen: CoordXY,
        destino: CoordXY,
        grafo: Any,
        paso_tiempo_inicial: int = 0,
        picker_id: Optional[str] = None,
        orden_exploracion: Optional[List[CoordXY]] = None,
    ) -> Tuple[List[CoordXY], Set[CoordXY]]:
        if origen == destino:
            return [origen], {origen}

        cola: List[Tuple[int, CoordXY]] = [(0, origen)]
        distancias: Dict[CoordXY, int] = {origen: 0}
        padres: Dict[CoordXY, Optional[CoordXY]] = {origen: None}
        nodos_explorados: Set[CoordXY] = set()

        while cola:
            dist_actual, nodo_actual = heapq.heappop(cola)
            if dist_actual > distancias.get(nodo_actual, float("inf")):
                continue

            nodos_explorados.add(nodo_actual)
            if orden_exploracion is not None:
                orden_exploracion.append(nodo_actual)
            if nodo_actual == destino:
                return Pathfinding._reconstruir_ruta(padres, destino), nodos_explorados

            paso_eval = (
                paso_tiempo_inicial + dist_actual + 1 if paso_tiempo_inicial > 0 else 0
            )
            vecinos = Pathfinding._obtener_vecinos(
                grafo, nodo_actual, paso_tiempo=paso_eval, picker_id=picker_id
            )

            for vecino in vecinos:
                nueva_distancia = dist_actual + 1
                if nueva_distancia < distancias.get(vecino, float("inf")):
                    distancias[vecino] = nueva_distancia
                    padres[vecino] = nodo_actual
                    heapq.heappush(cola, (nueva_distancia, vecino))

        return [], nodos_explorados

    @staticmethod
    def calcular_ruta_greedy(
        origen: CoordXY,
        destinos_pendientes: Any,
        grafo: Any,
        paso_tiempo_inicial: int = 0,
        orden_exploracion: Optional[List[CoordXY]] = None,
    ) -> Tuple[List[CoordXY], Optional[CoordXY], Set[CoordXY]]:
        if not destinos_pendientes:
            return [], None, set()

        set_destinos = (
            destinos_pendientes
            if isinstance(destinos_pendientes, set)
            else set(destinos_pendientes)
        )
        if origen in set_destinos:
            return [origen], origen, {origen}

        cola: List[Tuple[int, CoordXY]] = [(0, origen)]
        distancias: Dict[CoordXY, int] = {origen: 0}
        padres: Dict[CoordXY, Optional[CoordXY]] = {origen: None}
        nodos_explorados: Set[CoordXY] = set()

        while cola:
            dist_actual, nodo_actual = heapq.heappop(cola)
            if dist_actual > distancias.get(nodo_actual, float("inf")):
                continue

            nodos_explorados.add(nodo_actual)
            if orden_exploracion is not None:
                orden_exploracion.append(nodo_actual)
            if nodo_actual in set_destinos:
                return (
                    Pathfinding._reconstruir_ruta(padres, nodo_actual),
                    nodo_actual,
                    nodos_explorados,
                )

            paso_eval = (
                paso_tiempo_inicial + dist_actual + 1 if paso_tiempo_inicial > 0 else 0
            )
            vecinos = Pathfinding._obtener_vecinos(
                grafo, nodo_actual, paso_tiempo=paso_eval
            )

            for vecino in vecinos:
                nueva_distancia = dist_actual + 1
                if nueva_distancia < distancias.get(vecino, float("inf")):
                    distancias[vecino] = nueva_distancia
                    padres[vecino] = nodo_actual
                    heapq.heappush(cola, (nueva_distancia, vecino))

        return [], None, nodos_explorados

    def recalcular_evitando_obstaculo(
        self,
        grafo: Any,
        picker: Any,
        paso_actual: int,
        celdas_bloqueadas: Optional[Set[CoordXY]] = None,
    ) -> List[CoordXY]:
        """
        Recalcula la ruta del picker hacia su próximo waypoint o destino final
        evitando las celdas bloqueadas en el turno actual.
        Si no existe desvío posible, inserta una espera de 1 turno en su posición actual.
        """
        if not picker.ruta_asignada:
            return []

        # Próximo objetivo importante: el primer producto pendiente que aparece
        # en la ruta (o el final de la ruta, que es el despacho).
        objetivo_inmediato = Pathfinding.proximo_objetivo_en_ruta(picker)

        bloqueos_previos = set(getattr(grafo, "nodos_evasion_actual", set()))
        if hasattr(grafo, "nodos_evasion_actual") and celdas_bloqueadas:
            grafo.nodos_evasion_actual = set(celdas_bloqueadas)

        try:
            nueva_ruta, _ = self.calcular_ruta_dijkstra(
                origen=picker.posicion_actual,
                destino=objetivo_inmediato,
                grafo=grafo,
                paso_tiempo_inicial=paso_actual,
                picker_id=picker.id_picker,
            )
        finally:
            if hasattr(grafo, "nodos_evasion_actual"):
                grafo.nodos_evasion_actual = bloqueos_previos

        if nueva_ruta and len(nueva_ruta) > 1:
            # Reemplazar el tramo hasta objetivo_inmediato y conservar el resto de la ruta
            resto_ruta: List[CoordXY] = []
            if objetivo_inmediato in picker.ruta_asignada:
                idx = picker.ruta_asignada.index(objetivo_inmediato)
                resto_ruta = picker.ruta_asignada[idx + 1 :]
            return nueva_ruta[1:] + resto_ruta

        # Si no hay desvío válido, el picker espera 1 turno en su celda actual
        return [picker.posicion_actual] + list(picker.ruta_asignada)

    @staticmethod
    def proximo_objetivo_en_ruta(picker: Any) -> CoordXY:
        """Primer destino pendiente según el orden en que la ruta lo visita.

        Al desviar a un picker hay que ir a este objetivo y seguir con el resto
        de la ruta; si se fuera directo al final se saltearía productos.
        """
        pendientes = set(getattr(picker, "objetivos_pendientes", None) or [])
        for celda in picker.ruta_asignada:
            if celda in pendientes:
                return celda
        return picker.ruta_asignada[-1]

    @staticmethod
    def desviar_por(picker: Any, celda_escape: CoordXY, grafo: Any) -> Optional[List[CoordXY]]:
        """Ruta que pasa primero por ``celda_escape`` y retoma el recorrido
        en el próximo objetivo, sin perder ningún producto pendiente."""
        if not picker.ruta_asignada:
            return None
        objetivo = Pathfinding.proximo_objetivo_en_ruta(picker)
        tramo, _ = Pathfinding.calcular_ruta_dijkstra(celda_escape, objetivo, grafo)
        if not tramo:
            return None
        idx = picker.ruta_asignada.index(objetivo)
        return [celda_escape] + tramo[1:] + picker.ruta_asignada[idx + 1 :]

    @staticmethod
    def _reconstruir_ruta(
        padres: Dict[CoordXY, Optional[CoordXY]], destino_id: CoordXY
    ) -> List[CoordXY]:
        ruta: List[CoordXY] = []
        actual: Optional[CoordXY] = destino_id
        while actual is not None:
            ruta.append(actual)
            actual = padres.get(actual)
        ruta.reverse()
        return ruta

    @staticmethod
    def calcular_mapa_distancias_desde(
        origen_pasillo: CoordXY, grafo: Any
    ) -> Dict[CoordXY, float]:
        if not Pathfinding._es_celda_pasillo_en_grafo(origen_pasillo, grafo):
            return {}

        cola: List[Tuple[int, CoordXY]] = [(0, origen_pasillo)]
        distancias: Dict[CoordXY, float] = {origen_pasillo: 0.0}

        while cola:
            dist_actual, nodo_actual = heapq.heappop(cola)
            if dist_actual > distancias.get(nodo_actual, float("inf")):
                continue

            for vecino in Pathfinding._obtener_vecinos(grafo, nodo_actual, 0):
                nueva_dist = dist_actual + 1
                if nueva_dist < distancias.get(vecino, float("inf")):
                    distancias[vecino] = float(nueva_dist)
                    heapq.heappush(cola, (nueva_dist, vecino))

        return distancias

    @staticmethod
    def construir_matriz_distancias_productos(
        coordenadas_productos_xy: Set[CoordXY],
        grafo: Any,
        warehouse: Any = None,
    ) -> Dict[Tuple[CoordXY, CoordXY], float]:
        mapa_rack_a_pasillo: Dict[CoordXY, CoordXY] = {
            coord_rack: Pathfinding.obtener_celda_acceso_pasillo(
                coord_rack, grafo, warehouse
            )
            for coord_rack in coordenadas_productos_xy
        }

        pasillos_unicos = set(mapa_rack_a_pasillo.values())
        distancias_entre_pasillos: Dict[CoordXY, Dict[CoordXY, float]] = {
            pasillo_orig: Pathfinding.calcular_mapa_distancias_desde(
                pasillo_orig, grafo
            )
            for pasillo_orig in pasillos_unicos
        }

        matriz_distancias: Dict[Tuple[CoordXY, CoordXY], float] = {}
        for u_rack, u_pasillo in mapa_rack_a_pasillo.items():
            mapa_desde_u = distancias_entre_pasillos.get(u_pasillo, {})
            for v_rack, v_pasillo in mapa_rack_a_pasillo.items():
                if u_rack == v_rack:
                    matriz_distancias[(u_rack, v_rack)] = 0.0
                else:
                    matriz_distancias[(u_rack, v_rack)] = mapa_desde_u.get(
                        v_pasillo, float("inf")
                    )

        return matriz_distancias
