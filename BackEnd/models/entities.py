from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, TYPE_CHECKING
from BackEnd.enums.enums import EstadoPedido, EstadoWave

if TYPE_CHECKING:
    from BackEnd.models.catalog_manager import CatalogManager
    from BackEnd.models.warehouse_models import ZonaDespacho


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

    def obtener_peso_total(self, catalogo: "CatalogManager") -> float:
        peso_total = 0.0
        for item in self.items:
            prod = catalogo.buscar_producto_O1(item.producto_id)
            if prod:
                peso_total += prod.peso_kg * item.cantidad
        return round(peso_total, 4)

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
    wave_max_pedidos: int
    wave_max_productos: int
    peso_total_kg: float = 0.0
    pedidos: List[Order] = field(default_factory=list)
    recorrido_calculado: List[Tuple[int, int]] = field(default_factory=list)

    def agregar_pedido(
        self,
        pedido: Order,
        max_peso_picker: float,
        zona_despacho: "ZonaDespacho",
        catalogo: "CatalogManager",
    ) -> bool:
        if len(self.pedidos) >= self.wave_max_pedidos:
            return False

        unidades_actuales = sum(sum(i.cantidad for i in p.items) for p in self.pedidos)
        unidades_nuevas = sum(i.cantidad for i in pedido.items)
        if (unidades_actuales + unidades_nuevas) > self.wave_max_productos:
            return False

        peso_pedido = pedido.obtener_peso_total(catalogo)
        if (self.peso_total_kg + peso_pedido) > max_peso_picker:
            return False

        if not zona_despacho.puede_recibir_carga(peso_pedido):
            return False

        self.pedidos.append(pedido)
        self.peso_total_kg = round(self.peso_total_kg + peso_pedido, 4)
        zona_despacho.registrar_carga(peso_pedido)
        pedido.estado = EstadoPedido.EN_WAVE
        return True
