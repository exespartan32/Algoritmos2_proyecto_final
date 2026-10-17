import os
import json
import random
from typing import List, Optional, Dict, Any
from BackEnd.models.entities import Product, Order, DetallePedido, Picker
from BackEnd.enums.enums import EstadoPedido
from BackEnd.data_structures.linkedlist import LinkedList, add


class HashTableUniversal:
    """
    Tabla Hash propia con Encadenamiento (Chaining) sobre LinkedList
    y función de Hashing Universal h_ab(k) = ((a*k + b) mod p) mod m.
    """

    def __init__(self, tamano_tabla: int, primo_p: int, semilla: Optional[int] = None):
        self.m = tamano_tabla
        self.p = primo_p
        generador = random.Random(semilla) if semilla is not None else random
        self.a = generador.randint(1, self.p - 1)
        self.b = generador.randint(0, self.p - 1)

        self.tabla: List[LinkedList] = [LinkedList() for _ in range(self.m)]
        self.cantidad_elementos = 0

    def _hash_universal(self, key: str) -> int:
        k = 0
        for char in key:
            k = (k << 7) + ord(char)
        return ((self.a * k + self.b) % self.p) % self.m

    def insertar(self, clave: str, valor: Any) -> None:
        posicion = self._hash_universal(clave)
        lista_slot = self.tabla[posicion]

        actual = lista_slot.head
        while actual is not None:
            if actual.value[0] == clave:
                actual.value = (clave, valor)
                return
            actual = actual.nextNode

        add(lista_slot, (clave, valor))
        self.cantidad_elementos += 1

    def buscar(self, clave: str) -> Optional[Any]:
        posicion = self._hash_universal(clave)
        actual = self.tabla[posicion].head
        while actual is not None:
            if actual.value[0] == clave:
                return actual.value[1]
            actual = actual.nextNode
        return None

    def obtener_todos_los_valores(self) -> List[Any]:
        valores = []
        for lista_slot in self.tabla:
            actual = lista_slot.head
            while actual is not None:
                valores.append(actual.value[1])
                actual = actual.nextNode
        return valores

    def limpiar(self) -> None:
        self.tabla = [LinkedList() for _ in range(self.m)]
        self.cantidad_elementos = 0


class CatalogManager:
    def __init__(
        self,
        tamano_tabla: int,
        primo_p: int,
        semilla_hash: Optional[int] = None,
        directorio_datos: Optional[str] = None,
    ):
        if directorio_datos is not None:
            self.ruta_data = os.path.abspath(directorio_datos)
        else:
            directorio_actual = os.path.dirname(os.path.abspath(__file__))
            self.ruta_data = os.path.join(os.path.dirname(directorio_actual), "data")

        os.makedirs(self.ruta_data, exist_ok=True)

        self.productos_hash = HashTableUniversal(tamano_tabla, primo_p, semilla_hash)
        self.pedidos_hash = HashTableUniversal(tamano_tabla, primo_p, semilla_hash)

        self.warehouse_raw: Dict[str, Any] = {}
        self.pickers: List[Picker] = []
        self.wave_max_pedidos: Optional[int] = None
        self.wave_max_productos: Optional[int] = None

    def cargar_escenario_json(self, nombre_o_ruta_archivo: str) -> str:
        if os.path.isabs(nombre_o_ruta_archivo) or os.path.exists(
            nombre_o_ruta_archivo
        ):
            ruta_completa = os.path.abspath(nombre_o_ruta_archivo)
        else:
            ruta_completa = os.path.join(self.ruta_data, nombre_o_ruta_archivo)

        if not os.path.exists(ruta_completa):
            raise FileNotFoundError(
                f"No se encontró el archivo JSON en: {ruta_completa}"
            )

        with open(ruta_completa, "r", encoding="utf-8") as archivo:
            datos_json = json.load(archivo)

        self.warehouse_raw = datos_json.get("warehouse", {})

        self.productos_hash.limpiar()
        for item in datos_json.get("productos", []):
            ubic = item["ubicacion"]
            producto = Product(
                id_producto=str(item["id"]),
                nombre=str(item["nombre"]),
                rack_id=str(item["rack_id"]),
                ubicacion_x=int(ubic["x"]),
                ubicacion_y=int(ubic["y"]),
                altura_z=int(ubic["z"]),
                cantidad_disponible=int(item["cantidad_disponible"]),
                peso_kg=float(item["peso_kg"]),
            )
            self.productos_hash.insertar(producto.id_producto, producto)

        self.pedidos_hash.limpiar()
        for ped in datos_json.get("pedidos", []):
            detalles = [
                DetallePedido(
                    producto_id=str(it["producto_id"]), cantidad=int(it["cantidad"])
                )
                for it in ped.get("items", [])
            ]
            pedido = Order(
                id_pedido=str(ped["id"]),
                prioridad=int(ped["prioridad"]),
                estado=EstadoPedido(ped.get("estado", "PENDIENTE")),
                items=detalles,
            )
            pedido.obtener_peso_total(self)
            pedido.obtener_coordenadas_unicas(self)
            self.pedidos_hash.insertar(pedido.id_pedido, pedido)

        self.pickers.clear()
        for pk in datos_json.get("pickers", []):
            pos = (int(pk["posicion_inicial"]["x"]), int(pk["posicion_inicial"]["y"]))
            self.pickers.append(
                Picker(
                    id_picker=str(pk["id"]),
                    posicion_inicial=pos,
                    posicion_actual=pos,
                    capacidad_carga_kg=float(pk["capacidad_carga_kg"]),
                )
            )

        config = datos_json.get("configuracion", {})
        self.wave_max_pedidos = config.get("wave_max_pedidos")
        self.wave_max_productos = config.get("wave_max_productos")

        return ruta_completa

    def buscar_producto_O1(self, id_producto: str) -> Optional[Product]:
        return self.productos_hash.buscar(id_producto)

    def buscar_pedido_O1(self, id_pedido: str) -> Optional[Order]:
        return self.pedidos_hash.buscar(id_pedido)

    def descontar_stock(self, id_producto: str, cantidad: int) -> bool:
        producto = self.buscar_producto_O1(id_producto)
        if producto is not None and producto.cantidad_disponible >= cantidad:
            producto.cantidad_disponible -= cantidad
            return True
        return False

    def actualizar_estado_pedido_O1(
        self, id_pedido: str, nuevo_estado: EstadoPedido
    ) -> bool:
        pedido = self.buscar_pedido_O1(id_pedido)
        if pedido is not None:
            pedido.estado = nuevo_estado
            return True
        return False

    def obtener_todos_los_productos(self) -> List[Product]:
        return self.productos_hash.obtener_todos_los_valores()

    def obtener_todos_los_pedidos(self) -> List[Order]:
        return self.pedidos_hash.obtener_todos_los_valores()

    def obtener_pedidos_pendientes(self, prioridad_minima: int = 1) -> List[Order]:
        return [
            ped
            for ped in self.pedidos_hash.obtener_todos_los_valores()
            if ped.estado == EstadoPedido.PENDIENTE
            and ped.prioridad >= prioridad_minima
        ]

    def decodificar_productos_a_json(self) -> List[Dict[str, Any]]:
        lista_productos = self.obtener_todos_los_productos()
        lista_productos.sort(key=lambda p: p.id_producto)
        return [p.to_dict() for p in lista_productos]

    def decodificar_pedidos_a_json(self) -> List[Dict[str, Any]]:
        lista_pedidos = self.obtener_todos_los_pedidos()
        lista_pedidos.sort(key=lambda o: o.id_pedido)
        return [o.to_dict() for o in lista_pedidos]

    def guardar_estado_simulacion_json(
        self,
        nombre_archivo_salida: str,
        pickers_actualizados: Optional[List[Picker]] = None,
    ) -> str:
        lista_pickers = (
            pickers_actualizados if pickers_actualizados is not None else self.pickers
        )

        config_guardada = {}
        if self.wave_max_pedidos is not None:
            config_guardada["wave_max_pedidos"] = self.wave_max_pedidos
        if self.wave_max_productos is not None:
            config_guardada["wave_max_productos"] = self.wave_max_productos

        estado_actual = {
            "warehouse": self.warehouse_raw,
            "pickers": [pk.to_dict() for pk in lista_pickers],
            "productos": self.decodificar_productos_a_json(),
            "pedidos": self.decodificar_pedidos_a_json(),
            "configuracion": config_guardada,
        }

        ruta_salida = (
            os.path.abspath(nombre_archivo_salida)
            if os.path.isabs(nombre_archivo_salida)
            else os.path.join(self.ruta_data, nombre_archivo_salida)
        )

        with open(ruta_salida, "w", encoding="utf-8") as archivo:
            json.dump(estado_actual, archivo, indent=2, ensure_ascii=False)

        return ruta_salida
