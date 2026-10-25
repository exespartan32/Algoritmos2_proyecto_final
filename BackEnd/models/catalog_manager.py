import os
import json
import random
from typing import Dict, List, Optional, Tuple, Any, Set
from BackEnd.models.entities import Producto, Pedido, DetallePedido, Picker
from BackEnd.enums.enums import EstadoPedido
from BackEnd.controllers.path_finding import Pathfinding

CoordXY = Tuple[int, int]


class NodoHash:
    __slots__ = ("clave", "valor", "siguiente")

    def __init__(
        self, clave: str, valor: Any, siguiente: Optional["NodoHash"] = None
    ) -> None:
        self.clave = clave
        self.valor = valor
        self.siguiente = siguiente


class HashTableUniversal:
    """
    Tabla Hash con Encadenamiento (Chaining) y familia de Hashing Universal
    h_{a,b}(k) = ((a * k + b) mod p) mod m para acceso y actualización en O(1) promedio.
    """

    def __init__(
        self,
        tamano_m: int = 1009,
        primo_p: int = 999983,
        semilla: Optional[int] = 42,
    ) -> None:
        self.m = max(7, int(tamano_m))
        self.p = max(self.m + 1, int(primo_p))
        generador = random.Random(semilla)
        self.a = generador.randint(1, self.p - 1)
        self.b = generador.randint(0, self.p - 1)
        self.tabla: List[Optional[NodoHash]] = [None] * self.m
        self.cantidad_elementos: int = 0

    def _convertir_clave_a_entero(self, clave: str) -> int:
        acumulado = 0
        for caracter in str(clave):
            acumulado = (acumulado * 131 + ord(caracter)) % self.p
        return acumulado

    def _hash(self, clave: str) -> int:
        k = self._convertir_clave_a_entero(clave)
        return ((self.a * k + self.b) % self.p) % self.m

    def insertar(self, clave: str, valor: Any) -> None:
        indice = self._hash(clave)
        actual = self.tabla[indice]
        while actual is not None:
            if actual.clave == clave:
                actual.valor = valor
                return
            actual = actual.siguiente

        nuevo_nodo = NodoHash(clave, valor, self.tabla[indice])
        self.tabla[indice] = nuevo_nodo
        self.cantidad_elementos += 1

    def buscar(self, clave: str) -> Optional[Any]:
        indice = self._hash(clave)
        actual = self.tabla[indice]
        while actual is not None:
            if actual.clave == clave:
                return actual.valor
            actual = actual.siguiente
        return None

    def obtener_todos_los_valores(self) -> List[Any]:
        valores: List[Any] = []
        for cabeza in self.tabla:
            actual = cabeza
            while actual is not None:
                valores.append(actual.valor)
                actual = actual.siguiente
        return valores


class DigrafoEscenarioJSON:
    """
    Representación del Dígrafo del Warehouse construida directamente desde el bloque
    'warehouse' de escenario_basico.json y escenario_grande.json.
    Respeta el formato:
      - dimensiones: {"ancho_x": ..., "largo_y": ...}
      - ubicacion: {"x": ..., "y": ...} en racks, pasillos, puertas y zonas_despacho.
    Expone 'obtener_vecinos_validos(nodo_actual, paso_tiempo=0)' para el Pathfinding de Leonel.
    """

    def __init__(
        self, datos_warehouse: Dict[str, Any], norte_aumenta_y: bool = True
    ) -> None:
        dim = datos_warehouse.get("dimensiones", {})
        self.ancho_x: int = int(dim.get("ancho_x", dim.get("ancho", 0)))
        self.largo_y: int = int(dim.get("largo_y", dim.get("largo", 0)))
        self.norte_aumenta_y: bool = norte_aumenta_y

        self.racks_ocupados: Set[CoordXY] = set()
        self.sentido_celda: Dict[CoordXY, str] = {}
        self.lista_adyacencia: Dict[CoordXY, List[CoordXY]] = {}
        self.zonas_despacho: Dict[str, Dict[str, Any]] = {}
        self.puertas: Dict[str, Dict[str, Any]] = {}

        self._construir_digrafo(datos_warehouse)

    @staticmethod
    def _extraer_xy(elemento: Dict[str, Any]) -> CoordXY:
        if "ubicacion" in elemento and isinstance(elemento["ubicacion"], dict):
            return int(elemento["ubicacion"]["x"]), int(elemento["ubicacion"]["y"])
        return int(elemento.get("x", 0)), int(elemento.get("y", 0))

    def _construir_digrafo(self, wh: Dict[str, Any]) -> None:
        # 1. Celdas ocupadas por Racks (obstáculos físicos donde están los productos)
        for rack in wh.get("racks", []):
            rx, ry = self._extraer_xy(rack)
            ancho_r = int(rack.get("ancho", 1))
            alto_r = int(rack.get("alto", 1))
            for dx in range(ancho_r):
                for dy in range(alto_r):
                    self.racks_ocupados.add((rx + dx, ry + dy))

        # 2. Celdas de Pasillos y sus sentidos ('N', 'S', 'E', 'O', 'AMBOS')
        for pas in wh.get("pasillos", []):
            px, py = self._extraer_xy(pas)
            ancho_p = int(pas.get("ancho", 1))
            alto_p = int(pas.get("alto", 1))
            sentido = str(pas.get("sentido", "AMBOS")).upper()

            for dx in range(ancho_p):
                for dy in range(alto_p):
                    coord = (px + dx, py + dy)
                    if coord in self.racks_ocupados:
                        continue
                    # En intersecciones con pasillos horizontales AMBOS, prevalece AMBOS
                    if self.sentido_celda.get(coord) == "AMBOS":
                        continue
                    self.sentido_celda[coord] = sentido

        # 3. Zonas de Despacho y Puertas (transitables con sentido AMBOS)
        for zd in wh.get("zonas_despacho", []):
            zx, zy = self._extraer_xy(zd)
            ancho_z = int(zd.get("ancho", 1))
            alto_z = int(zd.get("alto", 1))
            self.zonas_despacho[str(zd["id"])] = zd
            for dx in range(ancho_z):
                for dy in range(alto_z):
                    coord = (zx + dx, zy + dy)
                    if coord not in self.racks_ocupados:
                        self.sentido_celda[coord] = "AMBOS"

        for pta in wh.get("puertas", []):
            px, py = self._extraer_xy(pta)
            self.puertas[str(pta["id"])] = pta
            if (px, py) not in self.racks_ocupados:
                self.sentido_celda[(px, py)] = "AMBOS"

        # 4. Generar aristas dirigidas según reglas de circulación del Warehouse
        pasos_ortogonales = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        for origen, sentido_orig in self.sentido_celda.items():
            vecinos: List[CoordXY] = []
            for dx, dy in pasos_ortogonales:
                destino = (origen[0] + dx, origen[1] + dy)
                if destino not in self.sentido_celda:
                    continue
                sentido_dest = self.sentido_celda[destino]
                if Pathfinding.es_movimiento_permitido_digrafo(
                    origen=origen,
                    destino=destino,
                    sentido_origen=sentido_orig,
                    sentido_destino=sentido_dest,
                    norte_aumenta_y=self.norte_aumenta_y,
                ):
                    vecinos.append(destino)
            self.lista_adyacencia[origen] = vecinos

    def obtener_vecinos_validos(
        self, nodo_actual: CoordXY, paso_tiempo: int = 0
    ) -> List[CoordXY]:
        return self.lista_adyacencia.get(nodo_actual, [])


class CatalogManager:
    """
    Administrador central de las Tablas Hash O(1) de Productos y Pedidos.
    Carga los escenarios base dados (escenario_basico.json y escenario_grande.json)
    y decodifica las Tablas Hash de vuelta a JSON sin alterar los archivos originales.
    """

    def __init__(
        self,
        tamano_tabla: int = 1009,
        primo_p: int = 999983,
        semilla_hash: Optional[int] = 42,
        directorio_datos: Optional[str] = None,
    ) -> None:
        if directorio_datos is None:
            dir_actual = os.path.dirname(os.path.abspath(__file__))
            self.ruta_data = os.path.join(os.path.dirname(dir_actual), "data")
        else:
            self.ruta_data = directorio_datos
        os.makedirs(self.ruta_data, exist_ok=True)

        self.tamano_tabla = tamano_tabla
        self.primo_p = primo_p
        self.semilla_hash = semilla_hash

        self.productos_hash = HashTableUniversal(
            tamano_m=tamano_tabla, primo_p=primo_p, semilla=semilla_hash
        )
        self.pedidos_hash = HashTableUniversal(
            tamano_m=tamano_tabla, primo_p=primo_p, semilla=semilla_hash
        )

        self.warehouse_raw: Dict[str, Any] = {}
        self.configuracion_raw: Dict[str, Any] = {}
        self.digrafo: Optional[DigrafoEscenarioJSON] = None
        self.pickers: List[Picker] = []
        self.wave_max_pedidos: int = 3
        self.wave_max_productos: int = 15

    def resolver_ruta_archivo(self, nombre_o_ruta: str) -> str:
        if os.path.isfile(nombre_o_ruta):
            return os.path.abspath(nombre_o_ruta)
        candidato_en_data = os.path.join(self.ruta_data, nombre_o_ruta)
        if os.path.isfile(candidato_en_data):
            return os.path.abspath(candidato_en_data)
        return os.path.abspath(candidato_en_data)

    def cargar_escenario_json(
        self, nombre_o_ruta_archivo: str, norte_aumenta_y: bool = True
    ) -> str:
        ruta_completa = self.resolver_ruta_archivo(nombre_o_ruta_archivo)
        with open(ruta_completa, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)

        # Reiniciar Tablas Hash
        self.productos_hash = HashTableUniversal(
            tamano_m=self.tamano_tabla, primo_p=self.primo_p, semilla=self.semilla_hash
        )
        self.pedidos_hash = HashTableUniversal(
            tamano_m=self.tamano_tabla, primo_p=self.primo_p, semilla=self.semilla_hash
        )

        # 1. Bloque warehouse y construcción del Dígrafo de pasillos
        self.warehouse_raw = datos.get("warehouse", {})
        self.digrafo = DigrafoEscenarioJSON(
            self.warehouse_raw, norte_aumenta_y=norte_aumenta_y
        )

        # 2. Bloque configuracion (wave_max_pedidos y wave_max_productos)
        self.configuracion_raw = datos.get("configuracion", {})
        self.wave_max_pedidos = int(self.configuracion_raw.get("wave_max_pedidos", 3))
        self.wave_max_productos = int(
            self.configuracion_raw.get("wave_max_productos", 15)
        )

        # 3. Bloque pickers
        self.pickers = []
        for pk in datos.get("pickers", []):
            pos_ini = pk.get("posicion_inicial", {"x": 0, "y": 0})
            coord = (int(pos_ini["x"]), int(pos_ini["y"]))
            self.pickers.append(
                Picker(
                    id_picker=str(pk["id"]),
                    capacidad_carga_kg=float(pk.get("capacidad_carga_kg", 100.0)),
                    posicion_actual=coord,
                )
            )

        # 4. Bloque productos -> Tabla Hash en O(1)
        for p_raw in datos.get("productos", []):
            ubic = p_raw.get("ubicacion", {})
            prod = Producto(
                id_producto=str(p_raw["id"]),
                nombre=str(p_raw.get("nombre", p_raw["id"])),
                rack_id=str(p_raw.get("rack_id", "")),
                ubicacion_x=int(ubic.get("x", 0)),
                ubicacion_y=int(ubic.get("y", 0)),
                ubicacion_z=int(ubic.get("z", 1)),
                cantidad_disponible=int(p_raw.get("cantidad_disponible", 0)),
                peso_kg=float(p_raw.get("peso_kg", 0.0)),
            )
            self.productos_hash.insertar(prod.id_producto, prod)

        # 5. Bloque pedidos -> Tabla Hash en O(1)
        for ped_raw in datos.get("pedidos", []):
            estado_str = str(ped_raw.get("estado", "PENDIENTE")).upper()
            estado_enum = (
                EstadoPedido[estado_str]
                if estado_str in EstadoPedido.__members__
                else EstadoPedido.PENDIENTE
            )
            items = [
                DetallePedido(
                    producto_id=str(it["producto_id"]),
                    cantidad=int(it["cantidad"]),
                )
                for it in ped_raw.get("items", [])
            ]
            pedido = Pedido(
                id_pedido=str(ped_raw["id"]),
                prioridad=int(ped_raw.get("prioridad", 1)),
                items=items,
                estado=estado_enum,
            )
            self.pedidos_hash.insertar(pedido.id_pedido, pedido)

        return ruta_completa

    # =========================================================================
    # OPERACIONES O(1) SOBRE LAS TABLAS HASH
    # =========================================================================
    def buscar_producto_O1(self, id_producto: str) -> Optional[Producto]:
        return self.productos_hash.buscar(id_producto)

    def buscar_pedido_O1(self, id_pedido: str) -> Optional[Pedido]:
        return self.pedidos_hash.buscar(id_pedido)

    def obtener_todos_los_productos(self) -> List[Producto]:
        productos = self.productos_hash.obtener_todos_los_valores()
        productos.sort(key=lambda p: p.id_producto)
        return productos

    def obtener_todos_los_pedidos(self) -> List[Pedido]:
        pedidos = self.pedidos_hash.obtener_todos_los_valores()
        pedidos.sort(key=lambda p: p.id_pedido)
        return pedidos

    def actualizar_estado_pedido_O1(
        self, id_pedido: str, nuevo_estado: EstadoPedido
    ) -> bool:
        pedido = self.buscar_pedido_O1(id_pedido)
        if pedido is None:
            return False
        pedido.estado = nuevo_estado
        return True

    def descontar_stock(self, id_producto: str, cantidad: int) -> bool:
        """
        Método exclusivo para la etapa de recolección física del Picker.
        NO se invoca durante el armado de las Waves.
        """
        prod = self.buscar_producto_O1(id_producto)
        if prod is None or cantidad < 0 or prod.cantidad_disponible < cantidad:
            return False
        prod.cantidad_disponible -= cantidad
        return True

    # =========================================================================
    # DECODIFICACIÓN DE TABLAS HASH A JSON (PERSISTENCIA DE ESTADO)
    # =========================================================================
    def guardar_estado_simulacion_json(
        self, nombre_archivo_salida: str = "estado_guardado.json"
    ) -> str:
        ruta_salida = (
            nombre_archivo_salida
            if os.path.isabs(nombre_archivo_salida)
            else os.path.join(self.ruta_data, nombre_archivo_salida)
        )

        productos_json = [
            {
                "id": p.id_producto,
                "nombre": p.nombre,
                "rack_id": p.rack_id,
                "ubicacion": {
                    "x": p.ubicacion_x,
                    "y": p.ubicacion_y,
                    "z": p.ubicacion_z,
                },
                "cantidad_disponible": p.cantidad_disponible,
                "peso_kg": p.peso_kg,
            }
            for p in self.obtener_todos_los_productos()
        ]

        pedidos_json = [
            {
                "id": ped.id_pedido,
                "prioridad": ped.prioridad,
                "estado": ped.estado.value,
                "items": [
                    {"producto_id": it.producto_id, "cantidad": it.cantidad}
                    for it in ped.items
                ],
            }
            for ped in self.obtener_todos_los_pedidos()
        ]

        pickers_json = [
            {
                "id": pk.id_picker,
                "posicion_inicial": {
                    "x": pk.posicion_actual[0],
                    "y": pk.posicion_actual[1],
                },
                "capacidad_carga_kg": pk.capacidad_carga_kg,
            }
            for pk in self.pickers
        ]

        estado_exportado = {
            "warehouse": self.warehouse_raw,
            "pickers": pickers_json,
            "productos": productos_json,
            "pedidos": pedidos_json,
            "configuracion": {
                "wave_max_pedidos": self.wave_max_pedidos,
                "wave_max_productos": self.wave_max_productos,
            },
        }

        with open(ruta_salida, "w", encoding="utf-8") as f:
            json.dump(estado_exportado, f, indent=2, ensure_ascii=False)

        return os.path.abspath(ruta_salida)
