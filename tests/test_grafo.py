"""
Tests del grafo del almacén (Warehouse + Digrafo + GraphBuilder).

Correr desde la raíz del repo:
    python -m unittest discover -s tests -v
"""
import copy
import json
import os
import sys
import unittest
from collections import deque

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from BackEnd.models.entity import Sentido, TipoCelda  # noqa: E402
from BackEnd.utils.graph_builder import GraphBuilder  # noqa: E402


# Escenario del Anexo A del enunciado
ESCENARIO_ANEXO_A = {
    "warehouse": {
        "dimensiones": {"ancho_x": 18, "largo_y": 16},
        "puertas": [
            {"id": "PUERTA_OUT_1", "tipo": "OUTBOUND", "ubicacion": {"x": 4, "y": 0}},
            {"id": "PUERTA_IN_1", "tipo": "INBOUND", "ubicacion": {"x": 13, "y": 0}},
        ],
        "zonas_despacho": [
            {"id": "ZONA_A", "puerta_id": "PUERTA_OUT_1", "ubicacion": {"x": 2, "y": 1},
             "ancho": 5, "alto": 2, "peso_max_kg": 500.0},
            {"id": "ZONA_B", "puerta_id": "PUERTA_IN_1", "ubicacion": {"x": 11, "y": 1},
             "ancho": 5, "alto": 2, "peso_max_kg": 500.0},
        ],
        "racks": [
            {"id": "R1", "ubicacion": {"x": 3, "y": 5}, "ancho": 2, "alto": 6},
            {"id": "R2", "ubicacion": {"x": 8, "y": 5}, "ancho": 2, "alto": 6},
            {"id": "R3", "ubicacion": {"x": 13, "y": 5}, "ancho": 2, "alto": 6},
        ],
        "pasillos": [
            {"id": "PAS_V0", "ubicacion": {"x": 0, "y": 5}, "ancho": 3, "alto": 6, "sentido": "N"},
            {"id": "PAS_V1", "ubicacion": {"x": 5, "y": 5}, "ancho": 3, "alto": 6, "sentido": "S"},
            {"id": "PAS_V2", "ubicacion": {"x": 10, "y": 5}, "ancho": 3, "alto": 6, "sentido": "N"},
            {"id": "PAS_V3", "ubicacion": {"x": 15, "y": 5}, "ancho": 3, "alto": 6, "sentido": "S"},
            {"id": "PAS_H_INF", "ubicacion": {"x": 0, "y": 3}, "ancho": 18, "alto": 2, "sentido": "AMBOS"},
            {"id": "PAS_H_SUP", "ubicacion": {"x": 0, "y": 11}, "ancho": 18, "alto": 5, "sentido": "AMBOS"},
        ],
    },
    "pickers": [
        {"id": "PK_01", "posicion_inicial": {"x": 1, "y": 3}, "capacidad_carga_kg": 150.0},
        {"id": "PK_02", "posicion_inicial": {"x": 16, "y": 3}, "capacidad_carga_kg": 120.0},
    ],
    "productos": [
        {"id": "P001", "nombre": "Monitor 27", "rack_id": "R1",
         "ubicacion": {"x": 3, "y": 5, "z": 1}, "cantidad_disponible": 40, "peso_kg": 4.5},
        {"id": "P003", "nombre": "Mouse", "rack_id": "R1",
         "ubicacion": {"x": 4, "y": 7, "z": 1}, "cantidad_disponible": 100, "peso_kg": 0.15},
        {"id": "P006", "nombre": "Auriculares", "rack_id": "R3",
         "ubicacion": {"x": 13, "y": 8, "z": 1}, "cantidad_disponible": 30, "peso_kg": 0.35},
    ],
}


def escenario():
    return copy.deepcopy(ESCENARIO_ANEXO_A)


def buscar(lista, elem_id):
    return next(e for e in lista if e["id"] == elem_id)


def alcanzables(grafo, origen):
    """BFS simple sobre lista_adyacencia."""
    vistos = {origen}
    cola = deque([origen])
    while cola:
        actual = cola.popleft()
        for v in grafo.lista_adyacencia.get(actual, []):
            if v not in vistos:
                vistos.add(v)
                cola.append(v)
    return vistos


def llega(grafo, origen, destino, bloqueados=()):
    """True si hay camino de origen a destino sin pasar por las celdas bloqueadas."""
    vistos = {origen}
    cola = deque([origen])
    while cola:
        actual = cola.popleft()
        for v in grafo.lista_adyacencia.get(actual, []):
            if v not in vistos and v not in bloqueados:
                vistos.add(v)
                cola.append(v)
    return destino in vistos


def ruta_escenario_grande():
    for carpeta in (RAIZ, os.path.join(RAIZ, "BackEnd", "data"), os.path.join(RAIZ, "tests", "data")):
        ruta = os.path.join(carpeta, "escenario_grande.json")
        if os.path.isfile(ruta):
            return ruta
    return None


class TestGrafoAnexoA(unittest.TestCase):
    def setUp(self):
        self.wh = GraphBuilder.construir_warehouse_desde_dict(escenario())
        self.g = self.wh.grafo_pasillos

    def tieneArista(self, a, b):
        return b in self.g.lista_adyacencia.get(a, [])

    def test_sin_advertencias_y_una_componente(self):
        self.assertEqual(self.wh.advertencias, [])
        self.assertEqual(len(GraphBuilder.componentes_fuertemente_conexas(self.wh)), 1)

    def test_cantidad_de_nodos(self):
        # 288 celdas - 36 de rack - 2 puertas - 20 de zonas
        self.assertEqual(len(self.g.nodos), 230)

    def test_sin_matriz_nodos_mas_obstaculos_cubren_el_almacen(self):
        self.assertFalse(hasattr(self.wh, "matriz"))
        self.assertEqual(len(self.wh.obstaculos), 36 + 2 + 20)
        self.assertEqual(len(self.g.nodos) + len(self.wh.obstaculos), 18 * 16)
        self.assertTrue(set(self.g.nodos).isdisjoint(self.wh.obstaculos))
        self.assertEqual(self.wh.obstaculos[(3, 5)].productos_en_z[1].id, "P001")
        self.assertEqual(self.g.nodos[(0, 5)].pasillo_id, "PAS_V0")
        self.assertIsNone(self.g.nodos[(0, 0)].pasillo_id)
        self.assertEqual(self.g.nodos[(0, 0)].sentido_permitido, Sentido.AMBOS)

    def test_puertas_y_zonas_no_son_nodos(self):
        for c in [(4, 0), (13, 0), (2, 2), (2, 1)]:
            self.assertNotIn(c, self.g.nodos)
        self.assertEqual(self.wh.obstaculos[(4, 0)].tipo, TipoCelda.PUERTA)
        self.assertIn("PUERTA_OUT_1", self.wh.puertas)
        self.assertFalse(self.tieneArista((2, 3), (2, 2)))

    def test_acceso_productos_por_el_costado(self):
        self.assertEqual(self.wh.obtener_nodos_acceso_producto("P001"), [(2, 5)])
        self.assertEqual(self.wh.obtener_nodos_acceso_producto("P003"), [(5, 7)])
        self.assertEqual(self.wh.obtener_nodo_acceso_producto("P001"), (2, 5))
        self.assertNotIn((3, 4), self.wh.accesos_rack_a_pasillo[(3, 5)])

    def test_accesos_zona(self):
        accesos = self.wh.obtener_nodos_acceso_zona("ZONA_A")
        self.assertEqual(len(accesos), 13)
        self.assertIn((2, 3), accesos)
        self.assertNotIn((4, 0), accesos)

    def test_contramano(self):
        self.assertTrue(self.tieneArista((0, 5), (0, 6)))
        self.assertFalse(self.tieneArista((0, 6), (0, 5)))
        self.assertTrue(self.tieneArista((5, 6), (5, 5)))
        self.assertFalse(self.tieneArista((5, 5), (5, 6)))
        self.assertFalse(self.tieneArista((5, 4), (5, 5)))

    def test_movimiento_lateral_en_pasillo_n(self):
        self.assertTrue(self.tieneArista((0, 7), (1, 7)))
        self.assertTrue(self.tieneArista((1, 7), (0, 7)))

    def test_ida_y_vuelta_desde_cada_picker(self):
        for pos in [(1, 3), (16, 3)]:
            desde_picker = alcanzables(self.g, pos)
            for prod_id in self.wh.catalogo_productos:
                accesos = self.wh.obtener_nodos_acceso_producto(prod_id)
                alcanzados = [a for a in accesos if a in desde_picker]
                self.assertTrue(alcanzados, f"{prod_id} inalcanzable desde {pos}")
                self.assertIn(pos, alcanzables(self.g, alcanzados[0]))

    def test_sentido_ninguno_sin_direcciones(self):
        self.assertEqual(GraphBuilder._direcciones_segun_sentido(Sentido.NINGUNO), [])


class TestErroresYAdvertencias(unittest.TestCase):
    def test_sentido_invalido(self):
        data = escenario()
        buscar(data["warehouse"]["pasillos"], "PAS_V0")["sentido"] = "NORTE"
        with self.assertRaises(ValueError):
            GraphBuilder.construir_warehouse_desde_dict(data)

    def test_rack_fuera_del_almacen(self):
        data = escenario()
        buscar(data["warehouse"]["racks"], "R3")["ubicacion"]["x"] = 17
        with self.assertRaises(ValueError):
            GraphBuilder.construir_warehouse_desde_dict(data)

    def test_superposicion(self):
        data = escenario()
        buscar(data["warehouse"]["racks"], "R2")["ubicacion"] = {"x": 3, "y": 6}
        wh = GraphBuilder.construir_warehouse_desde_dict(data)
        self.assertTrue(any("pisa" in a for a in wh.advertencias))

    def test_rack_sin_lado_2(self):
        data = escenario()
        buscar(data["warehouse"]["racks"], "R1")["ancho"] = 3
        wh = GraphBuilder.construir_warehouse_desde_dict(data)
        self.assertTrue(any("ningún lado vale 2" in a for a in wh.advertencias))

    def test_picker_sobre_rack(self):
        data = escenario()
        buscar(data["pickers"], "PK_01")["posicion_inicial"] = {"x": 3, "y": 6}
        wh = GraphBuilder.construir_warehouse_desde_dict(data)
        self.assertTrue(any("Picker" in a for a in wh.advertencias))

    def test_pasillo_inferior_en_sentido_s(self):
        data = escenario()
        buscar(data["warehouse"]["pasillos"], "PAS_H_INF")["sentido"] = "S"
        wh = GraphBuilder.construir_warehouse_desde_dict(data)
        self.assertTrue(any("no pertenecen a la red principal" in a for a in wh.advertencias))


@unittest.skipIf(ruta_escenario_grande() is None, "No se encontró escenario_grande.json")
class TestEscenarioGrande(unittest.TestCase):
    def setUp(self):
        with open(ruta_escenario_grande(), encoding="utf-8") as f:
            self.data = json.load(f)

    def test_escenario_grande_sin_trampas(self):
        wh = GraphBuilder.construir_warehouse_desde_dict(self.data)
        self.assertEqual(wh.advertencias, [])
        self.assertEqual(len(GraphBuilder.componentes_fuertemente_conexas(wh)), 1)
        self.assertEqual(len(wh.grafo_pasillos.nodos), 1898)
        for prod_id in wh.catalogo_productos:
            self.assertEqual(len(wh.obtener_nodos_acceso_producto(prod_id)), 1, prod_id)

    def test_rincon_sin_salida_con_pas_va00_en_n(self):
        # Con PAS_VA00 en N, el rincón x=0..3, y=15..17 sólo sale por (3,16).
        buscar(self.data["warehouse"]["pasillos"], "PAS_VA00")["sentido"] = "N"
        wh = GraphBuilder.construir_warehouse_desde_dict(self.data)
        g = wh.grafo_pasillos
        self.assertTrue(llega(g, (3, 15), (5, 4)))
        self.assertFalse(llega(g, (3, 15), (5, 4), {(3, 16)}))

    def test_rincon_con_salida_alternativa_con_pas_va00_ambos(self):
        wh = GraphBuilder.construir_warehouse_desde_dict(self.data)
        self.assertTrue(llega(wh.grafo_pasillos, (3, 15), (5, 4), {(3, 16)}))

    def test_trampa_con_pas_vb00_en_s(self):
        buscar(self.data["warehouse"]["pasillos"], "PAS_VB00")["sentido"] = "S"
        wh = GraphBuilder.construir_warehouse_desde_dict(self.data)
        self.assertTrue(any("no pertenecen a la red principal" in a for a in wh.advertencias))


if __name__ == "__main__":
    unittest.main()
