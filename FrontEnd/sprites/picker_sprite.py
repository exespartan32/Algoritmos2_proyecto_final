"""Representación de todos los pickers; borde negro en el seleccionado."""

import pygame

COLORS = [(41, 81, 132), (168, 85, 35), (124, 65, 145), (36, 117, 91)]


def draw_picker(surface, rect, index, active, font):
    radius = max(4, int(rect.width * 0.35))
    pygame.draw.circle(surface, COLORS[index % len(COLORS)], rect.center, radius)
    if active:
        pygame.draw.circle(surface, (20, 25, 30), rect.center, radius, 1)
    if rect.width >= 19:
        image = font(max(12, int(rect.width * 0.36)), True).render(
            str(index + 1), True, (255, 255, 255)
        )
        surface.blit(image, image.get_rect(center=rect.center))
