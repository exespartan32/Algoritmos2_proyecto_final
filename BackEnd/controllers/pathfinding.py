import heapq

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

