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
        if isinstance(tabla_o_catalogo, dict):
            return tabla_o_catalogo.get(producto_id)
        return None

    def obtener_cantidad_productos(self) -> int:
        if self._cache_unidades is None:
            self._cache_unidades = sum(item.cantidad for item in self.items)
        return self._cache_unidades

    def obtener_peso_total(self, tabla_o_catalogo: Any = None) -> float:
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
    id_wave_actual: Optional[str] = None
    ruta_asignada: List[Tuple[int, int]] = field(default_factory=list)
    productos_recogidos: Dict[str, int] = field(default_factory=dict)

    def puede_cargar(self, peso_adicional: float) -> bool:
        return (self.peso_actual_kg + peso_adicional) <= self.capacidad_carga_kg


@dataclass
class Wave:
    """
    Representa una Ola de Recolección (Wave) que puede ser ejecutada por uno o
    varios Pickers simultáneamente, y coexistir en paralelo con otras Waves activas.
    """

    id_wave: str
    estado: EstadoWave = EstadoWave.PENDIENTE
    wave_max_pedidos: int = 5
    wave_max_productos: int = 15

    # Soporte para 1 o Múltiples Pickers en la misma Wave
    id_picker_asignado: Optional[str] = None
    ids_pickers_asignados: List[str] = field(default_factory=list)
    capacidad_peso_wave_kg: float = float("inf")
    # Reparto interno de qué pedidos/ubicaciones lleva cada picker de la Wave:
    # {id_picker: [id_pedido_1, id_pedido_2, ...]}
    pedidos_por_picker: Dict[str, List[str]] = field(default_factory=dict)
    destinos_xy_por_picker: Dict[str, List[Tuple[int, int]]] = field(
        default_factory=dict
    )

    id_zona_despacho: Optional[str] = None
    tanda_ejecucion_simultanea: int = 1

    peso_total_kg: float = 0.0
    unidades_totales: int = 0
    costo_mst_total: float = 0.0

    pedidos: List[Pedido] = field(default_factory=list)
    ids_pedidos: Set[str] = field(default_factory=set)

    ubicaciones_xy: Set[Tuple[int, int]] = field(default_factory=set)
    ubicaciones_xyz: Set[Tuple[int, int, int]] = field(default_factory=set)

    def asignar_equipo_pickers(
        self, pickers_equipo: List[Picker], tabla_o_catalogo: Any = None
    ) -> None:
        """
        Asigna uno o varios Pickers a esta Wave, actualiza la capacidad de peso
        conjunta y reparte los pedidos/destinos de la Wave entre ellos sin superar
        la capacidad individual de cada Picker.
        """
        self.ids_pickers_asignados = [p.id_picker for p in pickers_equipo]
        self.id_picker_asignado = (
            self.ids_pickers_asignados[0] if self.ids_pickers_asignados else None
        )
        self.capacidad_peso_wave_kg = round(
            sum(p.capacidad_carga_kg for p in pickers_equipo), 4
        )

        self.pedidos_por_picker = {p.id_picker: [] for p in pickers_equipo}
        self.destinos_xy_por_picker = {p.id_picker: [] for p in pickers_equipo}
        carga_temporal = {p.id_picker: 0.0 for p in pickers_equipo}
        cap_individual = {p.id_picker: p.capacidad_carga_kg for p in pickers_equipo}

        if not pickers_equipo or not self.pedidos:
            return

        # Reparto Greedy Best-Fit de los pedidos de la Wave entre los pickers del equipo
        for ped in self.pedidos:
            peso_ped = (
                ped.obtener_peso_total(tabla_o_catalogo)
                if tabla_o_catalogo is not None
                else 0.0
            )
            # Elegir el picker del equipo con mayor capacidad libre que soporte el pedido
            pickers_validos = [
                pid
                for pid in self.ids_pickers_asignados
                if (carga_temporal[pid] + peso_ped) <= cap_individual[pid]
            ]
            if pickers_validos:
                mejor_pid = min(pickers_validos, key=lambda pid: carga_temporal[pid])
            else:
                mejor_pid = min(
                    self.ids_pickers_asignados, key=lambda pid: carga_temporal[pid]
                )

            self.pedidos_por_picker[mejor_pid].append(ped.id_pedido)
            carga_temporal[mejor_pid] = round(carga_temporal[mejor_pid] + peso_ped, 4)

            if tabla_o_catalogo is not None:
                for x, y, _ in ped.obtener_ubicaciones_xyz(tabla_o_catalogo):
                    if (x, y) not in self.destinos_xy_por_picker[mejor_pid]:
                        self.destinos_xy_por_picker[mejor_pid].append((x, y))

    def puede_agregar_pedido(
        self,
        pedido: Pedido,
        max_peso_wave: Optional[float] = None,
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

        limite_peso = (
            max_peso_wave if max_peso_wave is not None else self.capacidad_peso_wave_kg
        )

        if tabla_o_catalogo is not None and (
            limite_peso < float("inf") or peso_disponible_zona is not None
        ):
            peso_pedido = pedido.obtener_peso_total(tabla_o_catalogo)
            if (self.peso_total_kg + peso_pedido) > limite_peso:
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
        max_peso_wave: Optional[float] = None,
    ) -> bool:
        """
        Incorpora el pedido a la Wave, cambia su estado a EN_WAVE (SIN descontar stock)
        y registra sus ubicaciones (x, y) y (x, y, z).
        """
        fuente_datos = tabla_o_catalogo if tabla_o_catalogo is not None else catalogo
        if not self.puede_agregar_pedido(
            pedido, max_peso_wave=max_peso_wave, tabla_o_catalogo=fuente_datos
        ):
            return False

        self.pedidos.append(pedido)
        self.ids_pedidos.add(pedido.id_pedido)
        self.unidades_totales += pedido.obtener_cantidad_productos()

        pedido.estado = EstadoPedido.EN_WAVE
        pedido.waves_asignadas.add(self.id_wave)

        if catalogo is not None and hasattr(catalogo, "actualizar_estado_pedido_O1"):
            catalogo.actualizar_estado_pedido_O1(pedido.id_pedido, EstadoPedido.EN_WAVE)

        if fuente_datos is not None:
            self.peso_total_kg = round(
                self.peso_total_kg + pedido.obtener_peso_total(fuente_datos), 4
            )
            for x, y, z in pedido.obtener_ubicaciones_xyz(fuente_datos):
                self.ubicaciones_xy.add((x, y))
                self.ubicaciones_xyz.add((x, y, z))

        return True


Product = Producto
Order = Pedido
