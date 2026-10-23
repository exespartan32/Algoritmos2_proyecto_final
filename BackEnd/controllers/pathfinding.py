import time
import heapq

class RutaResultado:
    """
    Objeto de retorno esperado por SimulatorController.
    Centraliza las métricas y el camino trazado por el algoritmo.
    """
    def __init__(self, camino_completo, nodos_explorados, tiempo_ejecucion_ms):
        self.camino_completo = camino_completo
        self.nodos_explorados = nodos_explorados  # Lista o set de tuplas (x, y)
        self.distancia_total = len(camino_completo) - 1 if camino_completo else 0
        self.aristas_recorridas = self.distancia_total
        self.tiempo_ejecucion_ms = tiempo_ejecucion_ms


class Pathfinding:
    """
    Motor de búsqueda y ruteo espacial del Warehouse.
    Utiliza Dijkstra y heurísticas voraces sobre grafos de celdas unitarias.
    """

    # ==========================================
    # FUNCIONES ENVOLTORIO PARA EL SIMULADOR
    # ==========================================

    @staticmethod
    def calcular_estrategia_orden_pedidos(grafo, origen, destinos):
        """
        ESTRATEGIA A: Visita los destinos en el orden estricto de la lista
        y luego regresa a la zona de despacho.
        """
        tiempo_inicio = time.perf_counter()
        nodos_explorados_totales = set()
        
        ruta_total = []
        posicion_actual = origen
        
        # 1. Viajar a cada destino en el orden exacto de la lista
        for destino in destinos:
            ruta_tramo, explorados_tramo = Pathfinding.calcular_ruta_dijkstra(posicion_actual, destino, grafo)
            nodos_explorados_totales.update(explorados_tramo)
            
            if ruta_total:
                ruta_total.extend(ruta_tramo[1:])
            else:
                ruta_total.extend(ruta_tramo)
                
            posicion_actual = destino
            
        # 2. Regresar al origen (Zona de Despacho)
        ruta_regreso, explorados_regreso = Pathfinding.calcular_ruta_dijkstra(posicion_actual, origen, grafo)
        nodos_explorados_totales.update(explorados_regreso)
        
        if ruta_total:
            ruta_total.extend(ruta_regreso[1:])
        else:
            ruta_total.extend(ruta_regreso)
            
        tiempo_fin = time.perf_counter()
        tiempo_ms = (tiempo_fin - tiempo_inicio) * 1000
        
        return RutaResultado(ruta_total, list(nodos_explorados_totales), tiempo_ms)

    @staticmethod
    def calcular_estrategia_cercania_multidestino(grafo, origen, destinos_pendientes):
        """
        ESTRATEGIA B: Greedy multidestino. Desde el punto actual, encuentra 
        el destino no visitado más cercano, viaja allí y repite.
        """
        tiempo_inicio = time.perf_counter()
        nodos_explorados_totales = set()
        
        ruta_total = []
        posicion_actual = origen
        pendientes = destinos_pendientes.copy()
        
        while pendientes:
            ruta_tramo, destino_alcanzado, explorados_tramo = Pathfinding.calcular_ruta_greedy(posicion_actual, pendientes, grafo)
            nodos_explorados_totales.update(explorados_tramo)
            
            if not destino_alcanzado:
                break 
                
            if ruta_total:
                ruta_total.extend(ruta_tramo[1:])
            else:
                ruta_total.extend(ruta_tramo)
                
            posicion_actual = destino_alcanzado
            pendientes.remove(destino_alcanzado)
            
        # Regresar al origen (Zona de Despacho)
        ruta_regreso, explorados_regreso = Pathfinding.calcular_ruta_dijkstra(posicion_actual, origen, grafo)
        nodos_explorados_totales.update(explorados_regreso)
        
        if ruta_total:
            ruta_total.extend(ruta_regreso[1:])
        else:
            ruta_total.extend(ruta_regreso)
            
        tiempo_fin = time.perf_counter()
        tiempo_ms = (tiempo_fin - tiempo_inicio) * 1000
        
        return RutaResultado(ruta_total, list(nodos_explorados_totales), tiempo_ms)

    # ==========================================
    # ALGORITMOS CORE MATEMÁTICOS
    # ==========================================

    @staticmethod
    def calcular_ruta_dijkstra(origen, destino, grafo):
        cola = [(0, origen)]
        distancias = {origen: 0}
        padres = {origen: None}
        nodos_explorados = set()
        
        while cola:
            dist_actual, nodo_actual = heapq.heappop(cola)
            nodos_explorados.add(nodo_actual)
            
            if nodo_actual == destino:
                ruta = Pathfinding._reconstruir_ruta(padres, destino)
                return ruta, nodos_explorados
            
            if dist_actual > distancias.get(nodo_actual, float('inf')):
                continue
                
            vecinos = grafo.obtener_vecinos_validos(nodo_actual, paso_tiempo=0) if hasattr(grafo, 'obtener_vecinos_validos') else []
            
            for vecino in vecinos:
                peso = 1 
                nueva_distancia = dist_actual + peso
                
                if nueva_distancia < distancias.get(vecino, float('inf')):
                    distancias[vecino] = nueva_distancia
                    padres[vecino] = nodo_actual
                    heapq.heappush(cola, (nueva_distancia, vecino))
                    
        return [], nodos_explorados

    @staticmethod
    def calcular_ruta_greedy(origen, destinos_pendientes, grafo):
        set_destinos = set(destinos_pendientes)
        cola = [(0, origen)]
        distancias = {origen: 0}
        padres = {origen: None}
        nodos_explorados = set()
        
        while cola:
            dist_actual, nodo_actual = heapq.heappop(cola)
            nodos_explorados.add(nodo_actual)
            
            if nodo_actual in set_destinos:
                ruta = Pathfinding._reconstruir_ruta(padres, nodo_actual)
                return ruta, nodo_actual, nodos_explorados
                
            if dist_actual > distancias.get(nodo_actual, float('inf')):
                continue
                
            vecinos = grafo.obtener_vecinos_validos(nodo_actual, paso_tiempo=0) if hasattr(grafo, 'obtener_vecinos_validos') else []
            
            for vecino in vecinos:
                peso = 1 
                nueva_distancia = dist_actual + peso
                
                if nueva_distancia < distancias.get(vecino, float('inf')):
                    distancias[vecino] = nueva_distancia
                    padres[vecino] = nodo_actual
                    heapq.heappush(cola, (nueva_distancia, vecino))
                    
        return [], None, nodos_explorados

    @staticmethod
    def _reconstruir_ruta(padres, destino_id):
        ruta = []
        actual = destino_id
        while actual is not None:
            ruta.append(actual)
            actual = padres.get(actual)
        ruta.reverse()
        return ruta