from enum import Enum
from typing import Dict, Optional
# Clases base y enumeraciones (TipoCelda, Sentido, Celda, CeldaRack,
# Producto, Rack, ZonaDespacho, Puerta).
# Los pasillos no tienen clase de celda: cada pasillo es directamente un NodoGrafo.
class TipoCelda(Enum):
    # Tipos de celda que son OBSTÁCULOS (no son nodos del grafo)
    RACK = "RACK"
    ZONA_DESPACHO = "ZONA_DESPACHO"
    PUERTA = "PUERTA"

class Sentido(Enum):
    N = "N"         # Solo +y (y lateral en x)
    S = "S"         # Solo -y (y lateral en x)
    E = "E"         # Solo +x (y lateral en y)
    O = "O"         # Solo -x (y lateral en y)
    AMBOS = "AMBOS" # Libre en las 4 direcciones
    NINGUNO = "NINGUNO"

class Producto:
    def __init__(self, prod_id: str, nombre: str, rack_id: str, x: int, y: int, z: int, cantidad: int, peso_kg: float):
        self.id = prod_id
        self.nombre = nombre
        self.rack_id = rack_id
        self.x = x
        self.y = y
        self.z = z
        self.cantidad_disponible = cantidad
        self.peso_kg = peso_kg

class Celda:
    def __init__(self, x: int, y: int, tipo: TipoCelda, elemento_id: Optional[str] = None):
        self.x = x
        self.y = y
        self.tipo = tipo
        self.elemento_id = elemento_id

class CeldaRack(Celda):
    def __init__(self, x: int, y: int, rack_id: str):
        super().__init__(x, y, TipoCelda.RACK, rack_id)
        # Diccionario que actúa como pila en el eje Z: {nivel_z: Producto}
        self.productos_en_z: Dict[int, Producto] = {}

    def apilar_producto(self, z: int, producto: Producto):
        self.productos_en_z[z] = producto

class ElementoRectangular:
    def __init__(self, elem_id: str, x: int, y: int, ancho: int, alto: int):
        self.id = elem_id
        self.x = x
        self.y = y
        self.ancho = ancho
        self.alto = alto

class Rack(ElementoRectangular):
    def __init__(self, elem_id: str, x: int, y: int, ancho: int, alto: int):
        super().__init__(elem_id, x, y, ancho, alto)

class ZonaDespacho(ElementoRectangular):
    def __init__(self, elem_id: str, puerta_id: str, x: int, y: int, ancho: int, alto: int, peso_max_kg: float):
        super().__init__(elem_id, x, y, ancho, alto)
        self.puerta_id = puerta_id
        self.peso_max_kg = peso_max_kg

class Puerta:
    def __init__(self, puerta_id: str, tipo: str, x: int, y: int):
        self.id = puerta_id
        self.tipo = tipo
        self.x = x
        self.y = y