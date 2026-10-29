"""Sustituto mínimo de pygame para probar la interfaz sin pantalla.

Solo se usa en los tests cuando pygame no está instalado. Imita la parte de la
API que usa FrontEnd y registra lo dibujado para poder hacer comprobaciones.
"""

import sys
import types

QUIT, MOUSEBUTTONDOWN, KEYDOWN, TEXTINPUT, DROPFILE, MOUSEWHEEL, VIDEORESIZE = range(1, 8)
RESIZABLE, SRCALPHA = 16, 65536
K_ESCAPE, K_BACKSPACE, K_TAB, K_RETURN, K_KP_ENTER = 27, 8, 9, 13, 271
K_RIGHT, K_LEFT, K_UP, K_DOWN, K_SPACE, K_r = 275, 276, 273, 274, 32, 114

textos_dibujados = []


class error(Exception):
    pass


class Rect:
    def __init__(self, *args):
        if len(args) == 1:
            args = tuple(args[0]) if not isinstance(args[0], Rect) else (args[0].x, args[0].y, args[0].w, args[0].h)
        if len(args) == 2:
            (x, y), (w, h) = args
        else:
            x, y, w, h = args
        for v in (x, y, w, h):
            if not isinstance(v, (int, float)):
                raise TypeError("Rect necesita números")
        self.x, self.y, self.w, self.h = int(x), int(y), int(w), int(h)

    width = property(lambda s: s.w)
    height = property(lambda s: s.h)
    center = property(lambda s: (s.x + s.w // 2, s.y + s.h // 2))
    topleft = property(lambda s: (s.x, s.y))

    size = property(lambda s: (s.w, s.h))

    def __iter__(self):
        return iter((self.x, self.y, self.w, self.h))

    def move(self, dx, dy):
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def collidepoint(self, pos):
        return self.x <= pos[0] < self.x + self.w and self.y <= pos[1] < self.y + self.h

    def union(self, otro):
        x, y = min(self.x, otro.x), min(self.y, otro.y)
        return Rect(x, y, max(self.x + self.w, otro.x + otro.w) - x, max(self.y + self.h, otro.y + otro.h) - y)


class Surface:
    def __init__(self, size, flags=0):
        self.size = (int(size[0]), int(size[1]))

    def fill(self, color):
        assert len(color) in (3, 4)

    def blit(self, otra, pos):
        assert isinstance(otra, Surface)
        assert isinstance(pos, Rect) or len(pos) == 2

    def get_size(self):
        return self.size

    def get_rect(self, **kw):
        r = Rect(0, 0, *self.size)
        if "center" in kw:
            r.x, r.y = kw["center"][0] - r.w // 2, kw["center"][1] - r.h // 2
        return r


class _Font:
    def __init__(self, nombre, tam, bold=False):
        self.tam = tam

    def size(self, texto):
        return (int(len(texto) * self.tam * 0.52), self.tam)

    def render(self, texto, aa, color):
        assert isinstance(texto, str) and len(color) == 3
        textos_dibujados.append(texto)
        return Surface(self.size(texto))


def _punto(p):
    assert len(p) == 2 and all(isinstance(v, (int, float)) for v in p), p


def _rect(superficie, color, rect, ancho=0):
    assert isinstance(rect, Rect) and len(color) in (3, 4)


def _line(superficie, color, a, b, ancho=1):
    _punto(a)
    _punto(b)


def _lines(superficie, color, cerrado, puntos, ancho=1):
    assert len(puntos) >= 2
    for p in puntos:
        _punto(p)


def _ellipse(superficie, color, rect, ancho=0):
    assert isinstance(rect, Rect)


def _circle(superficie, color, centro, radio, ancho=0):
    _punto(centro)
    assert radio >= 0


class _Clock:
    def tick(self, fps=0):
        return 33


class Event:
    def __init__(self, tipo, **kw):
        self.type = tipo
        self.__dict__.update(kw)


cola_eventos = []


def instalar():
    m = types.ModuleType("pygame")
    m.__dict__.update({k: v for k, v in globals().items() if k.isupper() or k.startswith("K_")})
    m.Rect, m.Surface, m.error = Rect, Surface, error
    m.init = lambda: None
    m.quit = lambda: None
    m.display = types.SimpleNamespace(
        set_caption=lambda t: None,
        set_mode=lambda size, flags=0: Surface(size),
        flip=lambda: None,
        get_surface=lambda: None,
        Info=lambda: types.SimpleNamespace(current_w=1920, current_h=1080),
    )
    m.font = types.SimpleNamespace(SysFont=_Font)
    m.draw = types.SimpleNamespace(rect=_rect, line=_line, lines=_lines, circle=_circle, ellipse=_ellipse)
    m.transform = types.SimpleNamespace(
        smoothscale=lambda s, size: Surface(size),
        scale=lambda s, size: Surface(size),
        rotate=lambda s, angulo: Surface(s.size),
    )
    m.time = types.SimpleNamespace(Clock=_Clock)
    m.event = types.SimpleNamespace(get=lambda: [cola_eventos.pop(0) for _ in list(cola_eventos)], Event=Event)
    m.key = types.SimpleNamespace(start_text_input=lambda: None, stop_text_input=lambda: None)
    m.mouse = types.SimpleNamespace(get_pos=lambda: (0, 0))
    sys.modules["pygame"] = m
    return m
