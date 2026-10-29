"""Dibujo de los pickers: un círculo de color con su número."""

import pygame

COLORES = [
    (37, 99, 166), (196, 90, 30), (124, 65, 145), (31, 128, 98),
    (176, 52, 46), (90, 110, 20), (20, 120, 150), (150, 60, 100),
    (100, 80, 50), (60, 60, 160),
]


def color_picker(indice):
    return COLORES[indice % len(COLORES)]


def dibujar_picker(superficie, rect, indice, enfocado, fuente, cargado=False):
    radio = max(4, int(rect.width * 0.42))
    centro = rect.center
    pygame.draw.circle(superficie, color_picker(indice), centro, radio)
    if cargado:
        # Una "caja" chica indica que lleva productos.
        lado = max(3, radio // 2)
        pygame.draw.rect(superficie, (242, 205, 140), pygame.Rect(centro[0] + radio - lado, centro[1] - radio, lado, lado))
    if enfocado:
        pygame.draw.circle(superficie, (15, 20, 25), centro, radio + 2, 2)
    if rect.width >= 14:
        imagen = fuente(max(10, int(rect.width * 0.45)), True).render(str(indice + 1), True, (255, 255, 255))
        superficie.blit(imagen, imagen.get_rect(center=centro))
