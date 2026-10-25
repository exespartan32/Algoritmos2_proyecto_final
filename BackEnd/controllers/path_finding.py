import time
import heapq
from typing import List, Tuple, Set, Dict, Optional, Any

CoordXY = Tuple[int, int]


class RutaResultado:
    """
    Objeto de retorno esperado por SimulatorController.
    Centraliza las métricas y el camino trazado por el algoritmo.
    """

    def __init__(
        self,
        camino_completo: List[CoordXY],
        nodos_explorados: List[CoordXY],
        tiempo_ejecucion_ms: float,
        destinos_inalcanzables: Optional[List[CoordXY]] = None,
    ) -> None:
        self.camino_completo = camino_completo
        self.nodos_explorados = nodos_explorados  # Lista de tuplas (x, y)
        self.distancia_total = len(camino_completo) - 1 if camino_completo else 0
        self.aristas_recorridas = self.distancia_total
        self.tiempo_ejecucion_ms = tiempo_ejecucion_ms
        self.destinos_inalcanzables = destinos_inalcanzables or []


class Pathfinding:
    """
    Motor de búsqueda y ruteo espacial del Warehouse.
    Utiliza Dijkstra y heurísticas voraces sobre dígrafos de celdas unitarias.
    """

    # Parámetro global de orientación de ejes según escenario_basico.json y escenario_grande.json:
    # True  -> Norte (arriba) es y + 1, Sur (abajo) es y - 1
    # False -> Norte (arriba) es y - 1, Sur (abajo) es y + 1 (coordenadas de pantalla invertidas)
    NORTE_AUMENTA_Y: bool = True

    # =========================================================================
    # REGLAS DE CIRCULACIÓN EN EL DÍGRAFO Y TRADUCCIÓN RACK -> PASILLO
    # =========================================================================

    @staticmethod
    def es_movimiento_permitido_digrafo(
        origen: CoordXY,
        destino: CoordXY,
        sentido_origen: str,
        sentido_destino: str = "AMBOS",
        norte_aumenta_y: Optional[bool] = None,
    ) -> bool:
        """
        Verifica si es válido moverse de 'origen' a 'destino' (celdas ortogonalmente
        adyacentes) respetando las reglas de circulación del Warehouse:
        - Si el sentido de circulación es N o S, también se permite al picker
          moverse hacia los costados (Este-Oeste). Solo se prohíbe el sentido
          vertical opuesto.
        - Si el sentido de circulación es E u O, también se permite al picker
          moverse hacia arriba y abajo (Norte-Sur). Solo se prohíbe el sentido
          horizontal opuesto.
        - No se permite entrar a una celda vecina a contramano de su propio sentido.
        """
        usar_norte_positivo = (
            Pathfinding.NORTE_AUMENTA_Y if norte_aumenta_y is None else norte_aumenta_y
        )

        dx = destino[0] - origen[0]
        dy = destino[1] - origen[1]

        # Solo movimientos ortogonales de 1 celda
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

        # Determinar la dirección cardinal del paso (N, S, E, O)
        if dx == 1:
            dir_paso = "E"
            opuesto_paso = "O"
        elif dx == -1:
            dir_paso = "O"
            opuesto_paso = "E"
        elif dy == 1:
            dir_paso = "N" if usar_norte_positivo else "S"
            opuesto_paso = "S" if usar_norte_positivo else "N"
        else:  # dy == -1
            dir_paso = "S" if usar_norte_positivo else "N"
            opuesto_paso = "N" if usar_norte_positivo else "S"

        # 1. Restricción de salida desde la celda origen:
        # Si origen es N, prohíbe S (permite N, E, O).
        # Si origen es S, prohíbe N (permite S, E, O).
        # Si origen es E, prohíbe O (permite E, N, S).
        # Si origen es O, prohíbe E (permite O, N, S).
        if s_orig == opuesto_paso:
            return False

        # 2. Restricción de entrada a la celda destino (no entrar a contramano):
        if s_dest == opuesto_paso:
            return False

        return True

    @staticmethod
    def _es_celda_pasillo_en_grafo(coord: CoordXY, grafo: Any) -> bool:
        """Comprueba si 'coord' existe como nodo transitable dentro del grafo."""
        if grafo is None:
            return False
        if hasattr(grafo, "lista_adyacencia") and isinstance(
            grafo.lista_adyacencia, dict
        ):
            return coord in grafo.lista_adyacencia
        if hasattr(grafo, "nodos") and isinstance(grafo.nodos, dict):
            return coord in grafo.nodos
        if hasattr(grafo, "es_transitable"):
            return bool(grafo.es_transitable(coord))
        if hasattr(grafo, "obtener_vecinos_validos"):
            return len(grafo.obtener_vecinos_validos(coord, paso_tiempo=0)) > 0
        return False

    @staticmethod
    def obtener_celda_acceso_pasillo(
        coord_xy: CoordXY,
        grafo: Any,
        warehouse: Any = None,
    ) -> CoordXY:
        """
        Traduce la coordenada (rx, ry) de un producto (que cae adentro de un Rack
        de ancho 2) a su celda de pasillo adyacente en el dígrafo:
        - Si ya es una celda de pasillo transitable, la devuelve tal cual.
        - En los JSON del proyecto, los racks son verticales de ancho 2:
          la columna izquierda accede por (rx - 1, ry) y la derecha por (rx + 1, ry).
        """
        if Pathfinding._es_celda_pasillo_en_grafo(coord_xy, grafo):
            return coord_xy

        rx, ry = coord_xy

        # Si el objeto warehouse de Laureano provee un método específico, usarlo:
        if warehouse is not None and hasattr(warehouse, "obtener_celda_acceso_pasillo"):
            acceso = warehouse.obtener_celda_acceso_pasillo(rx, ry)
            if acceso is not None:
                return acceso

        # Priorizamos los pasillos laterales izquierdo (rx - 1, ry) y derecho (rx + 1, ry),
        # y luego superior/inferior por si hubiese un rack en borde horizontal.
        candidatos_adyacentes = [
            (rx - 1, ry),
            (rx + 1, ry),
            (rx, ry - 1),
            (rx, ry + 1),
        ]
        for candidato in candidatos_adyacentes:
            if Pathfinding._es_celda_pasillo_en_grafo(candidato, grafo):
                return candidato

        return coord_xy

    # =========================================================================
    # FUNCIONES ENVOLTORIO PARA EL SIMULADOR (CON MANEJO DE CASOS LÍMITE)
    # =========================================================================

    @staticmethod
    def calcular_estrategia_orden_pedidos(
        grafo: Any,
        origen: CoordXY,
        destinos: List[CoordXY],
    ) -> RutaResultado:
        """
        ESTRATEGIA A: Visita los destinos en el orden estricto de la lista
        y luego regresa a la zona de despacho.
        Contempla casos límite:
        - Lista de destinos vacía.
        - Coordenadas de destino dentro de racks (se traducen a su pasillo adyacente).
        - Destinos consecutivos idénticos.
        - Destinos inalcanzables (evita teletransportar al picker).
        """
        tiempo_inicio = time.perf_counter()
        nodos_explorados_totales: Set[CoordXY] = set()
        destinos_inalcanzables: List[CoordXY] = []

        origen_pasillo = Pathfinding.obtener_celda_acceso_pasillo(origen, grafo)

        # Caso límite: sin destinos
        if not destinos:
            tiempo_ms = (time.perf_counter() - tiempo_inicio) * 1000
            return RutaResultado([origen_pasillo], [], tiempo_ms)

        ruta_total: List[CoordXY] = [origen_pasillo]
        posicion_actual = origen_pasillo

        # 1. Viajar a cada destino en el orden exacto de la lista
        for destino_raw in destinos:
            destino = Pathfinding.obtener_celda_acceso_pasillo(destino_raw, grafo)

            # Caso límite: dos productos consecutivos comparten el mismo punto de acceso
            if destino == posicion_actual:
                continue

            ruta_tramo, explorados_tramo = Pathfinding.calcular_ruta_dijkstra(
                posicion_actual, destino, grafo
            )
            nodos_explorados_totales.update(explorados_tramo)

            # Caso límite crítico: si no existe camino, NO teletransportar posicion_actual
            if not ruta_tramo:
                destinos_inalcanzables.append(destino_raw)
                continue

            ruta_total.extend(ruta_tramo[1:])
            posicion_actual = destino

        # 2. Regresar al origen (Zona de Despacho)
        if posicion_actual != origen_pasillo:
            ruta_regreso, explorados_regreso = Pathfinding.calcular_ruta_dijkstra(
                posicion_actual, origen_pasillo, grafo
            )
            nodos_explorados_totales.update(explorados_regreso)

            if ruta_regreso:
                ruta_total.extend(ruta_regreso[1:])
            else:
                destinos_inalcanzables.append(origen_pasillo)

        tiempo_fin = time.perf_counter()
        tiempo_ms = (tiempo_fin - tiempo_inicio) * 1000

        return RutaResultado(
            ruta_total,
            list(nodos_explorados_totales),
            tiempo_ms,
            destinos_inalcanzables,
        )

    @staticmethod
    def calcular_estrategia_cercania_multidestino(
        grafo: Any,
        origen: CoordXY,
        destinos_pendientes: List[CoordXY],
    ) -> RutaResultado:
        """
        ESTRATEGIA B: Greedy multidestino. Desde el punto actual, encuentra
        el destino no visitado más cercano en una sola corrida de Dijkstra,
        viaja allí y repite.
        Contempla casos límite:
        - Duplicados en destinos_pendientes (ej. varios productos en el mismo rack).
        - Coordenadas en racks traducidas automáticamente a pasillo.
        - Destinos desconectados del dígrafo.
        """
        tiempo_inicio = time.perf_counter()
        nodos_explorados_totales: Set[CoordXY] = set()
        destinos_inalcanzables: List[CoordXY] = []

        origen_pasillo = Pathfinding.obtener_celda_acceso_pasillo(origen, grafo)

        if not destinos_pendientes:
            tiempo_ms = (time.perf_counter() - tiempo_inicio) * 1000
            return RutaResultado([origen_pasillo], [], tiempo_ms)

        ruta_total: List[CoordXY] = [origen_pasillo]
        posicion_actual = origen_pasillo

        # Traducir cada destino a su celda de pasillo y eliminar duplicados en O(1)
        pendientes: Set[CoordXY] = {
            Pathfinding.obtener_celda_acceso_pasillo(d, grafo)
            for d in destinos_pendientes
        }
        pendientes.discard(origen_pasillo)

        while pendientes:
            ruta_tramo, destino_alcanzado, explorados_tramo = (
                Pathfinding.calcular_ruta_greedy(posicion_actual, pendientes, grafo)
            )
            nodos_explorados_totales.update(explorados_tramo)

            if not destino_alcanzado or not ruta_tramo:
                # Los destinos que quedaron en 'pendientes' son inalcanzables
                destinos_inalcanzables.extend(pendientes)
                break

            ruta_total.extend(ruta_tramo[1:])
            posicion_actual = destino_alcanzado
            pendientes.discard(destino_alcanzado)

        # Regresar al origen (Zona de Despacho)
        if posicion_actual != origen_pasillo:
            ruta_regreso, explorados_regreso = Pathfinding.calcular_ruta_dijkstra(
                posicion_actual, origen_pasillo, grafo
            )
            nodos_explorados_totales.update(explorados_regreso)

            if ruta_regreso:
                ruta_total.extend(ruta_regreso[1:])
            else:
                destinos_inalcanzables.append(origen_pasillo)

        tiempo_fin = time.perf_counter()
        tiempo_ms = (tiempo_fin - tiempo_inicio) * 1000

        return RutaResultado(
            ruta_total,
            list(nodos_explorados_totales),
            tiempo_ms,
            destinos_inalcanzables,
        )

    # =========================================================================
    # ALGORITMOS CORE MATEMÁTICOS (DIJKSTRA PUNTO A PUNTO Y MULTIDESTINO)
    # =========================================================================

    @staticmethod
    def _obtener_vecinos(
        grafo: Any, nodo_actual: CoordXY, paso_tiempo: int = 0
    ) -> List[CoordXY]:
        if hasattr(grafo, "obtener_vecinos_validos"):
            return grafo.obtener_vecinos_validos(nodo_actual, paso_tiempo=paso_tiempo)
        if hasattr(grafo, "lista_adyacencia") and isinstance(
            grafo.lista_adyacencia, dict
        ):
            return grafo.lista_adyacencia.get(nodo_actual, [])
        if isinstance(grafo, dict):
            return grafo.get(nodo_actual, [])
        return []

    @staticmethod
    def calcular_ruta_dijkstra(
        origen: CoordXY,
        destino: CoordXY,
        grafo: Any,
        paso_tiempo_inicial: int = 0,
    ) -> Tuple[List[CoordXY], Set[CoordXY]]:
        if origen == destino:
            return [origen], {origen}

        cola: List[Tuple[int, CoordXY]] = [(0, origen)]
        distancias: Dict[CoordXY, int] = {origen: 0}
        padres: Dict[CoordXY, Optional[CoordXY]] = {origen: None}
        nodos_explorados: Set[CoordXY] = set()

        while cola:
            dist_actual, nodo_actual = heapq.heappop(cola)

            # Primero filtramos entradas obsoletas del heap antes de marcar explorado
            if dist_actual > distancias.get(nodo_actual, float("inf")):
                continue

            nodos_explorados.add(nodo_actual)

            if nodo_actual == destino:
                ruta = Pathfinding._reconstruir_ruta(padres, destino)
                return ruta, nodos_explorados

            paso_eval = (
                paso_tiempo_inicial + dist_actual if paso_tiempo_inicial > 0 else 0
            )
            vecinos = Pathfinding._obtener_vecinos(
                grafo, nodo_actual, paso_tiempo=paso_eval
            )

            for vecino in vecinos:
                peso = 1
                nueva_distancia = dist_actual + peso

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

            if nodo_actual in set_destinos:
                ruta = Pathfinding._reconstruir_ruta(padres, nodo_actual)
                return ruta, nodo_actual, nodos_explorados

            paso_eval = (
                paso_tiempo_inicial + dist_actual if paso_tiempo_inicial > 0 else 0
            )
            vecinos = Pathfinding._obtener_vecinos(
                grafo, nodo_actual, paso_tiempo=paso_eval
            )

            for vecino in vecinos:
                peso = 1
                nueva_distancia = dist_actual + peso

                if nueva_distancia < distancias.get(vecino, float("inf")):
                    distancias[vecino] = nueva_distancia
                    padres[vecino] = nodo_actual
                    heapq.heappush(cola, (nueva_distancia, vecino))

        return [], None, nodos_explorados

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

    # =========================================================================
    # SERVICIO DE DISTANCIAS DEL DÍGRAFO PARA WAVE MANAGER (CONSULTA O(1))
    # =========================================================================

    @staticmethod
    def calcular_mapa_distancias_desde(
        origen_pasillo: CoordXY, grafo: Any
    ) -> Dict[CoordXY, float]:
        """
        Ejecuta una única expansión de Dijkstra desde 'origen_pasillo' hacia
        todo el dígrafo en O((V + E) log V) y retorna el diccionario de distancias.
        """
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
        """
        Precalcula las distancias dirigidas reales en el dígrafo entre todas las
        coordenadas (x, y) de productos (racks), traduciéndolas internamente a su
        celda de pasillo adyacente.
        Retorna un diccionario {(u_rack_xy, v_rack_xy): distancia_dirigida} para que
        WaveManager consulte cualquier par en tiempo O(1).
        """
        # 1. Traducir cada coordenada de producto (rack) a su celda de pasillo
        mapa_rack_a_pasillo: Dict[CoordXY, CoordXY] = {
            coord_rack: Pathfinding.obtener_celda_acceso_pasillo(
                coord_rack, grafo, warehouse
            )
            for coord_rack in coordenadas_productos_xy
        }

        # 2. Ejecutar Dijkstra una sola vez por cada celda de pasillo origen única
        pasillos_unicos = set(mapa_rack_a_pasillo.values())
        distancias_entre_pasillos: Dict[CoordXY, Dict[CoordXY, float]] = {
            pasillo_orig: Pathfinding.calcular_mapa_distancias_desde(
                pasillo_orig, grafo
            )
            for pasillo_orig in pasillos_unicos
        }

        # 3. Indexar la matriz directamente por las coordenadas (x, y) de los productos
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
