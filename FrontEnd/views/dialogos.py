"""Ventanas modales y formularios (creación, generador automático, pedidos, configuración y comparaciones)."""

from pathlib import Path
import pygame
from BackEnd.controllers.simulador import NOMBRE_ESTRATEGIA
from FrontEnd.views.ui_elements import (
    ANCHO,
    ALTO,
    AZUL,
    BLANCO,
    GRIS,
    TINTA,
    VERDE,
    AMBAR,
)


class DialogosVistas:
    """Mixins para renderizar formularios y modales sobre la pantalla activa."""

    FILAS_COMPARACION = [
        ("Distancia total (pasos)", "distancia"),
        ("Nodos visitados", "nodos_visitados"),
        ("Aristas recorridas", "aristas"),
        ("Nodos explorados", "nodos_explorados"),
        ("Nodos expandidos (suma de búsquedas)", "expansiones"),
        ("Tiempo de cálculo de rutas (ms)", "tiempo_ms"),
        ("Turnos simulados hasta terminar", "turnos"),
        ("Esperas por colisión", "esperas"),
        ("Desvíos recalculados", "desvios"),
    ]

    FILAS_ARMADO = [
        ("Waves armadas", "waves"),
        ("Pedidos por wave (promedio)", "pedidos_por_wave"),
        ("Pasillos distintos por wave", "pasillos_por_wave"),
        ("Prioridad media de la 1.ª wave", "prioridad_primera_wave"),
        ("Distancia total recorrida", "distancia"),
        ("Turnos hasta preparar todo", "turnos"),
        ("Tiempo de armado (ms)", "tiempo_armado_ms"),
        ("Candidatos evaluados", "candidatos_evaluados"),
    ]
    MAYOR_ES_MEJOR = {"pedidos_por_wave", "prioridad_primera_wave"}

    def dibujar_comparacion(self, x, y):
        comp = self.comparacion
        orden, cerca = comp["ORDEN"], comp["CERCANIA"]
        self.texto(
            "Comparación · " + ", ".join(orden["waves"]),
            x,
            y,
            18,
            negrita=True,
            max_ancho=690,
        )
        self.texto("Métrica", x, y + 34, 16, GRIS, True)
        self.texto("Orden de pedidos", x + 330, y + 34, 16, GRIS, True)
        self.texto("Cercanía", x + 520, y + 34, 16, GRIS, True)
        for i, (etiqueta, clave) in enumerate(self.FILAS_COMPARACION):
            yy = y + 62 + i * 26
            self.texto(etiqueta, x, yy, 16)
            a, b = orden[clave], cerca[clave]
            for valor, otro, dx in ((a, b, 330), (b, a, 520)):
                mejor = valor < otro
                texto = f"{valor:.2f}" if isinstance(valor, float) else str(valor)
                self.texto(
                    texto + ("  (mejor)" if mejor else ""),
                    x + dx,
                    yy,
                    16,
                    VERDE if mejor else TINTA,
                    mejor,
                )
        return y + 62 + len(self.FILAS_COMPARACION) * 26

    def dialogo_actual(self):
        capa = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        capa.fill((0, 0, 0, 90))
        self.lienzo.blit(capa, (0, 0))
        self.botones = []
        tipo = self.dialogo[0] if isinstance(self.dialogo, tuple) else self.dialogo
        x, y, w, h = 300, 120, 920, 720
        self.caja(x, y, w, h)
        self.boton("Cerrar (Esc)", x + w - 150, y + 16, 130, "cerrar")
        getattr(self, "dialogo_" + tipo)(x + 30, y + 30, w - 60)

    def dialogo_crear(self, x, y, w):
        self.texto("Crear escenario", x, y, 26, negrita=True)
        self.texto("¿Cómo querés crearlo?", x, y + 70, 20)
        self.boton("Generador automático", x, y + 120, 380, "generador", marcado=True)
        self.boton("Desde archivo JSON", x + 400, y + 120, 380, "importar")
        self.parrafo(
            "El generador arma racks de 2x6 separados por pasillos verticales de un solo sentido (alternando N y S), "
            "con pasillos transversales de doble sentido, zonas de despacho abajo y productos según la localización elegida. "
            "Se verifica con Kosaraju que el grafo sea fuertemente conexo.",
            x,
            y + 200,
            w - 20,
            17,
            limite=6,
        )

    def _dibujar_formulario(self, x, y, w, titulo, texto_boton, ayuda=""):
        self.texto(titulo, x, y, 26, negrita=True)
        f = self.formulario
        for i, (clave, etiqueta, valor) in enumerate(f["campos"]):
            yy = y + 66 + i * 52
            self.texto(etiqueta, x, yy + 8, 18)
            if clave in self.OPCIONES_FORMULARIO:
                opciones = list(self.OPCIONES_FORMULARIO[clave])
                self.boton(
                    f"{valor}  (clic para cambiar)",
                    x + 470,
                    yy,
                    360,
                    ("campo", i),
                    marcado=f["foco"] == i,
                )
                self.texto(
                    self.OPCIONES_FORMULARIO[clave][valor], x + 470, yy + 36, 13, GRIS
                )
            else:
                self.campo(x + 470, yy, 360, valor, f["foco"] == i, ("campo", i))
        yy = y + 76 + len(f["campos"]) * 52
        if ayuda:
            self.parrafo(ayuda, x, yy, w - 20, 15, limite=3)
        self.boton(texto_boton + " (Enter)", x, y + 610, 320, "enviar", marcado=True)

    def dialogo_generador(self, x, y, w):
        self._dibujar_formulario(
            x,
            y,
            w,
            "Generador automático de escenarios",
            "Generar y guardar",
            "Tab cambia de campo. La localización se alterna con un clic. El resultado es determinista.",
        )

    def dialogo_pedido(self, x, y, w):
        self._dibujar_formulario(
            x,
            y,
            w,
            "Nuevo pedido",
            "Crear pedido",
            "Escribí los productos separados por coma, con la cantidad tras una x (ej: P001x2, P004x1).",
        )

    def dialogo_config(self, x, y, w):
        self._dibujar_formulario(
            x,
            y,
            w,
            "Capacidad de las waves",
            "Guardar",
            "Modificar la capacidad descarta las waves generadas que aún no se iniciaron.",
        )

    def dialogo_eliminar(self, x, y, w):
        self.texto("Eliminar de la biblioteca", x, y, 26, negrita=True)
        self.parrafo(
            "Se va a borrar permanentemente: " + Path(self.dialogo[1]).name,
            x,
            y + 80,
            w - 20,
            20,
        )
        self.boton("Eliminar", x, y + 180, 200, "confirmar_eliminar", marcado=True)
        self.boton("Cancelar", x + 220, y + 180, 200, "cerrar")

    def dialogo_waves(self, x, y, w):
        m = self.sim
        self.texto("Seleccionar waves", x, y, 26, negrita=True)
        self.boton("Ver cómo se armó", x + w - 400, y - 2, 230, "ver_armado")
        self.boton_armado(x + w - 342, y + 38, 342)
        libres = sum(1 for p in m.warehouse.pickers if p.id_wave_actual is None)
        self.texto(
            f"Pickers libres: {libres} de {len(m.warehouse.pickers)} · estrategia: {NOMBRE_ESTRATEGIA[m.estrategia]}",
            x,
            y + 42,
            16,
            GRIS,
            max_ancho=w - 358,
        )
        waves = m.resumen_waves()
        por_pagina = 12
        self.pag_waves_dialogo = min(
            self.pag_waves_dialogo, max(0, (len(waves) - 1) // por_pagina)
        )
        for etiqueta, dx in [
            ("Wave", 34),
            ("Estado", 130),
            ("Pedidos", 260),
            ("Unid.", 600),
            ("kg", 660),
            ("Zona", 730),
        ]:
            self.texto(etiqueta, x + dx, y + 78, 15, GRIS, True)
        for i, wv in enumerate(
            waves[self.pag_waves_dialogo * por_pagina :][:por_pagina]
        ):
            yy = y + 106 + i * 36
            pendiente = wv["estado"] == "PENDIENTE"
            self.casilla(
                x, yy, wv["id"] in self.seleccion, ("marcar", wv["id"]), pendiente
            )
            color = TINTA if pendiente else GRIS
            for valor, dx in [
                (wv["id"], 34),
                (wv["estado"], 130),
                (", ".join(wv["pedidos"]), 260),
                (wv["unidades"], 600),
                (f"{wv['peso']:.1f}", 660),
                (wv["zona"], 730),
            ]:
                self.texto(valor, x + dx, yy + 1, 16, color, max_ancho=330)
        self.paginador(
            "pag_waves_dialogo", len(waves), por_pagina, x + w - 150, y + 540
        )
        self.boton("Marcar todas", x, y + 540, 150, ("marcar_todas", True))
        self.boton("Ninguna", x + 160, y + 540, 120, ("marcar_todas", False))
        hay = bool(self.seleccion)
        self.boton(
            "Asignar e iniciar",
            x,
            y + 600,
            260,
            "iniciar_seleccion",
            hay and libres > 0,
            marcado=hay and libres > 0,
        )
        self.boton(
            "Comparar estrategias", x + 280, y + 600, 240, ("comparar", True), hay
        )

    def dialogo_armado(self, x, y, w):
        self.texto("Comparar estrategias de armado de waves", x, y, 26, negrita=True)
        self.parrafo(
            "Se arman las waves con cada estrategia a partir de los mismos pedidos, "
            "manteniendo la estrategia de recorrido actual ("
            + NOMBRE_ESTRATEGIA[self.sim.estrategia]
            + "). La tabla compara los resultados de cada criterio de armado.",
            x,
            y + 44,
            w - 20,
            16,
            limite=4,
        )
        comp = self.comparacion_armado
        claves = list(comp)
        columnas = {
            "CERCANIA": "Cercanía",
            "PASILLO": "Por pasillo",
            "PRIORIDAD": "Solo prioridad",
        }
        yy = y + 115
        self.texto("Métrica", x, yy, 16, GRIS, True)
        for j, clave in enumerate(claves):
            self.texto(
                columnas[clave],
                x + 360 + j * 170,
                yy,
                16,
                GRIS,
                True,
            )
        for i, (etiqueta, campo) in enumerate(self.FILAS_ARMADO):
            fila_y = yy + 30 + i * 28
            self.texto(etiqueta, x, fila_y, 16)
            valores = [comp[c][campo] for c in claves]
            mejor = max(valores) if campo in self.MAYOR_ES_MEJOR else min(valores)
            for j, valor in enumerate(valores):
                texto = f"{valor:.2f}" if isinstance(valor, float) else str(valor)
                es_mejor = valor == mejor and valores.count(mejor) < len(valores)
                self.texto(
                    texto + ("  (mejor)" if es_mejor else ""),
                    x + 360 + j * 170,
                    fila_y,
                    16,
                    VERDE if es_mejor else TINTA,
                    es_mejor,
                )

    def dialogo_comparar(self, x, y, w):
        self.texto("Comparar estrategias de recorrido", x, y, 26, negrita=True)
        self.parrafo(
            "Mismas waves, mismo estado y mismos pickers. Orden de pedidos: Dijkstra tramo a tramo. "
            "Cercanía: Dijkstra multidestino buscando siempre el producto pendiente más cercano.",
            x,
            y + 44,
            w - 20,
            16,
            limite=4,
        )
        fin = self.dibujar_comparacion(x, y + 140)
        o, c = self.comparacion["ORDEN"], self.comparacion["CERCANIA"]
        if o["distancia"] and c["distancia"]:
            ahorro = (o["distancia"] - c["distancia"]) / o["distancia"] * 100
            self.parrafo(
                f"Cercanía recorre {abs(ahorro):.1f}% {'menos' if ahorro >= 0 else 'más'} que Orden de pedidos.",
                x,
                fin + 20,
                w - 20,
                16,
            )
