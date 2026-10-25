import os
import json
import random
from typing import Dict, List, Optional, Tuple, Any
from BackEnd.models.entities import Producto, Pedido, DetallePedido, Picker
from BackEnd.enums.enums import EstadoPedido
from BackEnd.utils.file_parser import FileParser

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


class CatalogManager:
    """
    Integra el Warehouse/Digrafo de Laureano (FileParser + GraphBuilder) con las
    Tablas Hash Universales O(1) de Productos y Pedidos.
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
        self.warehouse = None
        self.digrafo = None
        self.pickers: List[Picker] = []
        self.wave_max_pedidos: int = 3
        self.wave_max_productos: int = 15

    def resolver_ruta_archivo(self, nombre_o_ruta: str) -> str:
        if os.path.isfile(nombre_o_ruta):
            return os.path.abspath(nombre_o_ruta)
        candidato_en_data = os.path.join(self.ruta_data, nombre_o_ruta)
        return os.path.abspath(candidato_en_data)

    def cargar_escenario_json(self, nombre_o_ruta_archivo: str) -> str:
        ruta_completa = self.resolver_ruta_archivo(nombre_o_ruta_archivo)
        datos = FileParser.leer_json(ruta_completa)

        self.productos_hash = HashTableUniversal(
            tamano_m=self.tamano_tabla, primo_p=self.primo_p, semilla=self.semilla_hash
        )
        self.pedidos_hash = HashTableUniversal(
            tamano_m=self.tamano_tabla, primo_p=self.primo_p, semilla=self.semilla_hash
        )

        # 1. Construir el Warehouse y el Dígrafo usando el módulo de Laureano
        self.warehouse_raw = datos.get("warehouse", {})
        self.warehouse = FileParser.cargar_warehouse_desde_json(ruta_completa)
        self.digrafo = self.warehouse.grafo_pasillos

        # 2. Configuración de Waves
        self.configuracion_raw = datos.get("configuracion", {})
        self.wave_max_pedidos = int(self.configuracion_raw.get("wave_max_pedidos", 3))
        self.wave_max_productos = int(
            self.configuracion_raw.get("wave_max_productos", 15)
        )

        # 3. Pickers (asegurando que su posición inicial esté en una celda de pasillo válida)
        self.pickers = []
        for pk in datos.get("pickers", []):
            pos_ini = pk.get("posicion_inicial", {"x": 0, "y": 0})
            coord_raw = (int(pos_ini["x"]), int(pos_ini["y"]))
            coord_valida = (
                self.warehouse.obtener_celda_acceso_pasillo(*coord_raw) or coord_raw
            )
            self.pickers.append(
                Picker(
                    id_picker=str(pk["id"]),
                    capacidad_carga_kg=float(pk.get("capacidad_carga_kg", 100.0)),
                    posicion_actual=coord_valida,
                )
            )

        # 4. Poblar Tabla Hash Universal O(1) con los objetos Product ya creados en el Warehouse
        for prod_id, prod_obj in self.warehouse.catalogo_productos.items():
            self.productos_hash.insertar(prod_id, prod_obj)

        # 5. Poblar Tabla Hash Universal O(1) de Pedidos
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
        prod = self.buscar_producto_O1(id_producto)
        if prod is None or cantidad < 0 or prod.cantidad_disponible < cantidad:
            return False
        prod.cantidad_disponible -= cantidad
        return True

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
