import json
from typing import Dict, List, Tuple, Any
from BackEnd.models.warehouse_models import (
    Warehouse,
    Rack,
    Pasillo,
    Puerta,
    zonaDespacho,
)
from BackEnd.models.catalog_manager import CatalogManager
from BackEnd.models.entities import Picker, Wave
from BackEnd.enums.enums import SentidoCirculacion, TipoPuerta


class PersistenceAndGenerator:
    def cargar_escenario_json(
        self, ruta: str
    ) -> Tuple[Warehouse, CatalogManager, List[Picker]]:
        with open(ruta, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)

        wh_data = datos["warehouse"]
        dim = wh_data["dimensiones"]
        warehouse = Warehouse(ancho_x=int(dim["ancho_x"]), largo_y=int(dim["largo_y"]))

        for puerta in wh_data.get("puertas", []):
            warehouse.puertas[puerta["id"]] = Puerta(
                id_puerta=puerta["id"],
                tipo=TipoPuerta(puerta["tipo"]),
                ubicacion_x=int(puerta["ubicacion"]["x"]),
                ubicacion_y=int(puerta["ubicacion"]["y"]),
            )

        for zonaDespacho in wh_data.get("zonas_despacho", []):
            warehouse.zonas_despacho[zonaDespacho["id"]] = zonaDespacho(
                id_zona=zonaDespacho["id"],
                puerta_id=zonaDespacho["puerta_id"],
                ubicacion_x=int(zonaDespacho["ubicacion"]["x"]),
                ubicacion_y=int(zonaDespacho["ubicacion"]["y"]),
                ancho=int(zonaDespacho["ancho"]),
                alto=int(zonaDespacho["alto"]),
                peso_max_kg=float(zonaDespacho["peso_max_kg"]),
            )

        for racks in wh_data.get("racks", []):
            warehouse.racks[racks["id"]] = Rack(
                id_rack=racks["id"],
                ubicacion_x=int(racks["ubicacion"]["x"]),
                ubicacion_y=int(racks["ubicacion"]["y"]),
                ancho=int(racks["ancho"]),
                alto=int(racks["alto"]),
            )

        for pasillo in wh_data.get("pasillos", []):
            warehouse.pasillos[pasillo["id"]] = Pasillo(
                id_pasillo=pasillo["id"],
                ubicacion_x=int(pasillo["ubicacion"]["x"]),
                ubicacion_y=int(pasillo["ubicacion"]["y"]),
                ancho=int(pasillo["ancho"]),
                alto=int(pasillo["alto"]),
                sentido=SentidoCirculacion(pasillo["sentido"]),
            )

        warehouse.poblar_grilla_y_grafo()

        catalogo = CatalogManager()
        catalogo.cargar_productos_desde_json(datos.get("productos", []))
        catalogo.cargar_pedidos_desde_json(datos.get("pedidos", []))

        pickers: List[Picker] = []
        for picker in datos.get("pickers", []):
            pos = (
                int(picker["posicion_inicial"]["x"]),
                int(picker["posicion_inicial"]["y"]),
            )
            pickers.append(
                Picker(
                    id_picker=picker["id"],
                    posicion_inicial=pos,
                    posicion_actual=pos,
                    capacidad_carga_kg=float(picker["capacidad_carga_kg"]),
                )
            )

        return warehouse, catalogo, pickers

    def guardar_escenario_json(
        self,
        ruta: str,
        warehouse: Warehouse,
        catalogo: CatalogManager,
        pickers: List[Picker],
        waves: List[Wave] = None,
        sim: Any = None,
    ) -> None:
        estado_json = {
            "warehouse": warehouse.to_dict(),
            "pickers": [p.to_dict() for p in pickers],
            "productos": catalogo.decodificar_productos_a_json(),
            "pedidos": catalogo.decodificar_pedidos_a_json(),
        }

        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump(estado_json, archivo, indent=2, ensure_ascii=False)
