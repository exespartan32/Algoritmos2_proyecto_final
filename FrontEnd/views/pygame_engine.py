"""Ventana Pygame: biblioteca y panel. Se inicia desde gui.py."""

from pathlib import Path
from datetime import datetime
import json
import uuid
import pygame
from FrontEnd.services.session import Session
from FrontEnd.services.scenarios import generate
from FrontEnd.views.ui_elements import (
    UIElements,
    WHITE,
    BG,
    INK,
    GRAY,
    BLUE,
    LIGHT,
    BORDER,
)
from FrontEnd.events.input_handler import handle_event
from FrontEnd.sprites.node_sprite import draw_cell
from FrontEnd.sprites.picker_sprite import draw_picker

ROOT = Path(__file__).resolve().parents[2]


class App(UIElements):
    def __init__(self, library=None):
        pygame.init()
        pygame.display.set_caption("Wave Picking - Algoritmos II")
        self.screen = pygame.display.set_mode(
            (1520, 960), pygame.SCALED | pygame.RESIZABLE
        )
        self.fonts = {}
        self.buttons = []
        self.running = True
        self.page = "home"
        self.dialog = None
        self.message = "Elegí un escenario o creá uno nuevo."
        self.playing = False
        self.elapsed = 0
        self.model = None
        self.name = ""
        self.stock_page = 0
        self.order_page = 0
        self.wave_page = 0
        self.lib_page = 0
        self.cart = 0
        self.library = Path(library or ROOT / "biblioteca")
        self.library.mkdir(exist_ok=True, parents=True)
        # Se incluyen ejemplos una sola vez. Eliminar no los restaura al reiniciar.
        marker = self.library / ".inicializada"
        if not marker.exists():
            for path in (ROOT / "BackEnd" / "data").glob("escenario_*.json"):
                (self.library / path.name).write_bytes(path.read_bytes())
            marker.touch()
        self.fields = ["10", "50", "20"]
        self.focus = 0

    def import_file(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        # Construcción de la grilla para comprobar también el contrato de lectura.
        Session(data)
        name = Path(path).stem[:45] + "_" + uuid.uuid4().hex[:6] + ".json"
        (self.library / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.dialog = None
        self.message = "Escenario validado y guardado en la biblioteca."

    def open_dialog_file(self):
        import tkinter as tk
        from tkinter.filedialog import askopenfilename

        root = tk.Tk()
        root.withdraw()
        try:
            path = askopenfilename(
                title="Importar escenario JSON", filetypes=[("JSON", "*.json")]
            )
        finally:
            root.destroy()
        if path:
            self.import_file(path)

    def load(self, path):
        model = Session(json.loads(Path(path).read_text(encoding="utf-8-sig")))
        self.model = model
        self.page = "sim"
        self.name = Path(path).stem
        self.playing = False
        self.stock_page = self.order_page = self.wave_page = self.cart = 0
        self.message = "Escenario cargado. Generá waves o continuá el estado guardado."

    def action(self, action):
        try:
            name, *args = action if isinstance(action, tuple) else (action,)
            m = self.model
            if name == "create":
                self.dialog = "create"
            elif name == "generator":
                self.dialog = "generator"
                self.fields = ["10", "50", "20"]
                self.focus = 0
                pygame.key.start_text_input()
            elif name == "field":
                self.focus = args[0]
            elif name == "import":
                self.open_dialog_file()
            elif name == "generate":
                data = generate(*(int(v) for v in self.fields))
                dest = self.library / f"generado_{uuid.uuid4().hex[:6]}.json"
                dest.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                self.dialog = None
                pygame.key.stop_text_input()
                self.message = "Escenario generado y guardado. Ya podés cargarlo."
            elif name == "load":
                self.load(args[0])
            elif name == "delete":
                self.dialog = ("delete", args[0])
            elif name == "confirm_delete":
                target = Path(self.dialog[1]).resolve()
                if target.parent != self.library.resolve() or target.suffix != ".json":
                    raise ValueError("Ruta ajena a la biblioteca.")
                target.unlink()
                self.dialog = None
                self.message = "Escenario eliminado de la biblioteca."
            elif name == "close":
                self.dialog = None
                pygame.key.stop_text_input()
            elif name == "home":
                self.page = "home"
                self.playing = False
            elif name == "resume_screen":
                self.page = "sim"
            elif name == "waves":
                m.generate_waves()
                self.message = (
                    f"{len(m.waves)} waves generadas. Seleccioná una wave."
                    + (" Avisos: " + "; ".join(m.alerts) if m.alerts else "")
                )
            elif name == "select":
                self.dialog = "waves"
                self.playing = False
            elif name == "wave":
                m.select(args[0])
                self.cart = list(m.pickers).index(m.wave["picker"])
                self.dialog = None
                self.playing = False
                self.message = (
                    "Ruta calculada con Dijkstra. Se ejecuta una wave a la vez."
                )
            elif name == "strategy":
                if m.step or m.finished:
                    raise ValueError("Reiniciá la wave antes de cambiar de estrategia.")
                m.set_strategy("Cercanía" if m.strategy == "Orden" else "Orden")
                self.message = "Estrategia: " + m.strategy
            elif name == "compare":
                self.dialog = "compare"
                self.playing = False
            elif name in ("start", "continue"):
                if not m.route:
                    raise ValueError("Primero generá waves y elegí una.")
                if m.finished:
                    raise ValueError("La wave terminó. Reiniciala o seleccioná otra.")
                self.playing = True
                self.elapsed = 0
            elif name == "pause":
                self.playing = False
            elif name == "forward":
                self.playing = False
                m.advance()
            elif name == "back":
                self.playing = False
                m.back()
            elif name == "reset":
                self.playing = False
                m.reset()
                self.message = "Wave reiniciada. Stock y carga restaurados."
            elif name == "save":
                self.playing = False
                dest = (
                    self.library
                    / f"estado_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:4]}.json"
                )
                m.save(dest)
                self.message = "Estado guardado en la biblioteca, incluido el historial para retroceder."
            elif name == "page":
                attr, delta, total, size = args
                setattr(
                    self,
                    attr,
                    max(0, min((total - 1) // size, getattr(self, attr) + delta)),
                )
            elif name == "cart":
                self.cart = (self.cart + 1) % len(m.pickers)
        except Exception as exc:
            self.message = "No se pudo completar la acción: " + str(exc)
            self.playing = False

    def home(self):
        self.text("Inicio · Gestor de escenarios", 30, 95, 27, bold=True)
        self.box(30, 150, 410, 390)
        self.text("Crear escenario", 50, 173, 23, bold=True)
        self.wrap(
            "Importá un JSON existente o completá los parámetros del generador.",
            50,
            217,
            365,
            19,
        )
        self.button("Crear Escenario", 50, 296, 365, "create", selected=True)
        self.text("Desde archivo", 50, 364, 20, bold=True)
        self.wrap("Validar y guardar en la biblioteca.", 50, 397, 360)
        self.text("Generador automático", 50, 444, 20, bold=True)
        self.wrap("Elegir cantidad de racks, productos y pedidos.", 50, 477, 360)
        self.text("Cargar escenario", 480, 158, 23, bold=True)
        paths = sorted(self.library.glob("*.json"))
        self.lib_page = min(self.lib_page, max(0, (len(paths) - 1) // 9))
        self.text("Escenarios guardados", 480, 203, 18, GRAY)
        for i, path in enumerate(paths[self.lib_page * 9 : self.lib_page * 9 + 9]):
            y = 240 + i * 64
            self.box(480, y, 1000, 54)
            self.text(path.stem[:60], 496, y + 17, 18)
            self.button("Cargar / Abrir", 1175, y + 9, 150, ("load", path))
            self.button("Eliminar", 1338, y + 9, 125, ("delete", path))
        self.pager("lib_page", len(paths), 9, 1125, 835)
        if self.model:
            self.button("Volver a la simulación", 50, 583, 365, "resume_screen")
        self.wrap(
            "También podés arrastrar un archivo JSON sobre esta ventana.",
            50,
            670,
            365,
            18,
        )

    def pager(self, attr, total, size, x, y):
        page = getattr(self, attr)
        self.button("<", x, y, 36, ("page", attr, -1, total, size), page > 0)
        self.text(f"{page+1} / {max(1,(total+size-1)//size)}", x + 48, y + 9, 16, GRAY)
        self.button(
            ">",
            x + 112,
            y,
            36,
            ("page", attr, 1, total, size),
            (page + 1) * size < total,
        )

    def map(self):
        m = self.model
        x0, y0, w, h = 30, 228, 710, 600
        size = min(w / m.width, h / m.height)
        left = x0 + (w - size * m.width) / 2
        top = y0 + (h - size * m.height) / 2

        def rect(coord):
            return pygame.Rect(
                round(left + coord[0] * size),
                round(top + (m.height - 1 - coord[1]) * size),
                max(1, round(size)),
                max(1, round(size)),
            )

        explored = set(m.results.get(m.strategy, {}).get("explorados", []))
        for coord, (kind, sense, _) in m.grid.items():
            draw_cell(
                self.screen, rect(coord), kind, sense, self.font, coord in explored
            )
        route = m.route
        if len(route) > 1:
            pygame.draw.lines(
                self.screen,
                BLUE,
                False,
                [rect(p).center for p in route],
                max(2, int(size * 0.1)),
            )
        for index, (pid, pos) in enumerate(m.positions.items()):
            draw_picker(
                self.screen,
                rect(pos),
                index,
                pid == (m.wave or {}).get("picker"),
                self.font,
            )
        self.text(
            f"Origen (0,0) abajo a la izquierda · {m.width} × {m.height}",
            30,
            846,
            16,
            GRAY,
        )
        self.text(
            "# Rack   D Despacho   P Puerta   Círculos: pickers   Celeste: explorados",
            30,
            873,
            16,
            GRAY,
        )

    def simulation(self):
        m = self.model
        self.text(self.name[:70], 30, 72, 18, GRAY)
        self.button("Inicio", 1390, 20, 100, "home")
        self.button("Generar Waves", 30, 104, 165, "waves", not bool(m.waves))
        self.button("Seleccionar Wave", 205, 104, 185, "select", bool(m.waves))
        self.button(
            "Estrategia: " + m.strategy, 400, 104, 210, "strategy", bool(m.results)
        )
        self.button("Comparar Estrategias", 620, 104, 220, "compare", bool(m.results))
        self.button("Guardar Escenario", 850, 104, 200, "save")
        valid = bool(m.route)
        for label, x, w, action, enabled in [
            (
                "Iniciar",
                30,
                110,
                "start",
                valid and not m.finished and not self.playing,
            ),
            ("Pausar", 150, 110, "pause", self.playing),
            (
                "Continuar",
                270,
                120,
                "continue",
                valid and not self.playing and not m.finished,
            ),
            ("Paso Adelante >", 400, 165, "forward", valid and not m.finished),
            ("Paso Atrás <", 575, 145, "back", bool(m.history)),
            ("Reiniciar", 730, 130, "reset", bool(m.baseline)),
        ]:
            self.button(label, x, 151, w, action, enabled)
        result = m.results.get(m.strategy)
        self.text(
            f'Wave: {m.wave["id"] if m.wave else "sin seleccionar"}    Paso: {m.step}    Estado: {"en reproducción" if self.playing else "pausado" if not m.finished else "finalizado"}',
            30,
            202,
            17,
        )
        if result:
            self.text(
                f'Dijkstra: {result["distancia"]} pasos · {result["nodos"]} nodos explorados · {result["tiempo"]:.2f} ms',
                780,
                191,
                17,
                BLUE,
            )
        self.map()
        # Stock: todas las columnas solicitadas y paginación.
        self.box(780, 228, 710, 300)
        self.text("Productos disponibles · Stock en racks", 794, 239, 20, bold=True)
        headers = [
            ("ID", 794),
            ("Nombre", 865),
            ("(x,y)", 1086),
            ("z", 1171),
            ("kg/u", 1215),
            ("Stock", 1290),
        ]
        for label, x in headers:
            self.text(label, x, 274, 16, GRAY, True)
        prods = list(m.products.values())
        for i, p in enumerate(prods[self.stock_page * 7 : self.stock_page * 7 + 7]):
            y = 302 + i * 25
            u = p["ubicacion"]
            for value, x in [
                (p["id"], 794),
                (p["nombre"][:24], 865),
                (f'({u["x"]},{u["y"]})', 1086),
                (u["z"], 1171),
                (p["peso_kg"], 1215),
                (m.stock[p["id"]], 1290),
            ]:
                self.text(value, x, y, 16)
        self.pager("stock_page", len(prods), 7, 1328, 482)
        # Carritos: un selector para consultar cada picker.
        self.box(780, 542, 710, 160)
        pids = list(m.pickers)
        pid = pids[self.cart]
        pk = m.pickers[pid]
        load = sum(m.products[k]["peso_kg"] * v for k, v in m.cargo[pid].items())
        self.text(f"Productos recogidos · {pid}", 794, 554, 20, bold=True)
        self.button("Cambiar picker", 1308, 551, 165, "cart", len(pids) > 1)
        self.text(
            f'Carga: {load:.2f} / {pk["capacidad_carga_kg"]:g} kg', 794, 588, 18, BLUE
        )
        cargo = (
            ", ".join(f"{p}: {q} u." for p, q in m.cargo[pid].items())
            or "Carrito vacío. Al volver a despacho, se descarga."
        )
        self.wrap(cargo, 794, 620, 670, 17, limit=3)
        # Pedidos y waves permanecen visibles juntos.
        self.box(780, 716, 710, 181)
        self.text("Pedidos y waves", 794, 727, 20, bold=True)
        orders = list(m.orders.values())
        for i, o in enumerate(orders[self.order_page * 4 : self.order_page * 4 + 4]):
            y = 763 + i * 26
            wave = next((w for w in m.waves if o["id"] in w["pedidos"]), None)
            self.text(o["id"], 794, y, 16)
            self.text(m.status[o["id"]], 926, y, 16)
            self.text(
                f'{wave["id"]} / {wave["estado"]}' if wave else "Sin wave", 1115, y, 16
            )
        self.pager("order_page", len(orders), 4, 1328, 853)

    def modal(self):
        overlay = pygame.Surface((1520, 960), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 80))
        self.screen.blit(overlay, (0, 0))
        self.buttons = []
        self.box(360, 210, 800, 540)
        kind = self.dialog[0] if isinstance(self.dialog, tuple) else self.dialog
        self.button("Cerrar", 1020, 229, 115, "close")
        if kind == "create":
            self.text("Crear escenario", 390, 246, 28, bold=True)
            self.text("¿Cómo querés crearlo?", 390, 316, 21)
            self.button("Desde archivo JSON", 390, 385, 340, "import")
            self.button("Generador automático", 750, 385, 375, "generator")
            self.wrap(
                "El archivo se valida y se copia a la biblioteca. El generador usa ScenarioGenerator del equipo con pasillos y racks.",
                390,
                466,
                730,
                20,
            )
        elif kind == "generator":
            self.text("Generador automático", 390, 246, 28, bold=True)
            for i, label in enumerate(
                [
                    "Cantidad de racks (1–30)",
                    "Cantidad de productos (1–300)",
                    "Cantidad de pedidos (1–100)",
                ]
            ):
                y = 330 + i * 76
                self.text(label, 390, y + 11, 20)
                self.box(850, y, 250, 44, LIGHT if i == self.focus else WHITE)
                self.text(self.fields[i], 865, y + 10, 23)
                self.buttons.append((pygame.Rect(850, y, 250, 44), ("field", i), True))
            self.button("Generar y guardar", 390, 615, 320, "generate", selected=True)
        elif kind == "delete":
            self.text("Eliminar escenario", 390, 246, 28, bold=True)
            self.wrap(
                "Se eliminará de la biblioteca: " + Path(self.dialog[1]).name,
                390,
                340,
                720,
                22,
            )
            self.button("Eliminar", 390, 500, 210, "confirm_delete")
            self.button("Cancelar", 620, 500, 210, "close")
        elif kind == "compare":
            self.text(
                "Comparar estrategias · " + self.model.wave["id"],
                390,
                246,
                26,
                bold=True,
            )
            self.text(
                "Dijkstra: orden de pedidos o destino más cercano.", 390, 302, 19, GRAY
            )
            for text, x in [("Métrica", 390), ("Orden", 740), ("Cercanía", 940)]:
                self.text(text, x, 365, 22, bold=True)
            for i, (label, key) in enumerate(
                [
                    ("Distancia / pasos", "distancia"),
                    ("Nodos explorados", "nodos"),
                    ("Tiempo (ms)", "tiempo"),
                ]
            ):
                y = 416 + i * 58
                self.text(label, 390, y, 21)
                for strategy, x in [("Orden", 740), ("Cercanía", 940)]:
                    self.text(self.model.results[strategy][key], x, y, 21)
            self.wrap(
                "Nodos únicos explorados entre tramos. Tiempo medido en esta ejecución. Aristas = pasos de la ruta.",
                390,
                628,
                720,
                18,
                GRAY,
            )
        elif kind == "waves":
            self.text("Seleccionar wave", 390, 246, 28, bold=True)
            waves = self.model.waves
            for i, w in enumerate(waves[self.wave_page * 6 : self.wave_page * 6 + 6]):
                y = 322 + i * 52
                self.text(
                    f'{w["id"]} · {len(w["pedidos"])} pedidos · {w["peso"]} kg · {w["picker"]}',
                    390,
                    y + 7,
                    19,
                )
                self.button(
                    "Seleccionar",
                    960,
                    y,
                    170,
                    ("wave", self.wave_page * 6 + i),
                    w["estado"] != "FINALIZADA",
                )
            self.pager("wave_page", len(waves), 6, 930, 670)

    def draw(self):
        self.screen.fill(BG)
        self.buttons = []
        self.text("Wave Picking", 30, 22, 30, bold=True)
        self.text("Simulación por wave · Algoritmos II", 260, 31, 18, GRAY)
        if self.page == "home":
            self.home()
        else:
            self.simulation()
        if self.dialog:
            self.modal()
        self.wrap(self.message, 30, 912, 1450, 16, BLUE, limit=2)
        pygame.display.flip()

    def event(self, event):
        handle_event(self, event)

    def run(self, frames=None):
        clock = pygame.time.Clock()
        count = 0
        while self.running and (frames is None or count < frames):
            dt = clock.tick(30) / 1000
            for event in pygame.event.get():
                self.event(event)
            if self.playing and not self.dialog:
                self.elapsed += dt
                if self.elapsed >= 0.18:
                    self.elapsed = 0
                    try:
                        self.model.advance()
                        self.playing = not self.model.finished
                    except Exception as exc:
                        self.message = str(exc)
                        self.playing = False
            self.draw()
            count += 1
