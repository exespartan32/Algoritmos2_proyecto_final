"""Dibujo de los pickers como operadores con carrito de compras y etiquetas identificatorias."""

from pathlib import Path
import pygame

COLORES = [
    (37, 99, 166),
    (196, 90, 30),
    (124, 65, 145),
    (31, 128, 98),
    (176, 52, 46),
    (90, 110, 20),
    (20, 120, 150),
    (150, 60, 100),
    (100, 80, 50),
    (60, 60, 160),
]
IMAGEN = Path(__file__).with_name("picker.png")
BASE = 96
ANGULOS = {(0, 1): 0, (-1, 0): 90, (0, -1): 180, (1, 0): -90}

_cache = {}
_imagen_usuario = None


def color_picker(indice):
    return COLORES[indice % len(COLORES)]


def angulo_para(dx, dy, anterior=0):
    if dx == 0 and dy == 0:
        return anterior
    if abs(dx) >= abs(dy):
        return ANGULOS[(1 if dx > 0 else -1, 0)]
    return ANGULOS[(0, 1 if dy > 0 else -1)]


def _cargar_imagen():
    global _imagen_usuario
    if _imagen_usuario is None:
        _imagen_usuario = False
        if IMAGEN.exists():
            try:
                imagen = pygame.image.load(str(IMAGEN))
                imagen = (
                    imagen.convert_alpha() if pygame.display.get_surface() else imagen
                )
                _imagen_usuario = pygame.transform.smoothscale(imagen, (BASE, BASE))
            except Exception:
                _imagen_usuario = False
    return _imagen_usuario


def _dibujo_base(color):
    s = pygame.Surface((BASE, BASE), pygame.SRCALPHA)
    oscuro = tuple(max(0, c - 60) for c in color)
    claro = tuple(min(255, c + 70) for c in color)
    grosor = 5
    carro = pygame.Rect(22, 6, 52, 34)
    pygame.draw.rect(s, (235, 238, 242), carro)
    pygame.draw.rect(s, (242, 205, 140), pygame.Rect(28, 11, 18, 14))
    pygame.draw.rect(s, (225, 180, 110), pygame.Rect(49, 15, 18, 18))
    pygame.draw.rect(s, color, carro, grosor)
    pygame.draw.line(s, color, (24, 44), (72, 44), grosor)
    pygame.draw.line(s, oscuro, (30, 62), (32, 46), 7)
    pygame.draw.line(s, oscuro, (66, 62), (64, 46), 7)
    pygame.draw.ellipse(s, claro, pygame.Rect(22, 54, 52, 30))
    pygame.draw.ellipse(s, color, pygame.Rect(22, 54, 52, 30), grosor)
    pygame.draw.circle(s, (250, 204, 21), (48, 68), 12)
    pygame.draw.circle(s, oscuro, (48, 68), 12, 3)
    return s


def _imagen_con_borde(color):
    imagen = _cargar_imagen()
    if not imagen:
        return _dibujo_base(color)
    s = pygame.Surface((BASE, BASE), pygame.SRCALPHA)
    s.blit(imagen, (0, 0))
    if hasattr(pygame, "mask"):
        contorno = pygame.mask.from_surface(imagen).outline()
        if len(contorno) > 2:
            pygame.draw.lines(s, color, True, contorno, 5)
    return s


def sprite(indice, angulo, lado):
    lado = max(12, int(lado))
    clave = (indice, angulo, lado, bool(_cargar_imagen()))
    if clave not in _cache:
        base = _imagen_con_borde(color_picker(indice))
        girada = pygame.transform.rotate(base, angulo)
        _cache[clave] = pygame.transform.smoothscale(girada, (lado, lado))
    return _cache[clave]


def dibujar_picker(
    superficie,
    centro,
    lado_celda,
    indice,
    angulo,
    nombre,
    fuente,
    enfocado=False,
    estado="",
):
    lado = max(14, int(lado_celda * 1.6))
    cx, cy = round(centro[0]), round(centro[1])
    color = color_picker(indice)
    if enfocado:
        pygame.draw.circle(superficie, (15, 20, 25), (cx, cy), lado // 2 + 2, 2)
    imagen = sprite(indice, angulo, lado)
    superficie.blit(imagen, imagen.get_rect(center=(cx, cy)))
    tam = max(10, min(15, int(lado_celda * 0.6)))
    texto = fuente(tam, True).render(
        nombre + (f" · {estado}" if estado else ""), True, (255, 255, 255)
    )
    rect = texto.get_rect(center=(cx, cy - lado // 2 - tam // 2 - 3))
    fondo = pygame.Rect(rect.x - 4, rect.y - 1, rect.width + 8, rect.height + 2)
    pygame.draw.rect(superficie, color, fondo)
    pygame.draw.rect(superficie, (255, 255, 255), fondo, 1)
    superficie.blit(texto, rect)
