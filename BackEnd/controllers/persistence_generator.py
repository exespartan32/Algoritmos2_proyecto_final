import json
from typing import Dict, List, Tuple, Any
from BackEnd.models.warehouse_models import (
    Warehouse,
    Rack,
    Pasillo,
    Puerta,
    ZonaDespacho,
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

        for pta in wh_data.get("puertas", []):
            warehouse.puertas[pta["id"]] = Puerta(
                id_puerta=pta["id"],
                tipo=TipoPuerta(pta["tipo"]),
                ubicacion_x=int(pta["ubicacion"]["x"]),
                ubicacion_y=int(pta["ubicacion"]["y"]),
            )

        for zd in wh_data.get("zonas_despacho", []):
            warehouse.zonas_despacho[zd["id"]] = ZonaDespacho(
                id_zona=zd["id"],
                puerta_id=zd["puerta_id"],
                ubicacion_x=int(zd["ubicacion"]["x"]),
                ubicacion_y=int(zd["ubicacion"]["y"]),
                ancho=int(zd["ancho"]),
                alto=int(zd["alto"]),
                peso_max_kg=float(zd["peso_max_kg"]),
            )

        for r in wh_data.get("racks", []):
            warehouse.racks[r["id"]] = Rack(
                id_rack=r["id"],
                ubicacion_x=int(r["ubicacion"]["x"]),
                ubicacion_y=int(r["ubicacion"]["y"]),
                ancho=int(r["ancho"]),
                alto=int(r["alto"]),
            )

        for pas in wh_data.get("pasillos", []):
            warehouse.pasillos[pas["id"]] = Pasillo(
                id_pasillo=pas["id"],
                ubicacion_x=int(pas["ubicacion"]["x"]),
                ubicacion_y=int(pas["ubicacion"]["y"]),
                ancho=int(pas["ancho"]),
                alto=int(pas["alto"]),
                sentido=SentidoCirculacion(pas["sentido"]),
            )

        warehouse.poblar_grilla_y_grafo()

        catalogo = CatalogManager()
        catalogo.cargar_productos_desde_json(datos.get("productos", []))
        catalogo.cargar_pedidos_desde_json(datos.get("pedidos", []))

        pickers: List[Picker] = []
        for pk in datos.get("pickers", []):
            pos = (int(pk["posicion_inicial"]["x"]), int(pk["posicion_inicial"]["y"]))
            pickers.append(
                Picker(
                    id_picker=pk["id"],
                    posicion_inicial=pos,
                    posicion_actual=pos,
                    capacidad_carga_kg=float(pk["capacidad_carga_kg"]),
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
