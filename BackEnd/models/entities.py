from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional, Set
from BackEnd.enums.enums import (
    TipoCelda,
    SentidoCirculacion,
    TipoPuerta,
    EstadoPedido,
    EstadoWave,
)


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
        self.id_zona = elem_id
        self.puerta_id = puerta_id
        self.peso_max_kg = float(peso_max_kg)
        self.peso_actual_kg = 0.0
        self.peso_comprometido_waves_kg = 0.0

    def puede_recibir_carga(self, peso_adicional: float) -> bool:
        return (
            self.peso_actual_kg + self.peso_comprometido_waves_kg + peso_adicional
        ) <= self.peso_max_kg

    def comprometer_carga_wave(self, peso: float) -> None:
        self.peso_comprometido_waves_kg = round(
            self.peso_comprometido_waves_kg + peso, 4
        )

    def registrar_descarga_fisica(self, peso: float) -> None:
        self.peso_actual_kg = round(self.peso_actual_kg + peso, 4)
        self.peso_comprometido_waves_kg = max(
            0.0, round(self.peso_comprometido_waves_kg - peso, 4)
        )


class Puerta:
    def __init__(self, puerta_id: str, tipo: Any, x: int, y: int) -> None:
        self.id = puerta_id
        self.tipo = (
            tipo if isinstance(tipo, TipoPuerta) else TipoPuerta[str(tipo).upper()]
        )
        self.x = x
        self.y = y

    def permite_despacho_salida(self) -> bool:
        return self.tipo in (TipoPuerta.OUTBOUND, TipoPuerta.AMBOS)


@dataclass
class Producto:
    id_producto: str
    nombre: str
    rack_id: str
    ubicacion_x: int
    ubicacion_y: int
    ubicacion_z: int = 1
    cantidad_disponible: int = 0
    peso_kg: float = 0.0

    def __init__(
        self,
        id_producto: str,
        nombre: str,
        rack_id: str,
        ubicacion_x: int,
        ubicacion_y: int,
        ubicacion_z: Optional[int] = None,
        cantidad_disponible: int = 0,
        peso_kg: float = 0.0,
        altura_z: Optional[int] = None,
    ) -> None:
        self.id_producto = str(id_producto)
        self.nombre = str(nombre)
        self.rack_id = str(rack_id)
        self.ubicacion_x = int(ubicacion_x)
        self.ubicacion_y = int(ubicacion_y)
        z_final = (
            ubicacion_z
            if ubicacion_z is not None
            else (altura_z if altura_z is not None else 1)
        )
        self.ubicacion_z = int(z_final)
        self.cantidad_disponible = int(cantidad_disponible)
        self.peso_kg = float(peso_kg)

    # Propiedades de compatibilidad con el código de Laureano (prod.id, prod.x, prod.y, prod.z)
    @property
    def id(self) -> str:
        return self.id_producto

    @property
    def x(self) -> int:
        return self.ubicacion_x

    @property
    def y(self) -> int:
        return self.ubicacion_y

    @property
    def z(self) -> int:
        return self.ubicacion_z

    @property
    def altura_z(self) -> int:
        return self.ubicacion_z

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
        if hasattr(tabla_o_catalogo, "catalogo_productos") and isinstance(
            tabla_o_catalogo.catalogo_productos, dict
        ):
            return tabla_o_catalogo.catalogo_productos.get(producto_id)
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
class TareaWavePicker:
    """
    Representa la asignación de una Wave (o sub-lote geográfico de una Wave) a un Picker.
    Garantiza que el Picker NUNCA mezcle dos Waves en el mismo viaje: ejecuta esta tarea,
    regresa a la Zona de Despacho, descarga a 0 kg y recién entonces toma la siguiente.
    """

    id_wave: str
    id_zona_despacho: str
    destino_despacho_pasillo: Tuple[int, int]
    pedidos_asignados: List[str]
    destinos_recoleccion_pasillo: List[Tuple[int, int]]
    peso_lote_kg: float
    ruta_calculada: List[Tuple[int, int]] = field(default_factory=list)


@dataclass
class Picker:
    id_picker: str
    capacidad_carga_kg: float
    posicion_actual: Tuple[int, int] = (0, 0)
    peso_actual_kg: float = 0.0
    id_wave_actual: Optional[str] = None
    destino_despacho_actual: Optional[Tuple[int, int]] = None
    ruta_asignada: List[Tuple[int, int]] = field(default_factory=list)
    objetivos_pendientes: List[Tuple[int, int]] = field(default_factory=list)
    cola_waves_asignadas: List[TareaWavePicker] = field(default_factory=list)
    productos_recogidos: Dict[str, int] = field(default_factory=dict)
    turnos_bloqueado: int = 0
    historial_recorrido: List[Tuple[int, int]] = field(default_factory=list)

    def puede_cargar(self, peso_adicional: float) -> bool:
        return (self.peso_actual_kg + peso_adicional) <= self.capacidad_carga_kg

    def iniciar_siguiente_tarea_en_cola(self) -> Optional[TareaWavePicker]:
        """
        Si el Picker está libre (peso 0 y sin Wave activa), extrae la siguiente
        Wave de su cola de trabajo sin mezclar jamás dos Waves en un mismo viaje.
        """
        if self.id_wave_actual is not None or not self.cola_waves_asignadas:
            return None

        tarea = self.cola_waves_asignadas.pop(0)
        self.id_wave_actual = tarea.id_wave
        self.peso_actual_kg = tarea.peso_lote_kg
        self.destino_despacho_actual = tarea.destino_despacho_pasillo
        self.objetivos_pendientes = list(tarea.destinos_recoleccion_pasillo)
        self.ruta_asignada = (
            list(tarea.ruta_calculada[1:])
            if len(tarea.ruta_calculada) > 1
            else list(tarea.ruta_calculada)
        )
        self.turnos_bloqueado = 0
        if not self.historial_recorrido:
            self.historial_recorrido.append(self.posicion_actual)
        return tarea


@dataclass
class Wave:
    id_wave: str
    estado: EstadoWave = EstadoWave.PENDIENTE
    wave_max_pedidos: int = 5
    wave_max_productos: int = 15

    id_picker_asignado: Optional[str] = None
    ids_pickers_asignados: List[str] = field(default_factory=list)
    capacidad_peso_wave_kg: float = float("inf")
    pedidos_por_picker: Dict[str, List[str]] = field(default_factory=dict)
    destinos_xy_por_picker: Dict[str, List[Tuple[int, int]]] = field(
        default_factory=dict
    )
    peso_por_picker: Dict[str, float] = field(default_factory=dict)

    id_zona_despacho: Optional[str] = None
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
        Divide la Wave en sub-lotes geográficos entre los pickers asignados a ella
        cuando el peso de la Wave supera la capacidad de un único picker.
        Ordena los pedidos espacialmente para que cada picker reciba un sector contiguo.
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
        self.peso_por_picker = {p.id_picker: 0.0 for p in pickers_equipo}
        cap_individual = {p.id_picker: p.capacidad_carga_kg for p in pickers_equipo}

        if not pickers_equipo or not self.pedidos:
            return

        # Ordenar pedidos por su centroide X para particionar en sub-lotes geográficos contiguos
        def _centroide_x(ped: Pedido) -> float:
            ubics = (
                ped.obtener_ubicaciones_xyz(tabla_o_catalogo)
                if tabla_o_catalogo
                else set()
            )
            if not ubics:
                return 0.0
            return sum(x for x, _, _ in ubics) / len(ubics)

        pedidos_ordenados_geo = sorted(self.pedidos, key=_centroide_x)

        for ped in pedidos_ordenados_geo:
            peso_ped = (
                ped.obtener_peso_total(tabla_o_catalogo)
                if tabla_o_catalogo is not None
                else 0.0
            )
            pickers_validos = [
                pid
                for pid in self.ids_pickers_asignados
                if (self.peso_por_picker[pid] + peso_ped) <= cap_individual[pid]
            ]
            if pickers_validos:
                mejor_pid = min(
                    pickers_validos, key=lambda pid: self.peso_por_picker[pid]
                )
            else:
                mejor_pid = min(
                    self.ids_pickers_asignados,
                    key=lambda pid: self.peso_por_picker[pid],
                )

            self.pedidos_por_picker[mejor_pid].append(ped.id_pedido)
            self.peso_por_picker[mejor_pid] = round(
                self.peso_por_picker[mejor_pid] + peso_ped, 4
            )

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
