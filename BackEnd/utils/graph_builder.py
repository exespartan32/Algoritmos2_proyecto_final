from typing import Dict, Any, List, Tuple
from BackEnd.enums.enums import TipoCelda, SentidoCirculacion
from BackEnd.models.entity import (
    Celda, CeldaPasillo, CeldaRack, Rack, ZonaDespacho, Puerta, Product
)
from BackEnd.models.warehouse import Warehouse

class GraphBuilder:
    @staticmethod
    def construir_warehouse_desde_dict(data: Dict[str, Any]) -> Warehouse:
        wh_data = data["warehouse"]
        ancho_x = wh_data["dimensiones"]["ancho_x"]
        largo_y = wh_data["dimensiones"]["largo_y"]

        wh = Warehouse(ancho_x, largo_y)

        # 1. Inicializar toda la matriz como PASILLO con sentido AMBOS por defecto
        for x in range(ancho_x):
            for y in range(largo_y):
                wh.matriz[x][y] = CeldaPasillo(x, y, SentidoCirculacion.AMBOS)

        # 2. Pintar Pasillos Declarados (con su sentido N, S, E, O, AMBOS)
        for pas in wh_data.get("pasillos", []):
            px, py = pas["ubicacion"]["x"], pas["ubicacion"]["y"]
            sentido_enum = SentidoCirculacion(pas["sentido"])
            for x in range(px, px + pas["ancho"]):
                for y in range(py, py + pas["alto"]):
                    wh.matriz[x][y] = CeldaPasillo(x, y, sentido_enum, pas["id"])

        # 3. Pintar Puertas
        for p in wh_data.get("puertas", []):
            px, py = p["ubicacion"]["x"], p["ubicacion"]["y"]
            puerta_obj = Puerta(p["id"], p["tipo"], px, py)
            wh.puertas[p["id"]] = puerta_obj
            wh.matriz[px][py] = Celda(px, py, TipoCelda.PUERTA, p["id"])

        # 4. Pintar Zonas de Despacho
        for zd in wh_data.get("zonas_despacho", []):
            zx, zy = zd["ubicacion"]["x"], zd["ubicacion"]["y"]
            zona_obj = ZonaDespacho(
                zd["id"], zd["puerta_id"], zx, zy, zd["ancho"], zd["alto"], zd["peso_max_kg"]
            )
            wh.zonas_despacho[zd["id"]] = zona_obj
            for x in range(zx, zx + zd["ancho"]):
                for y in range(zy, zy + zd["alto"]):
                    wh.matriz[x][y] = Celda(x, y, TipoCelda.ZONA_DESPACHO, zd["id"])

        # 5. Pintar Racks (usando CeldaRack que tiene la pila en Z)
        for r in wh_data.get("racks", []):
            rx, ry = r["ubicacion"]["x"], r["ubicacion"]["y"]
            rack_obj = Rack(r["id"], rx, ry, r["ancho"], r["alto"])
            wh.racks[r["id"]] = rack_obj
            for x in range(rx, rx + r["ancho"]):
                for y in range(ry, ry + r["alto"]):
                    wh.matriz[x][y] = CeldaRack(x, y, r["id"])

        # 6. Ubicar Productos en la pila Z de su CeldaRack correspondiente
        for prod in data.get("productos", []):
            ub = prod["ubicacion"]
            px, py, pz = ub["x"], ub["y"], ub["z"]
            prod_obj = Product(
                id_producto=prod["id"],
                nombre=prod["nombre"],
                rack_id=prod["rack_id"],
                ubicacion_x=px,
                ubicacion_y=py,
                altura_z=pz,
                cantidad_disponible=prod["cantidad_disponible"],
                peso_kg=prod["peso_kg"]
            )
            wh.catalogo_productos[prod_obj.id_producto] = prod_obj
            celda_actual = wh.matriz[px][py]
            if isinstance(celda_actual, CeldaRack):
                celda_actual.apilar_producto(pz, prod_obj)

        # 7. Construir el Digrafo a partir de la Matriz
        GraphBuilder._construir_digrafo(wh)
        return wh

    @staticmethod
    def _construir_digrafo(wh: Warehouse):
        # Paso A: Crear un NodoGrafo por cada celda que sea PASILLO
        for x in range(wh.ancho_x):
            for y in range(wh.largo_y):
                celda = wh.matriz[x][y]
                if isinstance(celda, CeldaPasillo):
                    wh.grafo_pasillos.agregar_nodo(x, y, celda.sentido)

        # Paso B: Conectar aristas dirigidas y detectar Racks / Zonas adyacentes
        for (x, y), nodo in wh.grafo_pasillos.nodos.items():
            movimientos_permitidos = GraphBuilder._direcciones_segun_sentido(nodo.sentido_permitido)

            # 1) Mirar las 4 celdas ortogonales para detectar Racks y Zonas de Despacho al costado
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < wh.ancho_x and 0 <= ny < wh.largo_y:
                    celda_vecina = wh.matriz[nx][ny]
                    
                    # Si al lado hay un RACK, lo asociamos (NO creamos arista hacia el rack)
                    if isinstance(celda_vecina, CeldaRack):
                        nodo.racks_adyacentes.append(celda_vecina)
                        wh.acceso_rack_a_pasillo[(nx, ny)] = (x, y)
                    
                    # Si al lado hay una ZONA DE DESPACHO, guardamos su referencia
                    elif celda_vecina.tipo == TipoCelda.ZONA_DESPACHO:
                        if celda_vecina.elemento_id not in nodo.zonas_despacho_adyacentes:
                            nodo.zonas_despacho_adyacentes.append(celda_vecina.elemento_id)

            # 2) Crear aristas dirigidas solo hacia otros PASILLOS según el sentido permitido
            for dx, dy in movimientos_permitidos:
                nx, ny = x + dx, y + dy
                if 0 <= nx < wh.ancho_x and 0 <= ny < wh.largo_y:
                    if isinstance(wh.matriz[nx][ny], CeldaPasillo):
                        wh.grafo_pasillos.agregar_arista_dirigida((x, y), (nx, ny))

    @staticmethod
    def _direcciones_segun_sentido(sentido: SentidoCirculacion) -> List[Tuple[int, int]]:
        """
        Regla 3.5 del PDF:
        - En N o S puede avanzar en su sentido (+y o -y) y desplazarse lateralmente en x (+x, -x).
        - En E u O puede avanzar en su sentido (+x o -x) y desplazarse lateralmente en y (+y, -y).
        - En AMBOS puede ir en las 4 direcciones.
        """
        if sentido == SentidoCirculacion.N:
            return [(0, 1), (-1, 0), (1, 0)]   # Norte (+y) y laterales (Oeste, Este)
        elif sentido == SentidoCirculacion.S:
            return [(0, -1), (-1, 0), (1, 0)]  # Sur (-y) y laterales (Oeste, Este)
        elif sentido == SentidoCirculacion.E:
            return [(1, 0), (0, 1), (0, -1)]   # Este (+x) y laterales (Norte, Sur)
        elif sentido == SentidoCirculacion.O:
            return [(-1, 0), (0, 1), (0, -1)]  # Oeste (-x) y laterales (Norte, Sur)
        else:  # SentidoCirculacion.AMBOS
            return [(0, 1), (0, -1), (1, 0), (-1, 0)]