"""Pruebas de la capa de simulación: recogida, historial, comparación y sesiones."""

import json
import unittest

from BackEnd.controllers.simulador import Simulador
from BackEnd.enums.enums import EstadoPedido
from BackEnd.utils.file_parser import FileParser
from BackEnd.utils.scenario_generator import ScenarioGenerator


def foto(sim):
    return (
        sim.estado.paso,
        [(p["id"], tuple(p["pos"]), tuple(sorted(p["recogidos"].items()))) for p in sim.resumen_pickers()],
        [(p["id"], p["stock"]) for p in sim.productos()],
        [(w["id"], w["estado"]) for w in sim.resumen_waves()],
        [(p["id"], p["estado"]) for p in sim.pedidos()],
    )


class TestSimuladorBasico(unittest.TestCase):
    def setUp(self):
        self.sim = Simulador(FileParser.leer_json("escenario_basico.json"))

    def test_recoge_todo_y_descarga_en_despacho(self):
        stock = {p["id"]: p["stock"] for p in self.sim.productos()}
        self.sim.generar_waves()
        self.sim.iniciar_waves(["WAVE_01"], "ORDEN")
        pedidos = {p["id"]: p for p in self.sim.pedidos()}
        self.assertTrue(all(p["estado"] == "EN_PREPARACION" for p in pedidos.values()))
        self.sim.avanzar_hasta_terminar()
        entregado = self.sim.estado.entregas[0]["productos"]
        pedido_total = {}
        for p in pedidos.values():
            for prod, cant in p["items"]:
                pedido_total[prod] = pedido_total.get(prod, 0) + cant
        self.assertEqual(entregado, pedido_total)
        for prod, cant in pedido_total.items():
            self.assertEqual(self.sim.warehouse.buscar_producto_O1(prod).cantidad_disponible, stock[prod] - cant)
        self.assertTrue(all(p.estado == EstadoPedido.PREPARADO for p in self.sim.warehouse.pedidos.values()))
        picker = self.sim.warehouse.pickers[0]
        self.assertIn(picker.posicion_actual, self.sim.warehouse.obtener_nodos_acceso_zona("ZONA_A"))
        self.assertEqual(self.sim.tanda_actual["paso_fin"], self.sim.estado.paso)

    def test_retroceder_y_reiniciar_restauran_el_estado(self):
        self.sim.generar_waves()
        self.sim.iniciar_waves(["WAVE_01"])
        inicio = foto(self.sim)
        fotos = [inicio]
        for _ in range(30):
            self.sim.avanzar()
            fotos.append(foto(self.sim))
        for esperado in reversed(fotos[:-1]):
            self.sim.retroceder()
            self.assertEqual(foto(self.sim), esperado)
        for _ in range(12):
            self.sim.avanzar()
        self.sim.reiniciar()
        self.assertEqual(foto(self.sim), inicio)

    def test_cambiar_estrategia_antes_de_avanzar_replanifica(self):
        self.sim.generar_waves()
        self.sim.iniciar_waves(["WAVE_01"], "ORDEN")
        orden = self.sim.estado.planes["PK_01"]["distancia"]
        self.assertTrue(self.sim.cambiar_estrategia("CERCANIA"))
        self.assertEqual(self.sim.tanda_actual["estrategia"], "CERCANIA")
        self.assertLess(self.sim.estado.planes["PK_01"]["distancia"], orden)

    def test_comparacion_no_modifica_la_simulacion(self):
        self.sim.generar_waves()
        antes = foto(self.sim)
        comp = self.sim.comparar_estrategias(["WAVE_01"])
        self.assertEqual(foto(self.sim), antes)
        self.assertEqual(set(comp), {"ORDEN", "CERCANIA"})
        for r in comp.values():
            self.assertGreater(r["distancia"], 0)
            self.assertEqual(r["distancia"], r["aristas"])
            self.assertGreaterEqual(r["turnos"], r["distancia"])

    def test_una_wave_entre_varios_pickers(self):
        sim = Simulador(FileParser.leer_json("escenario_gen_mediano.json"))
        sim.generar_waves()
        ids = [w.id_wave for w in sim.waves]
        tanda = sim.iniciar_waves(ids, "CERCANIA", 2)
        primera = sim.estado.gestor_waves.waves_por_id[ids[0]]
        self.assertEqual(len(primera.ids_pickers_asignados), 2)
        # Cada picker del equipo se lleva una parte distinta de los pedidos.
        partes = [set(primera.pedidos_por_picker[p]) for p in primera.ids_pickers_asignados]
        self.assertTrue(all(partes))
        self.assertFalse(partes[0] & partes[1])
        self.assertEqual(partes[0] | partes[1], {p.id_pedido for p in primera.pedidos})
        sim.avanzar_hasta_terminar()
        m = sim.metricas()
        self.assertEqual((m["pedidos_preparados"], m["waves_finalizadas"]), (40, len(ids)))
        # La sesión guarda cuántos pickers por wave se usaron.
        copia = Simulador(json.loads(json.dumps(sim.a_json())))
        self.assertEqual(foto(copia), foto(sim))
        self.assertEqual(copia.tanda_actual["pickers_por_wave"], 2)

    def test_comparar_estrategias_de_armado(self):
        sim = Simulador(FileParser.leer_json("escenario_gen_mediano.json"))
        antes = foto(sim)
        comp = sim.comparar_armado()
        self.assertEqual(foto(sim), antes)
        self.assertEqual(set(comp), {"CERCANIA", "PASILLO", "PRIORIDAD"})
        for r in comp.values():
            self.assertEqual(r["pedidos_preparados"], 40)
        # Agrupar por cercanía o por pasillo visita menos pasillos que solo prioridad.
        self.assertLess(comp["CERCANIA"]["pasillos_por_wave"], comp["PRIORIDAD"]["pasillos_por_wave"])
        self.assertLess(comp["PASILLO"]["pasillos_por_wave"], comp["PRIORIDAD"]["pasillos_por_wave"])
        sim.configurar(4, 20, 2, "PASILLO")
        sim.generar_waves()
        self.assertEqual(sim.estado.gestor_waves.estrategia_armado, "PASILLO")

    def test_explicar_armado_de_una_wave(self):
        sim = Simulador(FileParser.leer_json("escenario_gen_mediano.json"))
        waves = sim.generar_waves()
        antes = foto(sim)
        for wave in waves[:5]:
            exp = sim.explicar_armado(wave.id_wave)
            self.assertEqual(foto(sim), antes)  # explicar no cambia nada
            tipos = [p["tipo"] for p in exp["pasos"]]
            self.assertEqual(tipos[0], "raiz")
            self.assertEqual(tipos[-2:], ["fin", "ruta"])
            elegidos = [exp["pasos"][0]["pedido"]] + [p["pedido"] for p in exp["pasos"] if p["tipo"] == "elegir"]
            self.assertEqual(elegidos, [p.id_pedido for p in wave.pedidos])
            for i, paso in enumerate(exp["pasos"]):
                if paso["tipo"] == "elegir":
                    # Antes de cada elección se muestra el ranking y gana el primero.
                    previo = exp["pasos"][i - 1]
                    self.assertEqual(previo["tipo"], "evaluar")
                    self.assertEqual(previo["ranking"][0]["id_pedido"], paso["pedido"])
                    for enlace in paso["enlaces"]:
                        self.assertEqual(len(enlace["camino"]) - 1, enlace["distancia"])
            ruta = exp["ruta"]
            self.assertEqual(sorted(ruta["destinos"]), sorted(set(ruta["destinos"])))
            for a, b in zip(ruta["camino"], ruta["camino"][1:]):
                self.assertEqual(abs(a[0] - b[0]) + abs(a[1] - b[1]), 1)
            self.assertEqual(len(ruta["camino"]) - 1, ruta["distancia"])

    def test_pedido_nuevo_y_configuracion(self):
        nuevo = self.sim.agregar_pedido(5, Simulador.interpretar_items("P006x1, P007x2"))
        self.assertEqual(nuevo, "PED_04")
        self.sim.configurar(2, 10, 1)
        waves = self.sim.generar_waves()
        self.assertTrue(all(len(w.pedidos) <= 2 and w.unidades_totales <= 10 for w in waves))
        self.assertEqual(waves[0].pedidos[0].id_pedido, "PED_01")  # prioridad 5, menor id
        with self.assertRaises(ValueError):
            self.sim.agregar_pedido(9, [("P001", 1)])
        with self.assertRaises(ValueError):
            Simulador.interpretar_items("P001 x")

    def test_sesion_guardada_se_retoma_igual(self):
        self.sim.agregar_pedido(4, [("P007", 1)])
        self.sim.generar_waves()
        self.sim.iniciar_waves([w.id_wave for w in self.sim.waves], "ORDEN")
        for _ in range(40):
            self.sim.avanzar()
        self.sim.retroceder()
        datos = json.loads(json.dumps(self.sim.a_json()))
        copia = Simulador(datos)
        self.assertEqual(foto(copia), foto(self.sim))
        copia.avanzar_hasta_terminar()
        self.sim.avanzar_hasta_terminar()
        self.assertEqual(foto(copia), foto(self.sim))


class TestSimuladorVariosPickers(unittest.TestCase):
    def test_todas_las_waves_con_cola_de_espera(self):
        datos = ScenarioGenerator.generar_escenario_dict(24, 6, 150, "DISTRIBUIDA", 60, 5, 4, 20, 4)
        sim = Simulador(datos)
        sim.generar_waves()
        ids = [w.id_wave for w in sim.waves]
        tanda = sim.iniciar_waves(ids, "CERCANIA")
        self.assertEqual(len(tanda["waves"]), 4)  # 4 pickers libres
        self.assertEqual(len(tanda["en_espera"]), len(ids) - 4)
        sim.avanzar_hasta_terminar()
        self.assertFalse(sim.en_curso)
        self.assertEqual(sim.tanda_actual["en_espera"], [])
        m = sim.metricas()
        self.assertEqual(m["waves_finalizadas"], len(ids))
        self.assertEqual(m["pedidos_preparados"], m["pedidos"])
        self.assertFalse([e for e in sim.estado.eventos if "ATENCIÓN" in e])

    def test_muchos_pickers_no_se_traban(self):
        datos = ScenarioGenerator.generar_escenario_dict(10, 8, 60, "DISTRIBUIDA", 30, 4, 4, 16, 10)
        sim = Simulador(datos)
        sim.generar_waves()
        sim.iniciar_waves([w.id_wave for w in sim.waves], "CERCANIA")
        sim.avanzar_hasta_terminar(3000)
        self.assertFalse(sim.en_curso)
        self.assertEqual(sim.metricas()["pedidos_preparados"], 30)


if __name__ == "__main__":
    unittest.main()


class TestReglasDeMovimiento(unittest.TestCase):
    def simular(self):
        datos = ScenarioGenerator.generar_escenario_dict(12, 4, 80, "DISTRIBUIDA", 40, 4, 4, 16, 6)
        sim = Simulador(datos)
        sim.generar_waves()
        sim.iniciar_waves([w.id_wave for w in sim.waves], "CERCANIA")
        posiciones = [{p.id_picker: p.posicion_actual for p in sim.warehouse.pickers}]
        self.trabajando = [{p.id_picker for p in sim.warehouse.pickers if p.id_wave_actual}]
        while sim.avanzar():
            posiciones.append({p.id_picker: p.posicion_actual for p in sim.warehouse.pickers})
            self.trabajando.append({p.id_picker for p in sim.warehouse.pickers if p.id_wave_actual})
        return sim, posiciones

    def test_nadie_entra_a_la_estela_de_otro(self):
        sim, pos = self.simular()
        self.assertEqual(sim.metricas()["pedidos_preparados"], 40)
        salidas = {}  # celda -> (picker, turno en que la dejó)
        for k in range(1, len(pos)):
            for pid, celda in pos[k].items():
                antes = pos[k - 1][pid]
                if celda == antes:
                    continue
                dueno, turno = salidas.get(celda, (None, -99))
                if dueno not in (None, pid):
                    self.assertGreaterEqual(k - turno, 3, f"{pid} entró a {celda} pegado a {dueno}")
                if pid in self.trabajando[k - 1]:  # un picker libre que se corre no deja estela
                    salidas[antes] = (pid, k)
        for k in range(len(pos)):
            self.assertEqual(len(set(pos[k].values())), len(pos[k]), "dos pickers en la misma celda")

    def test_se_frena_al_cargar_y_al_descargar(self):
        sim = Simulador(FileParser.leer_json("escenario_basico.json"))
        sim.generar_waves()
        sim.iniciar_waves(["WAVE_01"], "ORDEN")
        plan = sim.estado.planes["PK_01"]
        destinos = set(plan["destinos"])
        recorrido = [sim.warehouse.pickers[0].posicion_actual]
        while sim.avanzar():
            recorrido.append(sim.warehouse.pickers[0].posicion_actual)
        col = sim.estado.colisiones
        carga, descarga = col.turnos_recogida, col.turnos_descarga
        self.assertEqual((carga, descarga), (4, 3))
        # En cada destino se queda quieto cargando.
        for celda in destinos:
            i = recorrido.index(celda)
            self.assertEqual(recorrido[i:i + carga + 1], [celda] * (carga + 1))
        # Termina en el despacho y se queda descargando antes de terminar.
        self.assertEqual(recorrido[-(descarga + 1):], [plan["despacho"]] * (descarga + 1))
        busqueda = plan["turnos_busqueda"]
        self.assertEqual(recorrido[: busqueda + 1], [recorrido[0]] * (busqueda + 1))
        self.assertEqual(len(recorrido) - 1, busqueda + plan["distancia"] + carga * len(destinos) + descarga)
        self.assertEqual(sim.metricas()["esperas"], 0)
