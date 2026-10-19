"""Validación de entrada y acceso al generador del equipo."""

import math


def cells(item):
    return [
        (x, y)
        for x in range(
            item["ubicacion"]["x"], item["ubicacion"]["x"] + item.get("ancho", 1)
        )
        for y in range(
            item["ubicacion"]["y"], item["ubicacion"]["y"] + item.get("alto", 1)
        )
    ]


def validate(data):
    # Validar tipos antes de construir rectángulos o reservar la matriz.
    def integer(value, minimum=0, maximum=1000000):
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError("Se esperaba un entero dentro del rango permitido.")

    def positive(value):
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("Peso o capacidad inválidos.")

    wh = data["warehouse"]
    integer(wh["dimensiones"]["ancho_x"], 1, 200)
    integer(wh["dimensiones"]["largo_y"], 1, 200)
    for group in ("racks", "puertas", "zonas_despacho", "pasillos"):
        for obj in wh[group]:
            if not isinstance(obj["id"], str) or not obj["id"]:
                raise ValueError("Los identificadores deben ser textos no vacíos.")
            for axis in ("x", "y"):
                integer(obj["ubicacion"][axis], 0, 199)
            if group != "puertas":
                integer(obj["ancho"], 1, 200)
                integer(obj["alto"], 1, 200)
    for product in data["productos"]:
        integer(product["cantidad_disponible"])
        integer(product["ubicacion"]["z"], 1)
        integer(product["ubicacion"]["x"], 0, 199)
        integer(product["ubicacion"]["y"], 0, 199)
        positive(product["peso_kg"])
    for order in data["pedidos"]:
        integer(order["prioridad"], 1, 5)
        if order.get("estado", "PENDIENTE") not in (
            "PENDIENTE",
            "PREPARADO",
            "IRREALIZABLE",
        ):
            raise ValueError(
                "Pedido en curso sin historial de interfaz: cargá el archivo de sesión completo."
            )
        items = set()
        for item in order["items"]:
            integer(item["cantidad"], 1)
            if item["producto_id"] in items:
                raise ValueError(
                    "Agrupá los ítems repetidos de un producto dentro del pedido."
                )
            items.add(item["producto_id"])
    for picker in data["pickers"]:
        positive(picker["capacidad_carga_kg"])
        for axis in ("x", "y"):
            integer(picker["posicion_inicial"][axis], 0, 199)
    for zone in wh["zonas_despacho"]:
        positive(zone["peso_max_kg"])
    for key, value in data.get("configuracion", {}).items():
        if key in ("wave_max_pedidos", "wave_max_productos"):
            integer(value, 1)
    w, h = wh["dimensiones"]["ancho_x"], wh["dimensiones"]["largo_y"]
    if not (
        isinstance(w, int) and isinstance(h, int) and 1 <= w <= 200 and 1 <= h <= 200
    ):
        raise ValueError("Dimensiones permitidas: de 1 a 200 celdas.")
    occupied, ids = set(), set()
    for group in ("racks", "puertas", "zonas_despacho", "pasillos"):
        for obj in wh.get(group, []):
            if obj["id"] in ids:
                raise ValueError("Identificador repetido: " + obj["id"])
            ids.add(obj["id"])
            rect = cells(obj)
            if not rect or any(x < 0 or y < 0 or x >= w or y >= h for x, y in rect):
                raise ValueError("Elemento fuera del mapa: " + obj["id"])
            if occupied.intersection(rect):
                raise ValueError("Elementos superpuestos: " + obj["id"])
            occupied.update(rect)
            if group == "racks" and 2 not in (obj["ancho"], obj["alto"]):
                raise ValueError("Un lado del rack debe medir 2.")
            if group == "puertas":
                x, y = rect[0]
                if x not in (0, w - 1) and y not in (0, h - 1):
                    raise ValueError("Puerta fuera del borde.")
                if obj["tipo"] not in ("INBOUND", "OUTBOUND", "AMBOS"):
                    raise ValueError("Tipo de puerta inválido.")
            if group == "pasillos" and obj["sentido"] not in (
                "N",
                "S",
                "E",
                "O",
                "AMBOS",
            ):
                raise ValueError("Sentido inválido.")
    doors = {p["id"]: p for p in wh["puertas"]}
    for zone in wh["zonas_despacho"]:
        door = doors.get(zone["puerta_id"])
        if not door or zone["peso_max_kg"] <= 0:
            raise ValueError("Despacho sin puerta válida o sin capacidad.")
        px, py = cells(door)[0]
        if not any(abs(x - px) + abs(y - py) == 1 for x, y in cells(zone)):
            raise ValueError("La zona debe ser adyacente a su puerta.")
    racks = {r["id"]: set(cells(r)) for r in wh["racks"]}
    products, locations = {}, set()
    for prod in data["productos"]:
        u = prod["ubicacion"]
        loc = (u["x"], u["y"], u["z"])
        if prod["id"] in products or loc in locations:
            raise ValueError("Producto o ubicación duplicados.")
        if (u["x"], u["y"]) not in racks.get(prod["rack_id"], set()) or u["z"] < 1:
            raise ValueError("Producto fuera de su rack.")
        if prod["peso_kg"] <= 0 or prod["cantidad_disponible"] < 0:
            raise ValueError("Peso o stock inválido.")
        products[prod["id"]] = prod
        locations.add(loc)
    order_ids = set()
    for order in data["pedidos"]:
        if (
            order["id"] in order_ids
            or not 1 <= order["prioridad"] <= 5
            or not order["items"]
        ):
            raise ValueError("Pedido inválido o duplicado.")
        order_ids.add(order["id"])
        for item in order["items"]:
            if item["producto_id"] not in products or item["cantidad"] <= 0:
                raise ValueError("Ítem de pedido inválido.")
    blocked = set().union(
        *(set(cells(a)) for g in ("racks", "puertas", "zonas_despacho") for a in wh[g])
    )
    seen = set()
    positions = set()
    for pk in data["pickers"]:
        pos = pk["posicion_inicial"]
        coord = (pos["x"], pos["y"])
        if (
            pk["id"] in seen
            or coord in positions
            or coord in blocked
            or not (0 <= coord[0] < w and 0 <= coord[1] < h)
            or pk["capacidad_carga_kg"] <= 0
        ):
            raise ValueError("Picker inválido.")
        seen.add(pk["id"])
        positions.add(coord)
    if not data["pickers"]:
        raise ValueError("Se necesita al menos un picker.")
    cfg = data.get("configuracion", {})
    if cfg.get("wave_max_pedidos", 3) < 1 or cfg.get("wave_max_productos", 15) < 1:
        raise ValueError("Límites de waves inválidos.")
    if not any(
        doors[z["puerta_id"]]["tipo"] in ("OUTBOUND", "AMBOS")
        for z in wh["zonas_despacho"]
    ):
        raise ValueError("Debe existir al menos un despacho con puerta de salida.")


def generate(racks=10, products=50, orders=20):
    from FrontEnd.services.backend_adapter import generator_class

    ScenarioGenerator = generator_class()
    if not 1 <= racks <= 30 or not 1 <= products <= 300 or not 1 <= orders <= 100:
        raise ValueError("Usá 1–30 racks, 1–300 productos y 1–100 pedidos.")
    data = ScenarioGenerator.generar_escenario_dict(
        cantidad_estantes=racks,
        cantidad_productos=products,
        cantidad_pedidos=orders,
        cantidad_pasillos=racks + 3,
    )
    validate(data)
    return data
