from typing import Dict, List, Tuple, Optional
from BackEnd.models.entity import (
    Celda, CeldaRack, Sentido, Rack, ZonaDespacho, Puerta, Producto
)

Coord = Tuple[int, int]

class NodoGrafo:
    """Representa una celda de PASILLO transitable dentro del Digrafo."""
    def __init__(self, x: int, y: int, sentido: Sentido):
        self.x = x
        self.y = y
        self.sentido_permitido = sentido
        # Celdas de rack que están pegadas al costado de este nodo calle
        self.racks_adyacentes: List[CeldaRack] = []
        # IDs de zonas de despacho pegadas a este nodo calle
        self.zonas_despacho_adyacentes: List[str] = []

class Digrafo:
    """Grafo dirigido representado mediante Lista de Adyacencia."""
    def __init__(self):
        self.nodos: Dict[Coord, NodoGrafo] = {}
        self.lista_adyacencia: Dict[Coord, List[Coord]] = {}

    def agregar_nodo(self, x: int, y: int, sentido: Sentido) -> NodoGrafo:
        coord = (x, y)
        if coord not in self.nodos:
            self.nodos[coord] = NodoGrafo(x, y, sentido)
            self.lista_adyacencia[coord] = []
        return self.nodos[coord]

    def agregar_arista_dirigida(self, origen: Coord, destino: Coord):
        if origen in self.lista_adyacencia and destino in self.nodos:
            if destino not in self.lista_adyacencia[origen]:
                self.lista_adyacencia[origen].append(destino)

    def obtener_vecinos(self, coord: Coord) -> List[Coord]:
        return self.lista_adyacencia.get(coord, [])

class Warehouse:
    def __init__(self, ancho_x: int, largo_y: int):
        self.ancho_x = ancho_x
        self.largo_y = largo_y
        # Matriz de [ancho_x][largo_y]
        self.matriz: List[List[Optional[Celda]]] = [
            [None for _ in range(largo_y)] for _ in range(ancho_x)
        ]
        self.grafo_pasillos = Digrafo()
        
        self.racks: Dict[str, Rack] = {}
        self.zonas_despacho: Dict[str, ZonaDespacho] = {}
        self.puertas: Dict[str, Puerta] = {}
        self.catalogo_productos: Dict[str, Producto] = {}
        
        # Mapa rápido: dada una coordenada (x, y) de un RACK, devuelve qué nodo de PASILLO lo atiende
        self.acceso_rack_a_pasillo: Dict[Coord, Coord] = {}

    def obtener_nodo_acceso_producto(self, prod_id: str) -> Optional[Coord]:
        """Devuelve la coordenada del nodo de PASILLO donde debe frenar el picker para recoger el producto."""
        prod = self.catalogo_productos.get(prod_id)
        if not prod:
            return None
        return self.acceso_rack_a_pasillo.get((prod.x, prod.y))