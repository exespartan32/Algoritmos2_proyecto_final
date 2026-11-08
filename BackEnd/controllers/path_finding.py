import time
from typing import Any, Dict, List, Optional, Set, Tuple

CoordXY = Tuple[int, int]


class _MinHeapRuteo:
    """Cola de prioridad mínima (Min-Heap) de implementación propia para Dijkstra.

    Ordena por (distancia, giros_acumulados, coordenada) en O(log V), logrando
    caminos mínimos con tramos rectos que reducen colisiones en pasillos anchos.
    """

    def __init__(self) -> None:
        self._heap: List[Tuple[int, int, CoordXY]] = []

    def insertar(self, distancia: int, nodo: CoordXY, giros: int = 0) -> None:
        self._heap.append((distancia, giros, nodo))
        i = len(self._heap) - 1
        while i > 0:
            padre = (i - 1) >> 1
            if self._heap[i] < self._heap[padre]:
                self._heap[i], self._heap[padre] = self._heap[padre], self._heap[i]
                i = padre
            else:
                break

    def extraer_minimo(self) -> Tuple[int, int, CoordXY]:
        if len(self._heap) == 1:
            return self._heap.pop()
        minimo = self._heap[0]
        self._heap[0] = self._heap.pop()
        self._min_heapify(0)
        return minimo

    def esta_vacio(self) -> bool:
        return len(self._heap) == 0

    def _min_heapify(self, i: int) -> None:
        n = len(self._heap)
        while True:
            izq = (i << 1) + 1
            der = (i << 1) + 2
            menor = i

            if izq < n and self._heap[izq] < self._heap[menor]:
                menor = izq
            if der < n and self._heap[der] < self._heap[menor]:
                menor = der

            if menor != i:
                self._heap[i], self._heap[menor] = self._heap[menor], self._heap[i]
                i = menor
            else:
                break


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
        self.expansiones = expansiones
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
        """Estrategia A: Visita los productos en la secuencia exacta de los pedidos usando Dijkstra tramo a tramo."""
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
        """Estrategia B: En cada paso selecciona el próximo producto pendiente más cercano mediante Dijkstra Multidestino."""
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
                Pathfinding.calcular_ruta_dijkstra_multidestino(
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
        """Calcula el camino mínimo punto a punto entre 'origen' y 'destino' usando Dijkstra."""
        ruta, _, explorados = Pathfinding.calcular_ruta_dijkstra_multidestino(
            origen=origen,
            destinos_objetivo={destino},
            grafo=grafo,
            paso_tiempo_inicial=paso_tiempo_inicial,
            picker_id=picker_id,
            orden_exploracion=orden_exploracion,
        )
        return ruta, explorados

    @staticmethod
    def calcular_ruta_dijkstra_multidestino(
        origen: CoordXY,
        destinos_objetivo: Any,
        grafo: Any,
        paso_tiempo_inicial: int = 0,
        picker_id: Optional[str] = None,
        orden_exploracion: Optional[List[CoordXY]] = None,
        bloqueos_cercanos: Optional[Set[CoordXY]] = None,
    ) -> Tuple[List[CoordXY], Optional[CoordXY], Set[CoordXY]]:
        """
        Motor central de Dijkstra sobre el dígrafo de pasillos.
        Expande por distancia mínima y desempata por menor cantidad de giros,
        deteniéndose apenas extrae el primer nodo perteneciente a 'destinos_objetivo'.
        """
        if not destinos_objetivo:
            return [], None, set()

        set_destinos = (
            destinos_objetivo
            if isinstance(destinos_objetivo, set)
            else set(destinos_objetivo)
        )
        if origen in set_destinos:
            return [origen], origen, {origen}

        cola = _MinHeapRuteo()
        cola.insertar(0, origen, giros=0)
        mejor_costo: Dict[CoordXY, Tuple[int, int]] = {origen: (0, 0)}
        padres: Dict[CoordXY, Optional[CoordXY]] = {origen: None}
        nodos_explorados: Set[CoordXY] = set()

        while not cola.esta_vacio():
            dist_actual, giros_actual, nodo_actual = cola.extraer_minimo()
            if (dist_actual, giros_actual) > mejor_costo.get(
                nodo_actual, (int(1e9), int(1e9))
            ):
                continue

            if nodo_actual not in nodos_explorados:
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
                grafo, nodo_actual, paso_tiempo=paso_eval, picker_id=picker_id
            )

            padre_actual = padres.get(nodo_actual)
            dir_previa = (
                (
                    nodo_actual[0] - padre_actual[0],
                    nodo_actual[1] - padre_actual[1],
                )
                if padre_actual is not None
                else None
            )

            for vecino in vecinos:
                # Si hay bloqueos por colisión inmediata, solo se prohíben en un radio corto (dist <= 2)
                if (
                    bloqueos_cercanos
                    and dist_actual < 2
                    and vecino in bloqueos_cercanos
                ):
                    continue

                nueva_distancia = dist_actual + 1
                dir_nueva = (vecino[0] - nodo_actual[0], vecino[1] - nodo_actual[1])
                penalizacion_giro = (
                    0 if (dir_previa is None or dir_previa == dir_nueva) else 1
                )
                nuevos_giros = giros_actual + penalizacion_giro
                nuevo_par = (nueva_distancia, nuevos_giros)

                if nuevo_par < mejor_costo.get(vecino, (int(1e9), int(1e9))):
                    mejor_costo[vecino] = nuevo_par
                    padres[vecino] = nodo_actual
                    cola.insertar(nueva_distancia, vecino, giros=nuevos_giros)

        return [], None, nodos_explorados

    @staticmethod
    def _empalmar_resto_ruta(picker: Any, objetivo_inmediato: CoordXY) -> List[CoordXY]:
        """Devuelve el tramo restante posterior a 'objetivo_inmediato' sin duplicar ciclos."""
        pendientes = set(getattr(picker, "objetivos_pendientes", None) or [])
        if not pendientes:
            # Si ya no quedan productos pendientes, el objetivo inmediato es el despacho final
            return []
        if objetivo_inmediato in picker.ruta_asignada:
            idx = picker.ruta_asignada.index(objetivo_inmediato)
            return list(picker.ruta_asignada[idx + 1 :])
        return []

    def recalcular_evitando_obstaculo(
        self,
        grafo: Any,
        picker: Any,
        paso_actual: int,
        celdas_bloqueadas: Optional[Set[CoordXY]] = None,
    ) -> List[CoordXY]:
        """Busca un desvío hacia el próximo objetivo evitando las celdas ocupadas en los próximos pasos."""
        if not picker.ruta_asignada:
            return []

        objetivo_inmediato = Pathfinding.proximo_objetivo_en_ruta(picker)
        bloqueos = set(celdas_bloqueadas or set())
        if picker.ruta_asignada:
            bloqueos.add(picker.ruta_asignada[0])

        nueva_ruta, _, _ = self.calcular_ruta_dijkstra_multidestino(
            origen=picker.posicion_actual,
            destinos_objetivo={objetivo_inmediato},
            grafo=grafo,
            paso_tiempo_inicial=paso_actual,
            picker_id=picker.id_picker,
            bloqueos_cercanos=bloqueos,
        )

        if nueva_ruta and len(nueva_ruta) > 1:
            resto_ruta = self._empalmar_resto_ruta(picker, objetivo_inmediato)
            return nueva_ruta[1:] + resto_ruta

        return [picker.posicion_actual] + list(picker.ruta_asignada)

    @staticmethod
    def proximo_objetivo_en_ruta(picker: Any) -> CoordXY:
        """Devuelve la próxima parada de recolección en la ruta o la zona de despacho al final."""
        pendientes = set(getattr(picker, "objetivos_pendientes", None) or [])
        for celda in picker.ruta_asignada:
            if celda in pendientes:
                return celda
        return picker.ruta_asignada[-1]

    @staticmethod
    def desviar_por(
        picker: Any, celda_escape: CoordXY, grafo: Any
    ) -> Optional[List[CoordXY]]:
        """Da un paso hacia celda_escape y retoma hacia el próximo objetivo sin rebotar al obstáculo."""
        if not picker.ruta_asignada:
            return None
        objetivo = Pathfinding.proximo_objetivo_en_ruta(picker)
        celda_conflicto = picker.ruta_asignada[0]

        tramo, _, _ = Pathfinding.calcular_ruta_dijkstra_multidestino(
            origen=celda_escape,
            destinos_objetivo={objetivo},
            grafo=grafo,
            picker_id=getattr(picker, "id_picker", None),
            bloqueos_cercanos={celda_conflicto},
        )
        if not tramo:
            # Si bloqueando la celda en conflicto no hay paso, intenta ruta normal desde celda_escape
            tramo, _ = Pathfinding.calcular_ruta_dijkstra(celda_escape, objetivo, grafo)
            if not tramo:
                return None

        resto_ruta = Pathfinding._empalmar_resto_ruta(picker, objetivo)
        return [celda_escape] + tramo[1:] + resto_ruta

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

        cola = _MinHeapRuteo()
        cola.insertar(0, origen_pasillo)
        distancias: Dict[CoordXY, float] = {origen_pasillo: 0.0}

        while not cola.esta_vacio():
            dist_actual, _, nodo_actual = cola.extraer_minimo()
            if dist_actual > distancias.get(nodo_actual, float("inf")):
                continue

            for vecino in Pathfinding._obtener_vecinos(grafo, nodo_actual, 0):
                nueva_dist = dist_actual + 1
                if nueva_dist < distancias.get(vecino, float("inf")):
                    distancias[vecino] = float(nueva_dist)
                    cola.insertar(nueva_dist, vecino)

        return distancias

    @staticmethod
    def construir_matriz_distancias_productos(
        coordenadas_productos_xy: Set[CoordXY],
        grafo: Any,
        warehouse: Any = None,
    ) -> Dict[Tuple[CoordXY, CoordXY], float]:
        """Precalcula las distancias mínimas entre todas las ubicaciones de productos en el dígrafo."""
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