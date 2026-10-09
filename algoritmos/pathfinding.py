import heapq


class PathfindingService:
    def __init__(self, grafo_warehouse):
        self.grafo = grafo_warehouse

    def calcular_camino_mas_corto(self, id_nodo_origen, id_nodo_destino):
        """
        Implementación de Dijkstra para encontrar la ruta óptima.
        Retorna una lista de nodos ordenados desde el origen hasta el destino.
        """
        # Cola de prioridad (min-queue) para extraer el vértice con menor distancia
        cola_prioridad = []
        heapq.heappush(cola_prioridad, (0, id_nodo_origen))

        # Diccionarios para rastrear distancias (d) y predecesores (pi)
        distancias = {id_nodo_origen: 0}
        padres = {id_nodo_origen: None}

        while cola_prioridad:
            # Extraemos el nodo con la distancia acumulada más pequeña
            distancia_actual, id_actual = heapq.heappop(cola_prioridad)

            # Si llegamos al destino, reconstruimos y retornamos la ruta
            if id_actual == id_nodo_destino:
                return self._reconstruir_ruta(padres, id_nodo_destino)

            # Si encontramos una ruta más larga en la cola por un remanente, la ignoramos
            if distancia_actual > distancias.get(id_actual, float("inf")):
                continue

            nodo_actual = self.grafo.nodos[id_actual]

            # Relajación de aristas: Escaneamos los vecinos
            for vecino in nodo_actual.vecinos:
                peso_arista = 1  # Costo uniforme de 1 metro por celda de suelo
                nueva_distancia = distancia_actual + peso_arista

                # Si encontramos un camino más corto hacia el vecino, lo actualizamos
                if nueva_distancia < distancias.get(vecino.id_nodo, float("inf")):
                    distancias[vecino.id_nodo] = nueva_distancia
                    padres[vecino.id_nodo] = id_actual
                    heapq.heappush(cola_prioridad, (nueva_distancia, vecino.id_nodo))

        return []  # Retorna vacío si no hay camino posible (ej. bloqueado por paredes)

    def _reconstruir_ruta(self, padres, id_destino):
        """Recorre los predecesores (pi) en reversa para armar la ruta secuencial."""
        ruta = []
        actual = id_destino
        while actual is not None:
            ruta.append(actual)
            actual = padres.get(actual)
        ruta.reverse()  # Invertimos para que empiece en el origen
        return ruta
