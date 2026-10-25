from typing import Dict, List, Tuple, Optional, Set, Any
from BackEnd.enums.enums import TipoCelda, SentidoCirculacion as Sentido, EstadoPedido
from BackEnd.models.entities import (
    Celda,
    CeldaPasillo,
    CeldaRack,
    Rack,
    ZonaDespacho,
    Puerta,
    Product,
    Pedido,
    Picker,
)

Coord = Tuple[int, int]


class NodoGrafo:
    """Una celda de PASILLO transitable. Es la única clase de celda que es nodo del grafo."""

    def __init__(
        self, x: int, y: int, sentido: Sentido, pasillo_id: Optional[str] = None
    ):
        self.x = x
        self.y = y
        self.sentido_permitido = sentido
        self.pasillo_id = pasillo_id
        self.racks_adyacentes: List[CeldaRack] = []
        self.zonas_despacho_adyacentes: List[str] = []


class Digrafo:
    """Grafo dirigido representado mediante Lista de Adyacencia con soporte de bloqueos temporales."""

    def __init__(self):
        self.nodos: Dict[Coord, NodoGrafo] = {}
        self.lista_adyacencia: Dict[Coord, List[Coord]] = {}
        self.bloqueos_temporales: Dict[Tuple[int, int, int], str] = {}
        self.nodos_evasion_actual: Set[Coord] = set()

    def agregar_nodo(
        self, x: int, y: int, sentido: Sentido, pasillo_id: Optional[str] = None
    ) -> NodoGrafo:
        coord = (x, y)
        if coord not in self.nodos:
            self.nodos[coord] = NodoGrafo(x, y, sentido, pasillo_id)
            self.lista_adyacencia[coord] = []
        return self.nodos[coord]

    def agregar_arista_dirigida(self, origen: Coord, destino: Coord) -> None:
        if origen in self.lista_adyacencia and destino in self.nodos:
            if destino not in self.lista_adyacencia[origen]:
                self.lista_adyacencia[origen].append(destino)

    def obtener_vecinos(self, coord: Coord) -> List[Coord]:
        return self.lista_adyacencia.get(coord, [])

    def bloquear_celda_temporal(
        self, coord: Coord, paso_tiempo: int, picker_id: str
    ) -> None:
        self.bloqueos_temporales[(coord[0], coord[1], int(paso_tiempo))] = picker_id

    def limpiar_bloqueos_antiguos(self, paso_actual: int) -> None:
        claves_borrar = [k for k in self.bloqueos_temporales if k[2] < paso_actual]
        for k in claves_borrar:
            del self.bloqueos_temporales[k]

    def obtener_vecinos_validos(
        self,
        nodo_actual: Coord,
        paso_tiempo: int = 0,
        picker_id_solicitante: Optional[str] = None,
    ) -> List[Coord]:
        vecinos_base = self.lista_adyacencia.get(nodo_actual, [])
        if not self.bloqueos_temporales and not self.nodos_evasion_actual:
            return list(vecinos_base)

        validos: List[Coord] = []
        for v in vecinos_base:
            if v in self.nodos_evasion_actual:
                continue
            if paso_tiempo > 0:
                ocupante = self.bloqueos_temporales.get((v[0], v[1], paso_tiempo))
                if ocupante is not None and ocupante != picker_id_solicitante:
                    continue
            validos.append(v)
        return validos


class Warehouse:
    """
    Almacén de ancho_x por largo_y (el eje y crece hacia arriba).
    Centraliza el Dígrafo de pasillos, los obstáculos y las Tablas Hash (dict O(1))
    de productos y pedidos, reemplazando por completo a CatalogManager.
    """

    def __init__(self, ancho_x: int, largo_y: int):
        self.ancho_x = ancho_x
        self.largo_y = largo_y
        self.grafo_pasillos = Digrafo()
        self.obstaculos: Dict[Coord, Celda] = {}

        self.racks: Dict[str, Rack] = {}
        self.zonas_despacho: Dict[str, ZonaDespacho] = {}
        self.puertas: Dict[str, Puerta] = {}

        # Tablas Hash O(1) de Productos y Pedidos + Flota de Pickers y Configuración
        self.catalogo_productos: Dict[str, Product] = {}
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

    # =========================================================================
    # OPERACIONES O(1) DE PRODUCTOS, STOCK Y PEDIDOS
    # =========================================================================
    def buscar_producto_O1(self, prod_id: str) -> Optional[Product]:
        return self.catalogo_productos.get(prod_id)

    def buscar_pedido_O1(self, id_pedido: str) -> Optional[Pedido]:
        return self.pedidos.get(id_pedido)

    def obtener_todos_los_productos(self) -> List[Product]:
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
        """
        Descuenta en O(1) el stock real del producto únicamente cuando el Picker
        finaliza su recorrido y descarga en la Zona de Despacho.
        """
        prod = self.catalogo_productos.get(prod_id)
        if prod is None or cantidad < 0 or prod.cantidad_disponible < cantidad:
            return False
        prod.cantidad_disponible -= cantidad
        return True

    # =========================================================================
    # TRADUCCIÓN DE RACKS Y ZONAS DE DESPACHO A CELDAS DE PASILLO
    # =========================================================================
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
        print("     +" + "-" * self.ancho_x)
