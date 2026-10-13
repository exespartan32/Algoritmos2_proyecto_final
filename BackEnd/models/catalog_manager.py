import random
from typing import List, Tuple, Optional, Dict, Any
from BackEnd.models.entities import Product, Order, DetallePedido
from BackEnd.enums.enums import EstadoPedido


class HashTableUniversal:
    def __init__(self, tamano_tabla: int = 1009):
        self.m = tamano_tabla
        self.p = 999983
        self.a = random.randint(1, self.p - 1)
        self.b = random.randint(0, self.p - 1)
        self.tabla: List[List[Tuple[str, Any]]] = [[] for _ in range(self.m)]

    def _str_a_int(self, key: str) -> int:
        val = 0
        for i, char in enumerate(reversed(key)):
            val += (128**i) * ord(char)
        return val

    def _hash(self, key: str) -> int:
        k = self._str_a_int(key)
        return ((self.a * k + self.b) % self.p) % self.m

    def insertar(self, clave: str, valor: Any) -> None:
        idx = self._hash(clave)
        cadena = self.tabla[idx]
        for i, (k, _) in enumerate(cadena):
            if k == clave:
                cadena[i] = (clave, valor)
                return
        cadena.append((clave, valor))

    def buscar(self, clave: str) -> Optional[Any]:
        idx = self._hash(clave)
        for k, v in self.tabla[idx]:
            if k == clave:
                return v
        return None

    def obtener_todos(self) -> List[Any]:
        elementos = []
        for cadena in self.tabla:
            for _, valor in cadena:
                elementos.append(valor)
        return elementos

    def limpiar(self) -> None:
        self.tabla = [[] for _ in range(self.m)]


class CatalogManager:
    def __init__(self, tamano_tabla: int = 1009):
        self._productos_hash = HashTableUniversal(tamano_tabla)
        self._pedidos_hash = HashTableUniversal(tamano_tabla)

    def cargar_productos_desde_json(
        self, lista_productos: List[Dict[str, Any]]
    ) -> None:
        self._productos_hash.limpiar()
        for p in lista_productos:
            ubic = p["ubicacion"]
            nuevo_prod = Product(
                id_producto=p["id"],
                nombre=p["nombre"],
                rack_id=p["rack_id"],
                ubicacion_x=int(ubic["x"]),
                ubicacion_y=int(ubic["y"]),
                altura_z=int(ubic["z"]),
                cantidad_disponible=int(p["cantidad_disponible"]),
                peso_kg=float(p["peso_kg"]),
            )
            self._productos_hash.insertar(nuevo_prod.id_producto, nuevo_prod)

    def cargar_pedidos_desde_json(self, lista_pedidos: List[Dict[str, Any]]) -> None:
        self._pedidos_hash.limpiar()
        for ped in lista_pedidos:
            items = [
                DetallePedido(
                    producto_id=item["producto_id"], cantidad=int(item["cantidad"])
                )
                for item in ped.get("items", [])
            ]
            nuevo_pedido = Order(
                id_pedido=ped["id"],
                prioridad=int(ped["prioridad"]),
                estado=EstadoPedido(ped["estado"]),
                items=items,
            )
            self._pedidos_hash.insertar(nuevo_pedido.id_pedido, nuevo_pedido)

    def buscar_producto_O1(self, id_producto: str) -> Optional[Product]:
        return self._productos_hash.buscar(id_producto)

    def buscar_pedido_O1(self, id_pedido: str) -> Optional[Order]:
        return self._pedidos_hash.buscar(id_pedido)

    def obtener_todos_los_pedidos(self) -> List[Order]:
        return self._pedidos_hash.obtener_todos()

    def obtener_todos_los_productos(self) -> List[Product]:
        return self._productos_hash.obtener_todos()

    def descontar_stock(self, id_producto: str, cantidad: int) -> bool:
        producto = self.buscar_producto_O1(id_producto)
        if producto and producto.cantidad_disponible >= cantidad:
            producto.cantidad_disponible -= cantidad
            return True
        return False

    def decodificar_productos_a_json(self) -> List[Dict[str, Any]]:
        productos = self._productos_hash.obtener_todos()
        productos.sort(key=lambda p: p.id_producto)
        return [p.to_dict() for p in productos]

    def decodificar_pedidos_a_json(self) -> List[Dict[str, Any]]:
        pedidos = self._pedidos_hash.obtener_todos()
        pedidos.sort(key=lambda o: o.id_pedido)
        return [o.to_dict() for o in pedidos]
