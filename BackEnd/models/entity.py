from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


class EstadoPedido(Enum):
    PENDIENTE = "PENDIENTE"
    EN_WAVE = "EN_WAVE"
    EN_PREPARACION = "EN_PREPARACION"
    PREPARADO = "PREPARADO"


class EstadoWave(Enum):
    PENDIENTE = "PENDIENTE"
    EN_EJECUCION = "EN_EJECUCION"
    FINALIZADA = "FINALIZADA"
    CANCELADA = "CANCELADA"


class EstadoSimulacion(Enum):
    DETENIDO = "DETENIDO"
    EJECUTANDO = "EJECUTANDO"
    PAUSADO = "PAUSADO"
    FINALIZADO = "FINALIZADO"


class TipoNodo(Enum):
    CALLE = "CALLE"
    RACK = "RACK"
    PUERTA = "PUERTA"
    DESPACHO = "DESPACHO"
    PARED = "PARED"
    OFICINA = "OFICINA"


class EstrategiaRuteo(Enum):
    ORDEN_PEDIDO = "ORDEN_PEDIDO"
    GREEDY_CERCANIA = "GREEDY_CERCANIA"
    DIJKSTRA_OPTIMO = "DIJKSTRA_OPTIMO"


@dataclass
class WarehouseNode:
    id_nodo: str
    tipo: TipoNodo

    @property
    def coordenadas(self) -> Tuple[int, int, int]:
        try:
            partes = self.id_nodo.replace("_", "-", ",", ";").split("-")
            return int(partes[0]), int(partes[1]), int(partes[2])
        except (IndexError, ValueError):
            # Retorno por defecto si el ID no tiene formato de coordenadas
            return 0, 0, 0


@dataclass
class Producto:
    id_producto: str
    nombre: str
    peso: float


@dataclass
class StockUbicacion:
    id_stock: str
    id_producto: str
    id_nodo: str
    cantidad_disponible: int


@dataclass
class DetallePedido:
    id_detalle: str
    id_pedido: str
    id_producto: str
    cantidad_solicitada: int
    producto: Optional[Producto] = None


@dataclass
class Pedido:
    id_pedido: str
    fecha: str
    prioridad: int
    estado: EstadoPedido
    detalles: List[DetallePedido] = field(default_factory=list)

    def obtener_peso_total(self) -> float:
        peso_total = 0.0
        for detalle in self.detalles:
            if detalle.producto:
                peso_total += detalle.producto.peso * detalle.cantidad_solicitada
        return peso_total


@dataclass
class Picker:
    id_picker: str
    id_nodo_actual: str
    capacidad_max_peso: float
    peso_actual: float = 0.0

    def puede_cargar(self, peso_adicional: float) -> bool:
        return (self.peso_actual + peso_adicional) <= self.capacidad_max_peso


@dataclass
class PickerProducto:
    id_picker_producto: str
    id_picker: str
    id_producto: str
    cantidad_cargada: int


@dataclass
class Wave:
    id_wave: str
    estado: EstadoWave
    capacidad_max_pedidos: int
    capacidad_max_productos: int
    capacidad_max_peso: float
    id_picker: Optional[str] = None
    pedidos: List[Pedido] = field(default_factory=list)

    def agregar_pedido(self, pedido: Pedido) -> bool:
        if len(self.pedidos) >= self.capacidad_max_pedidos:
            return False

        peso_actual_wave = sum(p.obtener_peso_total() for p in self.pedidos)
        peso_nuevo_pedido = pedido.obtener_peso_total()

        if (peso_actual_wave + peso_nuevo_pedido) > self.capacidad_max_peso:
            return False

        productos_actuales_wave = sum(
            sum(d.cantidad_solicitada for d in p.detalles) for p in self.pedidos
        )
        productos_nuevo_pedido = sum(d.cantidad_solicitada for d in pedido.detalles)

        if (
            productos_actuales_wave + productos_nuevo_pedido
        ) > self.capacidad_max_productos:
            return False

        self.pedidos.append(pedido)
        return True


@dataclass
class Simulacion:
    id_simulacion: int
    estado: EstadoSimulacion
    estrategia_activa: EstrategiaRuteo
    velocidad: float = 1.0


@dataclass
class MetricaSimulacion:
    id_metrica: int
    id_wave: str
    estrategia: str
    distancia_total: float
    nodos_visitados: int
    tiempo_ejecucion_ms: float
