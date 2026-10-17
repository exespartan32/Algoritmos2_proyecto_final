from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Dict, Any, Optional, TYPE_CHECKING
from BackEnd.enums.enums import (
    TipoCelda, SentidoCirculacion, TipoPuerta, EstadoPedido, EstadoWave
)

if TYPE_CHECKING:
    from BackEnd.models.catalog_manager import CatalogManager


# ==========================================
# 1. ESTRUCTURAS FÍSICAS DEL WAREHOUSE (Tus clases)
# ==========================================

class Celda:
    def __init__(self, x: int, y: int, tipo: TipoCelda, elemento_id: Optional[str] = None):
        self.x = x
        self.y = y
        self.tipo = tipo
        self.elemento_id = elemento_id

class CeldaPasillo(Celda):
    def __init__(self, x: int, y: int, sentido: SentidoCirculacion = SentidoCirculacion.AMBOS, pasillo_id: Optional[str] = None):
        super().__init__(x, y, TipoCelda.PASILLO, pasillo_id)
        self.sentido = sentido

class CeldaRack(Celda):
    def __init__(self, x: int, y: int, rack_id: str):
        super().__init__(x, y, TipoCelda.RACK, rack_id)
        # Diccionario que actúa como pila en el eje Z: {nivel_z: Product}
        self.productos_en_z: Dict[int, 'Product'] = {}

    def apilar_producto(self, z: int, producto: 'Product'):
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
        self.peso_actual_kg = 0.0

    def registrar_carga(self, peso: float):
        self.peso_actual_kg += peso

class Puerta:
    def __init__(self, puerta_id: str, tipo: TipoPuerta, x: int, y: int):
        self.id = puerta_id
        self.tipo = tipo
        self.x = x
        self.y = y


# ==========================================
# 2. MODELOS DE NEGOCIO Y WAVES (De tu compañero)
# ==========================================

@dataclass
class Product:
    id_producto: str
    nombre: str
    rack_id: str
    ubicacion_x: int
    ubicacion_y: int
    altura_z: int
    cantidad_disponible: int
    peso_kg: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id_producto,
            "nombre": self.nombre,
            "rack_id": self.rack_id,
            "ubicacion": {
                "x": self.ubicacion_x,
                "y": self.ubicacion_y,
                "z": self.altura_z,
            },
            "cantidad_disponible": self.cantidad_disponible,
            "peso_kg": self.peso_kg,
        }


@dataclass
class DetallePedido:
    producto_id: str
    cantidad: int

    def to_dict(self) -> Dict[str, Any]:
        return {"producto_id": self.producto_id, "cantidad": self.cantidad}


@dataclass
class Order:
    id_pedido: str
    prioridad: int
    estado: EstadoPedido
    items: List[DetallePedido] = field(default_factory=list)
    _peso_cache: Optional[float] = field(default=None, init=False, repr=False)
    _unidades_cache: Optional[int] = field(default=None, init=False, repr=False)
    _coordenadas_cache: Optional[List[Tuple[int, int]]] = field(
        default=None, init=False, repr=False
    )

    def obtener_cantidad_unidades(self) -> int:
        if self._unidades_cache is None:
            self._unidades_cache = sum(item.cantidad for item in self.items)
        return self._unidades_cache

    def obtener_peso_total(self, catalogo: "CatalogManager") -> float:
        if self._peso_cache is None:
            peso_total = 0.0
            for item in self.items:
                prod = catalogo.buscar_producto_O1(item.producto_id)
                if prod is not None:
                    peso_total += prod.peso_kg * item.cantidad
            self._peso_cache = round(peso_total, 4)
        return self._peso_cache

    def obtener_coordenadas_unicas(
        self, catalogo: "CatalogManager"
    ) -> List[Tuple[int, int]]:
        if self._coordenadas_cache is None:
            coords: List[Tuple[int, int]] = []
            vistos = set()
            for item in self.items:
                prod = catalogo.buscar_producto_O1(item.producto_id)
                if prod is not None:
                    pt = (prod.ubicacion_x, prod.ubicacion_y)
                    if pt not in vistos:
                        vistos.add(pt)
                        coords.append(pt)
            self._coordenadas_cache = coords
        return self._coordenadas_cache

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id_pedido,
            "prioridad": self.prioridad,
            "estado": self.estado.value,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class Picker:
    id_picker: str
    posicion_inicial: Tuple[int, int]
    posicion_actual: Tuple[int, int]
    capacidad_carga_kg: float
    peso_actual_kg: float = 0.0
    ruta_asignada: List[Tuple[int, int]] = field(default_factory=list)
    productos_recogidos: Dict[str, int] = field(default_factory=dict)

    def puede_cargar(self, peso: float) -> bool:
        return (self.peso_actual_kg + peso) <= self.capacidad_carga_kg

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id_picker,
            "posicion_inicial": {
                "x": self.posicion_actual[0],
                "y": self.posicion_actual[1],
            },
            "capacidad_carga_kg": self.capacidad_carga_kg,
        }


@dataclass
class Wave:
    id_wave: str
    estado: EstadoWave
    id_picker_asignado: str
    id_zona_despacho: str
    wave_max_pedidos: float
    wave_max_productos: float
    peso_total_kg: float = 0.0
    unidades_totales: int = 0
    pedidos: List[Order] = field(default_factory=list)
    recorrido_calculado: List[Tuple[int, int]] = field(default_factory=list)

    def puede_agregar_pedido(
        self,
        pedido: Order,
        max_peso_picker: float,
        catalogo: "CatalogManager",
        peso_disponible_zona: Optional[float] = None,
    ) -> bool:
        if len(self.pedidos) >= self.wave_max_pedidos:
            return False

        if (
            self.unidades_totales + pedido.obtener_cantidad_unidades()
        ) > self.wave_max_productos:
            return False

        peso_pedido = pedido.obtener_peso_total(catalogo)
        if (self.peso_total_kg + peso_pedido) > max_peso_picker:
            return False

        if peso_disponible_zona is not None and peso_pedido > peso_disponible_zona:
            return False

        return True

    def agregar_pedido(
        self,
        pedido: Order,
        max_peso_picker: float,
        catalogo: "CatalogManager",
        zona_despacho: Any = None,
    ) -> bool:
        peso_disp_zona = None
        if zona_despacho is not None and hasattr(zona_despacho, "peso_max_kg"):
            peso_disp_zona = zona_despacho.peso_max_kg - getattr(
                zona_despacho, "peso_actual_kg", 0.0
            )

        if not self.puede_agregar_pedido(
            pedido, max_peso_picker, catalogo, peso_disp_zona
        ):
            return False

        peso_pedido = pedido.obtener_peso_total(catalogo)
        self.pedidos.append(pedido)
        self.unidades_totales += pedido.obtener_cantidad_unidades()
        self.peso_total_kg = round(self.peso_total_kg + peso_pedido, 4)

        if zona_despacho is not None and hasattr(zona_despacho, "registrar_carga"):
            zona_despacho.registrar_carga(peso_pedido)

        catalogo.actualizar_estado_pedido_O1(pedido.id_pedido, EstadoPedido.EN_WAVE)
        return True