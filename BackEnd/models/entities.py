from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional, Set
from BackEnd.enums.enums import (
    TipoCelda,
    SentidoCirculacion,
    TipoPuerta,
    EstadoPedido,
    EstadoWave,
)

# =====================================================================
# MODELOS DE LA ESTRUCTURA DEL GRAFO Y ALMACÉN
# =====================================================================


class Celda:
    def __init__(
        self, x: int, y: int, tipo: TipoCelda, elemento_id: Optional[str] = None
    ) -> None:
        self.x = x
        self.y = y
        self.tipo = tipo
        self.elemento_id = elemento_id


class CeldaPasillo(Celda):
    def __init__(
        self,
        x: int,
        y: int,
        sentido: SentidoCirculacion = SentidoCirculacion.AMBOS,
        pasillo_id: Optional[str] = None,
    ) -> None:
        super().__init__(x, y, TipoCelda.PASILLO, pasillo_id)
        self.sentido = sentido


class CeldaRack(Celda):
    def __init__(self, x: int, y: int, rack_id: str) -> None:
        super().__init__(x, y, TipoCelda.RACK, rack_id)
        # Diccionario en el eje Z: {nivel_z: Producto}
        self.productos_en_z: Dict[int, "Producto"] = {}

    def apilar_producto(self, z: int, producto: "Producto") -> None:
        self.productos_en_z[z] = producto


class ElementoRectangular:
    def __init__(self, elem_id: str, x: int, y: int, ancho: int, alto: int) -> None:
        self.id = elem_id
        self.x = x
        self.y = y
        self.ancho = ancho
        self.alto = alto


class Rack(ElementoRectangular):
    def __init__(
        self, elem_id: str, x: int, y: int, ancho: int, alto: int, niveles: int = 1
    ) -> None:
        super().__init__(elem_id, x, y, ancho, alto)
        self.niveles = niveles


class ZonaDespacho(ElementoRectangular):
    def __init__(
        self,
        elem_id: str,
        puerta_id: str,
        x: int,
        y: int,
        ancho: int,
        alto: int,
        peso_max_kg: float,
    ) -> None:
        super().__init__(elem_id, x, y, ancho, alto)
        self.puerta_id = puerta_id
        self.peso_max_kg = float(peso_max_kg)
        self.peso_actual_kg = 0.0

    def puede_recibir_carga(self, peso_adicional: float) -> bool:
        return (self.peso_actual_kg + peso_adicional) <= self.peso_max_kg

    def registrar_carga(self, peso: float) -> None:
        self.peso_actual_kg = round(self.peso_actual_kg + peso, 4)


class Puerta:
    def __init__(self, puerta_id: str, tipo: TipoPuerta, x: int, y: int) -> None:
        self.id = puerta_id
        self.tipo = tipo
        self.x = x
        self.y = y

    def permite_despacho_salida(self) -> bool:
        return self.tipo in (TipoPuerta.OUTBOUND, TipoPuerta.AMBOS)


# =====================================================================
# ENTIDADES DE INVENTARIO, PEDIDOS, PICKERS Y WAVES
# =====================================================================


@dataclass
class Producto:
    id_producto: str
    nombre: str
    rack_id: str
    ubicacion_x: int
    ubicacion_y: int
    ubicacion_z: int
    cantidad_disponible: int
    peso_kg: float

    @property
    def coordenadas_xy(self) -> Tuple[int, int]:
        return (self.ubicacion_x, self.ubicacion_y)

    @property
    def coordenadas_xyz(self) -> Tuple[int, int, int]:
        return (self.ubicacion_x, self.ubicacion_y, self.ubicacion_z)


@dataclass
class DetallePedido:
    producto_id: str
    cantidad: int


@dataclass
class Pedido:
    id_pedido: str
    prioridad: int
    items: List[DetallePedido] = field(default_factory=list)
    estado: EstadoPedido = EstadoPedido.PENDIENTE
    waves_asignadas: Set[str] = field(default_factory=set)

    # Caché interna para evitar recalcular en cada iteración del WaveManager
    _cache_unidades: Optional[int] = field(default=None, init=False, repr=False)
    _cache_peso: Optional[float] = field(default=None, init=False, repr=False)
    _cache_xyz: Optional[Set[Tuple[int, int, int]]] = field(
        default=None, init=False, repr=False
    )

    @staticmethod
    def _buscar_producto(tabla_o_catalogo: Any, producto_id: str) -> Optional[Producto]:
        if tabla_o_catalogo is None:
            return None
        if hasattr(tabla_o_catalogo, "buscar_producto_O1"):
            return tabla_o_catalogo.buscar_producto_O1(producto_id)
        if hasattr(tabla_o_catalogo, "buscar"):
            return tabla_o_catalogo.buscar(producto_id)
        if hasattr(tabla_o_catalogo, "obtener"):
            return tabla_o_catalogo.obtener(producto_id)
        if isinstance(tabla_o_catalogo, dict):
            return tabla_o_catalogo.get(producto_id)
        return None

    def obtener_cantidad_productos(self) -> int:
        """Retorna el total de unidades solicitadas en el pedido."""
        if self._cache_unidades is None:
            self._cache_unidades = sum(item.cantidad for item in self.items)
        return self._cache_unidades

    def obtener_cantidad_unidades(self) -> int:
        """Alias de compatibilidad."""
        return self.obtener_cantidad_productos()

    def obtener_peso_total(self, tabla_o_catalogo: Any = None) -> float:
        """Calcula el peso total del pedido consultando la Tabla Hash en O(1)."""
        if self._cache_peso is not None:
            return self._cache_peso
        if tabla_o_catalogo is None:
            return 0.0

        peso_acumulado = 0.0
        for item in self.items:
            prod = self._buscar_producto(tabla_o_catalogo, item.producto_id)
            if prod is not None:
                peso_acumulado += prod.peso_kg * item.cantidad

        self._cache_peso = round(peso_acumulado, 4)
        return self._cache_peso

    def obtener_ubicaciones_xyz(
        self, tabla_o_catalogo: Any
    ) -> Set[Tuple[int, int, int]]:
        """
        Devuelve el conjunto de coordenadas únicas (x, y, z) de los productos
        del pedido. Si falta algún producto en el catálogo, retorna set vacío.
        """
        if self._cache_xyz is not None:
            return self._cache_xyz
        if tabla_o_catalogo is None:
            return set()

        ubicaciones: Set[Tuple[int, int, int]] = set()
        for item in self.items:
            prod = self._buscar_producto(tabla_o_catalogo, item.producto_id)
            if prod is None:
                return set()
            ubicaciones.add((prod.ubicacion_x, prod.ubicacion_y, prod.ubicacion_z))

        self._cache_xyz = ubicaciones
        return self._cache_xyz


@dataclass
class Picker:
    id_picker: str
    capacidad_carga_kg: float
    posicion_actual: Tuple[int, int] = (0, 0)
    peso_actual_kg: float = 0.0
    ruta_asignada: List[Tuple[int, int]] = field(default_factory=list)
    productos_recogidos: Dict[str, int] = field(default_factory=dict)


@dataclass
class Wave:
    id_wave: str
    estado: EstadoWave = EstadoWave.PENDIENTE
    wave_max_pedidos: int = 5
    wave_max_productos: int = 15
    id_picker_asignado: Optional[str] = None
    ids_pickers_asignados: List[str] = field(default_factory=list)
    id_zona_despacho: Optional[str] = None

    peso_total_kg: float = 0.0
    unidades_totales: int = 0
    costo_mst_total: float = 0.0

    pedidos: List[Pedido] = field(default_factory=list)
    ids_pedidos: Set[str] = field(default_factory=set)

    # Conjuntos de ubicaciones únicas para cálculo incremental O(1) y altura Z única
    ubicaciones_xy: Set[Tuple[int, int]] = field(default_factory=set)
    ubicaciones_xyz: Set[Tuple[int, int, int]] = field(default_factory=set)
    recorrido_calculado: List[Tuple[int, int]] = field(default_factory=list)

    def puede_agregar_pedido(
        self,
        pedido: Pedido,
        max_peso_picker: Optional[float] = None,
        tabla_o_catalogo: Any = None,
        peso_disponible_zona: Optional[float] = None,
    ) -> bool:
        if pedido.id_pedido in self.ids_pedidos:
            return False

        if len(self.pedidos) >= self.wave_max_pedidos:
            return False

        unidades_pedido = pedido.obtener_cantidad_productos()
        if unidades_pedido <= 0 or (
            self.unidades_totales + unidades_pedido > self.wave_max_productos
        ):
            return False

        if tabla_o_catalogo is not None and (
            max_peso_picker is not None or peso_disponible_zona is not None
        ):
            peso_pedido = pedido.obtener_peso_total(tabla_o_catalogo)
            if (
                max_peso_picker is not None
                and (self.peso_total_kg + peso_pedido) > max_peso_picker
            ):
                return False
            if (
                peso_disponible_zona is not None
                and (self.peso_total_kg + peso_pedido) > peso_disponible_zona
            ):
                return False

        return True

    def agregar_pedido(
        self,
        pedido: Pedido,
        tabla_o_catalogo: Any = None,
        catalogo: Any = None,
    ) -> bool:
        """
        Incorpora el pedido a la Wave, actualiza su estado a EN_WAVE y registra
        sus ubicaciones (x, y) y (x, y, z) para que la altura Z se cobre una sola vez.
        """
        if not self.puede_agregar_pedido(pedido):
            return False

        self.pedidos.append(pedido)
        self.ids_pedidos.add(pedido.id_pedido)
        self.unidades_totales += pedido.obtener_cantidad_productos()

        # Actualizar estado del pedido a EN_WAVE según especificación
        pedido.estado = EstadoPedido.EN_WAVE
        pedido.waves_asignadas.add(self.id_wave)

        if catalogo is not None and hasattr(catalogo, "actualizar_estado_pedido_O1"):
            catalogo.actualizar_estado_pedido_O1(pedido.id_pedido, EstadoPedido.EN_WAVE)

        fuente_datos = tabla_o_catalogo if tabla_o_catalogo is not None else catalogo
        if fuente_datos is not None:
            self.peso_total_kg = round(
                self.peso_total_kg + pedido.obtener_peso_total(fuente_datos), 4
            )
            for x, y, z in pedido.obtener_ubicaciones_xyz(fuente_datos):
                self.ubicaciones_xy.add((x, y))
                self.ubicaciones_xyz.add((x, y, z))

        return True


# Alias de compatibilidad por si otros módulos importan Order o Product en inglés
Product = Producto
Order = Pedido
