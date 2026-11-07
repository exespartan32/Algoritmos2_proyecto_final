"""Tests de la tabla hash propia (hashing universal + encadenamiento)."""

import json
import random
import unittest
from pathlib import Path

from BackEnd.data_structures.tabla_hash import (
    P_MERSENNE,
    TablaHashUniversal,
    es_primo,
)
from BackEnd.utils.graph_builder import GraphBuilder

RAIZ = Path(__file__).resolve().parents[1]


class TestTablaHash(unittest.TestCase):
    def test_se_comporta_igual_que_un_diccionario(self):
        tabla, dic = TablaHashUniversal(), {}
        r = random.Random(7)
        for i in range(4000):
            clave = (r.randrange(60), r.randrange(40)) if i % 2 else f"P{r.randrange(500):03d}"
            if r.random() < 0.7:
                tabla[clave] = i
                dic[clave] = i
            elif clave in dic:
                del tabla[clave]
                del dic[clave]
            self.assertEqual(clave in tabla, clave in dic)
        self.assertEqual(len(tabla), len(dic))
        self.assertEqual(list(tabla.items()), list(dic.items()), "mismo orden de inserción")
        self.assertEqual(tabla.get(("no", "está"), "x"), "x")
        with self.assertRaises(KeyError):
            tabla[(999, 999)]

    def test_funcion_hash_universal(self):
        t = TablaHashUniversal()
        k = t.clave_a_entero((3, 5))
        self.assertEqual(k, 3 * 1_000_003 + 5)
        self.assertEqual(t._hash((3, 5)), ((t._a * k + t._b) % P_MERSENNE) % t.cantidad_casillas())
        self.assertTrue(1 <= t._a < P_MERSENNE and 0 <= t._b < P_MERSENNE)
        # Semilla fija: dos tablas eligen los mismos a y b (determinismo).
        otra = TablaHashUniversal()
        self.assertEqual((t._a, t._b), (otra._a, otra._b))

    def test_coordenadas_distintas_dan_enteros_distintos(self):
        enteros = {TablaHashUniversal.clave_a_entero((x, y)) for x in range(200) for y in range(200)}
        self.assertEqual(len(enteros), 200 * 200)

    def test_colisiones_se_encadenan(self):
        t = TablaHashUniversal()
        for x in range(10):  # 10 claves en 17 casillas: tiene que haber choques
            t[(x, 0)] = x
        largos = t.longitudes_de_cadena()
        self.assertEqual(sum(largos), 10)
        self.assertTrue(all(t[(x, 0)] == x for x in range(10)))

    def test_rehash_mantiene_el_factor_de_carga(self):
        t = TablaHashUniversal()
        for x in range(60):
            for y in range(40):
                t[(x, y)] = None
        self.assertLessEqual(t.factor_de_carga(), 0.75)
        self.assertTrue(es_primo(t.cantidad_casillas()))
        self.assertGreater(t.cantidad_rehash, 0)

    def test_el_digrafo_usa_la_tabla_propia(self):
        datos = json.loads((RAIZ / "BackEnd" / "data" / "escenario_basico.json").read_text(encoding="utf-8-sig"))
        wh = GraphBuilder.construir_warehouse_desde_dict(datos)
        g = wh.grafo_pasillos
        self.assertIsInstance(g.nodos, TablaHashUniversal)
        self.assertIsInstance(g.lista_adyacencia, TablaHashUniversal)
        self.assertIsInstance(wh.obstaculos, TablaHashUniversal)
        self.assertEqual(len(g.nodos), 230)
        self.assertEqual(sum(len(v) for v in g.lista_adyacencia.values()), 692)
        self.assertEqual(g.obtener_vecinos((0, 5)), [(0, 6), (1, 5)])


if __name__ == "__main__":
    unittest.main()
