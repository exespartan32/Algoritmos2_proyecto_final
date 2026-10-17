"""Dibujo de celdas; no decide por dónde puede avanzar un picker."""

import pygame

COLORS = {
    "PASILLO": (251, 252, 253),
    "RACK": (155, 166, 176),
    "DESPACHO": (174, 212, 184),
    "PUERTA": (241, 208, 146),
}


def draw_cell(surface, rect, kind, sense, font, explored=False):
    color = (224, 237, 248) if explored and kind == "PASILLO" else COLORS[kind]
    pygame.draw.rect(surface, color, rect)
    pygame.draw.rect(surface, (193, 201, 211), rect, 1)
    color = (96, 107, 120)
    if kind == "PASILLO" and sense != "AMBOS":
        dx, dy = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "O": (-1, 0)}[sense]
        cx, cy = rect.center
        length = max(2, rect.width * 0.25)
        end = (cx + dx * length, cy + dy * length)
        pygame.draw.line(surface, color, (cx - dx * length, cy - dy * length), end)
        for side in (-1, 1):
            pygame.draw.line(
                surface,
                color,
                end,
                (
                    end[0] - dx * length + dy * length * side,
                    end[1] - dy * length - dx * length * side,
                ),
            )
    elif rect.width >= 17:
        symbol = {"RACK": "#", "DESPACHO": "D", "PUERTA": "P"}.get(kind, "·")
        image = font(max(12, int(rect.width * 0.43))).render(symbol, True, color)
        surface.blit(image, image.get_rect(center=rect.center))
