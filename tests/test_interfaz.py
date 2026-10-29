"""Recorre la interfaz completa como lo haría un usuario (sin ventana)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import pygame

from FrontEnd.events.input_handler import manejar_evento
from FrontEnd.views.pygame_engine import App, PESTANAS

RAIZ = Path(__file__).resolve().parents[1]


def evento(tipo, **kw):
    if hasattr(pygame, "event") and hasattr(pygame.event, "Event"):
        return pygame.event.Event(tipo, **kw)
    raise RuntimeError


class TestInterfaz(unittest.TestCase):
    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp())
        self.app = App(self.carpeta)
        self.app.animar_busqueda = False  # la animación se prueba aparte

    def tearDown(self):
        shutil.rmtree(self.carpeta, ignore_errors=True)

    def hacer(self, accion, permitir_error=False):
        self.app.mensaje = ""
        self.app.accion(accion)
        self.app.dibujar()
        if not permitir_error:
            self.assertNotIn("No se pudo", self.app.mensaje, accion)
        return self.app.mensaje

    def boton(self, prefijo):
        for rect, accion, habilitado in self.app.botones:
            if accion == prefijo or (isinstance(accion, tuple) and accion[0] == prefijo):
                return rect, accion, habilitado
        self.fail(f"No hay botón {prefijo}")

    def clic(self, rect):
        x = rect.x + rect.w // 2
        y = rect.y + rect.h // 2
        e = self.app.escala
        pos = (int(x * e + self.app.desplazamiento[0]) + 1, int(y * e + self.app.desplazamiento[1]) + 1)
        manejar_evento(self.app, evento(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
        manejar_evento(self.app, evento(pygame.MOUSEBUTTONUP, button=1, pos=pos))
        self.app.dibujar()

    def test_inicio_y_generador(self):
        self.app.dibujar()
        nombres = [p.name for p in self.app.biblioteca.archivos()]
        self.assertIn("escenario_basico.json", nombres)
        self.hacer("crear")
        self.hacer("generador")
        f = self.app.formulario
        f["foco"] = 0
        manejar_evento(self.app, evento(pygame.KEYDOWN, key=pygame.K_BACKSPACE))
        manejar_evento(self.app, evento(pygame.KEYDOWN, key=pygame.K_BACKSPACE))
        manejar_evento(self.app, evento(pygame.TEXTINPUT, text="8a"))
        self.assertEqual(f["campos"][0][2], "8")
        self.hacer(("campo", 3))  # cambia la localización
        self.assertEqual(f["campos"][3][2], "CERCA_DESPACHO")
        manejar_evento(self.app, evento(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertIn("generado", self.app.mensaje)
        generados = [p for p in self.app.biblioteca.archivos() if p.name.startswith("generado_")]
        self.assertEqual(len(generados), 1)
        self.hacer(("abrir", generados[0]))
        self.assertEqual(self.app.pagina, "sim")

    def test_flujo_completo_de_simulacion(self):
        self.app.dibujar()
        ruta = self.carpeta / "escenario_basico.json"
        self.hacer(("abrir", ruta))
        for pestana in PESTANAS:
            self.hacer(("pestana", pestana))
        # Crear un pedido nuevo
        self.hacer("nuevo_pedido")
        self.app.formulario["campos"][0][2] = "P001x1, P004x2"
        self.hacer("enviar")
        self.assertIn("PED_04", self.app.mensaje)
        # Capacidad de waves
        self.hacer("config")
        self.app.formulario["campos"][0][2] = "2"
        self.hacer("enviar")
        self.assertEqual(self.app.sim.config["wave_max_pedidos"], 2)
        # Generar y seleccionar
        self.hacer("generar_waves")
        self.assertEqual(self.app.dialogo, "waves")
        self.hacer(("marcar_todas", True))
        self.hacer(("comparar", True))
        self.assertEqual(self.app.dialogo, "comparar")
        self.hacer("cerrar")
        self.hacer("elegir_waves")
        rect, accion, habilitado = self.boton("iniciar_seleccion")
        self.assertTrue(habilitado)
        self.clic(rect)
        self.assertIn("Tanda 1", self.app.mensaje)
        for pestana in PESTANAS:
            self.hacer(("pestana", pestana))
        # Reproducir automáticamente
        self.hacer("iniciar")
        self.assertTrue(self.app.reproduciendo)
        for _ in range(5):
            self.app.paso_automatico(0.5)
            self.app.dibujar()
        paso = self.app.sim.estado.paso
        self.assertGreater(paso, 0)
        self.hacer("pausar")
        self.hacer("atras")
        self.assertEqual(self.app.sim.estado.paso, paso - 1)
        self.hacer("adelante")
        manejar_evento(self.app, evento(pygame.KEYDOWN, key=pygame.K_RIGHT))
        self.assertEqual(self.app.sim.estado.paso, paso + 1)
        self.hacer("reiniciar")
        self.assertEqual(self.app.sim.estado.paso, self.app.sim.tanda_actual["paso_inicio"])
        self.hacer("estrategia")
        self.assertIn("volvió a planificar", self.app.mensaje)
        self.hacer("comparar")
        self.hacer("cerrar")
        self.hacer("velocidad")
        self.hacer("exploracion")
        self.hacer("ampliar")
        self.hacer("ampliar")
        # Clic en el mapa
        celda = next(c for c, v in self.app.sim.celdas.items() if v[0] == "RACK")
        self.clic(self.app.mapa.rect_celda(celda))
        self.assertIn("rack", self.app.mensaje)
        # Terminar todas las waves
        self.app.velocidad = len(__import__("FrontEnd.views.pygame_engine", fromlist=["x"]).VELOCIDADES) - 1
        self.hacer("iniciar")
        for _ in range(400):
            self.app.paso_automatico(1.0)
            if not self.app.reproduciendo:
                break
        self.app.dibujar()
        self.assertIn("terminada", self.app.mensaje)
        while self.app.sim.resumen_waves() and any(w["estado"] == "PENDIENTE" for w in self.app.sim.resumen_waves()):
            self.hacer(("marcar_todas", True))
            self.hacer("iniciar_seleccion")
            self.app.sim.avanzar_hasta_terminar()
        self.assertEqual(self.app.sim.metricas()["pedidos_preparados"], 4)
        # Guardar y retomar
        paso_final = self.app.sim.estado.paso
        self.hacer("guardar")
        sesiones = [p for p in self.app.biblioteca.archivos() if p.name.startswith("sesion_")]
        self.assertEqual(len(sesiones), 1)
        self.hacer("inicio")
        self.hacer(("abrir", sesiones[0]))
        self.assertEqual(self.app.sim.estado.paso, paso_final)
        self.assertIn("retomada", self.app.mensaje)
        # Eliminar de la biblioteca
        self.hacer("inicio")
        self.hacer(("eliminar", sesiones[0]))
        self.hacer("confirmar_eliminar")
        self.assertFalse(sesiones[0].exists())

    def test_errores_se_muestran_sin_cerrar(self):
        self.hacer(("abrir", self.carpeta / "escenario_basico.json"))
        msg = self.hacer("adelante", permitir_error=True)
        self.assertIn("No hay pickers", msg)
        self.hacer("nuevo_pedido")
        self.app.formulario["campos"][0][2] = "NOEXISTE x2"
        msg = self.hacer("enviar", permitir_error=True)
        self.assertIn("no existe", msg)
        roto = self.carpeta / "roto.json"
        roto.write_text(json.dumps({"warehouse": {}}), encoding="utf-8")
        manejar_evento(self.app, evento(pygame.DROPFILE, file=str(roto)))
        self.assertIn("inválido", self.app.mensaje)

    def test_escenario_grande_se_dibuja(self):
        self.hacer(("abrir", self.carpeta / "escenario_grande.json"))
        self.hacer("generar_waves")
        self.hacer(("marcar", "WAVE_01"))
        self.hacer(("marcar", "WAVE_02"))
        self.hacer("iniciar_seleccion")
        for _ in range(30):
            self.hacer("adelante")
        for pestana in PESTANAS:
            self.hacer(("pestana", pestana))

    def test_zoom_arrastre_busqueda_y_armado(self):
        self.hacer(("abrir", self.carpeta / "escenario_gen_mediano.json"))
        mapa = self.app.mapa
        celda = (5, 10)
        centro = mapa.centro(celda)
        mapa.zoom_en(centro, 3)
        self.assertEqual(mapa.celda_en(centro), celda)  # el punto bajo el cursor queda fijo
        self.assertAlmostEqual(mapa.zoom, 3)
        self.app.dibujar()
        # Rueda del mouse sobre el mapa
        import tests.pygame_falso as falso
        falso.posicion_mouse[0] = centro
        if hasattr(falso, "Rect") and pygame.Rect is falso.Rect:
            manejar_evento(self.app, evento(pygame.MOUSEWHEEL, y=1))
            self.assertGreater(mapa.zoom, 3)
        # Arrastrar mueve el mapa y no cuenta como clic
        antes = list(mapa.desplazamiento)
        x, y = centro
        manejar_evento(self.app, evento(pygame.MOUSEBUTTONDOWN, button=1, pos=(x, y)))
        manejar_evento(self.app, evento(pygame.MOUSEMOTION, pos=(x + 40, y + 30), buttons=(1, 0, 0)))
        manejar_evento(self.app, evento(pygame.MOUSEBUTTONUP, button=1, pos=(x + 40, y + 30)))
        self.assertNotEqual(mapa.desplazamiento, antes)
        self.hacer("centrar_mapa")
        self.assertEqual(mapa.zoom, 1.0)
        # Comparar armado y cambiar la estrategia de armado
        self.hacer("comparar_armado")
        self.assertEqual(self.app.dialogo, "armado")
        self.hacer("cerrar")
        self.hacer("config")
        indice = [c[0] for c in self.app.formulario["campos"]].index("estrategia_waves")
        self.hacer(("campo", indice))
        self.hacer("enviar")
        self.assertEqual(self.app.sim.config["estrategia_waves"], "PASILLO")
        # Animación de búsqueda al asignar
        self.app.animar_busqueda = True
        self.hacer("generar_waves")
        self.hacer(("marcar_todas", True))
        self.hacer("iniciar_seleccion")
        self.app.dibujar()
        self.assertTrue(self.app.busquedas_activas())
        self.hacer("iniciar")
        paso = self.app.sim.estado.paso
        self.app.paso_automatico(5.0)
        self.assertEqual(self.app.sim.estado.paso, paso)  # espera mientras busca la ruta
        self.hacer("adelante")  # termina la animación
        self.assertFalse(self.app.busquedas_activas())
        self.hacer("adelante")
        self.assertEqual(self.app.sim.estado.paso, paso + 1)

    def test_arranque_con_cuadros(self):
        self.app.run(3)


if __name__ == "__main__":
    unittest.main()
