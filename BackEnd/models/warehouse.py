from typing import Any, Dict, List, Optional

from BackEnd.data_structures.digrafo import Coord, Digrafo, NodoGrafo
from BackEnd.enums.enums import (
    EstadoPedido,
    SentidoCirculacion as Sentido,
    TipoCelda,
)
from BackEnd.models.entities import (
    Celda,
    CeldaPasillo,
    Pedido,
    Picker,
    Producto,
    Puerta,
    Rack,
    ZonaDespacho,
)


class Warehouse:
    """Modelo central del almacén de ancho_x por largo_y (el eje y crece hacia arriba).

    Contiene el dígrafo de pasillos, los obstáculos físicos, las tablas hash en O(1)
    de productos y pedidos, y los accesos entre estanterías, zonas y pasillos.
    """

    def __init__(self, ancho_x: int, largo_y: int) -> None:
        self.ancho_x = ancho_x
        self.largo_y = largo_y
        self.grafo_pasillos = Digrafo()
        self.obstaculos: Dict[Coord, Celda] = {}

        self.racks: Dict[str, Rack] = {}
        self.zonas_despacho: Dict[str, ZonaDespacho] = {}
        self.puertas: Dict[str, Puerta] = {}

        self.catalogo_productos: Dict[str, Producto] = {}
        self.pedidos: Dict[str, Pedido] = {}
        self.pickers: List[Picker] = []
        self.wave_max_pedidos: int = 3
        self.wave_max_productos: int = 15
        self.warehouse_raw: Dict[str, Any] = {}

        self.acceso_rack_a_pasillo: Dict[Coord, Coord] = {}
        self.accesos_rack_a_pasillo: Dict[Coord, List[Coord]] = {}
        self.accesos_zona_a_pasillo: Dict[str, List[Coord]] = {}
        self.advertencias: List[str] = []

    def dentro(self, x: int, y: int) -> bool:
        return 0 <= x < self.ancho_x and 0 <= y < self.largo_y

    def obtener_celda(self, x: int, y: int) -> Optional[Celda]:
        celda = self.obstaculos.get((x, y))
        if celda is not None:
            return celda
        nodo = self.grafo_pasillos.nodos.get((x, y))
        if nodo is None:
            return None
        return CeldaPasillo(x, y, nodo.sentido_permitido, nodo.pasillo_id)

    # ------------------------------------------------------------------
    # Consultas y actualizaciones en O(1) de productos, stock y pedidos
    # ------------------------------------------------------------------
    def buscar_producto_O1(self, prod_id: str) -> Optional[Producto]:
        return self.catalogo_productos.get(prod_id)

    def buscar_pedido_O1(self, id_pedido: str) -> Optional[Pedido]:
        return self.pedidos.get(id_pedido)

    def obtener_todos_los_productos(self) -> List[Producto]:
        lista = list(self.catalogo_productos.values())
        lista.sort(key=lambda p: p.id_producto)
        return lista

    def obtener_todos_los_pedidos(self) -> List[Pedido]:
        lista = list(self.pedidos.values())
        lista.sort(key=lambda p: p.id_pedido)
        return lista

    def actualizar_estado_pedido_O1(
        self, id_pedido: str, nuevo_estado: EstadoPedido
    ) -> bool:
        ped = self.pedidos.get(id_pedido)
        if ped is None:
            return False
        ped.estado = nuevo_estado
        return True

    def descontar_stock(self, prod_id: str, cantidad: int) -> bool:
        """Descuenta el stock físico del producto cuando el picker descarga en despacho."""
        prod = self.catalogo_productos.get(prod_id)
        if prod is None or cantidad < 0 or prod.cantidad_disponible < cantidad:
            return False
        prod.cantidad_disponible -= cantidad
        return True

    # ------------------------------------------------------------------
    # Traducción de coordenadas de racks y zonas a celdas de pasillo
    # ------------------------------------------------------------------
    def obtener_celda_acceso_pasillo(self, rx: int, ry: int) -> Optional[Coord]:
        if (rx, ry) in self.grafo_pasillos.nodos:
            return (rx, ry)
        if (rx, ry) in self.acceso_rack_a_pasillo:
            return self.acceso_rack_a_pasillo[(rx, ry)]

        obst = self.obstaculos.get((rx, ry))
        if (
            obst is not None
            and obst.tipo == TipoCelda.ZONA_DESPACHO
            and obst.elemento_id
        ):
            accesos_z = self.accesos_zona_a_pasillo.get(obst.elemento_id, [])
            if accesos_z:
                return min(accesos_z, key=lambda c: abs(c[0] - rx) + abs(c[1] - ry))
        return None

    def obtener_nodo_acceso_producto(self, prod_id: str) -> Optional[Coord]:
        prod = self.catalogo_productos.get(prod_id)
        if not prod:
            return None
        return self.acceso_rack_a_pasillo.get((prod.x, prod.y))

    def obtener_nodos_acceso_producto(self, prod_id: str) -> List[Coord]:
        prod = self.catalogo_productos.get(prod_id)
        if not prod:
            return []
        return list(self.accesos_rack_a_pasillo.get((prod.x, prod.y), []))

    def obtener_nodos_acceso_zona(self, zona_id: str) -> List[Coord]:
        return list(self.accesos_zona_a_pasillo.get(zona_id, []))

    def imprimir_mapa(self, camino_bfs: Optional[List[Coord]] = None) -> None:
        camino_set = set(camino_bfs) if camino_bfs else set()
        simbolos_sentido = {
            Sentido.N: "^",
            Sentido.S: "v",
            Sentido.E: ">",
            Sentido.O: "<",
            Sentido.AMBOS: "+",
            Sentido.NINGUNO: "x",
        }
        simbolos_obstaculo = {
            TipoCelda.RACK: "#",
            TipoCelda.ZONA_DESPACHO: "D",
            TipoCelda.PUERTA: "P",
        }

        print("\n=== MAPA DEL WAREHOUSE ===")
        for y in range(self.largo_y - 1, -1, -1):
            fila_str = f"y={y:02d} | "
            for x in range(self.ancho_x):
                if (x, y) in camino_set:
                    fila_str += "*"
                elif (x, y) in self.obstaculos:
                    fila_str += simbolos_obstaculo[self.obstaculos[(x, y)].tipo]
                else:
                    nodo = self.grafo_pasillos.nodos[(x, y)]
                    fila_str += (
                        "."
                        if nodo.pasillo_id is None
                        else simbolos_sentido[nodo.sentido_permitido]
                    )
            print(fila_str)
        print("      +" + "-" * self.ancho_x)


__all__ = ["Warehouse", "Digrafo", "NodoGrafo", "Coord"]
