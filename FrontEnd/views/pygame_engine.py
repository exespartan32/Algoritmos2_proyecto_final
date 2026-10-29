"""Ventana principal (Pygame): biblioteca de escenarios y pantalla de simulación.

La vista solo llama a la capa de simulación (``BackEnd.controllers.simulador``)
a través de la biblioteca; no contiene lógica de waves ni de recorridos.
"""

from pathlib import Path

import pygame

from BackEnd.controllers.simulador import NOMBRE_ESTRATEGIA, Simulador
from BackEnd.utils.scenario_generator import LOCALIZACIONES
from FrontEnd.events.input_handler import manejar_evento
from FrontEnd.services.biblioteca import Biblioteca
from FrontEnd.sprites.picker_sprite import color_picker
from FrontEnd.views.mapa import VistaMapa
from FrontEnd.views.ui_elements import (
    ALTO,
    ANCHO,
    AMBAR,
    AZUL,
    AZUL_CLARO,
    BLANCO,
    FONDO,
    GRIS,
    ROJO,
    TINTA,
    VERDE,
    UIElements,
)

VELOCIDADES = [(0.40, "x0.5"), (0.20, "x1"), (0.10, "x2"), (0.04, "x5"), (0.01, "x20")]
PESTANAS = ["Productos", "Pedidos", "Waves", "Pickers", "Métricas", "Eventos"]

CAMPOS_GENERADOR = [
    ("cantidad_estantes", "Cantidad de estantes (racks)", "12"),
    ("cantidad_pasillos", "Cantidad de pasillos verticales", "5"),
    ("cantidad_productos", "Cantidad de productos", "60"),
    ("localizacion", "Localización de los productos", "DISTRIBUIDA"),
    ("cantidad_pedidos", "Cantidad de pedidos", "20"),
    ("max_productos_por_pedido", "Máx. productos distintos por pedido", "4"),
    ("wave_max_pedidos", "Capacidad de la wave: pedidos", "4"),
    ("wave_max_productos", "Capacidad de la wave: unidades", "20"),
    ("cantidad_pickers", "Cantidad de pickers", "3"),
]


class App(UIElements):
    def __init__(self, carpeta_biblioteca=None):
        pygame.init()
        pygame.display.set_caption("Wave Picking - Algoritmos II")
        info = pygame.display.Info()
        ancho = min(ANCHO, max(1024, int(getattr(info, "current_w", ANCHO) * 0.9)))
        alto = min(ALTO, max(640, int(getattr(info, "current_h", ALTO) * 0.85)))
        self.ventana = pygame.display.set_mode((ancho, alto), pygame.RESIZABLE)
        self.lienzo = pygame.Surface((ANCHO, ALTO))
        self.escala, self.desplazamiento = 1.0, (0, 0)
        self.fuentes = {}
        self.botones = []
        self.corriendo = True
        self.pagina = "inicio"
        self.dialogo = None
        self.mensaje = "Elegí un escenario de la biblioteca o creá uno nuevo."
        self.reproduciendo = False
        self.acumulado = 0.0
        self.velocidad = 1
        self.sim = None
        self.nombre = ""
        self.biblioteca = Biblioteca(carpeta_biblioteca)
        self.pestana = "Pickers"
        self.pag_biblioteca = self.pag_tabla = self.pag_waves_dialogo = 0
        self.seleccion = set()
        self.picker_foco = None
        self.wave_foco = None
        self.ver_exploracion = True
        self.comparacion = None
        self.formulario = None
        self.ultimo_clic = (0, 0)
        self.mapa_ampliado = False
        self.productos_por_celda = {}
        self.mapa = VistaMapa(self, 20, 186, 740, 690)

    # ------------------------------------------------------------------
    # Carga de escenarios
    # ------------------------------------------------------------------
    def cargar(self, ruta):
        sim = Biblioteca.abrir(ruta)
        self._usar(sim, Path(ruta).stem)
        sesion = Biblioteca.es_sesion(ruta)
        self.mensaje = (
            f"Sesión retomada en el turno {sim.estado.paso}. Podés continuar la simulación."
            if sesion
            else "Escenario cargado. Mirá los productos y pedidos, y generá las waves."
        )
        if sim.advertencias:
            self.mensaje += " Advertencias del mapa: " + "; ".join(sim.advertencias[:2])

    def _usar(self, sim: Simulador, nombre: str):
        self.sim = sim
        self.nombre = nombre
        self.pagina = "sim"
        self.reproduciendo = False
        self.seleccion = set()
        self.picker_foco = sim.warehouse.pickers[0].id_picker if sim.warehouse.pickers else None
        self.wave_foco = None
        self.comparacion = None
        self.pag_tabla = 0
        self.pestana = "Productos" if not sim.waves else "Pickers"
        self.productos_por_celda = {}
        for p in sim.warehouse.catalogo_productos.values():
            self.productos_por_celda[(p.x, p.y)] = self.productos_por_celda.get((p.x, p.y), 0) + 1

    def importar_con_dialogo(self):
        import tkinter as tk
        from tkinter.filedialog import askopenfilename

        raiz = tk.Tk()
        raiz.withdraw()
        try:
            ruta = askopenfilename(title="Importar escenario JSON", filetypes=[("JSON", "*.json")])
        finally:
            raiz.destroy()
        if ruta:
            self.importar(ruta)

    def importar(self, ruta):
        destino = self.biblioteca.importar(ruta)
        self.dialogo = None
        self.mensaje = f"Escenario validado y agregado a la biblioteca como {destino.name}."

    # ------------------------------------------------------------------
    # Ayudas para la vista
    # ------------------------------------------------------------------
    def picker_enfocado(self, pickers=None):
        pickers = pickers if pickers is not None else self.sim.resumen_pickers()
        for p in pickers:
            if p["id"] == self.picker_foco:
                return p
        return pickers[0] if pickers else None

    def pendientes_por_celda(self, picker):
        return list(self.sim.estado.por_recoger.get(picker["id"], {}).items())

    def celdas_resaltadas(self):
        wh = self.sim.warehouse
        celdas = set()
        for items_por_celda in self.sim.estado.por_recoger.values():
            for items in items_por_celda.values():
                for prod_id, _, _ in items:
                    celdas.add(wh.buscar_producto_O1(prod_id).coordenadas_xy)
        if self.wave_foco:
            for w in self.sim.resumen_waves():
                if w["id"] == self.wave_foco:
                    celdas.update(w["ubicaciones"])
        for wid in self.seleccion:
            for w in self.sim.resumen_waves():
                if w["id"] == wid:
                    celdas.update(w["ubicaciones"])
        return celdas

    def waves_pendientes(self):
        return [w for w in self.sim.resumen_waves() if w["estado"] == "PENDIENTE"]

    def abrir_formulario(self, tipo, campos):
        self.formulario = {"tipo": tipo, "campos": [list(c) for c in campos], "foco": 0}
        self.dialogo = tipo
        pygame.key.start_text_input()

    def valores_formulario(self):
        return {clave: valor for clave, _, valor in self.formulario["campos"]}

    def cerrar_dialogo(self):
        self.dialogo = None
        self.formulario = None
        pygame.key.stop_text_input()

    # ------------------------------------------------------------------
    # Acciones (botones y teclado)
    # ------------------------------------------------------------------
    def accion(self, accion):
        try:
            nombre, *args = accion if isinstance(accion, tuple) else (accion,)
            getattr(self, "_a_" + nombre)(*args)
        except Exception as exc:  # cualquier error se muestra, nunca cierra la app
            self.mensaje = "No se pudo completar la acción: " + str(exc)
            self.reproduciendo = False

    # --- inicio y biblioteca ---
    def _a_crear(self):
        self.dialogo = "crear"

    def _a_generador(self):
        self.abrir_formulario("generador", CAMPOS_GENERADOR)

    def _a_importar(self):
        self.importar_con_dialogo()

    def _a_generar_escenario(self):
        v = self.valores_formulario()
        destino = self.biblioteca.generar(**v)
        self.cerrar_dialogo()
        self.mensaje = f"Escenario generado y guardado como {destino.name}. Ya podés abrirlo."

    def _a_abrir(self, ruta):
        self.cargar(ruta)

    def _a_eliminar(self, ruta):
        self.dialogo = ("eliminar", ruta)

    def _a_confirmar_eliminar(self):
        self.biblioteca.eliminar(self.dialogo[1])
        self.dialogo = None
        self.mensaje = "Archivo eliminado de la biblioteca."

    def _a_cerrar(self):
        self.cerrar_dialogo()

    def _a_inicio(self):
        self.pagina = "inicio"
        self.reproduciendo = False

    def _a_volver(self):
        self.pagina = "sim"

    def _a_pagina(self, atributo, delta, total, por_pagina):
        paginas = max(1, (total + por_pagina - 1) // por_pagina)
        setattr(self, atributo, max(0, min(paginas - 1, getattr(self, atributo) + delta)))

    # --- formularios ---
    def _a_campo(self, indice):
        campo = self.formulario["campos"][indice]
        if campo[0] == "localizacion":
            opciones = list(LOCALIZACIONES)
            campo[2] = opciones[(opciones.index(campo[2]) + 1) % len(opciones)]
        self.formulario["foco"] = indice

    def _a_enviar(self):
        tipo = self.formulario["tipo"]
        if tipo == "generador":
            self._a_generar_escenario()
        elif tipo == "pedido":
            self._a_crear_pedido()
        elif tipo == "config":
            self._a_guardar_config()

    # --- pedidos y configuración ---
    def _a_nuevo_pedido(self):
        ejemplo = ", ".join(f"{p['id']}x1" for p in self.sim.productos()[:2])
        self.abrir_formulario(
            "pedido", [("items", "Productos (ej.: " + ejemplo + ")", ""), ("prioridad", "Prioridad (1 a 5)", "3")]
        )

    def _a_crear_pedido(self):
        v = self.valores_formulario()
        items = Simulador.interpretar_items(v["items"])
        nuevo = self.sim.agregar_pedido(int(v["prioridad"] or 0), items)
        self.cerrar_dialogo()
        self.pestana, self.pag_tabla = "Pedidos", 0
        self.mensaje = f"Pedido {nuevo} creado. Generá las waves para incluirlo."

    def _a_config(self):
        c = self.sim.config
        self.abrir_formulario(
            "config",
            [
                ("wave_max_pedidos", "Máximo de pedidos por wave", str(c["wave_max_pedidos"])),
                ("wave_max_productos", "Máximo de unidades por wave", str(c["wave_max_productos"])),
                ("max_pickers_por_wave", "Máximo de pickers por wave", str(c["max_pickers_por_wave"])),
            ],
        )

    def _a_guardar_config(self):
        v = self.valores_formulario()
        self.sim.configurar(int(v["wave_max_pedidos"] or 0), int(v["wave_max_productos"] or 0), int(v["max_pickers_por_wave"] or 0))
        self.cerrar_dialogo()
        self.mensaje = "Capacidad de las waves actualizada. Generá las waves de nuevo."

    # --- waves ---
    def _a_generar_waves(self):
        waves = self.sim.generar_waves()
        self.seleccion = set()
        self.comparacion = None
        self.pestana, self.pag_tabla = "Waves", 0
        descartados = len(self.sim.estado.gestor_waves.pedidos_descartados)
        self.mensaje = f"{len(waves)} waves generadas (Max-Heap por prioridad + cercanía en el dígrafo)."
        if descartados:
            self.mensaje += f" {descartados} pedidos no se pueden preparar (ver Eventos)."
        self.dialogo = "waves"

    def _a_elegir_waves(self):
        if not self.sim.waves:
            raise ValueError("Primero generá las waves.")
        self.dialogo = "waves"
        self.reproduciendo = False

    def _a_marcar(self, wid):
        self.seleccion ^= {wid}

    def _a_marcar_todas(self, todas):
        self.seleccion = {w["id"] for w in self.waves_pendientes()} if todas else set()

    def _a_iniciar_seleccion(self):
        ids = [w["id"] for w in self.waves_pendientes() if w["id"] in self.seleccion]
        if not ids:
            raise ValueError("Marcá al menos una wave pendiente.")
        tanda = self.sim.iniciar_waves(ids, self.sim.estrategia)
        self.seleccion = set()
        self.dialogo = None
        self.comparacion = None
        self.picker_foco = tanda["planes"][0]["picker"] if tanda["planes"] else self.picker_foco
        self.pestana = "Pickers"
        self.mensaje = (
            f"Tanda {tanda['numero']} ({NOMBRE_ESTRATEGIA[tanda['estrategia']]}): "
            f"{', '.join(tanda['waves'])} asignadas a los pickers más cercanos. Iniciá la simulación."
        )
        if tanda["en_espera"]:
            self.mensaje += f" En espera hasta que se libere un picker: {len(tanda['en_espera'])} waves."

    def _a_estrategia(self):
        nueva = "ORDEN" if self.sim.estrategia == "CERCANIA" else "CERCANIA"
        replanificada = self.sim.cambiar_estrategia(nueva)
        self.comparacion = None
        self.mensaje = "Estrategia: " + NOMBRE_ESTRATEGIA[nueva] + (
            ". La tanda actual se volvió a planificar." if replanificada
            else ". Se usa en la próxima tanda (o reiniciá la actual y volvé a cambiarla)."
        )

    def _a_comparar(self, desde_dialogo=False):
        self.reproduciendo = False
        ids = None
        if desde_dialogo or not self.sim.tanda_actual:
            ids = [w["id"] for w in self.waves_pendientes() if w["id"] in self.seleccion]
            if not ids:
                raise ValueError("Marcá waves pendientes en 'Seleccionar waves' o iniciá una tanda para comparar.")
        self.comparacion = self.sim.comparar_estrategias(ids)
        self.dialogo = "comparar"

    # --- simulación ---
    def _a_iniciar(self):
        if not self.sim.en_curso:
            if self.seleccion:
                self._a_iniciar_seleccion()
            elif self.sim.waves:
                self._a_elegir_waves()
                return
            else:
                self._a_generar_waves()
                return
        self.reproduciendo = True
        self.acumulado = 0.0

    def _a_continuar(self):
        if not self.sim.en_curso:
            raise ValueError("No hay pickers trabajando. Seleccioná waves e iniciá.")
        self.reproduciendo = True

    def _a_pausar(self):
        self.reproduciendo = False

    def _a_adelante(self):
        self.reproduciendo = False
        if not self.sim.avanzar():
            raise ValueError("No hay pickers trabajando. Seleccioná waves e iniciá.")

    def _a_atras(self):
        self.reproduciendo = False
        if not self.sim.retroceder():
            raise ValueError("No hay pasos para deshacer.")

    def _a_reiniciar(self):
        self.reproduciendo = False
        if not self.sim.reiniciar():
            raise ValueError("Todavía no se inició ninguna tanda.")
        self.mensaje = "Tanda reiniciada: los pickers vuelven al punto de partida y el stock se restaura."

    def _a_velocidad(self):
        self.velocidad = (self.velocidad + 1) % len(VELOCIDADES)

    def _a_guardar(self):
        self.reproduciendo = False
        ruta = self.biblioteca.guardar_sesion(self.sim, self.nombre)
        self.mensaje = f"Sesión guardada como {ruta.name}. Al abrirla se retoma en este mismo turno."

    def _a_pestana(self, nombre):
        self.pestana = nombre
        self.pag_tabla = 0

    def _a_foco_picker(self, pid):
        self.picker_foco = pid

    def _a_foco_wave(self, wid):
        self.wave_foco = None if self.wave_foco == wid else wid

    def _a_ampliar(self):
        self.mapa_ampliado = not self.mapa_ampliado

    def _a_exploracion(self):
        self.ver_exploracion = not self.ver_exploracion

    def _a_mapa(self):
        celda = self.mapa.celda_en(self.ultimo_clic)
        if celda is None:
            return
        tipo, sentido, elemento = self.sim.celdas[celda]
        for p in self.sim.resumen_pickers():
            if tuple(p["pos"]) == celda:
                self.picker_foco = p["id"]
        texto = f"Celda {celda}: {tipo.replace('_', ' ').lower()}"
        if tipo == "PASILLO":
            texto += f", sentido {sentido}" + (" (intersección)" if celda in self.sim.intersecciones else "")
        elif elemento:
            texto += f" {elemento}"
        productos = [p for p in self.sim.productos() if (p["x"], p["y"]) == celda]
        if productos:
            texto += " · " + ", ".join(f"z={p['z']}: {p['id']} {p['nombre']} (stock {p['stock']})" for p in productos)
        self.mensaje = texto

    def a_lienzo(self, pos):
        """Convierte una posición de la ventana a coordenadas del lienzo fijo."""
        return (
            int((pos[0] - self.desplazamiento[0]) / self.escala),
            int((pos[1] - self.desplazamiento[1]) / self.escala),
        )

    # ------------------------------------------------------------------
    # Pantallas
    # ------------------------------------------------------------------
    def pantalla_inicio(self):
        self.texto("Inicio · Escenarios", 30, 76, 26, negrita=True)
        self.caja(30, 130, 420, 450)
        self.texto("Crear escenario", 52, 152, 22, negrita=True)
        self.parrafo("Generá un almacén automáticamente o importá un JSON. Queda guardado en la biblioteca.", 52, 192, 375, 17)
        self.boton("Crear escenario", 52, 262, 375, "crear", marcado=True)
        self.texto("Generador automático", 52, 330, 19, negrita=True)
        self.parrafo("Determinista: con los mismos parámetros sale siempre el mismo almacén. Se garantiza que todo producto se alcance desde el despacho.", 52, 360, 375, 16, limite=4)
        self.texto("Desde archivo", 52, 455, 19, negrita=True)
        self.parrafo("También podés arrastrar un JSON sobre la ventana.", 52, 485, 375, 16)
        if self.sim:
            self.boton("Volver a la simulación", 52, 600, 375, "volver")

        self.texto("Biblioteca", 490, 140, 22, negrita=True)
        self.texto("Escenarios y sesiones guardadas", 490, 172, 16, GRIS)
        archivos = self.biblioteca.archivos()
        por_pagina = 10
        self.pag_biblioteca = min(self.pag_biblioteca, max(0, (len(archivos) - 1) // por_pagina))
        for i, ruta in enumerate(archivos[self.pag_biblioteca * por_pagina:][:por_pagina]):
            y = 205 + i * 62
            self.caja(490, y, 1000, 54)
            etiqueta = "SESIÓN" if ruta.name.startswith("sesion_") else "ESCENARIO"
            self.texto(etiqueta, 506, y + 18, 13, AZUL if etiqueta == "SESIÓN" else GRIS, True)
            self.texto(ruta.stem, 600, y + 16, 17, max_ancho=560)
            self.boton("Abrir", 1210, y + 10, 130, ("abrir", ruta))
            self.boton("Eliminar", 1352, y + 10, 120, ("eliminar", ruta))
        self.paginador("pag_biblioteca", len(archivos), por_pagina, 1330, 832)

    def barra_simulacion(self):
        m = self.sim
        self.texto(self.nombre, 260, 26, 17, GRIS, max_ancho=760)
        self.boton("Guardar sesión", 1210, 18, 150, "guardar")
        self.boton("Inicio", 1370, 18, 120, "inicio")
        hay_waves = bool(m.waves)
        iniciadas = m.waves_iniciadas
        fila1 = [
            ("Nuevo pedido", 140, "nuevo_pedido", not iniciadas),
            ("Capacidad de waves", 175, "config", not iniciadas),
            ("Generar waves", 150, "generar_waves", not iniciadas),
            ("Seleccionar waves", 170, "elegir_waves", hay_waves),
            ("Estrategia: " + NOMBRE_ESTRATEGIA[m.estrategia], 245, "estrategia", True),
            ("Comparar estrategias", 195, "comparar", hay_waves),
            ("Exploración: " + ("sí" if self.ver_exploracion else "no"), 160, "exploracion", True),
        ]
        x = 20
        for etiqueta, w, accion, habilitado in fila1:
            self.boton(etiqueta, x, 62, w, accion, habilitado)
            x += w + 8
        en_curso = m.en_curso
        fila2 = [
            ("Iniciar", 105, "iniciar", hay_waves and not self.reproduciendo),
            ("Pausar", 105, "pausar", self.reproduciendo),
            ("Continuar", 115, "continuar", en_curso and not self.reproduciendo),
            ("Paso adelante >", 155, "adelante", en_curso),
            ("< Paso atrás", 140, "atras", bool(m.historial)),
            ("Reiniciar", 115, "reiniciar", m.tanda_actual is not None),
            ("Velocidad " + VELOCIDADES[self.velocidad][1], 140, "velocidad", True),
            ("Ver paneles" if self.mapa_ampliado else "Ampliar mapa", 150, "ampliar", True),
        ]
        x = 20
        for etiqueta, w, accion, habilitado in fila2:
            self.boton(etiqueta, x, 104, w, accion, habilitado)
            x += w + 8
        tanda = m.tanda_actual
        estado = "en reproducción" if self.reproduciendo else "pausado" if en_curso else "sin pickers trabajando"
        linea = f"Turno {m.estado.paso} · {estado}"
        if tanda:
            hechas = sum(1 for w in m.resumen_waves() if w["id"] in tanda["waves"] and w["estado"] == "FINALIZADA")
            linea += (
                f" · Tanda {tanda['numero']} ({NOMBRE_ESTRATEGIA[tanda['estrategia']]}): "
                f"{len(tanda['waves'])} waves asignadas, {hechas} terminadas, {len(tanda['en_espera'])} en espera"
            )
        self.texto(linea, 20, 152, 17, AZUL if self.reproduciendo else TINTA, max_ancho=1470)

    def pantalla_simulacion(self):
        self.barra_simulacion()
        ancho = 1482 if self.mapa_ampliado else 744
        self.mapa.area = pygame.Rect(20, 186, ancho - 4, 690)
        self.caja(18, 184, ancho, 694)
        self.mapa.dibujar()
        self.mapa.leyenda(20, 884)
        if not self.mapa_ampliado:
            self.panel_derecho()

    # ------------------------------------------------------------------
    # Panel derecho con pestañas
    # ------------------------------------------------------------------
    def panel_derecho(self):
        x0, y0 = 778, 184
        ancho_pestana = 118
        for i, nombre in enumerate(PESTANAS):
            self.boton(nombre, x0 + i * (ancho_pestana + 2), y0, ancho_pestana, ("pestana", nombre), marcado=self.pestana == nombre)
        self.caja(x0, y0 + 40, 722, 680)
        getattr(self, "panel_" + {"Métricas": "metricas"}.get(self.pestana, self.pestana.lower()))(x0 + 14, y0 + 52)

    def _tabla(self, x, y, columnas, filas, por_pagina=24, acciones=None, marcadas=()):
        for etiqueta, dx in columnas:
            self.texto(etiqueta, x + dx, y, 15, GRIS, True)
        inicio = self.pag_tabla * por_pagina
        if inicio >= len(filas):
            self.pag_tabla, inicio = 0, 0
        for i, fila in enumerate(filas[inicio:inicio + por_pagina]):
            yy = y + 26 + i * 24
            if inicio + i in marcadas:
                self.caja(x - 6, yy - 3, 706, 23, AZUL_CLARO, None)
            for (valor, color), (_, dx), siguiente in zip(fila, columnas, columnas[1:] + [("", 700)]):
                self.texto(valor, x + dx, yy, 15, color, max_ancho=siguiente[1] - dx - 6)
            if acciones:
                self.zona_clic((x - 6, yy - 3, 706, 23), acciones[inicio + i])
        self.paginador("pag_tabla", len(filas), por_pagina, x + 540, y + 26 + por_pagina * 24 + 6)

    def panel_productos(self, x, y):
        resaltadas = self.celdas_resaltadas()
        productos = self.sim.productos()
        self.texto(f"{len(productos)} productos · ubicación <x,y,z> en el rack · stock actual", x, y, 16, GRIS)
        filas, marcadas = [], set()
        for i, p in enumerate(productos):
            color = AMBAR if (p["x"], p["y"]) in resaltadas else TINTA
            if color == AMBAR:
                marcadas.add(i)
            filas.append([
                (p["id"], TINTA), (p["nombre"], TINTA), (p["rack"], TINTA),
                (f"<{p['x']},{p['y']},{p['z']}>", TINTA), (f"{p['peso']:g}", TINTA),
                (p["stock"], ROJO if p["stock"] == 0 else color),
            ])
        self._tabla(x, y + 28, [("ID", 0), ("Nombre", 70), ("Rack", 270), ("Ubicación", 340), ("kg/u", 470), ("Stock", 540)], filas, 23, marcadas=marcadas)

    def panel_pedidos(self, x, y):
        pedidos = self.sim.pedidos()
        estados = {}
        for p in pedidos:
            estados[p["estado"]] = estados.get(p["estado"], 0) + 1
        self.texto(" · ".join(f"{k}: {v}" for k, v in sorted(estados.items())), x, y, 16, GRIS, max_ancho=690)
        colores = {"PENDIENTE": TINTA, "EN_WAVE": AZUL, "EN_PREPARACION": AMBAR, "PREPARADO": VERDE, "IRREALIZABLE": ROJO}
        filas = [
            [
                (p["id"], TINTA), (p["prioridad"], TINTA), (p["estado"], colores.get(p["estado"], TINTA)),
                (", ".join(f"{a}×{b}" for a, b in p["items"]), TINTA), (p["wave"] or "-", TINTA),
            ]
            for p in pedidos
        ]
        self._tabla(x, y + 28, [("Pedido", 0), ("Prio.", 80), ("Estado", 130), ("Productos", 290), ("Wave", 610)], filas, 23)

    def panel_waves(self, x, y):
        waves = self.sim.resumen_waves()
        if not waves:
            self.parrafo("Todavía no hay waves. Usá 'Generar waves': se toman los pedidos pendientes de mayor prioridad (Max-Heap) y se les suman los pedidos más cercanos en el dígrafo, respetando la capacidad.", x, y, 680, 17, limite=5)
            return
        self.texto("Clic en una wave para ver sus ubicaciones en el mapa", x, y, 16, GRIS)
        colores = {"PENDIENTE": TINTA, "EN_EJECUCION": AMBAR, "FINALIZADA": VERDE}
        filas = [
            [
                (w["id"], TINTA), (w["estado"], colores.get(w["estado"], TINTA)), (", ".join(w["pedidos"]), TINTA),
                (w["unidades"], TINTA), (f"{w['peso']:.1f}", TINTA), (w["zona"], TINTA), (", ".join(w["pickers"]) or "-", TINTA),
            ]
            for w in waves
        ]
        marcadas = {i for i, w in enumerate(waves) if w["id"] == self.wave_foco}
        self._tabla(
            x, y + 28,
            [("Wave", 0), ("Estado", 85), ("Pedidos", 205), ("Unid.", 440), ("kg", 495), ("Zona", 555), ("Pickers", 630)],
            filas, 23, acciones=[("foco_wave", w["id"]) for w in waves], marcadas=marcadas,
        )

    def panel_pickers(self, x, y):
        pickers = self.sim.resumen_pickers()
        enfocado = self.picker_enfocado(pickers)
        alto = 150 if len(pickers) <= 4 else 74
        for i, p in enumerate(pickers[:8]):
            yy = y + i * (alto + 6)
            seleccionado = enfocado and p["id"] == enfocado["id"]
            rect = self.caja(x - 4, yy, 700, alto, AZUL_CLARO if seleccionado else BLANCO)
            self.zona_clic(rect, ("foco_picker", p["id"]))
            pygame.draw.circle(self.lienzo, color_picker(i), (x + 12, yy + 18), 9)
            estado = f"haciendo {p['wave']}" if p["wave"] else "libre"
            self.texto(f"{p['id']} · {estado} · en {tuple(p['pos'])}", x + 30, yy + 8, 17, negrita=True)
            self.texto(f"Carga {p['carga']:.1f}/{p['capacidad']:g} kg · {p['pasos']} pasos · {p['esperas']} esperas", x + 380, yy + 10, 15, GRIS)
            recogidos = ", ".join(f"{k}×{v}" for k, v in p["recogidos"].items()) or "nada todavía"
            self.texto("Recogido: " + recogidos, x + 30, yy + 34, 15, VERDE if p["recogidos"] else GRIS, max_ancho=660)
            if alto > 100:
                pendientes = ", ".join(f"{k}×{v}" for k, v in p["pendientes"]) or "-"
                self.texto("Falta recoger: " + pendientes, x + 30, yy + 58, 15, AMBAR if p["pendientes"] else GRIS, max_ancho=660)
                plan = p["plan"]
                if plan:
                    self.texto(
                        f"Plan ({NOMBRE_ESTRATEGIA[plan['estrategia']]}): {plan['distancia']} pasos · "
                        f"{plan['nodos_visitados']} nodos visitados · {plan['nodos_explorados']} explorados · {plan['tiempo_ms']:.2f} ms",
                        x + 30, yy + 82, 15, AZUL, max_ancho=660,
                    )
                    self.texto(f"Pedidos: {', '.join(plan['pedidos'])} · restan {len(p['ruta_restante'])} pasos", x + 30, yy + 106, 15, GRIS, max_ancho=660)
        if len(pickers) > 8:
            self.texto(f"(+{len(pickers) - 8} pickers más)", x, y + 8 * (alto + 6), 15, GRIS)

    def panel_metricas(self, x, y):
        m = self.sim
        met = m.metricas()
        self.texto("Grafo y simulación", x, y, 18, negrita=True)
        lineas = [
            f"Dígrafo: {met['nodos']} nodos (celdas de pasillo), {met['aristas']} aristas dirigidas, {len(m.intersecciones)} intersecciones.",
            f"Matriz de distancias entre productos (Dijkstra desde cada acceso): {m.tiempo_matriz_ms:.1f} ms.",
            f"Waves: {met['waves']} generadas, {met['waves_finalizadas']} finalizadas. Pedidos preparados: {met['pedidos_preparados']}/{met['pedidos']}.",
            f"Turno {met['paso']} · pasos caminados en total: {met['pasos_totales']} · esperas por colisión: {met['esperas']} · desvíos: {met['desvios']}.",
        ]
        for i, linea in enumerate(lineas):
            self.texto(linea, x, y + 30 + i * 24, 15, max_ancho=690)
        tanda = met["tanda"]
        yy = y + 140
        if tanda:
            self.texto(f"Tanda {tanda['numero']} · {NOMBRE_ESTRATEGIA[tanda['estrategia']]}", x, yy, 18, negrita=True)
            columnas = [("Picker", 0), ("Wave", 90), ("Distancia", 190), ("Aristas", 290), ("Nodos visitados", 380), ("Explorados", 520), ("ms", 630)]
            for etiqueta, dx in columnas:
                self.texto(etiqueta, x + dx, yy + 30, 15, GRIS, True)
            planes = tanda["planes"][-10:]
            for i, plan in enumerate(planes):
                valores = [plan["picker"], plan["wave"], plan["distancia"], plan["aristas"], plan["nodos_visitados"], plan["nodos_explorados"], f"{plan['tiempo_ms']:.2f}"]
                for valor, (_, dx) in zip(valores, columnas):
                    self.texto(valor, x + dx, yy + 56 + i * 22, 15)
            yy += 70 + 22 * len(planes)
            if tanda["en_espera"]:
                self.texto(f"En espera: {', '.join(tanda['en_espera'])}", x, yy, 15, AMBAR, max_ancho=690)
                yy += 22
            if tanda["paso_fin"] is not None:
                self.texto(f"Terminó en {tanda['paso_fin'] - tanda['paso_inicio']} turnos de simulación.", x, yy, 15, VERDE)
            yy += 34
        if self.comparacion:
            self.dibujar_comparacion(x, yy)
        else:
            self.parrafo("Usá 'Comparar estrategias' para correr las mismas waves con Orden de pedidos y con Cercanía y ver sus métricas lado a lado.", x, yy, 680, 16)

    def panel_eventos(self, x, y):
        eventos = list(reversed(self.sim.estado.eventos))
        self.texto("Lo último primero: recogidas, descargas, esperas y desvíos", x, y, 16, GRIS)
        filas = [[(e, ROJO if "ATENCIÓN" in e or "Error" in e else TINTA)] for e in eventos]
        self._tabla(x, y + 28, [("Evento", 0)], filas, 23)

    # ------------------------------------------------------------------
    # Diálogos
    # ------------------------------------------------------------------
    FILAS_COMPARACION = [
        ("Distancia total (pasos)", "distancia"),
        ("Nodos visitados (celdas distintas)", "nodos_visitados"),
        ("Aristas recorridas", "aristas"),
        ("Nodos explorados (celdas distintas)", "nodos_explorados"),
        ("Nodos expandidos (suma de búsquedas)", "expansiones"),
        ("Tiempo de cálculo de rutas (ms)", "tiempo_ms"),
        ("Turnos simulados hasta terminar", "turnos"),
        ("Esperas por colisión", "esperas"),
        ("Desvíos recalculados", "desvios"),
    ]

    def dibujar_comparacion(self, x, y):
        comp = self.comparacion
        orden, cerca = comp["ORDEN"], comp["CERCANIA"]
        self.texto("Comparación · " + ", ".join(orden["waves"]), x, y, 18, negrita=True, max_ancho=690)
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
                self.texto(texto + ("  (mejor)" if mejor else ""), x + dx, yy, 16, VERDE if mejor else TINTA, mejor)
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
            "El generador arma racks de 2 x 6 separados por pasillos verticales de un solo sentido (alternando N y S), "
            "con pasillos transversales de doble sentido, las zonas de despacho abajo y los productos según la localización elegida. "
            "Antes de guardarlo se verifica con Kosaraju que desde cualquier pasillo se pueda ir y volver.",
            x, y + 200, w - 20, 17, limite=6,
        )

    def _dibujar_formulario(self, x, y, w, titulo, texto_boton, ayuda=""):
        self.texto(titulo, x, y, 26, negrita=True)
        f = self.formulario
        for i, (clave, etiqueta, valor) in enumerate(f["campos"]):
            yy = y + 66 + i * 52
            self.texto(etiqueta, x, yy + 8, 18)
            if clave == "localizacion":
                self.boton(f"{valor}  (clic para cambiar)", x + 470, yy, 360, ("campo", i), marcado=f["foco"] == i)
                self.texto(LOCALIZACIONES[valor], x + 470, yy + 36, 13, GRIS)
            else:
                self.campo(x + 470, yy, 360, valor, f["foco"] == i, ("campo", i))
        yy = y + 76 + len(f["campos"]) * 52
        if ayuda:
            self.parrafo(ayuda, x, yy, w - 20, 15, limite=3)
        self.boton(texto_boton + " (Enter)", x, y + 610, 320, "enviar", marcado=True)

    def dialogo_generador(self, x, y, w):
        self._dibujar_formulario(x, y, w, "Generador automático de escenarios", "Generar y guardar",
                                 "Tab cambia de campo. La localización se cambia con un clic. El resultado es siempre el mismo para los mismos valores.")

    def dialogo_pedido(self, x, y, w):
        self._dibujar_formulario(x, y, w, "Nuevo pedido", "Crear pedido",
                                 "Escribí los productos separados por coma, con la cantidad después de una x. El pedido queda PENDIENTE hasta generar las waves.")

    def dialogo_config(self, x, y, w):
        self._dibujar_formulario(x, y, w, "Capacidad de las waves", "Guardar",
                                 "Cambiar la capacidad descarta las waves generadas que todavía no se iniciaron.")

    def dialogo_eliminar(self, x, y, w):
        self.texto("Eliminar de la biblioteca", x, y, 26, negrita=True)
        self.parrafo("Se va a borrar: " + Path(self.dialogo[1]).name, x, y + 80, w - 20, 20)
        self.boton("Eliminar", x, y + 180, 200, "confirmar_eliminar", marcado=True)
        self.boton("Cancelar", x + 220, y + 180, 200, "cerrar")

    def dialogo_waves(self, x, y, w):
        m = self.sim
        self.texto("Seleccionar waves", x, y, 26, negrita=True)
        libres = sum(1 for p in m.warehouse.pickers if p.id_wave_actual is None)
        self.texto(
            f"Pickers libres: {libres} de {len(m.warehouse.pickers)} · cada picker hace una sola wave por viaje · estrategia: {NOMBRE_ESTRATEGIA[m.estrategia]}",
            x, y + 42, 16, GRIS, max_ancho=w,
        )
        waves = m.resumen_waves()
        por_pagina = 12
        self.pag_waves_dialogo = min(self.pag_waves_dialogo, max(0, (len(waves) - 1) // por_pagina))
        for etiqueta, dx in [("Wave", 34), ("Estado", 130), ("Pedidos", 260), ("Unid.", 600), ("kg", 660), ("Zona", 730)]:
            self.texto(etiqueta, x + dx, y + 78, 15, GRIS, True)
        for i, wv in enumerate(waves[self.pag_waves_dialogo * por_pagina:][:por_pagina]):
            yy = y + 106 + i * 36
            pendiente = wv["estado"] == "PENDIENTE"
            self.casilla(x, yy, wv["id"] in self.seleccion, ("marcar", wv["id"]), pendiente)
            color = TINTA if pendiente else GRIS
            for valor, dx in [(wv["id"], 34), (wv["estado"], 130), (", ".join(wv["pedidos"]), 260), (wv["unidades"], 600), (f"{wv['peso']:.1f}", 660), (wv["zona"], 730)]:
                self.texto(valor, x + dx, yy + 1, 16, color, max_ancho=330)
        self.paginador("pag_waves_dialogo", len(waves), por_pagina, x + w - 150, y + 540)
        self.boton("Marcar todas", x, y + 540, 150, ("marcar_todas", True))
        self.boton("Ninguna", x + 160, y + 540, 120, ("marcar_todas", False))
        hay = bool(self.seleccion)
        self.boton("Asignar e iniciar", x, y + 600, 260, "iniciar_seleccion", hay and libres > 0, marcado=hay and libres > 0)
        self.boton("Comparar estrategias", x + 280, y + 600, 240, ("comparar", True), hay)
        self.parrafo("Las waves marcadas se asignan a los pickers libres más cercanos y se mueven todos a la vez.", x + 540, y + 596, w - 560, 15)

    def dialogo_comparar(self, x, y, w):
        self.texto("Comparar estrategias de recorrido", x, y, 26, negrita=True)
        self.parrafo(
            "Mismas waves, mismo estado inicial y mismos pickers. Orden de pedidos: Dijkstra tramo a tramo en el orden de los pedidos. "
            "Cercanía: después de cada producto va al más cercano todavía no visitado (Dijkstra multidestino). "
            "Las dos se simulan completas con el gestor de colisiones; la simulación real no se modifica.",
            x, y + 44, w - 20, 16, limite=4,
        )
        fin = self.dibujar_comparacion(x, y + 140)
        o, c = self.comparacion["ORDEN"], self.comparacion["CERCANIA"]
        if o["distancia"] and c["distancia"]:
            ahorro = (o["distancia"] - c["distancia"]) / o["distancia"] * 100
            self.parrafo(
                f"Cercanía recorre {abs(ahorro):.1f}% {'menos' if ahorro >= 0 else 'más'} que Orden de pedidos. "
                "(mejor) marca el menor valor de cada fila.",
                x, fin + 20, w - 20, 16,
            )

    # ------------------------------------------------------------------
    # Bucle principal
    # ------------------------------------------------------------------
    def dibujar(self):
        self.lienzo.fill(FONDO)
        self.botones = []
        self.texto("Wave Picking", 20, 18, 28, negrita=True)
        if self.pagina == "inicio" or self.sim is None:
            self.pantalla_inicio()
        else:
            self.pantalla_simulacion()
        if self.dialogo:
            self.dialogo_actual()
        self.caja(0, ALTO - 34, ANCHO, 34, BLANCO, None)
        self.texto(self.mensaje, 20, ALTO - 27, 16, AZUL, max_ancho=ANCHO - 40)
        self.presentar()

    def presentar(self):
        ancho, alto = self.ventana.get_size()
        self.escala = min(ancho / ANCHO, alto / ALTO)
        w, h = max(1, int(ANCHO * self.escala)), max(1, int(ALTO * self.escala))
        self.desplazamiento = ((ancho - w) // 2, (alto - h) // 2)
        try:
            imagen = pygame.transform.smoothscale(self.lienzo, (w, h))
        except (ValueError, pygame.error):
            imagen = pygame.transform.scale(self.lienzo, (w, h))
        self.ventana.fill(FONDO)
        self.ventana.blit(imagen, self.desplazamiento)
        pygame.display.flip()

    def paso_automatico(self, dt):
        if not (self.reproduciendo and self.sim and not self.dialogo):
            return
        self.acumulado += dt
        intervalo = VELOCIDADES[self.velocidad][0]
        pasos = 0
        while self.acumulado >= intervalo and pasos < 10:
            self.acumulado -= intervalo
            pasos += 1
            try:
                if not self.sim.avanzar():
                    self.reproduciendo = False
                    tanda = self.sim.tanda_actual
                    self.mensaje = "Simulación terminada." + (
                        f" Tanda {tanda['numero']} en {tanda['paso_fin'] - tanda['paso_inicio']} turnos."
                        if tanda and tanda["paso_fin"] is not None else ""
                    ) + " Seleccioná más waves o compará estrategias."
                    break
            except Exception as exc:
                self.mensaje = "Error en la simulación: " + str(exc)
                self.reproduciendo = False
                break

    def run(self, cuadros=None):
        reloj = pygame.time.Clock()
        n = 0
        while self.corriendo and (cuadros is None or n < cuadros):
            dt = reloj.tick(30) / 1000
            for evento in pygame.event.get():
                manejar_evento(self, evento)
            self.paso_automatico(dt)
            self.dibujar()
            n += 1
