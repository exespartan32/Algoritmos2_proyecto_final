"""Elementos gráficos reutilizables: texto, paneles y botones."""

import pygame

WHITE = (255, 255, 255)
BG = (240, 242, 245)
INK = (33, 42, 52)
GRAY = (96, 107, 120)
BLUE = (40, 101, 166)
LIGHT = (224, 234, 247)
BORDER = (193, 201, 211)
RED = (167, 54, 49)


class UIElements:
    def font(self, size=18, bold=False):
        if (size, bold) not in self.fonts:
            self.fonts[size, bold] = pygame.font.SysFont("arial", size, bold=bold)
        return self.fonts[size, bold]

    def text(self, value, x, y, size=18, color=INK, bold=False):
        self.screen.blit(self.font(size, bold).render(str(value), True, color), (x, y))

    def wrap(self, value, x, y, width, size=17, color=GRAY, limit=3):
        lines = []
        line = ""
        for word in str(value).split():
            candidate = (line + " " + word).strip()
            if self.font(size).size(candidate)[0] > width and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        for i, line in enumerate(lines[:limit]):
            self.text(line, x, y + i * (size + 5), size, color)

    def box(self, x, y, w, h, color=WHITE):
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, color, rect)
        pygame.draw.rect(self.screen, BORDER, rect, 1)
        return rect

    def button(self, label, x, y, w, action, enabled=True, selected=False):
        rect = pygame.Rect(x, y, w, 36)
        fill = BLUE if selected else WHITE if enabled else (228, 231, 234)
        self.box(x, y, w, 36, fill)
        label_color = WHITE if selected else INK if enabled else (145, 151, 157)
        image = self.font(17).render(label, True, label_color)
        self.screen.blit(image, image.get_rect(center=rect.center))
        self.buttons.append((rect, action, enabled))
