import json
import math
import random
from typing import Dict, Any, List, Tuple
from BackEnd.models.warehouse import Warehouse
from BackEnd.utils.graph_builder import GraphBuilder


class ScenarioGenerator:
    """
    Sección 16: Generador automático de escenarios de Warehouse válidos.
    """
    NOMBRES_PRODUCTOS = [
        "Monitor 27", "Monitor 24", "Teclado Mecánico", "Mouse Gamer",
        "Notebook 14", "Auriculares BT", "Impresora Láser", "Cable HDMI",
        "Webcam HD", "Micrófono USB", "Disco SSD 1TB", "Memoria RAM 16GB",
        "Fuente 650W", "Gabinete ATX", "Placa de Video", "Silla Oficina"
    ]

    @staticmethod
    def generar_escenario_dict(
        cantidad_estantes: int = 6,
        cantidad_pasillos: int = 9,
        cantidad_productos: int = 30,
        modo_localizacion: str = "ALEATORIO",
        cantidad_pedidos: int = 10,
        max_productos_por_pedido: int = 4,
        wave_max_pedidos: int = 3,
        wave_max_productos: int = 15,
        alto_rack: int = 6
    ) -> Dict[str, Any]:
        cantidad_estantes = max(1, cantidad_estantes)
        cols = min(cantidad_estantes, max(2, int(math.ceil(math.sqrt(cantidad_estantes * 1.5)))))
        filas = int(math.ceil(cantidad_estantes / cols))

        ancho_rack = 2
        ancho_pasillo_v = 3
        alto_pasillo_h = 2

        ancho_x = cols * (ancho_pasillo_v + ancho_rack) + ancho_pasillo_v
        y_base_pasillo_inf = 3
        largo_y = y_base_pasillo_inf + alto_pasillo_h + filas * (alto_rack + alto_pasillo_h)

        x_puerta_out = max(2, ancho_x // 4)
        puertas = [
            {
                "id": "PUERTA_OUT_1",
                "tipo": "OUTBOUND",
                "ubicacion": {"x": x_puerta_out, "y": 0}
            }
        ]
        zonas_despacho = [
            {
                "id": "ZONA_A",
                "puerta_id": "PUERTA_OUT_1",
                "ubicacion": {"x": max(1, x_puerta_out - 2), "y": 1},
                "ancho": 5,
                "alto": 2,
                "peso_max_kg": 800.0
            }
        ]

        if ancho_x >= 16:
            x_puerta_in = min(ancho_x - 4, (ancho_x * 3) // 4)
            puertas.append({
                "id": "PUERTA_IN_1",
                "tipo": "INBOUND",
                "ubicacion": {"x": x_puerta_in, "y": 0}
            })
            zonas_despacho.append({
                "id": "ZONA_B",
                "puerta_id": "PUERTA_IN_1",
                "ubicacion": {"x": x_puerta_in - 2, "y": 1},
                "ancho": 5,
                "alto": 2,
                "peso_max_kg": 800.0
            })

        racks = []
        pasillos = []
        celdas_racks_disponibles: List[Tuple[str, int, int]] = []

        pasillos.append({
            "id": "PAS_H_0",
            "ubicacion": {"x": 0, "y": y_base_pasillo_inf},
            "ancho": ancho_x,
            "alto": alto_pasillo_h,
            "sentido": "AMBOS"
        })

        racks_creados = 0
        for f in range(filas):
            y_fila_rack = y_base_pasillo_inf + alto_pasillo_h + f * (alto_rack + alto_pasillo_h)

            for c in range(cols + 1):
                x_pas_v = c * (ancho_pasillo_v + ancho_rack)
                sentido_v = "N" if (c + f) % 2 == 0 else "S"
                if len(pasillos) < cantidad_pasillos or c in (0, cols):
                    pasillos.append({
                        "id": f"PAS_V_{f}_{c}",
                        "ubicacion": {"x": x_pas_v, "y": y_fila_rack},
                        "ancho": ancho_pasillo_v,
                        "alto": alto_rack,
                        "sentido": sentido_v
                    })

            for c in range(cols):
                if racks_creados >= cantidad_estantes:
                    break
                racks_creados += 1
                rack_id = f"R{racks_creados:02d}"
                x_rack = ancho_pasillo_v + c * (ancho_pasillo_v + ancho_rack)

                racks.append({
                    "id": rack_id,
                    "ubicacion": {"x": x_rack, "y": y_fila_rack},
                    "ancho": ancho_rack,
                    "alto": alto_rack
                })

                for rx in range(x_rack, x_rack + ancho_rack):
                    for ry in range(y_fila_rack, y_fila_rack + alto_rack):
                        celdas_racks_disponibles.append((rack_id, rx, ry))

            y_pas_h_sup = y_fila_rack + alto_rack
            pasillos.append({
                "id": f"PAS_H_{f + 1}",
                "ubicacion": {"x": 0, "y": y_pas_h_sup},
                "ancho": ancho_x,
                "alto": alto_pasillo_h,
                "sentido": "AMBOS"
            })

        if modo_localizacion == "CERCA_DESPACHO":
            celdas_racks_disponibles.sort(key=lambda item: (item[2], item[1]))
            pool_celdas = celdas_racks_disponibles[:max(1, len(celdas_racks_disponibles) // 2)]
        elif modo_localizacion == "DISPERSO":
            random.shuffle(celdas_racks_disponibles)
            pool_celdas = celdas_racks_disponibles
        else:
            pool_celdas = celdas_racks_disponibles

        altura_actual_por_celda: Dict[Tuple[int, int], int] = {}
        productos = []

        for i in range(1, cantidad_productos + 1):
            if modo_localizacion == "DISPERSO" and i <= len(pool_celdas):
                rack_id, px, py = pool_celdas[i - 1]
            else:
                rack_id, px, py = random.choice(pool_celdas)

            z_actual = altura_actual_por_celda.get((px, py), 0) + 1
            altura_actual_por_celda[(px, py)] = z_actual

            productos.append({
                "id": f"P{i:03d}",
                "nombre": random.choice(ScenarioGenerator.NOMBRES_PRODUCTOS),
                "rack_id": rack_id,
                "ubicacion": {"x": px, "y": py, "z": z_actual},
                "cantidad_disponible": random.randint(15, 60),
                "peso_kg": round(random.uniform(0.2, 8.0), 2)
            })

        pickers = [
            {
                "id": "PK_01",
                "posicion_inicial": {"x": 1, "y": y_base_pasillo_inf},
                "capacidad_carga_kg": 150.0
            }
        ]
        if ancho_x >= 12:
            pickers.append({
                "id": "PK_02",
                "posicion_inicial": {"x": ancho_x - 2, "y": y_base_pasillo_inf},
                "capacidad_carga_kg": 120.0
            })

        pedidos = []
        ids_productos = [p["id"] for p in productos]
        for j in range(1, cantidad_pedidos + 1):
            cant_items = random.randint(1, min(max_productos_por_pedido, len(ids_productos)))
            prods_elegidos = random.sample(ids_productos, cant_items)
            items_pedido = [
                {"producto_id": pid, "cantidad": random.randint(1, 3)}
                for pid in prods_elegidos
            ]
            pedidos.append({
                "id": f"PED_{j:02d}",
                "prioridad": random.randint(1, 5),
                "estado": "PENDIENTE",
                "items": items_pedido
            })

        return {
            "warehouse": {
                "dimensiones": {"ancho_x": ancho_x, "largo_y": largo_y},
                "puertas": puertas,
                "zonas_despacho": zonas_despacho,
                "racks": racks,
                "pasillos": pasillos
            },
            "pickers": pickers,
            "productos": productos,
            "pedidos": pedidos,
            "configuracion": {
                "wave_max_pedidos": wave_max_pedidos,
                "wave_max_productos": wave_max_productos
            }
        }

    @staticmethod
    def generar_y_validar_warehouse(
        ruta_guardado_json: str = None,
        **kwargs
    ) -> Tuple[Warehouse, bool]:
        datos = ScenarioGenerator.generar_escenario_dict(**kwargs)
        wh = GraphBuilder.construir_warehouse_desde_dict(datos)

        # El escenario es válido si la construcción no dejó advertencias: eso implica
        # una sola componente fuertemente conexa (ida y vuelta entre cualquier par de
        # pasillos), y que todos los productos, zonas y pickers estén en esa red.
        es_valido = not wh.advertencias

        if ruta_guardado_json and es_valido:
            with open(ruta_guardado_json, "w", encoding="utf-8") as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)

        return wh, es_valido