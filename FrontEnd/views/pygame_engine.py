"""Ventana principal de Pygame: biblioteca de escenarios y pantalla interactiva de simulación."""

from pathlib import Path
import time
import pygame

from BackEnd.controllers.simulador import NOMBRE_ESTRATEGIA, Simulador
from BackEnd.controllers.wave_manager import OPCIONES_ESTRATEGIA_ARMADO
from BackEnd.utils.scenario_generator import LOCALIZACIONES
from FrontEnd.events.input_handler import manejar_evento
from FrontEnd.services.biblioteca import Biblioteca
from FrontEnd.sprites.picker_sprite import angulo_para, color_picker
from FrontEnd.views.mapa import VistaMapa
from FrontEnd.views.paneles import PanelesVistas
from FrontEnd.views.dialogos import DialogosVistas
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

VELOCIDADES = [(0.70, "x0.5"), (0.35, "x1"), (0.18, "x2"), (0.07, "x5"), (0.02, "x20")]
DURACION_PASO_MANUAL = 0.30


class App(UIElements, PanelesVistas, DialogosVistas):
    OPCIONES_FORMULARIO = {
        "localizacion": LOCALIZACIONES,
        "estrategia_waves": OPCIONES_ESTRATEGIA_ARMADO,
    }

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
        self.reproduccion_iniciada = False
        self.sesion_guardada = False
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
        self.armado = None
        self.animacion = {}
        self.angulos = {}
        self.inicio_animacion = 0.0
        self.duracion_animacion = 0.0
        self.arrastre = None
        self.comparacion_armado = None
        self.productos_por_celda = {}
        self.mapa = VistaMapa(self, 20, 186, 740, 690)

    def cargar(self, ruta):
        sim = Biblioteca.abrir(ruta)
        self._usar(sim, Path(ruta).stem)
        sesion = Biblioteca.es_sesion(ruta)
        self.mensaje = (
            f"Sesión retomada en el turno {sim.estado.paso}. Podés continuar la simulación."
            if sesion
            else "Escenario cargado. Revisá los productos y pedidos, y generá las waves."
        )
        if sim.advertencias:
            self.mensaje += " Advertencias: " + "; ".join(sim.advertencias[:2])

    def _usar(self, sim: Simulador, nombre: str):
        self.sim = sim
        self.nombre = nombre
        self.pagina = "sim"
        self.reproduciendo = False
        self.sesion_guardada = False
        self.reproduccion_iniciada = bool(
            sim.en_curso
            and sim.tanda_actual
            and sim.estado.paso > sim.tanda_actual["paso_inicio"]
        )
        self.seleccion = set()
        self.picker_foco = (
            sim.warehouse.pickers[0].id_picker if sim.warehouse.pickers else None
        )
        self.wave_foco = None
        self.comparacion = None
        self.pag_tabla = 0
        self.animacion, self.angulos = {}, {}
        self.armado = None
        self.comparacion_armado = None
        self.mapa.centrar()
        self.pestana = "Productos" if not sim.waves else "Pickers"
        self.productos_por_celda = {}
        for p in sim.warehouse.catalogo_productos.values():
            self.productos_por_celda[(p.x, p.y)] = (
                self.productos_por_celda.get((p.x, p.y), 0) + 1
            )

    def _a_cambiar_armado(self):
        if self.sim.waves_iniciadas:
            return
        c = self.sim.config
        opciones = tuple(OPCIONES_ESTRATEGIA_ARMADO)
        actual = c["estrategia_waves"]
        indice = opciones.index(actual) + 1 if actual in opciones else 0
        ya_generadas = bool(self.sim.waves)
        dialogo = self.dialogo
        self.sim.configurar(
            c["wave_max_pedidos"],
            c["wave_max_productos"],
            c["max_pickers_por_wave"],
            opciones[indice % len(opciones)],
        )
        if ya_generadas:
            self._a_generar_waves()
            self.dialogo = dialogo
        else:
            self.mensaje = "Estrategia de armado seleccionada. Generá las waves para aplicarla."

    def importar_con_dialogo(self):
        import tkinter as tk
        from tkinter.filedialog import askopenfilename

        raiz = tk.Tk()
        raiz.withdraw()
        try:
            ruta = askopenfilename(
                title="Importar escenario JSON", filetypes=[("JSON", "*.json")]
            )
            raiz.update()
        finally:
            raiz.destroy()
        if ruta:
            self.importar(ruta)

    def importar(self, ruta):
        destino = self.biblioteca.importar(ruta)
        self.dialogo = None
        self.mensaje = (
            f"Escenario validado y agregado a la biblioteca como {destino.name}."
        )

    def picker_enfocado(self, pickers=None):
        pickers = pickers if pickers is not None else self.sim.resumen_pickers()
        for p in pickers:
            if p["id"] == self.picker_foco:
                return p
        return pickers[0] if pickers else None

    def mover(self, funcion, duracion=None):
        antes = {p.id_picker: p.posicion_actual for p in self.sim.warehouse.pickers}
        resultado = funcion()
        despues = {p.id_picker: p.posicion_actual for p in self.sim.warehouse.pickers}
        self.animacion = {
            pid: (antes.get(pid, pos), pos) for pid, pos in despues.items()
        }
        for pid, (desde, hasta) in self.animacion.items():
            dx, dy = hasta[0] - desde[0], hasta[1] - desde[1]
            if abs(dx) + abs(dy) == 1:
                self.angulos[pid] = angulo_para(dx, dy, self.angulos.get(pid, 0))
        self.inicio_animacion = time.perf_counter()
        if duracion is None:
            duracion = (
                VELOCIDADES[self.velocidad][0]
                if self.reproduciendo
                else DURACION_PASO_MANUAL
            )
        self.duracion_animacion = duracion
        return resultado

    def busquedas_activas(self):
        if self.sim is None:
            return {}
        if self.duracion_animacion > 0:
            t = min(
                1.0,
                (time.perf_counter() - self.inicio_animacion) / self.duracion_animacion,
            )
        else:
            t = 1.0
        activas = {}
        for p in self.sim.warehouse.pickers:
            plan = self.sim.estado.planes.get(p.id_picker)
            if p.turnos_busqueda <= 0 or plan is None:
                continue
            total = max(1, plan.get("turnos_busqueda", 1))
            hechos = total - p.turnos_busqueda
            activas[p.id_picker] = (plan, min(1.0, (hechos + t) / total))
        return activas

    def posicion_animada(self, pid, posicion):
        posicion = tuple(posicion)
        angulo = self.angulos.get(pid, 0)
        desde, hasta = self.animacion.get(pid, (posicion, posicion))
        if (
            hasta != posicion
            or self.duracion_animacion <= 0
            or abs(hasta[0] - desde[0]) + abs(hasta[1] - desde[1]) != 1
        ):
            return posicion, angulo
        t = min(
            1.0, (time.perf_counter() - self.inicio_animacion) / self.duracion_animacion
        )
        return (
            desde[0] + (hasta[0] - desde[0]) * t,
            desde[1] + (hasta[1] - desde[1]) * t,
        ), angulo

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
    # Acciones e interacciones
    # ------------------------------------------------------------------
    def accion(self, accion):
        try:
            nombre, *args = accion if isinstance(accion, tuple) else (accion,)
            getattr(self, "_a_" + nombre)(*args)
        except Exception as exc:
            self.mensaje = "Acción interrumpida: " + str(exc)
            self.reproduciendo = False

    def _a_crear(self):
        self.dialogo = "crear"

    def _a_generador(self):
        campos_gen = [
            ("cantidad_estantes", "Cantidad de estantes (racks)", "12"),
            ("cantidad_pasillos", "Cantidad de pasillos verticales", "5"),
            ("cantidad_productos", "Cantidad de productos", "60"),
            ("localizacion", "Localización de los productos", "DISTRIBUIDA"),
            ("cantidad_pedidos", "Cantidad de pedidos", "20"),
            ("max_productos_por_pedido", "Máx. productos por pedido", "4"),
            ("wave_max_pedidos", "Capacidad wave: pedidos", "4"),
            ("wave_max_productos", "Capacidad wave: unidades", "20"),
            ("cantidad_pickers", "Cantidad de pickers", "3"),
        ]
        self.abrir_formulario("generador", campos_gen)

    def _a_importar(self):
        self.importar_con_dialogo()

    def _a_generar_escenario(self):
        v = self.valores_formulario()
        destino = self.biblioteca.generar(**v)
        self.cerrar_dialogo()
        self.mensaje = (
            f"Escenario generado y guardado como {destino.name}. Ya podés abrirlo."
        )

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
        setattr(
            self, atributo, max(0, min(paginas - 1, getattr(self, atributo) + delta))
        )

    def _a_campo(self, indice):
        campo = self.formulario["campos"][indice]
        if campo[0] in self.OPCIONES_FORMULARIO:
            opciones = list(self.OPCIONES_FORMULARIO[campo[0]])
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

    def _a_nuevo_pedido(self):
        ejemplo = ", ".join(f"{p['id']}x1" for p in self.sim.productos()[:2])
        self.abrir_formulario(
            "pedido",
            [
                ("items", "Productos (ej.: " + ejemplo + ")", ""),
                ("prioridad", "Prioridad (1 a 5)", "3"),
            ],
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
                (
                    "wave_max_pedidos",
                    "Máximo de pedidos por wave",
                    str(c["wave_max_pedidos"]),
                ),
                (
                    "wave_max_productos",
                    "Máximo de unidades por wave",
                    str(c["wave_max_productos"]),
                ),
                (
                    "max_pickers_por_wave",
                    "Máximo de pickers por wave",
                    str(c["max_pickers_por_wave"]),
                ),
                (
                    "estrategia_waves",
                    "Estrategia de armado de waves",
                    c["estrategia_waves"],
                ),
            ],
        )

    def _a_guardar_config(self):
        v = self.valores_formulario()
        self.sim.configurar(
            int(v["wave_max_pedidos"] or 0),
            int(v["wave_max_productos"] or 0),
            int(v["max_pickers_por_wave"] or 0),
            v["estrategia_waves"],
        )
        self.cerrar_dialogo()
        self.mensaje = "Capacidad de waves actualizada. Generá las waves."

    def _a_generar_waves(self):
        waves = self.sim.generar_waves()
        self.seleccion = set()
        self.comparacion = None
        self.armado = None
        self.wave_foco = None
        self.pestana, self.pag_tabla = "Waves", 0
        descartados = len(self.sim.estado.gestor_waves.pedidos_descartados)
        self.mensaje = f"{len(waves)} waves generadas correctamente."
        if descartados:
            self.mensaje += (
                f" {descartados} pedidos no pudieron prepararse (ver pestaña Eventos)."
            )
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
        estaba_en_curso = self.sim.en_curso
        tanda = self.sim.iniciar_waves(
            ids, self.sim.estrategia, self.sim.pickers_por_wave
        )
        if not estaba_en_curso:
            self.reproduccion_iniciada = False
        self.seleccion = set()
        self.dialogo = None
        self.comparacion = None
        self.picker_foco = (
            tanda["planes"][0]["picker"] if tanda["planes"] else self.picker_foco
        )
        self.pestana = "Pickers"
        self.mensaje = f"Tanda {tanda['numero']} asignada a los pickers más cercanos."

    def _a_estrategia(self):
        nueva = "ORDEN" if self.sim.estrategia == "CERCANIA" else "CERCANIA"
        replanificada = self.sim.cambiar_estrategia(nueva)
        self.comparacion = None
        self.mensaje = (
            "Estrategia: "
            + NOMBRE_ESTRATEGIA[nueva]
            + (". Tanda actual re-planificada." if replanificada else ".")
        )

    def _a_comparar(self, desde_dialogo=False):
        self.reproduciendo = False
        ids = None
        if desde_dialogo or not self.sim.tanda_actual:
            ids = [
                w["id"] for w in self.waves_pendientes() if w["id"] in self.seleccion
            ]
            if not ids:
                raise ValueError("Seleccioná waves pendientes para comparar.")
        self.comparacion = self.sim.comparar_estrategias(
            ids, self.sim.pickers_por_wave if ids else None
        )
        self.dialogo = "comparar"

    @property
    def puede_continuar(self):
        return self.sim.en_curso and self.reproduccion_iniciada and not self.reproduciendo

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
        self.reproduccion_iniciada = True
        self.acumulado = 0.0

    def _a_continuar(self):
        if not self.sim.en_curso:
            raise ValueError("No hay pickers trabajando.")
        self.reproduciendo = True
        if self.sesion_guardada:
            self.sesion_guardada = False
            self.mensaje = "Simulación reanudada."

    def _a_pausar(self):
        self.reproduciendo = False

    def _a_adelante(self):
        self.reproduciendo = False
        if not self.mover(self.sim.avanzar):
            raise ValueError("No hay pickers trabajando.")
        self.reproduccion_iniciada = True

    def _a_atras(self):
        self.reproduciendo = False
        if not self.mover(self.sim.retroceder):
            raise ValueError("No hay pasos previos para deshacer.")

    def _a_reiniciar(self):
        self.reproduciendo = False
        if not self.mover(self.sim.reiniciar, 0):
            raise ValueError("Todavía no se inició ninguna tanda.")
        self.sesion_guardada = False
        self.mensaje = "Tanda reiniciada: stock restaurado."

    def _a_velocidad(self):
        self.velocidad = (self.velocidad + 1) % len(VELOCIDADES)

    def _a_guardar(self):
        if self.sesion_guardada:
            return
        self.reproduciendo = False
        ruta = self.biblioteca.guardar_sesion(self.sim, self.nombre)
        self.sesion_guardada = True
        self.mensaje = f"Sesión guardada como {ruta.name}."

    def _a_pestana(self, nombre):
        self.pestana = nombre
        self.pag_tabla = 0

    def _a_foco_picker(self, pid):
        self.picker_foco = pid

    def _a_foco_wave(self, wid):
        self.wave_foco = None if self.wave_foco == wid else wid

    def _a_zoom(self, factor):
        self.mapa.zoom_en(self.mapa.area.center, factor)

    def _a_centrar_mapa(self):
        self.mapa.centrar()

    def _a_comparar_armado(self):
        self.reproduciendo = False
        self.comparacion_armado = self.sim.comparar_armado()
        self.dialogo = "armado"

    DURACION_ARMADO = {
        "raiz": 3.0,
        "evaluar": 4.0,
        "elegir": 3.5,
        "fin": 2.5,
        "ruta": 9.0,
    }
    COLORES_PEDIDO = [
        (196, 90, 30),
        (37, 99, 166),
        (31, 128, 98),
        (124, 65, 145),
        (176, 52, 46),
        (20, 120, 150),
        (150, 110, 20),
        (150, 60, 100),
    ]

    def colores_pedidos(self, datos):
        orden = [p["pedido"] for p in datos["pasos"] if p["tipo"] in ("raiz", "elegir")]
        return {
            pid: self.COLORES_PEDIDO[i % len(self.COLORES_PEDIDO)]
            for i, pid in enumerate(orden)
        }

    def progreso_armado(self):
        if not self.armado:
            return 1.0
        tipo = self.armado["datos"]["pasos"][self.armado["paso"]]["tipo"]
        duracion = self.DURACION_ARMADO.get(tipo, 3.0)
        return min(1.0, (time.perf_counter() - self.armado["inicio"]) / duracion)

    def _mover_armado(self, delta):
        pasos = self.armado["datos"]["pasos"]
        self.armado["paso"] = max(0, min(len(pasos) - 1, self.armado["paso"] + delta))
        self.armado["inicio"] = time.perf_counter()

    def _a_ver_armado(self, id_wave=None):
        waves = [w["id"] for w in self.sim.resumen_waves()]
        if not waves:
            raise ValueError("Primero generá las waves.")
        if id_wave not in waves:
            id_wave = next((wid for wid in waves if wid in self.seleccion), waves[0])
        datos = self.sim.explicar_armado(id_wave)
        if not datos["pasos"]:
            raise ValueError(f"No hay pasos de armado registrados para {id_wave}.")
        volver_a_waves = self.dialogo == "waves" or (
            self.armado is not None and self.armado["volver_a_waves"]
        )
        self.reproduciendo = False
        self.dialogo = None
        self.armado = {
            "datos": datos,
            "paso": 0,
            "inicio": time.perf_counter(),
            "auto": True,
            "volver_a_waves": volver_a_waves,
        }
        self.wave_foco = id_wave
        self.mapa_ampliado = False
        self.mapa.area = pygame.Rect(20, 186, 740, 690)
        celdas = [c for p in datos["pasos"] for c in p.get("celdas", [])]
        if datos["ruta"]:
            celdas += datos["ruta"]["camino"]
        self.mapa.encuadrar(celdas)
        self.mensaje = f"Visualizando cómo se armó {id_wave} paso a paso."

    def _a_armado_paso(self, delta):
        self.armado["auto"] = False
        self._mover_armado(delta)

    def _a_armado_wave(self, delta):
        waves = [w["id"] for w in self.sim.resumen_waves()]
        i = waves.index(self.armado["datos"]["wave"])
        self._a_ver_armado(waves[(i + delta) % len(waves)])

    def _a_armado_auto(self):
        self.armado["auto"] = not self.armado["auto"]
        if self.armado["auto"] and self.progreso_armado() >= 1.0:
            if self.armado["paso"] + 1 >= len(self.armado["datos"]["pasos"]):
                self.armado["paso"] = -1
            self._mover_armado(1)

    def _a_salir_armado(self):
        if self.armado and self.armado["volver_a_waves"]:
            self.dialogo = "waves"
        self.armado = None
        self.mensaje = "Fin de la explicación del armado."

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
            texto += f", sentido {sentido}" + (
                " (intersección)" if celda in self.sim.intersecciones else ""
            )
        elif elemento:
            texto += f" {elemento}"
        productos = [p for p in self.sim.productos() if (p["x"], p["y"]) == celda]
        if productos:
            texto += " · " + ", ".join(
                f"z={p['z']}: {p['id']} {p['nombre']} (stock {p['stock']})"
                for p in productos
            )
        self.mensaje = texto

    def a_lienzo(self, pos):
        return (
            int((pos[0] - self.desplazamiento[0]) / self.escala),
            int((pos[1] - self.desplazamiento[1]) / self.escala),
        )

    # ------------------------------------------------------------------
    # Pantallas y bucle principal
    # ------------------------------------------------------------------
    def pantalla_inicio(self):
        self.texto("Inicio · Escenarios", 30, 76, 26, negrita=True)
        self.caja(30, 130, 420, 450)
        self.texto("Crear escenario", 52, 152, 22, negrita=True)
        self.parrafo(
            "Generá un almacén automáticamente o importá un JSON.", 52, 192, 375, 17
        )
        self.boton("Crear escenario", 52, 262, 375, "crear", marcado=True)
        self.texto("Generador automático", 52, 330, 19, negrita=True)
        self.parrafo(
            "Determinista: mismos parámetros producen siempre el mismo almacén.",
            52,
            360,
            375,
            16,
            limite=4,
        )
        self.texto("Desde archivo", 52, 455, 19, negrita=True)
        self.parrafo(
            "También podés arrastrar un JSON sobre la ventana.", 52, 485, 375, 16
        )
        if self.sim:
            self.boton("Volver a la simulación", 52, 600, 375, "volver")

        self.texto("Biblioteca", 490, 140, 22, negrita=True)
        self.texto("Escenarios y sesiones guardadas", 490, 172, 16, GRIS)
        archivos = self.biblioteca.archivos()
        por_pagina = 10
        self.pag_biblioteca = min(
            self.pag_biblioteca, max(0, (len(archivos) - 1) // por_pagina)
        )
        for i, ruta in enumerate(
            archivos[self.pag_biblioteca * por_pagina :][:por_pagina]
        ):
            y = 205 + i * 62
            self.caja(490, y, 1000, 54)
            etiqueta = "SESIÓN" if ruta.name.startswith("sesion_") else "ESCENARIO"
            self.texto(
                etiqueta, 506, y + 18, 13, AZUL if etiqueta == "SESIÓN" else GRIS, True
            )
            self.texto(ruta.stem, 600, y + 16, 17, max_ancho=560)
            self.boton("Abrir", 1210, y + 10, 130, ("abrir", ruta))
            self.boton("Eliminar", 1352, y + 10, 120, ("eliminar", ruta))
        self.paginador("pag_biblioteca", len(archivos), por_pagina, 1330, 832)

    def boton_armado(self, x, y, ancho):
        m = self.sim
        configurada = m.config["estrategia_waves"]
        gestor = m.estado.gestor_waves if m.waves else None
        efectiva = gestor.estrategia_armado if gestor else configurada
        armado = OPCIONES_ESTRATEGIA_ARMADO.get(efectiva, efectiva).split(" (", 1)[0]
        if configurada == "AUTO":
            armado = f"{armado} (auto)" if gestor else "Automática"
        etiqueta = f"Armado de waves: {armado}"
        if m.waves_iniciadas:
            self.caja(x, y, ancho, 34, AZUL_CLARO)
            self.texto(etiqueta, x + 12, y + 8, 16, max_ancho=ancho - 24)
        else:
            self.boton(etiqueta, x, y, ancho, "cambiar_armado")

    def barra_simulacion(self):
        m = self.sim
        self.texto(self.nombre, 220, 26, 17, GRIS, max_ancho=200)
        self.boton(
            "Estrategia de recorrido seleccionada: " + NOMBRE_ESTRATEGIA[m.estrategia],
            430,
            18,
            414,
            "estrategia",
        )
        self.boton_armado(852, 18, 342)
        self.boton("Guardar sesión", 1210, 18, 150, "guardar", not self.sesion_guardada)
        self.boton("Inicio", 1370, 18, 120, "inicio")
        hay_waves = bool(m.waves)
        iniciadas = m.waves_iniciadas
        fila1 = [
            ("Nuevo pedido", 140, "nuevo_pedido", not iniciadas),
            ("Capacidad de waves", 175, "config", not iniciadas),
            ("Generar waves", 150, "generar_waves", not iniciadas),
            ("Seleccionar waves", 170, "elegir_waves", hay_waves),
            ("Comparar estrategias", 195, "comparar", hay_waves),
            (
                "Exploración: " + ("sí" if self.ver_exploracion else "no"),
                160,
                "exploracion",
                True,
            ),
            ("Comparar armado", 172, "comparar_armado", True),
        ]
        x = 20
        for etiqueta, w, accion, habilitado in fila1:
            self.boton(etiqueta, x, 62, w, accion, habilitado)
            x += w + 8
        en_curso = m.en_curso
        fila2 = [
            (
                "Iniciar", 105, "iniciar",
                hay_waves and not self.reproduciendo and not self.puede_continuar,
            ),
            ("Pausar", 105, "pausar", self.reproduciendo),
            ("Continuar", 115, "continuar", self.puede_continuar),
            ("Paso adelante >", 155, "adelante", en_curso),
            ("< Paso atrás", 140, "atras", bool(m.historial)),
            ("Reiniciar", 115, "reiniciar", m.tanda_actual is not None),
            ("Velocidad " + VELOCIDADES[self.velocidad][1], 140, "velocidad", True),
            (
                "Ver paneles" if self.mapa_ampliado else "Ampliar mapa",
                150,
                "ampliar",
                True,
            ),
        ]
        x = 20
        for etiqueta, w, accion, habilitado in fila2:
            self.boton(etiqueta, x, 104, w, accion, habilitado)
            x += w + 8
        if self.sesion_guardada:
            self.texto("Sesión guardada correctamente", x + 12, 112, 16, VERDE, True)
        tanda = m.tanda_actual
        estado = (
            "reproduciendo"
            if self.reproduciendo
            else "pausado" if en_curso else "sin pickers activos"
        )
        linea = f"Turno {m.estado.paso} · {estado}"
        if tanda:
            hechas = sum(
                1
                for w in m.resumen_waves()
                if w["id"] in tanda["waves"] and w["estado"] == "FINALIZADA"
            )
            linea += (
                f" · Tanda {tanda['numero']} ({NOMBRE_ESTRATEGIA[tanda['estrategia']]}): "
                f"{len(tanda['waves'])} waves asignadas, {hechas} terminadas"
            )
        self.texto(
            linea, 20, 152, 17, AZUL if self.reproduciendo else TINTA, max_ancho=1470
        )

    def pantalla_simulacion(self):
        self.barra_simulacion()
        ancho = 1482 if self.mapa_ampliado else 744
        self.mapa.area = pygame.Rect(20, 186, ancho - 4, 690)
        self.caja(18, 184, ancho, 694)
        self.mapa.dibujar()
        self.mapa.leyenda(20, 884)
        if not self.mapa_ampliado:
            self.panel_derecho()

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
        if self.armado and not self.dialogo:
            if self.armado["auto"] and self.progreso_armado() >= 1.0:
                if self.armado["paso"] + 1 < len(self.armado["datos"]["pasos"]):
                    self._mover_armado(1)
                else:
                    self.armado["auto"] = False
            return
        if not (self.reproduciendo and self.sim and not self.dialogo):
            return
        self.acumulado += dt
        intervalo = VELOCIDADES[self.velocidad][0]
        pasos = 0
        while self.acumulado >= intervalo and pasos < 10:
            self.acumulado -= intervalo
            pasos += 1
            try:
                avanzo = self.mover(self.sim.avanzar, intervalo)
                if not avanzo:
                    self.reproduciendo = False
                    self.mensaje = "Simulación finalizada."
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
