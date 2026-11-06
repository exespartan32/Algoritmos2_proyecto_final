"""Paneles de pestañas del panel derecho (Productos, Pedidos, Waves, Pickers, Métricas, Eventos y Armado)."""

import pygame
from BackEnd.controllers.wave_manager import (
    ESTRATEGIAS_ARMADO,
    OPCIONES_ESTRATEGIA_ARMADO,
)
from BackEnd.controllers.simulador import NOMBRE_ESTRATEGIA
from FrontEnd.views.ui_elements import (
    ALTO,
    ANCHO,
    AMBAR,
    AZUL,
    AZUL_CLARO,
    BLANCO,
    GRIS,
    ROJO,
    TINTA,
    VERDE,
)

PESTANAS = ["Productos", "Pedidos", "Waves", "Pickers", "Métricas", "Eventos"]


class PanelesVistas:
    """Mezcla de mixins para renderizar las pestañas y el panel interactivo de armado."""

    def panel_derecho(self):
        x0, y0 = 778, 184
        if self.armado:
            self.caja(x0, y0, 722, 720)
            self.panel_armado(x0 + 14, y0 + 12)
            return
        ancho_pestana = 118
        for i, nombre in enumerate(PESTANAS):
            self.boton(
                nombre,
                x0 + i * (ancho_pestana + 2),
                y0,
                ancho_pestana,
                ("pestana", nombre),
                marcado=self.pestana == nombre,
            )
        self.caja(x0, y0 + 40, 722, 680)
        getattr(
            self,
            "panel_" + {"Métricas": "metricas"}.get(self.pestana, self.pestana.lower()),
        )(x0 + 14, y0 + 52)

    def _tabla(self, x, y, columnas, filas, por_pagina=24, acciones=None, marcadas=()):
        for etiqueta, dx in columnas:
            self.texto(etiqueta, x + dx, y, 15, GRIS, True)
        inicio = self.pag_tabla * por_pagina
        if inicio >= len(filas):
            self.pag_tabla, inicio = 0, 0
        for i, fila in enumerate(filas[inicio : inicio + por_pagina]):
            yy = y + 26 + i * 24
            if inicio + i in marcadas:
                self.caja(x - 6, yy - 3, 706, 23, AZUL_CLARO, None)
            for (valor, color), (_, dx), siguiente in zip(
                fila, columnas, columnas[1:] + [("", 700)]
            ):
                self.texto(
                    valor, x + dx, yy, 15, color, max_ancho=siguiente[1] - dx - 6
                )
            if acciones:
                self.zona_clic((x - 6, yy - 3, 706, 23), acciones[inicio + i])
        self.paginador(
            "pag_tabla", len(filas), por_pagina, x + 540, y + 26 + por_pagina * 24 + 6
        )

    def panel_productos(self, x, y):
        resaltadas = self.celdas_resaltadas()
        productos = self.sim.productos()
        self.texto(
            f"{len(productos)} productos · ubicación <x,y,z> en rack · stock actual",
            x,
            y,
            16,
            GRIS,
        )
        filas, marcadas = [], set()
        for i, p in enumerate(productos):
            color = AMBAR if (p["x"], p["y"]) in resaltadas else TINTA
            if color == AMBAR:
                marcadas.add(i)
            filas.append(
                [
                    (p["id"], TINTA),
                    (p["nombre"], TINTA),
                    (p["rack"], TINTA),
                    (f"<{p['x']},{p['y']},{p['z']}>", TINTA),
                    (f"{p['peso']:g}", TINTA),
                    (p["stock"], ROJO if p["stock"] == 0 else color),
                ]
            )
        self._tabla(
            x,
            y + 28,
            [
                ("ID", 0),
                ("Nombre", 70),
                ("Rack", 270),
                ("Ubicación", 340),
                ("kg/u", 470),
                ("Stock", 540),
            ],
            filas,
            23,
            marcadas=marcadas,
        )

    def panel_pedidos(self, x, y):
        pedidos = self.sim.pedidos()
        estados = {}
        for p in pedidos:
            estados[p["estado"]] = estados.get(p["estado"], 0) + 1
        self.texto(
            " · ".join(f"{k}: {v}" for k, v in sorted(estados.items())),
            x,
            y,
            16,
            GRIS,
            max_ancho=690,
        )
        colores = {
            "PENDIENTE": TINTA,
            "EN_WAVE": AZUL,
            "EN_PREPARACION": AMBAR,
            "PREPARADO": VERDE,
            "IRREALIZABLE": ROJO,
        }
        filas = [
            [
                (p["id"], TINTA),
                (p["prioridad"], TINTA),
                (p["estado"], colores.get(p["estado"], TINTA)),
                (", ".join(f"{a}×{b}" for a, b in p["items"]), TINTA),
                (p["wave"] or "-", TINTA),
            ]
            for p in pedidos
        ]
        self._tabla(
            x,
            y + 28,
            [
                ("Pedido", 0),
                ("Prio.", 80),
                ("Estado", 130),
                ("Productos", 290),
                ("Wave", 610),
            ],
            filas,
            23,
        )

    def panel_waves(self, x, y):
        waves = self.sim.resumen_waves()
        if not waves:
            self.parrafo(
                "Todavía no hay waves. Usá 'Generar waves' para agrupar los pedidos.",
                x,
                y,
                680,
                17,
                limite=5,
            )
            return
        self.texto(
            "Clic en una wave para ver sus ubicaciones en el mapa", x, y + 8, 16, GRIS
        )
        self.boton(
            "Ver cómo se armó",
            x + 500,
            y,
            190,
            ("ver_armado", self.wave_foco),
            marcado=True,
        )
        colores = {"PENDIENTE": TINTA, "EN_EJECUCION": AMBAR, "FINALIZADA": VERDE}
        filas = [
            [
                (w["id"], TINTA),
                (w["estado"], colores.get(w["estado"], TINTA)),
                (", ".join(w["pedidos"]), TINTA),
                (w["unidades"], TINTA),
                (f"{w['peso']:.1f}", TINTA),
                (w["zona"], TINTA),
                (", ".join(w["pickers"]) or "-", TINTA),
            ]
            for w in waves
        ]
        marcadas = {i for i, w in enumerate(waves) if w["id"] == self.wave_foco}
        self._tabla(
            x,
            y + 28,
            [
                ("Wave", 0),
                ("Estado", 85),
                ("Pedidos", 205),
                ("Unid.", 440),
                ("kg", 495),
                ("Zona", 555),
                ("Pickers", 630),
            ],
            filas,
            23,
            acciones=[("foco_wave", w["id"]) for w in waves],
            marcadas=marcadas,
        )

    def panel_pickers(self, x, y):
        pickers = self.sim.resumen_pickers()
        enfocado = self.picker_enfocado(pickers)
        alto = 150 if len(pickers) <= 4 else 74
        for i, p in enumerate(pickers[:8]):
            yy = y + i * (alto + 6)
            seleccionado = enfocado and p["id"] == enfocado["id"]
            rect = self.caja(
                x - 4, yy, 700, alto, AZUL_CLARO if seleccionado else BLANCO
            )
            self.zona_clic(rect, ("foco_picker", p["id"]))
            from FrontEnd.sprites.picker_sprite import color_picker

            pygame.draw.circle(self.lienzo, color_picker(i), (x + 12, yy + 18), 9)
            estado_p = p["estado"]
            estado = f"{estado_p} · {p['wave']}" if p["wave"] else "libre"
            self.texto(
                f"{p['id']} · {estado} · en {tuple(p['pos'])}",
                x + 30,
                yy + 8,
                17,
                negrita=True,
            )
            self.texto(
                f"Carga {p['carga']:.1f}/{p['capacidad']:g} kg · {p['pasos']} pasos · {p['esperas']} esperas",
                x + 380,
                yy + 10,
                15,
                GRIS,
            )
            recogidos = (
                ", ".join(f"{k}×{v}" for k, v in p["recogidos"].items())
                or "nada todavía"
            )
            self.texto(
                "Recogido: " + recogidos,
                x + 30,
                yy + 34,
                15,
                VERDE if p["recogidos"] else GRIS,
                max_ancho=660,
            )
            if alto > 100:
                pendientes = ", ".join(f"{k}×{v}" for k, v in p["pendientes"]) or "-"
                self.texto(
                    "Falta recoger: " + pendientes,
                    x + 30,
                    yy + 58,
                    15,
                    AMBAR if p["pendientes"] else GRIS,
                    max_ancho=660,
                )
                plan = p["plan"]
                if plan:
                    self.texto(
                        f"Plan ({NOMBRE_ESTRATEGIA[plan['estrategia']]}): {plan['distancia']} pasos · "
                        f"{plan['nodos_visitados']} nodos · {plan['nodos_explorados']} explorados · {plan['tiempo_ms']:.2f} ms",
                        x + 30,
                        yy + 82,
                        15,
                        AZUL,
                        max_ancho=660,
                    )
                    self.texto(
                        f"Pedidos: {', '.join(plan['pedidos'])} · restan {len(p['ruta_restante'])} pasos",
                        x + 30,
                        yy + 106,
                        15,
                        GRIS,
                        max_ancho=660,
                    )
        if len(pickers) > 8:
            self.texto(
                f"(+{len(pickers) - 8} pickers más)", x, y + 8 * (alto + 6), 15, GRIS
            )

    def color_picker_indexed(self, idx):
        from FrontEnd.sprites.picker_sprite import color_picker

        return color_picker(idx)

    def panel_metricas(self, x, y):
        m = self.sim
        met = m.metricas()
        self.texto("Grafo y simulación", x, y, 18, negrita=True)

        # --- Lógica de estrategia agregada aquí, DESPUÉS de definir 'm' ---
        efectiva = (
            m.estado.gestor_waves.estrategia_armado
            if m.estado.gestor_waves
            else m.config["estrategia_waves"]
        )
        texto_armado = OPCIONES_ESTRATEGIA_ARMADO.get(
            m.config["estrategia_waves"], efectiva
        )
        if m.config["estrategia_waves"] == "AUTO" and m.estado.gestor_waves:
            texto_armado += f" -> Ganó: {ESTRATEGIAS_ARMADO[efectiva]}"
        # ------------------------------------------------------------------

        lineas = [
            f"Dígrafo: {met['nodos']} nodos (pasillos), {met['aristas']} aristas, {len(m.intersecciones)} intersecciones.",
            f"Matriz de distancias (Dijkstra APSP por acceso): {m.tiempo_matriz_ms:.1f} ms.",
            f"Waves: {met['waves']} generadas, {met['waves_finalizadas']} finalizadas. Pedidos listos: {met['pedidos_preparados']}/{met['pedidos']}.",
            f"Turno {met['paso']} · pasos totales: {met['pasos_totales']} · esperas: {met['esperas']} · desvíos: {met['desvios']}.",
            f"Armado de waves: {texto_armado}",
        ]

        for i, linea in enumerate(lineas):
            self.texto(linea, x, y + 30 + i * 24, 15, max_ancho=690)

        tanda = met["tanda"]
        yy = y + 36 + 24 * len(lineas)

        if tanda:
            self.texto(
                f"Tanda {tanda['numero']} · {NOMBRE_ESTRATEGIA[tanda['estrategia']]}",
                x,
                yy,
                18,
                negrita=True,
            )
            columnas = [
                ("Picker", 0),
                ("Wave", 90),
                ("Distancia", 190),
                ("Aristas", 290),
                ("Nodos", 380),
                ("Explorados", 520),
                ("ms", 630),
            ]
            for etiqueta, dx in columnas:
                self.texto(etiqueta, x + dx, yy + 30, 15, GRIS, True)
            planes = tanda["planes"][-10:]
            for i, plan in enumerate(planes):
                valores = [
                    plan["picker"],
                    plan["wave"],
                    plan["distancia"],
                    plan["aristas"],
                    plan["nodos_visitados"],
                    plan["nodos_explorados"],
                    f"{plan['tiempo_ms']:.2f}",
                ]
                for valor, (_, dx) in zip(valores, columnas):
                    self.texto(valor, x + dx, yy + 56 + i * 22, 15)
            yy += 70 + 22 * len(planes)

            if tanda["en_espera"]:
                self.texto(
                    f"En espera: {', '.join(tanda['en_espera'])}",
                    x,
                    yy,
                    15,
                    AMBAR,
                    max_ancho=690,
                )
                yy += 22
            if tanda["paso_fin"] is not None:
                self.texto(
                    f"Terminó en {tanda['paso_fin'] - tanda['paso_inicio']} turnos de simulación.",
                    x,
                    yy,
                    15,
                    VERDE,
                )
            yy += 34

        if self.comparacion:
            self.dibujar_comparacion(x, yy)
        else:
            self.parrafo(
                "Usá 'Comparar estrategias' para correr las mismas waves con Orden y con Cercanía lado a lado.",
                x,
                yy,
                680,
                16,
            )

    def panel_eventos(self, x, y):
        eventos = list(reversed(self.sim.estado.eventos))
        self.texto("Eventos de la simulación (lo más reciente primero)", x, y, 16, GRIS)
        filas = [
            [(e, ROJO if "ATENCIÓN" in e or "Error" in e else TINTA)] for e in eventos
        ]
        self._tabla(x, y + 28, [("Evento", 0)], filas, 23)

    def panel_armado(self, x, y):
        a = self.armado
        datos = a["datos"]
        pasos = datos["pasos"]
        paso = pasos[a["paso"]]
        colores = self.colores_pedidos(datos)
        from BackEnd.controllers.wave_manager import (
            ESTRATEGIAS_ARMADO as NOMBRES_ARMADO,
        )

        self.texto(f"Cómo se armó {datos['wave']}", x, y, 22, negrita=True)
        self.texto(
            f"Armado: {NOMBRES_ARMADO[datos['estrategia_armado']]} · zona {datos['zona']}",
            x,
            y + 32,
            15,
            GRIS,
            max_ancho=690,
        )
        botones = [
            ("< Wave", 90, ("armado_wave", -1), True),
            ("Wave >", 90, ("armado_wave", 1), True),
            ("< Paso", 90, ("armado_paso", -1), a["paso"] > 0),
            ("Paso >", 90, ("armado_paso", 1), a["paso"] + 1 < len(pasos)),
            ("Pausar" if a["auto"] else "Reproducir", 120, "armado_auto", True),
            ("Salir", 90, "salir_armado", True),
        ]
        bx = x
        for etiqueta, w, accion, habilitado in botones:
            self.boton(etiqueta, bx, y + 60, w, accion, habilitado)
            bx += w + 8

        total = len(pasos)
        ancho = 690 / total
        for j, pj in enumerate(pasos):
            color = (
                AZUL if j < a["paso"] else AMBAR if j == a["paso"] else (225, 229, 235)
            )
            self.caja(x + j * ancho, y + 106, max(4, ancho - 4), 10, color, None)
        nombres_tipo = {
            "raiz": "Pedido raíz",
            "evaluar": "Evaluar candidatos",
            "elegir": "Elegir pedido",
            "fin": "Cierre de wave",
            "ruta": "Ruta del picker",
        }
        self.texto(
            f"Paso {a['paso'] + 1} de {total}: {nombres_tipo[paso['tipo']]}",
            x,
            y + 126,
            18,
            negrita=True,
        )
        lineas = self.parrafo(paso["texto"], x, y + 156, 690, 16, TINTA, limite=6)
        yy = y + 166 + lineas * 21

        if paso["tipo"] == "evaluar":
            self.texto("Mejores candidatos", x, yy, 17, negrita=True)
            for etiqueta, dx in [("Pedido", 0), ("Prioridad", 150), ("Ponderado", 280)]:
                self.texto(etiqueta, x + dx, yy + 28, 15, GRIS, True)
            for k, cand in enumerate(paso["ranking"]):
                fy = yy + 54 + k * 24
                color = AMBAR if k == 0 else TINTA
                self.texto(cand["id_pedido"], x, fy, 15, color, k == 0)
                self.texto(cand["prioridad"], x + 150, fy, 15, color)
                self.texto(
                    f"{cand['score']:.2f}" + ("    <- gana" if k == 0 else ""),
                    x + 280,
                    fy,
                    15,
                    color,
                    k == 0,
                )
            yy += 60 + 24 * len(paso["ranking"])
        elif paso["tipo"] == "elegir":
            color = colores[paso["pedido"]]
            for enlace in paso["enlaces"]:
                camino = enlace["camino"]
                hasta = max(
                    2, int(len(camino) * min(1.0, self.progreso_armado() * 1.3))
                )
                puntos = [self.mapa.rect_celda(c).center for c in camino[:hasta]]
                if len(puntos) > 1:
                    pygame.draw.lines(
                        self.lienzo,
                        color,
                        False,
                        puntos,
                        max(2, min(7, int(self.mapa.geometria()[0] * 0.18))),
                    )
                if self.progreso_armado() > 0.7 and camino:
                    medio = self.mapa.rect_celda(camino[len(camino) // 2]).center
                    self.mapa._etiqueta(
                        f"{enlace['distancia']} pasos", medio, color, 12
                    )
        elif paso["tipo"] == "ruta" and datos["ruta"]:
            ruta = datos["ruta"]
            self.texto(
                f"{len(ruta['destinos'])} paradas · {ruta['distancia']} pasos · "
                f"{len(set(ruta['orden_exploracion']))} celdas exploradas por Dijkstra",
                x,
                yy,
                15,
                AZUL,
                max_ancho=690,
            )
            yy += 30

        self.texto("Pedidos en la wave", x, yy + 10, 17, negrita=True)
        fila = 0
        for pj in pasos[: a["paso"] + 1]:
            if pj["tipo"] not in ("raiz", "elegir"):
                continue
            fy = yy + 40 + fila * 26
            pygame.draw.rect(
                self.lienzo, colores[pj["pedido"]], pygame.Rect(x, fy + 2, 16, 16)
            )
            detalle = (
                "raíz (mayor prioridad)"
                if pj["tipo"] == "raiz"
                else f"ponderado {pj['score']:.2f}"
            )
            self.texto(
                f"{pj['pedido']} · prioridad {pj['prioridad']} · {len(pj['celdas'])} ubicaciones · {detalle}",
                x + 26,
                fy,
                15,
                max_ancho=660,
            )
            fila += 1
