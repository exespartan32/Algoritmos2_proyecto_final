from typing import Dict, Any, List, Tuple, Optional
from BackEnd.enums.enums import TipoCelda, SentidoCirculacion as Sentido
from BackEnd.models.entity import Celda, CeldaRack, Rack, ZonaDespacho, Puerta, Product
from BackEnd.models.warehouse import Warehouse, Coord

# Las 4 direcciones ortogonales (sin diagonales): Norte, Sur, Este, Oeste
DIRECCIONES_ORTOGONALES: List[Tuple[int, int]] = [(0, 1), (0, -1), (1, 0), (-1, 0)]


class GraphBuilder:
    """Construye el dígrafo de pasillos del Warehouse directamente desde el JSON y lo valida."""

    # ------------------------------------------------------------------ #
    # Construcción del almacén
    # ------------------------------------------------------------------ #
    @staticmethod
    def construir_warehouse_desde_dict(data: Dict[str, Any]) -> Warehouse:
        wh_data = data["warehouse"]
        ancho_x = wh_data["dimensiones"]["ancho_x"]
        largo_y = wh_data["dimensiones"]["largo_y"]

        wh = Warehouse(ancho_x, largo_y)
        advertencias: List[str] = []
        # Qué elemento declarado ocupó cada celda (para detectar superposiciones)
        ocupado_por: Dict[Coord, str] = {}
        # Sentido e ID de cada celda de pasillo declarada en el JSON
        pasillos_declarados: Dict[Coord, Tuple[Sentido, str]] = {}

        def ocupar(x: int, y: int, elem_id: str):
            """Controla que la celda esté dentro del almacén y avisa si otro elemento ya la ocupaba."""
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

        # 1. Pasillos declarados, con su sentido (N, S, E, O, AMBOS, NINGUNO).
        #    Las celdas no declaradas serán pasillo AMBOS (enunciado 3.5).
        validos = [s.value for s in Sentido]
        for pas in wh_data.get("pasillos", []):
            try:
                sentido_enum = Sentido(pas["sentido"])
            except ValueError:
                raise ValueError(
                    f"Sentido inválido '{pas['sentido']}' en el pasillo {pas['id']}. "
                    f"Valores válidos: {', '.join(validos)}."
                ) from None
            px, py = pas["ubicacion"]["x"], pas["ubicacion"]["y"]
            for x in range(px, px + pas["ancho"]):
                for y in range(py, py + pas["alto"]):
                    ocupar(x, y, pas["id"])
                    pasillos_declarados[(x, y)] = (sentido_enum, pas["id"])

        # 2. Puertas: obstáculo sin función en el grafo
        for p in wh_data.get("puertas", []):
            px, py = p["ubicacion"]["x"], p["ubicacion"]["y"]
            ocupar_obstaculo(px, py, Celda(px, py, TipoCelda.PUERTA, p["id"]), p["id"])
            wh.puertas[p["id"]] = Puerta(p["id"], p["tipo"], px, py)

        # 3. Zonas de despacho: obstáculo
        for zd in wh_data.get("zonas_despacho", []):
            zx, zy = zd["ubicacion"]["x"], zd["ubicacion"]["y"]
            for x in range(zx, zx + zd["ancho"]):
                for y in range(zy, zy + zd["alto"]):
                    ocupar_obstaculo(x, y, Celda(x, y, TipoCelda.ZONA_DESPACHO, zd["id"]), zd["id"])
            wh.zonas_despacho[zd["id"]] = ZonaDespacho(
                zd["id"], zd["puerta_id"], zx, zy, zd["ancho"], zd["alto"], zd["peso_max_kg"]
            )

        # 4. Racks: obstáculo (CeldaRack tiene la pila en Z). Deben tener un lado igual a 2 (enunciado 3.2)
        for r in wh_data.get("racks", []):
            rx, ry = r["ubicacion"]["x"], r["ubicacion"]["y"]
            if r["ancho"] != 2 and r["alto"] != 2:
                advertencias.append(
                    f"El rack {r['id']} mide {r['ancho']}x{r['alto']}: ningún lado vale 2 "
                    f"(enunciado 3.2). Se lo considera accesible desde sus 4 lados."
                )
            for x in range(rx, rx + r["ancho"]):
                for y in range(ry, ry + r["alto"]):
                    ocupar_obstaculo(x, y, CeldaRack(x, y, r["id"]), r["id"])
            wh.racks[r["id"]] = Rack(r["id"], rx, ry, r["ancho"], r["alto"])

        # 5. Productos: se apilan en la posición Z de su CeldaRack
        for prod in data.get("productos", []):
            ub = prod["ubicacion"]
            px, py, pz = ub["x"], ub["y"], ub["z"]
            if not wh.dentro(px, py):
                raise ValueError(
                    f"El producto {prod['id']} está en ({px},{py}), fuera del almacén ({ancho_x}x{largo_y})."
                )
            prod_obj = Product(
                id_producto=prod["id"],
                nombre=prod["nombre"],
                rack_id=prod["rack_id"],
                ubicacion_x=px,
                ubicacion_y=py,
                altura_z=pz,
                cantidad_disponible=prod["cantidad_disponible"],
                peso_kg=prod["peso_kg"],
            )
            wh.catalogo_productos[prod_obj.id] = prod_obj
            celda = wh.obstaculos.get((px, py))
            if isinstance(celda, CeldaRack):
                if celda.elemento_id != prod_obj.rack_id:
                    advertencias.append(
                        f"El producto {prod_obj.id} declara rack {prod_obj.rack_id} pero la celda "
                        f"({px},{py}) pertenece al rack {celda.elemento_id}."
                    )
                celda.apilar_producto(pz, prod_obj)
            else:
                advertencias.append(
                    f"El producto {prod_obj.id} está en ({px},{py}), que no es una celda de rack."
                )

        # 6. Dígrafo de pasillos
        GraphBuilder._construir_digrafo(wh, pasillos_declarados)

        # 7. Validación del grafo
        posiciones_pickers = [
            (pk["id"], (pk["posicion_inicial"]["x"], pk["posicion_inicial"]["y"]))
            for pk in data.get("pickers", [])
        ]
        advertencias.extend(GraphBuilder.validar_grafo(wh, posiciones_pickers))
        wh.advertencias = advertencias
        return wh

    # ------------------------------------------------------------------ #
    # Dígrafo
    # ------------------------------------------------------------------ #
    @staticmethod
    def _construir_digrafo(wh: Warehouse, pasillos_declarados: Optional[Dict[Coord, Tuple[Sentido, str]]] = None):
        grafo = wh.grafo_pasillos
        pasillos_declarados = pasillos_declarados or {}

        # Paso A: un NodoGrafo por cada coordenada que NO es obstáculo.
        # Si fue declarada como pasillo usa ese sentido; si no, es pasillo AMBOS.
        for x in range(wh.ancho_x):
            for y in range(wh.largo_y):
                if (x, y) in wh.obstaculos:
                    continue
                sentido, pasillo_id = pasillos_declarados.get((x, y), (Sentido.AMBOS, None))
                grafo.agregar_nodo(x, y, sentido, pasillo_id)

        # Paso B: accesos a racks / zonas y aristas dirigidas
        for (x, y), nodo in grafo.nodos.items():
            # a) Racks y zonas de despacho pegados a este nodo
            for dx, dy in DIRECCIONES_ORTOGONALES:
                nx, ny = x + dx, y + dy
                vecina = wh.obstaculos.get((nx, ny))
                if vecina is None:
                    continue

                if isinstance(vecina, CeldaRack):
                    rack = wh.racks.get(vecina.elemento_id)
                    # Dirección desde la celda de rack hacia este pasillo
                    if (x - nx, y - ny) in GraphBuilder._dirs_acceso(rack, nx, ny):
                        nodo.racks_adyacentes.append(vecina)
                        wh.accesos_rack_a_pasillo.setdefault((nx, ny), []).append((x, y))
                        if (nx, ny) not in wh.acceso_rack_a_pasillo:
                            wh.acceso_rack_a_pasillo[(nx, ny)] = (x, y)

                elif vecina.tipo == TipoCelda.ZONA_DESPACHO:
                    zona_id = vecina.elemento_id
                    if zona_id not in nodo.zonas_despacho_adyacentes:
                        nodo.zonas_despacho_adyacentes.append(zona_id)
                        wh.accesos_zona_a_pasillo.setdefault(zona_id, []).append((x, y))

            # b) Aristas hacia pasillos vecinos, según el sentido del origen y sin entrar en contramano
            for dx, dy in GraphBuilder._direcciones_segun_sentido(nodo.sentido_permitido):
                destino = grafo.nodos.get((x + dx, y + dy))  # None si es obstáculo o está fuera
                if destino is not None and not GraphBuilder._es_contramano(dx, dy, destino.sentido_permitido):
                    grafo.agregar_arista_dirigida((x, y), (destino.x, destino.y))

    @staticmethod
    def _direcciones_segun_sentido(sentido: Sentido) -> List[Tuple[int, int]]:
        """
        Regla 3.5 del enunciado:
        - En N o S se avanza en su sentido (+y o -y) y se puede ir lateralmente en x.
        - En E u O se avanza en su sentido (+x o -x) y se puede ir lateralmente en y.
        - En AMBOS se puede ir en las 4 direcciones. En NINGUNO no se sale.
        """
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
        return []  # Sentido.NINGUNO

    @staticmethod
    def _es_contramano(dx: int, dy: int, sentido_destino: Sentido) -> bool:
        """True si moverse (dx, dy) hacia la celda destino va contra el sentido de ese pasillo."""
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
        """
        Direcciones (desde la celda de rack (x, y) hacia afuera) por las que se puede recoger.
        Un rack de 2 de ancho se recoge por los costados izquierdo/derecho; uno de 2 de alto,
        por abajo/arriba. Los extremos del rack no son accesibles.
        """
        if rack is not None and rack.ancho == 2 and rack.alto != 2:
            return [(-1, 0)] if x == rack.x else [(1, 0)]
        if rack is not None and rack.alto == 2 and rack.ancho != 2:
            return [(0, -1)] if y == rack.y else [(0, 1)]
        return list(DIRECCIONES_ORTOGONALES)  # 2x2 o rack inválido

    # ------------------------------------------------------------------ #
    # Validación
    # ------------------------------------------------------------------ #
    @staticmethod
    def componentes_fuertemente_conexas(wh: Warehouse) -> List[List[Coord]]:
        """Algoritmo de Kosaraju ITERATIVO. Devuelve las componentes de mayor a menor."""
        grafo = wh.grafo_pasillos
        adyacencia = grafo.lista_adyacencia

        # 1ra pasada: DFS sobre G, guardando los nodos en orden de finalización
        visitado = set()
        orden_fin: List[Coord] = []
        for inicio in grafo.nodos:
            if inicio in visitado:
                continue
            visitado.add(inicio)
            pila = [(inicio, 0)]  # (nodo, índice del próximo vecino a mirar)
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

        # Grafo transpuesto (todas las aristas invertidas)
        transpuesto: Dict[Coord, List[Coord]] = {c: [] for c in grafo.nodos}
        for origen, destinos in adyacencia.items():
            for destino in destinos:
                transpuesto[destino].append(origen)

        # 2da pasada: DFS sobre G^T en orden de finalización decreciente
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
        """
        Revisa la conectividad del grafo y devuelve una lista de advertencias.
        posiciones_pickers: lista de (picker_id, (x, y)) o de (x, y).
        """
        advertencias: List[str] = []
        componentes = GraphBuilder.componentes_fuertemente_conexas(wh)
        principal = set(componentes[0]) if componentes else set()

        # Celdas fuera de la componente principal (trampas sin salida o islas)
        if len(componentes) > 1:
            fuera = [c for comp in componentes[1:] for c in comp]
            xs = [c[0] for c in fuera]
            ys = [c[1] for c in fuera]
            advertencias.append(
                f"Hay {len(componentes)} componentes fuertemente conexas: {len(fuera)} celdas de pasillo "
                f"no pertenecen a la red principal (x={min(xs)}..{max(xs)}, y={min(ys)}..{max(ys)}). "
                f"Son trampas sin salida o islas: revisar los sentidos de los pasillos."
            )

        # Productos
        for prod_id, prod in wh.catalogo_productos.items():
            accesos = wh.accesos_rack_a_pasillo.get((prod.x, prod.y), [])
            if not accesos:
                advertencias.append(
                    f"El producto {prod_id} en ({prod.x},{prod.y}) no tiene pasillo de acceso."
                )
            elif not any(a in principal for a in accesos):
                advertencias.append(
                    f"El producto {prod_id} en ({prod.x},{prod.y}) no tiene ningún acceso en la red principal."
                )

        # Zonas de despacho
        for zona_id in wh.zonas_despacho:
            accesos = wh.accesos_zona_a_pasillo.get(zona_id, [])
            if not accesos:
                advertencias.append(f"La zona {zona_id} no tiene pasillos adyacentes.")
            elif not any(a in principal for a in accesos):
                advertencias.append(f"La zona {zona_id} no tiene ningún pasillo adyacente en la red principal.")

        # Pickers
        for item in posiciones_pickers or []:
            if len(item) == 2 and isinstance(item[1], tuple):
                pk_id, pos = item
            else:
                pk_id, pos = "?", tuple(item)
            if pos not in wh.grafo_pasillos.nodos:
                advertencias.append(f"Picker {pk_id} arranca en {pos}, que no es una celda de pasillo.")
            elif pos not in principal:
                advertencias.append(f"Picker {pk_id} arranca en {pos}, fuera de la red principal.")

        return advertencias
