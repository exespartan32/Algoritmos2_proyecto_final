"""Pruebas de las estructuras y algoritmos: Max-Heap, Dijkstra, estrategias y waves."""

import unittest
from collections import deque

from BackEnd.controllers.path_finding import Pathfinding
from BackEnd.controllers.wave_manager import WaveManager
from BackEnd.data_structures.max_heap_pedidos import MaxHeapPedidos
from BackEnd.enums.enums import EstadoPedido, EstadoWave
from BackEnd.models.entities import DetallePedido, Pedido
from BackEnd.utils.file_parser import FileParser


def bfs_distancias(grafo, origen):
    dist = {origen: 0}
    cola = deque([origen])
    while cola:
        u = cola.popleft()
        for v in grafo.lista_adyacencia[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                cola.append(v)
    return dist


class TestMaxHeap(unittest.TestCase):
    def test_extrae_por_prioridad_y_desempata_por_id(self):
        pedidos = [Pedido(f"PED_{i:02d}", p, [DetallePedido("P001", 1)]) for i, p in enumerate([3, 5, 1, 5, 2, 4])]
        heap = MaxHeapPedidos()
        heap.construir_monticulo(pedidos)
        orden = []
        while not heap.esta_vacio():
            orden.append(heap.extraer_maximo().id_pedido)
        self.assertEqual(orden, ["PED_01", "PED_03", "PED_05", "PED_00", "PED_04", "PED_02"])

    def test_eliminar_mantiene_invariante(self):
        pedidos = [Pedido(f"PED_{i:02d}", (i * 7) % 5 + 1, [DetallePedido("P001", 1)]) for i in range(30)]
        heap = MaxHeapPedidos()
        heap.construir_monticulo(pedidos)
        for pid in ("PED_03", "PED_17", "PED_00", "PED_29"):
            self.assertTrue(heap.eliminar_pedido(pid))
        self.assertFalse(heap.eliminar_pedido("NO"))
        prioridades = []
        while not heap.esta_vacio():
            prioridades.append(heap.extraer_maximo().prioridad)
        self.assertEqual(prioridades, sorted(prioridades, reverse=True))
        self.assertEqual(len(prioridades), 26)


class TestDijkstraYEstrategias(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wh = FileParser.cargar_warehouse_desde_json("escenario_grande.json")
        cls.g = cls.wh.grafo_pasillos

    def test_dijkstra_da_la_misma_distancia_que_bfs(self):
        # Todas las aristas cuestan 1: Dijkstra debe coincidir con BFS.
        origen = (40, 17)
        dist = bfs_distancias(self.g, origen)
        for destino in [(0, 0), (89, 0), (45, 39), (12, 30), (70, 5)]:
            if destino not in self.g.nodos:
                continue
            ruta, explorados = Pathfinding.calcular_ruta_dijkstra(origen, destino, self.g)
            self.assertEqual(len(ruta) - 1, dist[destino])
            self.assertIn(destino, explorados)
            for a, b in zip(ruta, ruta[1:]):
                self.assertIn(b, self.g.lista_adyacencia[a], "la ruta usa solo aristas del dígrafo")

    def test_estrategias_visitan_todos_los_destinos_y_vuelven(self):
        productos = self.wh.obtener_todos_los_productos()[:12]
        destinos = [self.wh.obtener_celda_acceso_pasillo(p.x, p.y) for p in productos]
        despacho = self.wh.obtener_nodos_acceso_zona("ZONA_A")[0]
        origen = self.wh.pickers[0].posicion_actual
        orden = Pathfinding.calcular_estrategia_orden_pedidos(self.g, origen, destinos, despacho, self.wh)
        cerca = Pathfinding.calcular_estrategia_cercania_multidestino(self.g, origen, destinos, despacho, self.wh)
        for res in (orden, cerca):
            self.assertFalse(res.destinos_inalcanzables)
            self.assertTrue(set(destinos) <= set(res.camino_completo))
            self.assertEqual(res.camino_completo[-1], despacho)
            self.assertEqual(res.distancia_total, len(res.camino_completo) - 1)
        # Orden: visita los destinos en el orden dado.
        objetivos = list(dict.fromkeys(destinos))
        i = 0
        for celda in orden.camino_completo:
            if i < len(objetivos) and celda == objetivos[i]:
                i += 1
        self.assertEqual(i, len(objetivos))
        # Con 12 destinos dispersos, ir al más cercano recorre menos.
        self.assertLess(cerca.distancia_total, orden.distancia_total)

    def test_greedy_elige_el_destino_mas_cercano(self):
        origen = self.wh.pickers[0].posicion_actual
        dist = bfs_distancias(self.g, origen)
        candidatos = {c for c in list(self.g.nodos)[::97]}
        ruta, elegido, _ = Pathfinding.calcular_ruta_greedy(origen, candidatos, self.g)
        self.assertEqual(len(ruta) - 1, min(dist[c] for c in candidatos if c in dist))
        self.assertIn(elegido, candidatos)


class TestWaveManager(unittest.TestCase):
    def setUp(self):
        self.wh = FileParser.cargar_warehouse_desde_json("escenario_grande.json")
        self.gestor = WaveManager(wave_max_pedidos=5, wave_max_productos=25)
        self.waves = self.gestor.generar_waves(self.wh)

    def test_respeta_capacidad_y_no_repite_pedidos(self):
        vistos = set()
        for w in self.waves:
            self.assertLessEqual(len(w.pedidos), 5)
            self.assertLessEqual(w.unidades_totales, 25)
            for p in w.pedidos:
                self.assertNotIn(p.id_pedido, vistos)
                vistos.add(p.id_pedido)
                self.assertEqual(p.estado, EstadoPedido.EN_WAVE)
            self.assertEqual(w.estado, EstadoWave.PENDIENTE)

    def test_cada_wave_arranca_por_el_pedido_de_mayor_prioridad_restante(self):
        restantes = {p.id_pedido: p.prioridad for w in self.waves for p in w.pedidos}
        for w in self.waves:
            raiz = w.pedidos[0]
            self.assertEqual(raiz.prioridad, max(restantes.values()))
            for p in w.pedidos:
                del restantes[p.id_pedido]

    def test_armar_waves_no_descuenta_stock(self):
        self.assertTrue(all(p.cantidad_disponible > 0 for p in self.wh.obtener_todos_los_productos()))
        antes = {p.id_producto: p.cantidad_disponible for p in self.wh.obtener_todos_los_productos()}
        WaveManager(5, 25).generar_waves(FileParser.cargar_warehouse_desde_json("escenario_grande.json"))
        self.assertEqual(antes, {p.id_producto: p.cantidad_disponible for p in self.wh.obtener_todos_los_productos()})


if __name__ == "__main__":
    unittest.main()
