"""Pruebas del generador determinista de escenarios y del validador."""

import itertools
import unittest

from BackEnd.utils.graph_builder import GraphBuilder
from BackEnd.utils.scenario_generator import LOCALIZACIONES, ScenarioGenerator
from BackEnd.utils.validador_escenario import validar_escenario


class TestGenerador(unittest.TestCase):
    def test_es_determinista(self):
        a = ScenarioGenerator.generar_escenario_dict(12, 5, 60, "DISTRIBUIDA", 20, 4, 4, 20, 3)
        b = ScenarioGenerator.generar_escenario_dict(12, 5, 60, "DISTRIBUIDA", 20, 4, 4, 20, 3)
        self.assertEqual(a, b)

    def test_respeta_los_parametros(self):
        d = ScenarioGenerator.generar_escenario_dict(9, 4, 70, "POR_RACK", 25, 3, 5, 12, 2)
        self.assertEqual(len(d["warehouse"]["racks"]), 9)
        verticales = {p["ubicacion"]["x"] for p in d["warehouse"]["pasillos"] if p["sentido"] in ("N", "S")}
        self.assertEqual(len(verticales), 4)
        self.assertEqual(len(d["productos"]), 70)
        self.assertEqual(len(d["pedidos"]), 25)
        self.assertEqual(len(d["pickers"]), 2)
        self.assertTrue(all(1 <= len(p["items"]) <= 3 for p in d["pedidos"]))
        self.assertTrue(all(sum(i["cantidad"] for i in p["items"]) <= 12 for p in d["pedidos"]))
        self.assertEqual(d["configuracion"], {"wave_max_pedidos": 5, "wave_max_productos": 12})

    def test_siempre_valido_y_alcanzable(self):
        for est, pas, prod, loc in itertools.product([1, 7, 20], [2, 3, 7], [1, 45, 400], LOCALIZACIONES):
            d = ScenarioGenerator.generar_escenario_dict(est, pas, prod, loc, 10, 4, 4, 20, 3)
            validar_escenario(d)
            wh = GraphBuilder.construir_warehouse_desde_dict(d)
            self.assertEqual(wh.advertencias, [])
            self.assertEqual(len(GraphBuilder.componentes_fuertemente_conexas(wh)), 1)
            for p in wh.catalogo_productos.values():
                self.assertIn(wh.obtener_nodo_acceso_producto(p.id), wh.grafo_pasillos.nodos)

    def test_cerca_del_despacho_ubica_mas_cerca(self):
        def distancia_media(loc):
            d = ScenarioGenerator.generar_escenario_dict(20, 6, 30, loc, 5, 2, 4, 20, 1)
            return sum(p["ubicacion"]["y"] for p in d["productos"]) / 30

        self.assertLess(distancia_media("CERCA_DESPACHO"), distancia_media("DISTRIBUIDA"))

    def test_parametros_invalidos(self):
        with self.assertRaises(ValueError):
            ScenarioGenerator.generar_escenario_dict(cantidad_pasillos=1)
        with self.assertRaises(ValueError):
            ScenarioGenerator.generar_escenario_dict(localizacion="AL_AZAR")
        with self.assertRaises(ValueError):
            ScenarioGenerator.generar_escenario_dict(max_productos_por_pedido=8, wave_max_productos=4)


class TestValidador(unittest.TestCase):
    def setUp(self):
        self.d = ScenarioGenerator.generar_escenario_dict(4, 3, 10, "DISTRIBUIDA", 4, 2, 2, 8, 1)

    def test_detecta_errores(self):
        casos = [
            lambda d: d["productos"][0]["ubicacion"].update(x=0),  # fuera de su rack
            lambda d: d["pedidos"][0].update(prioridad=7),
            lambda d: d["pickers"][0]["posicion_inicial"].update(x=d["warehouse"]["racks"][0]["ubicacion"]["x"], y=d["warehouse"]["racks"][0]["ubicacion"]["y"]),
            lambda d: d["warehouse"]["racks"].append(dict(d["warehouse"]["racks"][0], id="R99")),
            lambda d: d.pop("pickers"),
        ]
        import copy

        for romper in casos:
            d = copy.deepcopy(self.d)
            romper(d)
            with self.assertRaises(ValueError):
                validar_escenario(d)


if __name__ == "__main__":
    unittest.main()
