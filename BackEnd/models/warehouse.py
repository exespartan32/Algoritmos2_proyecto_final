from typing import Dict, List, Tuple, Optional
from BackEnd.models.entity import (
    Celda, CeldaRack, TipoCelda, Sentido, Rack, ZonaDespacho, Puerta, Producto
)

Coord = Tuple[int, int]


class NodoGrafo:
    """Una celda de PASILLO transitable. Es la única clase de celda que es nodo del grafo.

    Racks, zonas de despacho y puertas son obstáculos que el picker no atraviesa
    (enunciado 3.6), así que no son nodos.
    """
    def __init__(self, x: int, y: int, sentido: Sentido, pasillo_id: Optional[str] = None):
        self.x = x
        self.y = y
        self.sentido_permitido = sentido
        # ID del pasillo declarado en el JSON (None si es una celda libre, que es pasillo AMBOS)
        self.pasillo_id = pasillo_id
        # Celdas de rack que se pueden recoger desde este nodo (por el costado del rack)
        self.racks_adyacentes: List[CeldaRack] = []
        # IDs de zonas de despacho pegadas a este nodo
        self.zonas_despacho_adyacentes: List[str] = []


class Digrafo:
    """Grafo dirigido representado mediante Lista de Adyacencia.

    nodos:            (x, y) -> NodoGrafo
    lista_adyacencia: (x, y) -> lista de coordenadas destino (aristas de costo 1)
    """
    def __init__(self):
        self.nodos: Dict[Coord, NodoGrafo] = {}
        self.lista_adyacencia: Dict[Coord, List[Coord]] = {}

    def agregar_nodo(self, x: int, y: int, sentido: Sentido, pasillo_id: Optional[str] = None) -> NodoGrafo:
        coord = (x, y)
        if coord not in self.nodos:
            self.nodos[coord] = NodoGrafo(x, y, sentido, pasillo_id)
            self.lista_adyacencia[coord] = []
        return self.nodos[coord]

    def agregar_arista_dirigida(self, origen: Coord, destino: Coord):
        # Cada nodo tiene como máximo 4 vecinos, así que el chequeo de
        # duplicados sobre la lista es O(1) en la práctica.
        if origen in self.lista_adyacencia and destino in self.nodos:
            if destino not in self.lista_adyacencia[origen]:
                self.lista_adyacencia[origen].append(destino)

    def obtener_vecinos(self, coord: Coord) -> List[Coord]:
        return self.lista_adyacencia.get(coord, [])


class Warehouse:
    """Almacén de ancho_x por largo_y (el eje y crece hacia arriba).

    No hay una matriz con todas las celdas: los pasillos viven en el dígrafo
    (grafo_pasillos.nodos) y los obstáculos en el diccionario `obstaculos`.
    Toda coordenada dentro del almacén es exactamente una de las dos cosas.
    """
    def __init__(self, ancho_x: int, largo_y: int):
        self.ancho_x = ancho_x
        self.largo_y = largo_y
        self.grafo_pasillos = Digrafo()
        # Celdas que NO son nodo: (x, y) -> CeldaRack o Celda de tipo ZONA_DESPACHO / PUERTA
        self.obstaculos: Dict[Coord, Celda] = {}

        self.racks: Dict[str, Rack] = {}
        self.zonas_despacho: Dict[str, ZonaDespacho] = {}
        self.puertas: Dict[str, Puerta] = {}
        self.catalogo_productos: Dict[str, Producto] = {}

        # Compatibilidad: celda de RACK -> PRIMER nodo de PASILLO desde el que se la recoge
        self.acceso_rack_a_pasillo: Dict[Coord, Coord] = {}
        # Celda de RACK -> TODOS los nodos de PASILLO desde los que se la recoge
        self.accesos_rack_a_pasillo: Dict[Coord, List[Coord]] = {}
        # ID de zona de despacho -> nodos de PASILLO pegados a la zona
        self.accesos_zona_a_pasillo: Dict[str, List[Coord]] = {}
        # Problemas del mapa detectados al construir/validar (no son errores fatales)
        self.advertencias: List[str] = []

    def dentro(self, x: int, y: int) -> bool:
        return 0 <= x < self.ancho_x and 0 <= y < self.largo_y

    def obtener_nodo_acceso_producto(self, prod_id: str) -> Optional[Coord]:
        """Devuelve la coordenada del nodo de PASILLO donde debe frenar el picker para recoger el producto."""
        prod = self.catalogo_productos.get(prod_id)
        if not prod:
            return None
        return self.acceso_rack_a_pasillo.get((prod.x, prod.y))

    def obtener_nodos_acceso_producto(self, prod_id: str) -> List[Coord]:
        """Devuelve todos los nodos de PASILLO desde los que se puede recoger el producto."""
        prod = self.catalogo_productos.get(prod_id)
        if not prod:
            return []
        return list(self.accesos_rack_a_pasillo.get((prod.x, prod.y), []))

    def obtener_nodos_acceso_zona(self, zona_id: str) -> List[Coord]:
        """Devuelve los nodos de PASILLO pegados a la zona de despacho."""
        return list(self.accesos_zona_a_pasillo.get(zona_id, []))

    def imprimir_mapa(self, camino_bfs: Optional[List[Coord]] = None):
        """Imprime el almacén en la terminal (y crece hacia arriba, x hacia la derecha).

        camino_bfs: lista opcional de coordenadas a marcar con '*' (por ejemplo, un camino o los puntos de acceso).
        """
        camino_set = set(camino_bfs) if camino_bfs else set()

        simbolos_sentido = {
            Sentido.N: "^",
            Sentido.S: "v",
            Sentido.E: ">",
            Sentido.O: "<",
            Sentido.AMBOS: "+",
            Sentido.NINGUNO: "x",
        }
        simbolos_obstaculo = {
            TipoCelda.RACK: "#",
            TipoCelda.ZONA_DESPACHO: "D",
            TipoCelda.PUERTA: "P",
        }

        print("\n=== MAPA DEL WAREHOUSE ===")
        # Recorremos Y de arriba hacia abajo para que el (0,0) quede abajo a la izquierda
        for y in range(self.largo_y - 1, -1, -1):
            fila_str = f"y={y:02d} | "
            for x in range(self.ancho_x):
                if (x, y) in camino_set:
                    fila_str += "*"
                elif (x, y) in self.obstaculos:
                    fila_str += simbolos_obstaculo[self.obstaculos[(x, y)].tipo]
                else:
                    nodo = self.grafo_pasillos.nodos[(x, y)]
                    # Celda libre (no declarada) -> '.', pasillo declarado -> símbolo de su sentido
                    fila_str += "." if nodo.pasillo_id is None else simbolos_sentido[nodo.sentido_permitido]
            print(fila_str)

        # Eje X abajo
        print("     +" + "-" * self.ancho_x)
        decenas = "       " + "".join(str((x // 10) % 10) for x in range(self.ancho_x))
        unidades = "       " + "".join(str(x % 10) for x in range(self.ancho_x))
        print(decenas)
        print(unidades)
        print("Referencias: [#] Rack | [D] Despacho | [P] Puerta | [^ v > < + x .] Pasillos | [*] Celdas marcadas\n")
