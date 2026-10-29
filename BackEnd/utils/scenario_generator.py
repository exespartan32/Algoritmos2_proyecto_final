"""Generador automático y DETERMINISTA de escenarios (enunciado, sección 16).

No usa números aleatorios: con los mismos parámetros siempre se obtiene el
mismo warehouse, los mismos productos y los mismos pedidos. Así los
experimentos se pueden repetir y comparar.

Distribución del almacén (el eje y crece hacia arriba)::

    y alto-1  ═══════ pasillo transversal (AMBOS) ═══════
              ║N║ R ║S║ R ║N║ R ║S║    <- fila de racks: pasillos verticales
              ║ ║ R ║ ║ R ║ ║ R ║ ║       de un solo sentido, alternando N y S
              ═══════ pasillo transversal (AMBOS) ═══════
              ...
    y = 3..4  ═══════ pasillo transversal inferior ══════   <- arrancan los pickers
    y = 1..2      [ZONA_A]            [ZONA_B]
    y = 0           PUERTA              PUERTA

- ``cantidad_pasillos`` es la cantidad de pasillos verticales (de picking).
  Entre dos pasillos verticales consecutivos hay una columna de racks, así
  que hay ``cantidad_pasillos - 1`` columnas.
- Cada rack mide 2 x ``alto_rack``: se recoge desde los pasillos de los costados.
- Se garantiza que el mapa sea válido con la misma validación del grafo
  (Kosaraju): una sola componente fuertemente conexa y todos los productos,
  zonas y pickers dentro de ella. Por lo tanto, todo producto se puede
  alcanzar desde la zona de despacho y volver.
"""

import json
import math
from typing import Any, Dict, List, Tuple

from BackEnd.models.warehouse import Warehouse
from BackEnd.utils.graph_builder import GraphBuilder
from BackEnd.utils.validador_escenario import validar_escenario

LOCALIZACIONES = {
    "DISTRIBUIDA": "Repartidos en todo el almacén",
    "CERCA_DESPACHO": "Los primeros, más cerca del despacho",
    "POR_RACK": "Llenando un rack por vez",
}

NOMBRES_PRODUCTOS = [
    "Monitor 27", "Monitor 24", "Teclado Mecánico", "Mouse Inalámbrico",
    "Notebook 14", "Auriculares BT", "Impresora Láser", "Cable HDMI",
    "Webcam HD", "Micrófono USB", "Disco SSD 1TB", "Memoria RAM 16GB",
    "Fuente 650W", "Gabinete ATX", "Placa de Video", "Silla de Oficina",
    "Router WiFi", "Parlantes", "Tablet 10", "Cargador USB-C",
]

ALTO_RACK = 6
ANCHO_RACK = 2
ANCHO_PASILLO = 2
ALTO_TRANSVERSAL = 2
Y_TRANSVERSAL_INFERIOR = 3

LIMITES = {
    "cantidad_estantes": (1, 400),
    "cantidad_pasillos": (2, 40),
    "cantidad_productos": (1, 3000),
    "cantidad_pedidos": (1, 1000),
    "max_productos_por_pedido": (1, 20),
    "wave_max_pedidos": (1, 50),
    "wave_max_productos": (1, 500),
    "cantidad_pickers": (1, 10),
}


class ScenarioGenerator:
    @staticmethod
    def validar_parametros(**params) -> Dict[str, Any]:
        salida = {}
        for clave, (minimo, maximo) in LIMITES.items():
            valor = int(params[clave])
            if not minimo <= valor <= maximo:
                raise ValueError(f"{clave} debe estar entre {minimo} y {maximo}.")
            salida[clave] = valor
        localizacion = str(params.get("localizacion", "DISTRIBUIDA")).upper()
        if localizacion not in LOCALIZACIONES:
            raise ValueError("Localización válida: " + ", ".join(LOCALIZACIONES))
        salida["localizacion"] = localizacion
        if salida["wave_max_productos"] < salida["max_productos_por_pedido"]:
            raise ValueError(
                "La capacidad de productos de la wave debe ser al menos la cantidad máxima de productos por pedido."
            )
        return salida

    @staticmethod
    def generar_escenario_dict(
        cantidad_estantes: int = 12,
        cantidad_pasillos: int = 5,
        cantidad_productos: int = 60,
        localizacion: str = "DISTRIBUIDA",
        cantidad_pedidos: int = 20,
        max_productos_por_pedido: int = 4,
        wave_max_pedidos: int = 4,
        wave_max_productos: int = 20,
        cantidad_pickers: int = 3,
    ) -> Dict[str, Any]:
        p = ScenarioGenerator.validar_parametros(
            cantidad_estantes=cantidad_estantes,
            cantidad_pasillos=cantidad_pasillos,
            cantidad_productos=cantidad_productos,
            localizacion=localizacion,
            cantidad_pedidos=cantidad_pedidos,
            max_productos_por_pedido=max_productos_por_pedido,
            wave_max_pedidos=wave_max_pedidos,
            wave_max_productos=wave_max_productos,
            cantidad_pickers=cantidad_pickers,
        )
        columnas = p["cantidad_pasillos"] - 1
        filas = math.ceil(p["cantidad_estantes"] / columnas)
        paso_x = ANCHO_PASILLO + ANCHO_RACK
        ancho_x = columnas * paso_x + ANCHO_PASILLO
        y_primera_fila = Y_TRANSVERSAL_INFERIOR + ALTO_TRANSVERSAL
        largo_y = y_primera_fila + filas * (ALTO_RACK + ALTO_TRANSVERSAL)
        if ancho_x > 200 or largo_y > 200:
            raise ValueError("El almacén resultante supera 200 x 200 celdas. Usá menos estantes o pasillos.")

        # ---- Puertas y zonas de despacho (abajo) ------------------------
        cantidad_zonas = 1 if ancho_x < 16 else 2
        puertas, zonas = [], []
        for i in range(cantidad_zonas):
            x_puerta = round((i + 0.5) * ancho_x / cantidad_zonas)
            x_puerta = min(max(x_puerta, 2), ancho_x - 3)
            ancho_zona = min(5, ancho_x - 2)
            x_zona = min(max(x_puerta - ancho_zona // 2, 0), ancho_x - ancho_zona)
            letra = chr(ord("A") + i)
            puertas.append({"id": f"PUERTA_{letra}", "tipo": "OUTBOUND", "ubicacion": {"x": x_puerta, "y": 0}})
            zonas.append(
                {
                    "id": f"ZONA_{letra}",
                    "puerta_id": f"PUERTA_{letra}",
                    "ubicacion": {"x": x_zona, "y": 1},
                    "ancho": ancho_zona,
                    "alto": 2,
                    "peso_max_kg": 0.0,  # se completa al final según los pedidos
                }
            )

        # ---- Pasillos y racks --------------------------------------------
        pasillos = [
            {
                "id": "PAS_T0",
                "ubicacion": {"x": 0, "y": Y_TRANSVERSAL_INFERIOR},
                "ancho": ancho_x,
                "alto": ALTO_TRANSVERSAL,
                "sentido": "AMBOS",
            }
        ]
        racks: List[Dict[str, Any]] = []
        for f in range(filas):
            y_fila = y_primera_fila + f * (ALTO_RACK + ALTO_TRANSVERSAL)
            for c in range(columnas + 1):
                pasillos.append(
                    {
                        "id": f"PAS_V{c:02d}_F{f}",
                        "ubicacion": {"x": c * paso_x, "y": y_fila},
                        "ancho": ANCHO_PASILLO,
                        "alto": ALTO_RACK,
                        # De un solo sentido, alternando (como un almacén real).
                        "sentido": "N" if (c + f) % 2 == 0 else "S",
                    }
                )
            for c in range(columnas):
                if len(racks) == p["cantidad_estantes"]:
                    break
                racks.append(
                    {
                        "id": f"R{len(racks) + 1:02d}",
                        "ubicacion": {"x": c * paso_x + ANCHO_PASILLO, "y": y_fila},
                        "ancho": ANCHO_RACK,
                        "alto": ALTO_RACK,
                    }
                )
            pasillos.append(
                {
                    "id": f"PAS_T{f + 1}",
                    "ubicacion": {"x": 0, "y": y_fila + ALTO_RACK},
                    "ancho": ancho_x,
                    "alto": ALTO_TRANSVERSAL,
                    "sentido": "AMBOS",
                }
            )

        # ---- Productos -----------------------------------------------------
        celdas = ScenarioGenerator._celdas_ordenadas(racks, zonas, p["localizacion"])
        productos = []
        nivel_por_celda: Dict[Tuple[int, int], int] = {}
        n = p["cantidad_productos"]
        for i in range(n):
            if p["localizacion"] == "DISTRIBUIDA":
                # Recorre las celdas con un salto fijo para repartir parejo.
                rack_id, x, y = celdas[(i * len(celdas)) // n if n <= len(celdas) else i % len(celdas)]
            else:
                rack_id, x, y = celdas[i % len(celdas)]
            z = nivel_por_celda.get((x, y), 0) + 1
            nivel_por_celda[(x, y)] = z
            productos.append(
                {
                    "id": f"P{i + 1:03d}",
                    "nombre": NOMBRES_PRODUCTOS[i % len(NOMBRES_PRODUCTOS)],
                    "rack_id": rack_id,
                    "ubicacion": {"x": x, "y": y, "z": z},
                    "cantidad_disponible": 0,  # se completa con la demanda
                    "peso_kg": round(0.3 + ((i * 37) % 60) / 10, 2),
                }
            )

        # ---- Pedidos ------------------------------------------------------
        pedidos = []
        demanda = [0] * n
        salto = ScenarioGenerator._coprimo(n)
        for j in range(p["cantidad_pedidos"]):
            maximo = min(p["max_productos_por_pedido"], n)
            cantidad_items = 1 + (j * 3) % maximo
            inicio = (j * 17) % n
            items = []
            unidades = 0
            for t in range(cantidad_items):
                indice = (inicio + t * salto) % n
                cantidad = 1 + (j + t) % 3
                if unidades + cantidad > p["wave_max_productos"]:
                    break
                unidades += cantidad
                demanda[indice] += cantidad
                items.append({"producto_id": productos[indice]["id"], "cantidad": cantidad})
            pedidos.append(
                {
                    "id": f"PED_{j + 1:02d}",
                    "prioridad": 1 + (j * 2 + j // 5) % 5,
                    "estado": "PENDIENTE",
                    "items": items,
                }
            )
        for i, prod in enumerate(productos):
            prod["cantidad_disponible"] = demanda[i] + 5 + (i * 7) % 20

        pesos = {prod["id"]: prod["peso_kg"] for prod in productos}
        peso_pedidos = [
            sum(pesos[it["producto_id"]] * it["cantidad"] for it in ped["items"]) for ped in pedidos
        ]
        peso_total = sum(peso_pedidos)
        for zona in zonas:
            zona["peso_max_kg"] = round(max(500.0, peso_total), 1)

        # ---- Pickers (sobre el pasillo transversal inferior) -------------------
        capacidad = float(max(150, math.ceil(max(peso_pedidos, default=0) * 1.5)))
        pickers = []
        usados = set()
        for k in range(p["cantidad_pickers"]):
            x = min(ancho_x - 1, int((k + 0.5) * ancho_x / p["cantidad_pickers"]))
            y = Y_TRANSVERSAL_INFERIOR + (k % 2)
            while (x, y) in usados:
                x = (x + 1) % ancho_x
            usados.add((x, y))
            pickers.append(
                {"id": f"PK_{k + 1:02d}", "posicion_inicial": {"x": x, "y": y}, "capacidad_carga_kg": capacidad}
            )

        datos = {
            "warehouse": {
                "dimensiones": {"ancho_x": ancho_x, "largo_y": largo_y},
                "puertas": puertas,
                "zonas_despacho": zonas,
                "racks": racks,
                "pasillos": pasillos,
            },
            "pickers": pickers,
            "productos": productos,
            "pedidos": pedidos,
            "configuracion": {
                "wave_max_pedidos": p["wave_max_pedidos"],
                "wave_max_productos": p["wave_max_productos"],
            },
            "_generador": dict(p),
        }
        ScenarioGenerator.verificar(datos)
        return datos

    @staticmethod
    def _celdas_ordenadas(racks, zonas, localizacion) -> List[Tuple[str, int, int]]:
        celdas = [
            (r["id"], x, y)
            for r in racks
            for x in range(r["ubicacion"]["x"], r["ubicacion"]["x"] + r["ancho"])
            for y in range(r["ubicacion"]["y"], r["ubicacion"]["y"] + r["alto"])
        ]
        if localizacion == "CERCA_DESPACHO":
            centros = [
                (z["ubicacion"]["x"] + z["ancho"] / 2, z["ubicacion"]["y"] + z["alto"] / 2) for z in zonas
            ]
            celdas.sort(
                key=lambda c: (min(abs(c[1] - cx) + abs(c[2] - cy) for cx, cy in centros), c[2], c[1])
            )
        elif localizacion == "DISTRIBUIDA":
            # Intercala racks: celda 0 de cada rack, luego la 1, etc.
            por_rack: Dict[str, List[Tuple[str, int, int]]] = {}
            for celda in celdas:
                por_rack.setdefault(celda[0], []).append(celda)
            listas = list(por_rack.values())
            celdas = [lst[i] for i in range(max(map(len, listas))) for lst in listas if i < len(lst)]
        return celdas

    @staticmethod
    def _coprimo(n: int) -> int:
        """Salto que recorre todos los productos sin repetir (mcd(salto, n) = 1)."""
        salto = max(1, n // 3 + 1)
        while math.gcd(salto, n) != 1:
            salto += 1
        return salto

    @staticmethod
    def verificar(datos: Dict[str, Any]) -> Warehouse:
        """Construye el warehouse y falla si tiene cualquier advertencia."""
        validar_escenario(datos)
        wh = GraphBuilder.construir_warehouse_desde_dict(datos)
        if wh.advertencias:
            raise ValueError("El escenario generado no es válido: " + "; ".join(wh.advertencias))
        return wh

    @staticmethod
    def generar_y_guardar(ruta_json: str, **params) -> Dict[str, Any]:
        datos = ScenarioGenerator.generar_escenario_dict(**params)
        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        return datos
