import json
from typing import Dict, Any
from BackEnd.models.warehouse import Warehouse
from BackEnd.utils.graph_builder import GraphBuilder

class FileParser:
    @staticmethod
    def leer_json(ruta_archivo: str) -> Dict[str, Any]:
        with open(ruta_archivo, "r", encoding="utf-8") as archivo:
            return json.load(archivo)

    @staticmethod
    def cargar_warehouse_desde_json(ruta_archivo: str) -> Warehouse:
        datos = FileParser.leer_json(ruta_archivo)
        return GraphBuilder.construir_warehouse_desde_dict(datos)