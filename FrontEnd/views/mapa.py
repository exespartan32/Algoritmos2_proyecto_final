"""Dibujo del mapa: celdas, exploración de Dijkstra, rutas, destinos y pickers.

Se puede acercar y alejar con la rueda del mouse (el punto bajo el cursor
queda fijo) y mover arrastrando, como en un mapa en línea. Siempre es vista
desde arriba.
"""

import pygame

from FrontEnd.sprites.node_sprite import dibujar_celda
from FrontEnd.sprites.picker_sprite import angulo_para, color_picker, dibujar_picker
from FrontEnd.views.ui_elements import AMBAR, GRIS, TINTA

ZOOM_MIN, ZOOM_MAX = 1.0, 16.0


def _aclarar(color, factor=0.55):
    return tuple(int(c + (255 - c) * factor) for c in color)


class VistaMapa:
    def __init__(self, app, x, y, w, h):
        self.app = app
        self.area = pygame.Rect(x, y, w, h)
        self.zoom = 1.0
        self.desplazamiento = [0.0, 0.0]
        self._orden_unico = {}

    # ------------------------------------------------------------------
    # Geometría, zoom y arrastre
    # ------------------------------------------------------------------
    def geometria(self):
        m = self.app.sim
        lado = min(self.area.width / m.ancho, self.area.height / m.alto) * self.zoom
        izquierda = self.area.x + (self.area.width - lado * m.ancho) / 2 + self.desplazamiento[0]
        arriba = self.area.y + (self.area.height - lado * m.alto) / 2 + self.desplazamiento[1]
        return lado, izquierda, arriba

    def _limitar(self):
        """El mapa no puede irse fuera de la vista: siempre queda algo a la vista."""
        m = self.app.sim
        lado = min(self.area.width / m.ancho, self.area.height / m.alto) * self.zoom
        for eje, tam_mapa, tam_area in ((0, lado * m.ancho, self.area.width), (1, lado * m.alto, self.area.height)):
            limite = max(0.0, (tam_mapa - tam_area) / 2 + tam_area * 0.3) if self.zoom > 1 else 0.0
            self.desplazamiento[eje] = max(-limite, min(limite, self.desplazamiento[eje]))

    def zoom_en(self, pos, factor):
        """Acerca (factor > 1) o aleja manteniendo fijo el punto bajo el cursor."""
        lado, izq, arr = self.geometria()
        mundo_x, mundo_y = (pos[0] - izq) / lado, (pos[1] - arr) / lado
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom * factor))
        m = self.app.sim
        lado2 = min(self.area.width / m.ancho, self.area.height / m.alto) * self.zoom
        centrado_x = self.area.x + (self.area.width - lado2 * m.ancho) / 2
        centrado_y = self.area.y + (self.area.height - lado2 * m.alto) / 2
        self.desplazamiento = [pos[0] - mundo_x * lado2 - centrado_x, pos[1] - mundo_y * lado2 - centrado_y]
        self._limitar()

    def mover(self, dx, dy):
        self.desplazamiento[0] += dx
        self.desplazamiento[1] += dy
        self._limitar()

    def centrar(self):
        self.zoom = 1.0
        self.desplazamiento = [0.0, 0.0]

    def rect_celda(self, coord):
        lado, izq, arr = self.geometria()
        x, y = coord
        x0 = round(izq + x * lado)
        y0 = round(arr + (self.app.sim.alto - 1 - y) * lado)
        x1 = round(izq + (x + 1) * lado)
        y1 = round(arr + (self.app.sim.alto - y) * lado)
        return pygame.Rect(x0, y0, max(1, x1 - x0), max(1, y1 - y0))

    def centro(self, coord):
        """Centro en píxeles de una posición, aunque sea fraccionaria (animación)."""
        lado, izq, arr = self.geometria()
        x, y = coord
        return (round(izq + (x + 0.5) * lado), round(arr + (self.app.sim.alto - 1 - y + 0.5) * lado))

    def celda_en(self, pos):
        lado, izq, arr = self.geometria()
        x = int((pos[0] - izq) // lado)
        y = self.app.sim.alto - 1 - int((pos[1] - arr) // lado)
        if 0 <= x < self.app.sim.ancho and 0 <= y < self.app.sim.alto:
            return (x, y)
        return None

    def visibles(self):
        """Rango de celdas que se ven en la vista actual (para no dibujar de más)."""
        lado, izq, arr = self.geometria()
        m = self.app.sim
        x0 = max(0, int((self.area.x - izq) // lado))
        x1 = min(m.ancho - 1, int((self.area.right - izq) // lado))
        fila0 = max(0, int((self.area.y - arr) // lado))
        fila1 = min(m.alto - 1, int((self.area.bottom - arr) // lado))
        return x0, x1, m.alto - 1 - fila1, m.alto - 1 - fila0

    def es_visible(self, coord):
        x0, x1, y0, y1 = self.visibles()
        return x0 <= coord[0] <= x1 and y0 <= coord[1] <= y1

    # ------------------------------------------------------------------
    # Fondo (celdas) en caché
    # ------------------------------------------------------------------
    def _fondo(self, plan, explorados):
        """Celdas, intersecciones, productos y zonas, dibujados una sola vez.

        Se vuelve a dibujar solo si cambia el escenario, la vista (zoom o
        arrastre) o la ruta cuya exploración se muestra.
        """
        app, m = self.app, self.app.sim
        clave = (
            id(m), tuple(self.area), round(self.zoom, 4),
            tuple(round(d) for d in self.desplazamiento), id(plan) if explorados else None,
        )
        if getattr(self, "_clave_fondo", None) == clave:
            return self._superficie_fondo
        superficie = pygame.Surface(self.area.size)
        superficie.fill((236, 239, 243))
        dx, dy = -self.area.x, -self.area.y
        x0, x1, y0, y1 = self.visibles()
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                tipo, sentido, _ = m.celdas[(x, y)]
                dibujar_celda(
                    superficie,
                    self.rect_celda((x, y)).move(dx, dy),
                    tipo,
                    sentido,
                    app.fuente,
                    explorado=(x, y) in explorados,
                    interseccion=(x, y) in m.intersecciones,
                    productos=app.productos_por_celda.get((x, y), 0),
                )
        for zona in m.warehouse.zonas_despacho.values():
            r1 = self.rect_celda((zona.x, zona.y + zona.alto - 1))
            r2 = self.rect_celda((zona.x + zona.ancho - 1, zona.y))
            rect = r1.union(r2).move(dx, dy)
            tam = max(9, min(26, rect.height // 2))
            while tam > 9 and app.fuente(tam, True).size(zona.id)[0] > rect.width - 4:
                tam -= 1
            if app.fuente(tam, True).size(zona.id)[0] <= rect.width + 8:
                imagen = app.fuente(tam, True).render(zona.id, True, (30, 90, 50))
                superficie.blit(imagen, imagen.get_rect(center=rect.center))
        self._clave_fondo, self._superficie_fondo = clave, superficie
        return superficie

    # ------------------------------------------------------------------
    # Animación de "buscando ruta"
    # ------------------------------------------------------------------
    def orden_unico(self, plan):
        """Celdas exploradas en el orden en que Dijkstra las visitó, sin repetir."""
        clave = id(plan)
        if clave not in self._orden_unico:
            vistas, orden = set(), []
            for celda in plan.get("orden_exploracion", []):
                if celda not in vistas:
                    vistas.add(celda)
                    orden.append(celda)
            if len(self._orden_unico) > 200:
                self._orden_unico.clear()
            self._orden_unico[clave] = (orden, plan)  # se guarda el plan para que su id no se reutilice
        return self._orden_unico[clave][0]

    def dibujar_busqueda(self, color, plan, progreso, lado):
        """Pinta de a poco lo que explora Dijkstra y después el camino elegido."""
        lienzo = self.app.lienzo
        orden = self.orden_unico(plan)
        fase_exploracion = 0.8
        cantidad = int(len(orden) * min(1.0, progreso / fase_exploracion))
        # Capa semitransparente: se siguen viendo las flechas de los pasillos.
        capa = pygame.Surface(self.area.size, pygame.SRCALPHA)
        relleno, frente = color + (60,), color + (170,)
        borde_frente = max(0, cantidad - max(8, len(orden) // 25))
        dx, dy = -self.area.x, -self.area.y
        for i, celda in enumerate(orden[:cantidad]):
            if self.es_visible(celda):
                pygame.draw.rect(capa, frente if i >= borde_frente else relleno, self.rect_celda(celda).move(dx, dy))
        lienzo.blit(capa, self.area.topleft)
        if progreso > fase_exploracion:
            ruta = plan["ruta"]
            hasta = max(2, int(len(ruta) * (progreso - fase_exploracion) / (1 - fase_exploracion)))
            puntos = [self.rect_celda(c).center for c in ruta[:hasta]]
            if len(puntos) > 1:
                pygame.draw.lines(lienzo, color, False, puntos, max(2, min(8, int(lado * 0.2))))
        return cantidad, len(orden), progreso > fase_exploracion

    # ------------------------------------------------------------------
    # Dibujo completo
    # ------------------------------------------------------------------
    def dibujar(self):
        app, m = self.app, self.app.sim
        lienzo = app.lienzo
        pickers = m.resumen_pickers()
        enfocado = app.picker_enfocado(pickers)
        plan = enfocado["plan"] if enfocado else None
        buscando = app.busquedas_activas()
        explorados = (
            set(plan["explorados"])
            if plan and app.ver_exploracion and enfocado["id"] not in buscando
            else set()
        )
        resaltadas = app.celdas_resaltadas()

        lienzo.blit(self._fondo(plan, explorados), self.area.topleft)
        lienzo.set_clip(self.area)
        lado = self.geometria()[0]
        for coord in resaltadas:
            if self.es_visible(coord):
                pygame.draw.rect(lienzo, AMBAR, self.rect_celda(coord), max(2, min(6, int(lado) // 7)))

        grosor = max(2, min(8, int(lado * 0.16)))
        indices = {p["id"]: i for i, p in enumerate(pickers)}
        animadas = {p["id"]: app.posicion_animada(p["id"], p["pos"]) for p in pickers}

        resumen_busqueda = []
        for p in pickers:
            if p["id"] in buscando:
                plan_b, progreso = buscando[p["id"]]
                hechas, total, ruta_lista = self.dibujar_busqueda(color_picker(indices[p["id"]]), plan_b, progreso, lado)
                resumen_busqueda.append((p["id"], indices[p["id"]], hechas, total, ruta_lista, plan_b))

        for p in pickers:
            color = color_picker(indices[p["id"]])
            hecho = p["recorrido"][-400:]
            if len(hecho) > 1:
                pygame.draw.lines(lienzo, _aclarar(color, 0.6), False, [self.rect_celda(c).center for c in hecho], max(1, grosor - 1))
            if p["id"] in buscando:
                continue
            actual = self.centro(animadas[p["id"]][0])
            futuro = [actual] + [self.rect_celda(c).center for c in p["ruta_restante"] if c != tuple(p["pos"])]
            if len(futuro) > 1:
                pygame.draw.lines(lienzo, color, False, futuro, grosor)

        # Destinos numerados del picker enfocado (orden de visita del plan).
        if plan and enfocado["id"] not in buscando:
            pendientes = {c for c, _ in app.pendientes_por_celda(enfocado)}
            radio = max(5, min(18, int(lado * 0.36)))
            for n, celda in enumerate(plan["destinos"], start=1):
                rect = self.rect_celda(celda)
                color = AMBAR if celda in pendientes else GRIS
                pygame.draw.circle(lienzo, color, rect.center, radio)
                if lado >= 12:
                    imagen = app.fuente(max(9, min(20, int(lado * 0.42))), True).render(str(n), True, (255, 255, 255))
                    lienzo.blit(imagen, imagen.get_rect(center=rect.center))
            despacho = self.rect_celda(plan["despacho"])
            pygame.draw.rect(lienzo, (30, 90, 50), despacho, max(2, min(6, int(lado * 0.15))))

        for p in pickers:
            posicion, angulo = animadas[p["id"]]
            estado = ""
            if p["id"] in buscando:
                estado = "buscando ruta"
            elif p["estado"] in ("cargando", "descargando"):
                estado = p["estado"]
            if p["estado"] == "cargando" and p.get("mirando"):
                # Mientras carga, mira hacia el rack del producto.
                mx, my = p["mirando"]
                angulo = angulo_para(mx - p["pos"][0], my - p["pos"][1], angulo)
            dibujar_picker(
                lienzo,
                self.centro(posicion),
                lado,
                indices[p["id"]],
                angulo,
                p["id"],
                app.fuente,
                enfocado=enfocado is not None and p["id"] == enfocado["id"],
                estado=estado,
            )
        lienzo.set_clip(None)
        app.zona_clic(self.area, ("mapa",))

        # Cartel con el avance de cada búsqueda de ruta.
        for i, (pid, indice, hechas, total, ruta_lista, plan_b) in enumerate(resumen_busqueda[:4]):
            texto = (
                f"{pid}: ruta encontrada · {plan_b['distancia']} pasos"
                if ruta_lista
                else f"{pid}: buscando ruta con Dijkstra · {hechas}/{total} celdas exploradas"
            )
            y = self.area.bottom - 30 - i * 28
            app.caja(self.area.x + 6, y, 470, 24, (255, 255, 255), color_picker(indice))
            app.texto(texto, self.area.x + 14, y + 3, 15, color_picker(indice), True, max_ancho=455)

        # Controles de la vista (arriba a la derecha del mapa).
        x = self.area.right - 128
        app.boton("+", x, self.area.y + 8, 36, ("zoom", 1.5), self.zoom < ZOOM_MAX, alto=32)
        app.boton("-", x + 42, self.area.y + 8, 36, ("zoom", 1 / 1.5), self.zoom > ZOOM_MIN, alto=32)
        app.boton("1:1", x + 84, self.area.y + 8, 40, "centrar_mapa", self.zoom > 1 or any(self.desplazamiento), alto=32)
        if self.zoom > 1:
            app.texto(f"x{self.zoom:.1f}", x - 50, self.area.y + 15, 15, GRIS)
        app.caja(self.area.x + 6, self.area.y + 8, 330, 24, (255, 255, 255), None)
        app.texto("Rueda: acercar / alejar  ·  Arrastrar: mover", self.area.x + 12, self.area.y + 11, 14, GRIS)

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
