from typing import Dict, Any, List, Tuple, Optional
from BackEnd.enums.enums import TipoCelda, SentidoCirculacion as Sentido
from BackEnd.models.entities import (
    Celda,
    CeldaRack,
    Rack,
    ZonaDespacho,
    Puerta,
    Product,
)
from BackEnd.models.warehouse import Warehouse, Coord

DIRECCIONES_ORTOGONALES: List[Tuple[int, int]] = [(0, 1), (0, -1), (1, 0), (-1, 0)]


class GraphBuilder:
    """Construye el dígrafo de pasillos del Warehouse directamente desde el JSON y lo valida."""

    @staticmethod
    def construir_warehouse_desde_dict(data: Dict[str, Any]) -> Warehouse:
        wh_data = data["warehouse"]
        ancho_x = int(wh_data["dimensiones"]["ancho_x"])
        largo_y = int(wh_data["dimensiones"]["largo_y"])

        wh = Warehouse(ancho_x, largo_y)
        advertencias: List[str] = []
        ocupado_por: Dict[Coord, str] = {}
        pasillos_declarados: Dict[Coord, Tuple[Sentido, str]] = {}

        def ocupar(x: int, y: int, elem_id: str):
            if not wh.dentro(x, y):
                raise ValueError(
                    f"El elemento {elem_id} ocupa la celda ({x},{y}), que está fuera del "
                    f"almacén ({ancho_x}x{largo_y})."
                )
            anterior = ocupado_por.get((x, y))
            if anterior is not None and anterior != elem_id:
                advertencias.append(f"{elem_id} pisa a {anterior} en ({x},{y}).")
            ocupado_por[(x, y)] = elem_id

        def ocupar_obstaculo(x: int, y: int, celda: Celda, elem_id: str):
            ocupar(x, y, elem_id)
            wh.obstaculos[(x, y)] = celda

        # 1. Pasillos declarados (En intersecciones con AMBOS prevalece AMBOS para permitir giro)
        validos = [s.value for s in Sentido]
        for pas in wh_data.get("pasillos", []):
            try:
                sentido_enum = Sentido(pas["sentido"])
            except ValueError:
                raise ValueError(
                    f"Sentido inválido '{pas['sentido']}' en el pasillo {pas['id']}. "
                    f"Valores válidos: {', '.join(validos)}."
                ) from None
            px, py = int(pas["ubicacion"]["x"]), int(pas["ubicacion"]["y"])
            for x in range(px, px + int(pas["ancho"])):
                for y in range(py, py + int(pas["alto"])):
                    ocupar(x, y, pas["id"])
                    previo = pasillos_declarados.get((x, y))
                    if previo is not None and previo[0] == Sentido.AMBOS:
                        continue
                    pasillos_declarados[(x, y)] = (sentido_enum, pas["id"])

        # 2. Puertas
        for p in wh_data.get("puertas", []):
            px, py = int(p["ubicacion"]["x"]), int(p["ubicacion"]["y"])
            ocupar_obstaculo(px, py, Celda(px, py, TipoCelda.PUERTA, p["id"]), p["id"])
            wh.puertas[p["id"]] = Puerta(p["id"], p["tipo"], px, py)

        # 3. Zonas de despacho
        for zd in wh_data.get("zonas_despacho", []):
            zx, zy = int(zd["ubicacion"]["x"]), int(zd["ubicacion"]["y"])
            for x in range(zx, zx + int(zd["ancho"])):
                for y in range(zy, zy + int(zd["alto"])):
                    ocupar_obstaculo(
                        x, y, Celda(x, y, TipoCelda.ZONA_DESPACHO, zd["id"]), zd["id"]
                    )
            wh.zonas_despacho[zd["id"]] = ZonaDespacho(
                zd["id"],
                zd["puerta_id"],
                zx,
                zy,
                int(zd["ancho"]),
                int(zd["alto"]),
                float(zd["peso_max_kg"]),
            )

        # 4. Racks
        for r in wh_data.get("racks", []):
            rx, ry = int(r["ubicacion"]["x"]), int(r["ubicacion"]["y"])
            ancho_r, alto_r = int(r["ancho"]), int(r["alto"])
            if ancho_r != 2 and alto_r != 2:
                advertencias.append(
                    f"El rack {r['id']} mide {ancho_r}x{alto_r}: ningún lado vale 2."
                )
            for x in range(rx, rx + ancho_r):
                for y in range(ry, ry + alto_r):
                    ocupar_obstaculo(x, y, CeldaRack(x, y, r["id"]), r["id"])
            wh.racks[r["id"]] = Rack(r["id"], rx, ry, ancho_r, alto_r)

        # 5. Productos
        for prod in data.get("productos", []):
            ub = prod["ubicacion"]
            px, py, pz = int(ub["x"]), int(ub["y"]), int(ub.get("z", 1))
            if not wh.dentro(px, py):
                raise ValueError(
                    f"El producto {prod['id']} está en ({px},{py}), fuera del almacén."
                )
            prod_obj = Product(
                id_producto=prod["id"],
                nombre=prod["nombre"],
                rack_id=prod["rack_id"],
                ubicacion_x=px,
                ubicacion_y=py,
                ubicacion_z=pz,
                cantidad_disponible=prod["cantidad_disponible"],
                peso_kg=prod["peso_kg"],
            )
            wh.catalogo_productos[prod_obj.id] = prod_obj
            celda = wh.obstaculos.get((px, py))
            if isinstance(celda, CeldaRack):
                celda.apilar_producto(pz, prod_obj)

        # 6. Construir Dígrafo
        GraphBuilder._construir_digrafo(wh, pasillos_declarados)

        # 7. Validar con Kosaraju
        posiciones_pickers = [
            (pk["id"], (pk["posicion_inicial"]["x"], pk["posicion_inicial"]["y"]))
            for pk in data.get("pickers", [])
        ]
        advertencias.extend(GraphBuilder.validar_grafo(wh, posiciones_pickers))
        wh.advertencias = advertencias
        return wh

    @staticmethod
    def _construir_digrafo(
        wh: Warehouse,
        pasillos_declarados: Optional[Dict[Coord, Tuple[Sentido, str]]] = None,
    ) -> None:
        grafo = wh.grafo_pasillos
        pasillos_declarados = pasillos_declarados or {}

        for x in range(wh.ancho_x):
            for y in range(wh.largo_y):
                if (x, y) in wh.obstaculos:
                    continue
                sentido, pasillo_id = pasillos_declarados.get(
                    (x, y), (Sentido.AMBOS, None)
                )
                grafo.agregar_nodo(x, y, sentido, pasillo_id)

        for (x, y), nodo in grafo.nodos.items():
            for dx, dy in DIRECCIONES_ORTOGONALES:
                nx, ny = x + dx, y + dy
                vecina = wh.obstaculos.get((nx, ny))
                if vecina is None:
                    continue

                if isinstance(vecina, CeldaRack):
                    rack = wh.racks.get(vecina.elemento_id)
                    if (x - nx, y - ny) in GraphBuilder._dirs_acceso(rack, nx, ny):
                        nodo.racks_adyacentes.append(vecina)
                        wh.accesos_rack_a_pasillo.setdefault((nx, ny), []).append(
                            (x, y)
                        )
                        if (nx, ny) not in wh.acceso_rack_a_pasillo:
                            wh.acceso_rack_a_pasillo[(nx, ny)] = (x, y)

                elif vecina.tipo == TipoCelda.ZONA_DESPACHO:
                    zona_id = vecina.elemento_id
                    if zona_id not in nodo.zonas_despacho_adyacentes:
                        nodo.zonas_despacho_adyacentes.append(zona_id)
                    if (x, y) not in wh.accesos_zona_a_pasillo.setdefault(zona_id, []):
                        wh.accesos_zona_a_pasillo[zona_id].append((x, y))

            for dx, dy in GraphBuilder._direcciones_segun_sentido(
                nodo.sentido_permitido
            ):
                destino = grafo.nodos.get((x + dx, y + dy))
                if destino is not None and not GraphBuilder._es_contramano(
                    dx, dy, destino.sentido_permitido
                ):
                    grafo.agregar_arista_dirigida((x, y), (destino.x, destino.y))

    @staticmethod
    def _direcciones_segun_sentido(sentido: Sentido) -> List[Tuple[int, int]]:
        if sentido == Sentido.N:
            return [(0, 1), (-1, 0), (1, 0)]
        if sentido == Sentido.S:
            return [(0, -1), (-1, 0), (1, 0)]
        if sentido == Sentido.E:
            return [(1, 0), (0, 1), (0, -1)]
        if sentido == Sentido.O:
            return [(-1, 0), (0, 1), (0, -1)]
        if sentido == Sentido.AMBOS:
            return [(0, 1), (0, -1), (1, 0), (-1, 0)]
        return []

    @staticmethod
    def _es_contramano(dx: int, dy: int, sentido_destino: Sentido) -> bool:
        if sentido_destino == Sentido.NINGUNO:
            return True
        return (
            (dy == 1 and sentido_destino == Sentido.S)
            or (dy == -1 and sentido_destino == Sentido.N)
            or (dx == 1 and sentido_destino == Sentido.O)
            or (dx == -1 and sentido_destino == Sentido.E)
        )

    @staticmethod
    def _dirs_acceso(rack: Optional[Rack], x: int, y: int) -> List[Tuple[int, int]]:
        if rack is not None and rack.ancho == 2 and rack.alto != 2:
            return [(-1, 0)] if x == rack.x else [(1, 0)]
        if rack is not None and rack.alto == 2 and rack.ancho != 2:
            return [(0, -1)] if y == rack.y else [(0, 1)]
        return list(DIRECCIONES_ORTOGONALES)

    @staticmethod
    def componentes_fuertemente_conexas(wh: Warehouse) -> List[List[Coord]]:
        grafo = wh.grafo_pasillos
        adyacencia = grafo.lista_adyacencia

        visitado = set()
        orden_fin: List[Coord] = []
        for inicio in grafo.nodos:
            if inicio in visitado:
                continue
            visitado.add(inicio)
            pila = [(inicio, 0)]
            while pila:
                nodo, i = pila[-1]
                vecinos = adyacencia[nodo]
                if i < len(vecinos):
                    pila[-1] = (nodo, i + 1)
                    vecino = vecinos[i]
                    if vecino not in visitado:
                        visitado.add(vecino)
                        pila.append((vecino, 0))
                else:
                    pila.pop()
                    orden_fin.append(nodo)

        transpuesto: Dict[Coord, List[Coord]] = {c: [] for c in grafo.nodos}
        for origen, destinos in adyacencia.items():
            for destino in destinos:
                transpuesto[destino].append(origen)

        asignado = set()
        componentes: List[List[Coord]] = []
        for raiz in reversed(orden_fin):
            if raiz in asignado:
                continue
            asignado.add(raiz)
            componente = []
            pila = [raiz]
            while pila:
                nodo = pila.pop()
                componente.append(nodo)
                for vecino in transpuesto[nodo]:
                    if vecino not in asignado:
                        asignado.add(vecino)
                        pila.append(vecino)
            componentes.append(componente)

        componentes.sort(key=len, reverse=True)
        return componentes

    @staticmethod
    def validar_grafo(wh: Warehouse, posiciones_pickers=None) -> List[str]:
        advertencias: List[str] = []
        componentes = GraphBuilder.componentes_fuertemente_conexas(wh)
        principal = set(componentes[0]) if componentes else set()

        # Garantizar que acceso_rack_a_pasillo apunte siempre a la red principal conexa
        for coord_rack, lista_acc in wh.accesos_rack_a_pasillo.items():
            en_principal = [a for a in lista_acc if a in principal]
            if en_principal:
                wh.acceso_rack_a_pasillo[coord_rack] = en_principal[0]

        if len(componentes) > 1:
            fuera = [c for comp in componentes[1:] for c in comp]
            advertencias.append(
                f"Hay {len(componentes)} componentes fuertemente conexas ({len(fuera)} celdas fuera de la red principal)."
            )
        return advertencias
