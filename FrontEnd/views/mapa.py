"""Dibujo del mapa: celdas, exploración de Dijkstra, rutas, destinos y pickers."""

import pygame

from FrontEnd.sprites.node_sprite import dibujar_celda
from FrontEnd.sprites.picker_sprite import color_picker, dibujar_picker
from FrontEnd.views.ui_elements import GRIS, TINTA, AMBAR


def _aclarar(color, factor=0.55):
    return tuple(int(c + (255 - c) * factor) for c in color)


class VistaMapa:
    def __init__(self, app, x, y, w, h):
        self.app = app
        self.area = pygame.Rect(x, y, w, h)

    def geometria(self):
        m = self.app.sim
        lado = min(self.area.width / m.ancho, self.area.height / m.alto)
        izquierda = self.area.x + (self.area.width - lado * m.ancho) / 2
        arriba = self.area.y + (self.area.height - lado * m.alto) / 2
        return lado, izquierda, arriba

    def rect_celda(self, coord):
        lado, izq, arr = self.geometria()
        x, y = coord
        x0 = round(izq + x * lado)
        y0 = round(arr + (self.app.sim.alto - 1 - y) * lado)
        x1 = round(izq + (x + 1) * lado)
        y1 = round(arr + (self.app.sim.alto - y) * lado)
        return pygame.Rect(x0, y0, max(1, x1 - x0), max(1, y1 - y0))

    def celda_en(self, pos):
        lado, izq, arr = self.geometria()
        x = int((pos[0] - izq) // lado)
        y = self.app.sim.alto - 1 - int((pos[1] - arr) // lado)
        if 0 <= x < self.app.sim.ancho and 0 <= y < self.app.sim.alto:
            return (x, y)
        return None

    def dibujar(self):
        app, m = self.app, self.app.sim
        lienzo = app.lienzo
        pickers = m.resumen_pickers()
        enfocado = app.picker_enfocado(pickers)
        plan = enfocado["plan"] if enfocado else None
        explorados = set(plan["explorados"]) if plan and app.ver_exploracion else set()
        resaltadas = app.celdas_resaltadas()

        for coord, (tipo, sentido, _) in m.celdas.items():
            dibujar_celda(
                lienzo,
                self.rect_celda(coord),
                tipo,
                sentido,
                app.fuente,
                explorado=coord in explorados,
                interseccion=coord in m.intersecciones,
                productos=app.productos_por_celda.get(coord, 0),
                resaltada=coord in resaltadas,
            )

        # Nombre de cada zona de despacho sobre su rectángulo.
        for zona in m.warehouse.zonas_despacho.values():
            r1 = self.rect_celda((zona.x, zona.y + zona.alto - 1))
            r2 = self.rect_celda((zona.x + zona.ancho - 1, zona.y))
            rect = r1.union(r2)
            tam = max(9, min(18, rect.height // 2))
            while tam > 9 and app.fuente(tam, True).size(zona.id)[0] > rect.width - 4:
                tam -= 1
            if app.fuente(tam, True).size(zona.id)[0] <= rect.width + 8:
                imagen = app.fuente(tam, True).render(zona.id, True, (30, 90, 50))
                lienzo.blit(imagen, imagen.get_rect(center=rect.center))

        lado = self.geometria()[0]
        grosor = max(2, int(lado * 0.16))
        indices = {p["id"]: i for i, p in enumerate(pickers)}
        for p in pickers:
            color = color_picker(indices[p["id"]])
            hecho = p["recorrido"][-400:]
            if len(hecho) > 1:
                pygame.draw.lines(lienzo, _aclarar(color, 0.6), False, [self.rect_celda(c).center for c in hecho], max(1, grosor - 1))
            futuro = [p["pos"]] + p["ruta_restante"]
            if len(futuro) > 1:
                pygame.draw.lines(lienzo, color, False, [self.rect_celda(c).center for c in futuro], grosor)

        # Destinos numerados del picker enfocado (orden de visita del plan).
        if plan:
            pendientes = {c for c, _ in app.pendientes_por_celda(enfocado)}
            for n, celda in enumerate(plan["destinos"], start=1):
                rect = self.rect_celda(celda)
                color = AMBAR if celda in pendientes else GRIS
                pygame.draw.circle(lienzo, color, rect.center, max(5, int(lado * 0.36)))
                if lado >= 12:
                    imagen = app.fuente(max(9, int(lado * 0.42)), True).render(str(n), True, (255, 255, 255))
                    lienzo.blit(imagen, imagen.get_rect(center=rect.center))
            despacho = self.rect_celda(plan["despacho"])
            pygame.draw.rect(lienzo, (30, 90, 50), despacho, max(2, int(lado * 0.15)))

        for p in pickers:
            dibujar_picker(
                lienzo,
                self.rect_celda(p["pos"]),
                indices[p["id"]],
                enfocado is not None and p["id"] == enfocado["id"],
                app.fuente,
                cargado=bool(p["recogidos"]),
            )
        app.zona_clic(self.area, ("mapa",))

    def leyenda(self, x, y):
        app = self.app
        items = [
            ((251, 252, 253), "Pasillo (flecha = sentido)"),
            ((241, 244, 248), "Intersección"),
            ((120, 131, 143), "Rack con productos (cantidad)"),
            ((172, 214, 184), "Zona de despacho"),
            ((242, 205, 140), "Puerta"),
            ((219, 234, 250), "Explorado por Dijkstra"),
            (AMBAR, "Producto por recoger (n° = orden)"),
        ]
        cx = x
        for color, etiqueta in items:
            pygame.draw.rect(app.lienzo, color, pygame.Rect(cx, y + 3, 14, 14))
            pygame.draw.rect(app.lienzo, (190, 199, 210), pygame.Rect(cx, y + 3, 14, 14), 1)
            app.texto(etiqueta, cx + 19, y + 1, 14, TINTA)
            cx += 24 + app.fuente(14).size(etiqueta)[0] + 10
            if cx > x + 560:
                cx = x
                y += 20
