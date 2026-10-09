from modelos.entidades import WarehouseNode, TipoNodo


class GrafoWarehouse:
    def __init__(self):
        self.nodos = {}  # Diccionario O(1) para buscar coordenadas
        self.matriz_plano = []  # Guardará la matriz 2D original

    def cargar_desde_matriz(self, matriz_2d):
        """
        Recibe una matriz de listas de Python con valores del 0 al 5
        y genera los nodos en z=0 (el suelo).
        """
        self.matriz_plano = matriz_2d
        filas = len(matriz_2d)
        columnas = len(matriz_2d[0])

        # 1. Instanciar todos los nodos del plano (z=0)
        for y in range(filas):
            for x in range(columnas):
                valor = matriz_2d[y][x]
                tipo = TipoNodo(valor)
                nodo = WarehouseNode(x, y, 0, tipo)
                self.nodos[nodo.id_nodo] = nodo

        # 2. Conectar el grafo (Solo calles transitables, en forma de cruz)
        self._conectar_cruz_recta(filas, columnas)

    def _conectar_cruz_recta(self, filas, columnas):
        """Conecta los nodos Norte-Sur y Este-Oeste sin diagonales"""
        # (dx, dy): Derecha (Este), Izquierda (Oeste), Abajo (Sur), Arriba (Norte)
        direcciones = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        for y in range(filas):
            for x in range(columnas):
                nodo_actual = self.obtener_nodo(x, y, 0)

                # Si el nodo actual no es caminable (Ej: Rack, Pared, Oficina),
                # no le calculamos caminos de salida.
                if not nodo_actual.es_transitable():
                    continue

                for dx, dy in direcciones:
                    nx, ny = x + dx, y + dy
                    vecino = self.obtener_nodo(nx, ny, 0)

                    # Si el vecino existe y TAMBIÉN es transitable, creamos la arista
                    if vecino and vecino.es_transitable():
                        nodo_actual.agregar_vecino(vecino)

    def obtener_nodo(self, x, y, z):
        return self.nodos.get(f"{x},{y},{z}")

    def encontrar_calle_adyacente_a_rack(self, rack_x, rack_y):
        """
        Dado un Rack, busca cuál es la CALLE adyacente (en cruz)
        donde el picker debe detenerse para recoger el producto.
        """
        direcciones = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        calles_disponibles = []

        for dx, dy in direcciones:
            vecino = self.obtener_nodo(rack_x + dx, rack_y + dy, 0)
            if vecino and vecino.es_transitable():
                calles_disponibles.append(vecino)

        return calles_disponibles  # Retorna los puntos donde el picker puede pararse


def calcular_costo_recoleccion(ruta_suelo, altura_z):
    """
    ruta_suelo: Lista de nodos (x,y,0) que el picker recorrió hasta llegar frente al rack.
    altura_z: El nivel z donde está guardado el producto en el rack.
    """
    # Costo de caminar por el suelo (cada celda es 1 metro)
    distancia_caminada = len(ruta_suelo) - 1

    # Costo de subir/bajar a recoger el producto en el estante
    # No puede ser menor a 0.
    esfuerzo_vertical = max(0, altura_z)

    costo_total = distancia_caminada + esfuerzo_vertical
    return costo_total
