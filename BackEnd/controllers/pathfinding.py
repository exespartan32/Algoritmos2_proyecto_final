import heapq
<<<<<<< Updated upstream

# --- GRAFO SIMULADO ---

class WarehouseNode:
    def __init__(self, id_nodo):
        self.id_nodo = id_nodo
    
    def __repr__(self):
        return f"Nodo({self.id_nodo})"

class GrafoMock:
    def __init__(self):
        self.nodos = {}
        self.adyacencias = {}

    def agregar_nodo(self, id_nodo):
        self.nodos[id_nodo] = WarehouseNode(id_nodo)
        self.adyacencias[id_nodo] = []

    def agregar_arista(self, origen, destino, peso):
        self.adyacencias[origen].append((destino, peso))

    def obtener_nodo(self, id_nodo):
        return self.nodos.get(id_nodo)

    def obtener_vecinos(self, id_nodo):
        return self.adyacencias.get(id_nodo, [])
=======
import time
>>>>>>> Stashed changes

# --- ESTRUCTURAS DE DATOS DE INTEGRACIÓN ---

<<<<<<< Updated upstream
# --- PATHFINDING ---

class Pathfinding:
    @staticmethod
    def calcular_ruta_dijkstra(origen, destino, grafo):
        cola = [(0, origen.id_nodo)]
        distancias = {origen.id_nodo: 0}
        padres = {origen.id_nodo: None}
        
        while cola:
            dist_actual, nodo_actual_id = heapq.heappop(cola)
            
            if nodo_actual_id == destino.id_nodo:
                return Pathfinding._reconstruir_ruta(padres, destino.id_nodo, grafo)
            
            if dist_actual > distancias.get(nodo_actual_id, float('inf')):
                continue
                
            for vecino_id, peso in grafo.obtener_vecinos(nodo_actual_id):
                nueva_distancia = dist_actual + peso
                
                if nueva_distancia < distancias.get(vecino_id, float('inf')):
                    distancias[vecino_id] = nueva_distancia
                    padres[vecino_id] = nodo_actual_id
                    heapq.heappush(cola, (nueva_distancia, vecino_id))
                    
        return []

    @staticmethod
    def calcular_ruta_greedy(origen, destinos_pendientes, grafo):
        ids_destinos = set(d.id_nodo for d in destinos_pendientes)
        
        cola = [(0, origen.id_nodo)]
        distancias = {origen.id_nodo: 0}
        padres = {origen.id_nodo: None}
        
        while cola:
            dist_actual, nodo_actual_id = heapq.heappop(cola)
            
            if nodo_actual_id in ids_destinos:
                ruta = Pathfinding._reconstruir_ruta(padres, nodo_actual_id, grafo)
                destino_encontrado = grafo.obtener_nodo(nodo_actual_id)
                return ruta, destino_encontrado
                
            if dist_actual > distancias.get(nodo_actual_id, float('inf')):
                continue
                
            for vecino_id, peso in grafo.obtener_vecinos(nodo_actual_id):
                nueva_distancia = dist_actual + peso
                
                if nueva_distancia < distancias.get(vecino_id, float('inf')):
                    distancias[vecino_id] = nueva_distancia
                    padres[vecino_id] = nodo_actual_id
                    heapq.heappush(cola, (nueva_distancia, vecino_id))
                    
        return [], None

    @staticmethod
    def _reconstruir_ruta(padres, destino_id, grafo):
        ruta_ids = []
        actual = destino_id
        while actual is not None:
            ruta_ids.append(actual)
            actual = padres.get(actual)
            
        ruta_ids.reverse()
        return [grafo.obtener_nodo(id_nodo) for id_nodo in ruta_ids]


# --- PRUEBA DE EJECUCIÓN ---

if __name__ == "__main__":
    # Mapa de prueba
    grafo = GrafoMock()
    for nodo in ['Despacho', 'Pasillo_1', 'Rack_A', 'Rack_B']:
        grafo.agregar_nodo(nodo)

    # Conectamos los nodos
    grafo.agregar_arista('Despacho', 'Pasillo_1', 30)
    grafo.agregar_arista('Pasillo_1', 'Rack_A', 50)
    grafo.agregar_arista('Pasillo_1', 'Rack_B', 60)  # Ir al Rack B es más corto
    grafo.agregar_arista('Rack_B', 'Rack_A', 5)     # Atajo desde B hacia A
    
    # Definimos origen y objetivos
    inicio = grafo.obtener_nodo('Despacho')
    objetivo_a = grafo.obtener_nodo('Rack_A')
    objetivo_b = grafo.obtener_nodo('Rack_B')
    
    print("--- PRUEBA ESTRATEGIA A (Dijkstra) ---")
    # El picker debe ir al rack A para comprobar que tome la ruta de menor costo
    ruta_a = Pathfinding.calcular_ruta_dijkstra(inicio, objetivo_a, grafo)
    print(f"Ruta hacia {objetivo_a}: {ruta_a}")
    # Resultado esperado: [Despacho, Pasillo_1, Rack_B, Rack_A] porque usa el atajo.

    print("\n--- PRUEBA ESTRATEGIA B (Greedy) ---")
    # Le damos una lista de pedidos. En teoria deberia tomar el rack que corresponda al camino de menor costo
    pendientes = [objetivo_a, objetivo_b]
    ruta_b, destino_alcanzado = Pathfinding.calcular_ruta_greedy(inicio, pendientes, grafo)
    print(f"Objetivo mas cercano encontrado: {destino_alcanzado}")
    print(f"Ruta tomada: {ruta_b}")

=======
class RutaResultado:
    """
    Objeto de retorno esperado por SimulatorController.
    Centraliza las métricas y el camino trazado por el algoritmo.
    """
    def __init__(self, camino_completo, nodos_explorados, tiempo_ejecucion_ms):
        self.camino_completo = camino_completo
        self.nodos_explorados = nodos_explorados  # Espera una lista o un set de tuplas (x,y)
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
            
            # Unimos la ruta evitando duplicar la celda donde estamos parados
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
        
        # 1. Viajar al más cercano iterativamente
        while pendientes:
            ruta_tramo, destino_alcanzado, explorados_tramo = Pathfinding.calcular_ruta_greedy(posicion_actual, pendientes, grafo)
            nodos_explorados_totales.update(explorados_tramo)
            
            if not destino_alcanzado:
                break # Evita bucles infinitos si hay un nodo inalcanzable
                
            # Agregamos los pasos al historial
            if ruta_total:
                ruta_total.extend(ruta_tramo[1:])
            else:
                ruta_total.extend(ruta_tramo)
                
            # Actualizamos estado
            posicion_actual = destino_alcanzado
            pendientes.remove(destino_alcanzado)
            
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


    # ==========================================
    # ALGORITMOS CORE MATEMÁTICOS
    # ==========================================

    @staticmethod
    def calcular_ruta_dijkstra(origen, destino, grafo):
        """
        Dijkstra Clásico Punto a Punto.
        Retorna la ruta y un set de los nodos que tuvo que explorar.
        """
        cola = [(0, origen)]
        distancias = {origen: 0}
        padres = {origen: None}
        nodos_explorados = set()
        
        while cola:
            dist_actual, nodo_actual = heapq.heappop(cola)
            nodos_explorados.add(nodo_actual)
            
            # Early exit: llegamos al destino exacto
            if nodo_actual == destino:
                ruta = Pathfinding._reconstruir_ruta(padres, destino)
                return ruta, nodos_explorados
            
            if dist_actual > distancias.get(nodo_actual, float('inf')):
                continue
                
            # Asumimos que grafo.obtener_vecinos_validos retorna List[Tuple[int,int]]
            # y que en la grilla unitaria cada paso vale 1.
            vecinos = grafo.obtener_vecinos_validos(nodo_actual, paso_tiempo=0)
            
            for vecino in vecinos:
                peso = 1 # Grilla discreta (costo unitario)
                nueva_distancia = dist_actual + peso
                
                if nueva_distancia < distancias.get(vecino, float('inf')):
                    distancias[vecino] = nueva_distancia
                    padres[vecino] = nodo_actual
                    heapq.heappush(cola, (nueva_distancia, vecino))
                    
        return [], nodos_explorados

    @staticmethod
    def calcular_ruta_greedy(origen, destinos_pendientes, grafo):
        """
        Dijkstra optimizado con Early Exit Multidestino.
        Retorna (ruta, destino_alcanzado, nodos_explorados).
        """
        # Convertimos la lista a un set (hash table interno) para búsqueda O(1)
        set_destinos = set(destinos_pendientes)
        
        cola = [(0, origen)]
        distancias = {origen: 0}
        padres = {origen: None}
        nodos_explorados = set()
        
        while cola:
            dist_actual, nodo_actual = heapq.heappop(cola)
            nodos_explorados.add(nodo_actual)
            
            # Early exit multidestino: si el nodo actual está en el set de destinos, ganamos.
            if nodo_actual in set_destinos:
                ruta = Pathfinding._reconstruir_ruta(padres, nodo_actual)
                return ruta, nodo_actual, nodos_explorados
                
            if dist_actual > distancias.get(nodo_actual, float('inf')):
                continue
                
            vecinos = grafo.obtener_vecinos_validos(nodo_actual, paso_tiempo=0)
            
            for vecino in vecinos:
                peso = 1 # Grilla discreta
                nueva_distancia = dist_actual + peso
                
                if nueva_distancia < distancias.get(vecino, float('inf')):
                    distancias[vecino] = nueva_distancia
                    padres[vecino] = nodo_actual
                    heapq.heappush(cola, (nueva_distancia, vecino))
                    
        return [], None, nodos_explorados

    @staticmethod
    def _reconstruir_ruta(padres, destino_id):
        """Reconstruye el camino desde el destino hacia el origen."""
        ruta = []
        actual = destino_id
        while actual is not None:
            ruta.append(actual)
            actual = padres.get(actual)
            
        ruta.reverse()
        return ruta
>>>>>>> Stashed changes
