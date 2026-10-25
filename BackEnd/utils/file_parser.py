import os
import json
from typing import Dict, Any
from BackEnd.models.warehouse import Warehouse
from BackEnd.utils.graph_builder import GraphBuilder


class FileParser:
    @staticmethod
    def resolver_ruta(nombre_o_ruta: str) -> str:
        if os.path.isfile(nombre_o_ruta):
            return os.path.abspath(nombre_o_ruta)
        dir_actual = os.path.dirname(os.path.abspath(__file__))
        ruta_data = os.path.join(os.path.dirname(dir_actual), "data")
        return os.path.abspath(os.path.join(ruta_data, nombre_o_ruta))

    @staticmethod
    def leer_json(ruta_archivo: str) -> Dict[str, Any]:
        ruta_resuelta = FileParser.resolver_ruta(ruta_archivo)
        with open(ruta_resuelta, "r", encoding="utf-8") as archivo:
            return json.load(archivo)

    @staticmethod
    def cargar_warehouse_desde_json(ruta_archivo: str) -> Warehouse:
        datos = FileParser.leer_json(ruta_archivo)
        return GraphBuilder.construir_warehouse_desde_dict(datos)

    @staticmethod
    def guardar_estado_warehouse_json(
        warehouse: Warehouse, nombre_archivo_salida: str = "estado_guardado.json"
    ) -> str:
        """
        Exporta el estado actual del Warehouse (con stock y estados de pedidos actualizados)
        a un archivo JSON sin pisar los archivos base (escenario_basico.json / escenario_grande.json).
        """
        dir_actual = os.path.dirname(os.path.abspath(__file__))
        ruta_data = os.path.join(os.path.dirname(dir_actual), "data")
        os.makedirs(ruta_data, exist_ok=True)

        ruta_salida = (
            os.path.abspath(nombre_archivo_salida)
            if os.path.isabs(nombre_archivo_salida)
            else os.path.abspath(os.path.join(ruta_data, nombre_archivo_salida))
        )

        productos_json = [
            {
                "id": p.id_producto,
                "nombre": p.nombre,
                "rack_id": p.rack_id,
                "ubicacion": {
                    "x": p.ubicacion_x,
                    "y": p.ubicacion_y,
                    "z": p.ubicacion_z,
                },
                "cantidad_disponible": p.cantidad_disponible,
                "peso_kg": p.peso_kg,
            }
            for p in warehouse.obtener_todos_los_productos()
        ]

        pedidos_json = [
            {
                "id": ped.id_pedido,
                "prioridad": ped.prioridad,
                "estado": ped.estado.value,
                "items": [
                    {"producto_id": it.producto_id, "cantidad": it.cantidad}
                    for it in ped.items
                ],
            }
            for ped in warehouse.obtener_todos_los_pedidos()
        ]

        pickers_json = [
            {
                "id": pk.id_picker,
                "posicion_inicial": {
                    "x": pk.posicion_actual[0],
                    "y": pk.posicion_actual[1],
                },
                "capacidad_carga_kg": pk.capacidad_carga_kg,
            }
            for pk in warehouse.pickers
        ]

        estado_exportado = {
            "warehouse": warehouse.warehouse_raw,
            "pickers": pickers_json,
            "productos": productos_json,
            "pedidos": pedidos_json,
            "configuracion": {
                "wave_max_pedidos": warehouse.wave_max_pedidos,
                "wave_max_productos": warehouse.wave_max_productos,
            },
        }

        with open(ruta_salida, "w", encoding="utf-8") as f:
            json.dump(estado_exportado, f, indent=2, ensure_ascii=False)

        return ruta_salida
