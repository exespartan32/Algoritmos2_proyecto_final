"""Ejercita botones y eventos reales de Pygame con video y audio virtuales."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import json
from pathlib import Path
import tempfile
import unittest
import pygame

from FrontEnd.views.pygame_engine import App

ROOT = Path(__file__).resolve().parents[1]


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(Path(self.temp.name))

    def tearDown(self):
        pygame.quit()
        self.temp.cleanup()

    def click(self, action):
        self.app.draw()
        rect = next(
            rect
            for rect, name, enabled in self.app.buttons
            if name == action and enabled
        )
        self.app.event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center)
        )
        self.assertFalse(self.app.message.startswith("No se pudo"), self.app.message)

    def test_load_play_pause_compare_undo_save(self):
        path = self.app.library / "escenario_basico.json"
        self.click(("load", path))
        self.click("waves")
        self.click("select")
        self.click(("wave", 0))
        self.click("strategy")
        self.assertEqual(self.app.model.strategy, "Cercanía")
        self.click("compare")
        self.app.draw()
        self.click("close")
        self.click("start")
        self.assertTrue(self.app.playing)
        self.click("pause")
        self.assertFalse(self.app.playing)
        self.click("forward")
        self.assertEqual(self.app.model.step, 1)
        self.click("back")
        self.assertEqual(self.app.model.step, 0)
        self.click("continue")
        self.app.run(frames=7)
        self.assertGreater(self.app.model.step, 0)
        self.click("save")
        self.assertTrue(list(self.app.library.glob("estado_*.json")))
        self.click("reset")
        self.assertEqual(self.app.model.step, 0)

    def test_generator_import_delete_and_screenshots(self):
        self.click("create")
        self.click("generator")
        self.app.fields = ["2", "5", "3"]
        self.click("generate")
        generated = next(self.app.library.glob("generado_*.json"))
        self.click(("delete", generated))
        self.click("confirm_delete")
        self.assertFalse(generated.exists())
        self.app.import_file(ROOT / "BackEnd/data/escenario_grande.json")
        self.assertEqual(len(list(self.app.library.glob("escenario_grande*.json"))), 2)
        output = ROOT / "test-output"
        output.mkdir(exist_ok=True)
        self.app.draw()
        pygame.image.save(self.app.screen, str(output / "inicio.png"))
        self.app.load(self.app.library / "escenario_grande.json")
        self.click("waves")
        self.click("select")
        self.click(("wave", 0))
        self.app.draw()
        pygame.image.save(self.app.screen, str(output / "simulacion.png"))
        self.click("compare")
        self.app.draw()
        pygame.image.save(self.app.screen, str(output / "comparacion.png"))

    def test_error_keeps_app_alive_and_modal_captures_clicks(self):
        path = self.app.library / "invalido.json"
        path.write_text("{}", encoding="utf-8")
        self.app.action(("load", path))
        self.assertEqual(self.app.page, "home")
        self.assertIn("No se pudo", self.app.message)
        self.app.action("create")
        self.app.draw()
        self.assertFalse(any(name == "create" for _, name, _ in self.app.buttons))
        self.app.run(frames=2)


if __name__ == "__main__":
    unittest.main()
