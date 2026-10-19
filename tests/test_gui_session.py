"""Pruebas contra el backend real, sin abrir ventanas ni modificar ejemplos."""

import json
from copy import deepcopy
from pathlib import Path
import random
import tempfile
import unittest

from FrontEnd.services.scenarios import generate, validate
from FrontEnd.services.session import Session

ROOT = Path(__file__).resolve().parents[1]


def example(name="basico"):
    return json.loads(
        (ROOT / "BackEnd" / "data" / f"escenario_{name}.json").read_text(
            encoding="utf-8"
        )
    )


def prepared(name="basico"):
    session = Session(example(name))
    session.generate_waves()
    session.select(0)
    return session


class SessionTests(unittest.TestCase):
    def test_all_example_waves_complete_with_exact_stock(self):
        for name in ("basico", "grande", "generado"):
            for strategy in ("Orden", "Cercanía"):
                with self.subTest(name=name, strategy=strategy):
                    session = Session(example(name))
                    initial = session.stock.copy()
                    session.generate_waves()
                    self.assertEqual(
                        initial, session.stock, "Planificar no consume stock"
                    )
                    expected = initial.copy()
                    for i in range(len(session.waves)):
                        session.select(i)
                        session.set_strategy(strategy)
                        for pid, qty in session.quantities().items():
                            expected[pid] -= qty
                        for start, end in zip(session.route, session.route[1:]):
                            self.assertIn(
                                end,
                                session.warehouse.grafo_pasillos.obtener_vecinos(start),
                            )
                        limit = len(session.route) + 1
                        while not session.finished and limit:
                            session.advance()
                            self.assertEqual(
                                len(session.positions),
                                len(set(session.positions.values())),
                            )
                            limit -= 1
                        self.assertTrue(session.finished)
                        self.assertEqual(session.cargo[session.wave["picker"]], {})
                        self.assertTrue(
                            all(
                                session.status[oid] == "PREPARADO"
                                for oid in session.wave["pedidos"]
                            )
                        )
                    self.assertEqual(session.stock, expected)
                    self.assertTrue(all(q >= 0 for q in expected.values()))

    def test_undo_pickup_and_reset_restore_real_objects(self):
        session = prepared()
        initial = session.snapshot()
        for _ in range(len(session.route)):
            before = session.snapshot()
            session.advance()
            if session.stock != initial["stock"]:
                break
        self.assertNotEqual(session.stock, initial["stock"])
        session.back()
        self.assertEqual(session.snapshot(), before)
        session.advance()
        session.reset()
        self.assertEqual(session.snapshot(), initial)
        for pid, product in session.warehouse.catalogo_productos.items():
            self.assertIs(product, session.catalog.buscar_producto_O1(pid))

    def test_save_resume_and_undo_after_reload(self):
        session = prepared("grande")
        session.set_strategy("Cercanía")
        for _ in range(15):
            session.advance()
        session.back()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sesion.json"
            session.save(path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                {p["id"]: p["cantidad_disponible"] for p in raw["productos"]},
                session.stock,
            )
            loaded = Session(raw)
            self.assertEqual(loaded.snapshot(), session.snapshot())
            self.assertEqual(loaded.route, session.route)
            loaded.back()
            session.back()
            self.assertEqual(loaded.snapshot(), session.snapshot())

    def test_end_undo_and_reset_do_not_duplicate_dispatch(self):
        session = prepared()
        while not session.finished:
            before = session.snapshot()
            session.advance()
        final = session.snapshot()
        session.back()
        self.assertEqual(session.snapshot(), before)
        session.advance()
        self.assertEqual(session.snapshot(), final)
        session.reset()
        self.assertEqual(session.snapshot(), session.baseline)

    def test_invalid_stock_rolls_back_entire_step(self):
        session = prepared()
        pid = next(iter(session.quantities()))
        session.catalog.buscar_producto_O1(pid).cantidad_disponible = 0
        for _ in range(len(session.route)):
            before = session.snapshot()
            try:
                session.advance()
            except ValueError:
                self.assertEqual(session.snapshot(), before)
                return
        self.fail("Debió rechazar el paso sin stock")

    def test_unreachable_route_does_not_change_selection(self):
        session = prepared("grande")
        snapshot = session.snapshot()
        route = session.route.copy()
        session.warehouse.grafo_pasillos.lista_adyacencia = {}
        with self.assertRaises(ValueError):
            session.select(1)
        self.assertEqual(session.selected, 0)
        self.assertEqual(session.snapshot(), snapshot)
        self.assertEqual(session.route, route)

    def test_stationary_picker_is_never_crossed(self):
        session = prepared()
        obstacle = next(p for p in session.catalog.pickers if p != session.picker())
        obstacle.posicion_actual = session.route[2]
        try:
            session.select(0)
        except ValueError:
            return  # El mapa puede quedar bloqueado: se informa, no se atraviesa.
        self.assertNotIn(obstacle.posicion_actual, session.route)

    def test_invalid_inputs_are_rejected(self):
        for mutate in (
            lambda d: d["productos"][0].update(cantidad_disponible=-1),
            lambda d: d["productos"][0].update(peso_kg=float("nan")),
            lambda d: d["pedidos"][0]["items"][0].update(cantidad=1.5),
            lambda d: d["warehouse"]["racks"][0].update(ancho=10000000),
            lambda d: d["pickers"][0]["posicion_inicial"].update(x=-1),
            lambda d: d["pedidos"][0]["items"].append(
                deepcopy(d["pedidos"][0]["items"][0])
            ),
        ):
            data = example()
            mutate(data)
            with self.assertRaises(ValueError):
                validate(data)

    def test_generator_uses_backend_and_respects_counts(self):
        random.seed(42)
        for counts in ((1, 1, 1), (10, 50, 20), (30, 300, 100)):
            data = generate(*counts)
            self.assertEqual(
                (
                    len(data["warehouse"]["racks"]),
                    len(data["productos"]),
                    len(data["pedidos"]),
                ),
                counts,
            )
            session = Session(data)
            session.generate_waves()
            session.select(0)
            self.assertTrue(session.route)

    def test_loaded_actions_are_whitelisted(self):
        data = example()
        data["_interfaz"] = {
            "version": 1,
            "escenario_inicial": example(),
            "acciones": [["save", ["bad.json"]]],
        }
        with self.assertRaises(ValueError):
            Session(data)


if __name__ == "__main__":
    unittest.main()
