"""Elementos gráficos reutilizables: texto, paneles, botones, casillas y campos.

Todo se dibuja sobre un lienzo fijo de ANCHO x ALTO que después se escala a la
ventana, así la interfaz se ve igual en cualquier resolución.
"""

import pygame

ANCHO, ALTO = 1520, 960

BLANCO = (255, 255, 255)
FONDO = (238, 241, 245)
TINTA = (31, 41, 51)
GRIS = (98, 109, 122)
GRIS_CLARO = (228, 231, 235)
AZUL = (37, 99, 166)
AZUL_CLARO = (222, 233, 247)
BORDE = (190, 199, 210)
ROJO = (176, 52, 46)
VERDE = (42, 128, 79)
AMBAR = (214, 140, 22)


class UIElements:
    """Mezcla para la App: espera ``self.lienzo``, ``self.fuentes`` y ``self.botones``."""

    def fuente(self, tam=18, negrita=False):
        clave = (tam, negrita)
        if clave not in self.fuentes:
            self.fuentes[clave] = pygame.font.SysFont("arial", tam, bold=negrita)
        return self.fuentes[clave]

    def texto(self, valor, x, y, tam=18, color=TINTA, negrita=False, max_ancho=None):
        valor = str(valor)
        fuente = self.fuente(tam, negrita)
        if max_ancho is not None:
            while valor and fuente.size(valor)[0] > max_ancho:
                valor = valor[:-2] + "…" if len(valor) > 2 else ""
        self.lienzo.blit(fuente.render(valor, True, color), (round(x), round(y)))

    def parrafo(self, valor, x, y, ancho, tam=17, color=GRIS, limite=3):
        lineas, linea = [], ""
        for palabra in str(valor).split():
            candidata = (linea + " " + palabra).strip()
            if self.fuente(tam).size(candidata)[0] > ancho and linea:
                lineas.append(linea)
                linea = palabra
            else:
                linea = candidata
        if linea:
            lineas.append(linea)
        for i, linea in enumerate(lineas[:limite]):
            self.texto(linea, x, y + i * (tam + 5), tam, color)
        return min(len(lineas), limite)

    def caja(self, x, y, w, h, color=BLANCO, borde=BORDE):
        rect = pygame.Rect(round(x), round(y), round(w), round(h))
        pygame.draw.rect(self.lienzo, color, rect)
        if borde:
            pygame.draw.rect(self.lienzo, borde, rect, 1)
        return rect

    def boton(self, etiqueta, x, y, w, accion, habilitado=True, marcado=False, alto=34):
        rect = pygame.Rect(round(x), round(y), round(w), alto)
        relleno = AZUL if marcado else BLANCO if habilitado else GRIS_CLARO
        self.caja(x, y, w, alto, relleno)
        color = BLANCO if marcado else TINTA if habilitado else (150, 155, 162)
        imagen = self.fuente(16).render(str(etiqueta), True, color)
        self.lienzo.blit(imagen, imagen.get_rect(center=rect.center))
        self.botones.append((rect, accion, habilitado))
        return rect

    def zona_clic(self, rect, accion):
        """Área invisible que responde al clic (filas de tablas, mapa)."""
        self.botones.append((pygame.Rect(rect), accion, True))

    def casilla(self, x, y, marcada, accion, habilitada=True):
        rect = self.caja(x, y, 20, 20, BLANCO if habilitada else GRIS_CLARO)
        if marcada:
            pygame.draw.line(self.lienzo, AZUL, (x + 4, y + 10), (x + 8, y + 15), 3)
            pygame.draw.line(self.lienzo, AZUL, (x + 8, y + 15), (x + 16, y + 4), 3)
        self.botones.append((rect, accion, habilitada))

    def campo(self, x, y, w, valor, enfocado, accion):
        rect = self.caja(x, y, w, 36, AZUL_CLARO if enfocado else BLANCO, AZUL if enfocado else BORDE)
        self.texto(str(valor) + ("|" if enfocado else ""), x + 10, y + 8, 18, max_ancho=w - 16)
        self.botones.append((rect, accion, True))

    def paginador(self, atributo, total, por_pagina, x, y):
        pagina = getattr(self, atributo)
        paginas = max(1, (total + por_pagina - 1) // por_pagina)
        self.boton("<", x, y, 34, ("pagina", atributo, -1, total, por_pagina), pagina > 0, alto=30)
        self.texto(f"{pagina + 1} / {paginas}", x + 44, y + 6, 15, GRIS)
        self.boton(">", x + 104, y, 34, ("pagina", atributo, 1, total, por_pagina), pagina + 1 < paginas, alto=30)
