"""Validación de estructura, rangos y geometría de un escenario JSON."""

import math

from BackEnd.enums.enums import EstadoPedido

ESTADOS_PEDIDO = {e.value for e in EstadoPedido}


def celdas(item):
    return [
        (x, y)
        for x in range(
            item["ubicacion"]["x"], item["ubicacion"]["x"] + item.get("ancho", 1)
        )
        for y in range(
            item["ubicacion"]["y"], item["ubicacion"]["y"] + item.get("alto", 1)
        )
    ]


def validar_escenario(data):
    """Lanza ValueError con un mensaje descriptivo si el escenario tiene inconsistencias."""
    try:
        _validar(data)
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError(
            f"Formato de escenario inválido (campo faltante o mal escrito: {exc})."
        ) from None


def _validar(data):
    def entero(valor, minimo=0, maximo=1000000):
        if type(valor) is not int or not minimo <= valor <= maximo:
            raise ValueError("Se esperaba un entero dentro del rango permitido.")

    def positivo(valor):
        if type(valor) not in (int, float) or not math.isfinite(valor) or valor <= 0:
            raise ValueError("Peso o capacidad inválidos.")

    wh = data["warehouse"]
    entero(wh["dimensiones"]["ancho_x"], 1, 200)
    entero(wh["dimensiones"]["largo_y"], 1, 200)

    for grupo in ("racks", "puertas", "zonas_despacho", "pasillos"):
        for obj in wh[grupo]:
            if not isinstance(obj["id"], str) or not obj["id"]:
                raise ValueError("Los identificadores deben ser textos no vacíos.")
            for eje in ("x", "y"):
                entero(obj["ubicacion"][eje], 0, 199)
            if grupo != "puertas":
                entero(obj["ancho"], 1, 200)
                entero(obj["alto"], 1, 200)

    for prod in data["productos"]:
        entero(prod["cantidad_disponible"])
        entero(prod["ubicacion"]["z"], 1)
        entero(prod["ubicacion"]["x"], 0, 199)
        entero(prod["ubicacion"]["y"], 0, 199)
        positivo(prod["peso_kg"])

    for ped in data["pedidos"]:
        entero(ped["prioridad"], 1, 5)
        if ped.get("estado", "PENDIENTE") not in ESTADOS_PEDIDO:
            raise ValueError("Estado de pedido inválido: " + str(ped.get("estado")))
        vistos = set()
        for item in ped["items"]:
            entero(item["cantidad"], 1)
            if item["producto_id"] in vistos:
                raise ValueError(
                    "Agrupá los ítems repetidos de un mismo producto dentro del pedido."
                )
            vistos.add(item["producto_id"])

    for picker in data["pickers"]:
        positivo(picker["capacidad_carga_kg"])
        for eje in ("x", "y"):
            entero(picker["posicion_inicial"][eje], 0, 199)

    for zona in wh["zonas_despacho"]:
        positivo(zona["peso_max_kg"])

    for clave, valor in data.get("configuracion", {}).items():
        if clave in ("wave_max_pedidos", "wave_max_productos", "max_pickers_por_wave"):
            entero(valor, 1)

    w, h = wh["dimensiones"]["ancho_x"], wh["dimensiones"]["largo_y"]
    if not (
        isinstance(w, int) and isinstance(h, int) and 1 <= w <= 200 and 1 <= h <= 200
    ):
        raise ValueError("Dimensiones permitidas: de 1 a 200 celdas.")

    ocupadas, ids = set(), set()
    for grupo in ("racks", "puertas", "zonas_despacho", "pasillos"):
        for obj in wh.get(grupo, []):
            if obj["id"] in ids:
                raise ValueError("Identificador repetido: " + obj["id"])
            ids.add(obj["id"])
            rect = celdas(obj)
            if not rect or any(x < 0 or y < 0 or x >= w or y >= h for x, y in rect):
                raise ValueError("Elemento fuera del mapa: " + obj["id"])
            if grupo != "pasillos" and ocupadas.intersection(rect):
                raise ValueError("Elementos superpuestos: " + obj["id"])
            if grupo != "pasillos":
                ocupadas.update(rect)
            if grupo == "racks" and 2 not in (obj["ancho"], obj["alto"]):
                raise ValueError("Un lado del rack debe medir 2.")
            if grupo == "puertas":
                x, y = rect[0]
                if x not in (0, w - 1) and y not in (0, h - 1):
                    raise ValueError("Puerta fuera del borde.")
                if obj["tipo"] not in ("INBOUND", "OUTBOUND", "AMBOS"):
                    raise ValueError("Tipo de puerta inválido.")
            if grupo == "pasillos" and obj["sentido"] not in (
                "N",
                "S",
                "E",
                "O",
                "AMBOS",
            ):
                raise ValueError("Sentido inválido.")

    puertas = {p["id"]: p for p in wh["puertas"]}
    for zona in wh["zonas_despacho"]:
        puerta = puertas.get(zona["puerta_id"])
        if not puerta or zona["peso_max_kg"] <= 0:
            raise ValueError("Despacho sin puerta válida o sin capacidad.")
        px, py = celdas(puerta)[0]
        if not any(abs(x - px) + abs(y - py) == 1 for x, y in celdas(zona)):
            raise ValueError("La zona debe ser adyacente a su puerta.")

    racks = {r["id"]: set(celdas(r)) for r in wh["racks"]}
    productos, ubicaciones = {}, set()
    for prod in data["productos"]:
        u = prod["ubicacion"]
        loc = (u["x"], u["y"], u["z"])
        if prod["id"] in productos or loc in ubicaciones:
            raise ValueError("Producto o ubicación duplicados.")
        if (u["x"], u["y"]) not in racks.get(prod["rack_id"], set()) or u["z"] < 1:
            raise ValueError("Producto fuera de su rack.")
        if prod["peso_kg"] <= 0 or prod["cantidad_disponible"] < 0:
            raise ValueError("Peso o stock inválido.")
        productos[prod["id"]] = prod
        ubicaciones.add(loc)

    ids_pedidos = set()
    for ped in data["pedidos"]:
        if (
            ped["id"] in ids_pedidos
            or not 1 <= ped["prioridad"] <= 5
            or not ped["items"]
        ):
            raise ValueError("Pedido inválido o duplicado.")
        ids_pedidos.add(ped["id"])
        for item in ped["items"]:
            if item["producto_id"] not in productos or item["cantidad"] <= 0:
                raise ValueError("Ítem de pedido inválido.")

    bloqueadas = set().union(
        *(set(celdas(a)) for g in ("racks", "puertas", "zonas_despacho") for a in wh[g])
    )
    pickers_vistos, posiciones = set(), set()
    for pk in data["pickers"]:
        pos = pk["posicion_inicial"]
        coord = (pos["x"], pos["y"])
        if (
            pk["id"] in pickers_vistos
            or coord in posiciones
            or coord in bloqueadas
            or not (0 <= coord[0] < w and 0 <= coord[1] < h)
            or pk["capacidad_carga_kg"] <= 0
        ):
            raise ValueError("Picker inválido.")
        pickers_vistos.add(pk["id"])
        posiciones.add(coord)

    if not data["pickers"]:
        raise ValueError("Se necesita al menos un picker.")

    cfg = data.get("configuracion", {})
    if cfg.get("wave_max_pedidos", 3) < 1 or cfg.get("wave_max_productos", 15) < 1:
        raise ValueError("Límites de waves inválidos.")

    if not any(
        puertas[z["puerta_id"]]["tipo"] in ("OUTBOUND", "AMBOS")
        for z in wh["zonas_despacho"]
    ):
        raise ValueError("Debe existir al menos un despacho con puerta de salida.")
