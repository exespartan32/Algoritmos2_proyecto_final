"""Orquestador de estado de la simulación interactiva: avance por turnos, historial y sesiones."""

from copy import deepcopy
import json
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.controllers.evaluador_estrategias import EvaluadorEstrategias
from BackEnd.controllers.path_finding import Pathfinding, RutaResultado
from BackEnd.controllers.turn_collision_manager import TurnAndCollisionManager
from BackEnd.controllers.wave_manager import (
    ESTRATEGIAS_ARMADO,
    OPCIONES_ESTRATEGIA_ARMADO,
    WaveManager,
)
from BackEnd.enums.enums import EstadoPedido, EstadoWave, EstrategiaRuteo
from BackEnd.models.entities import (
    DetallePedido,
    ListaDeInmutables,
    Pedido,
    TareaWavePicker,
)
from BackEnd.utils.graph_builder import GraphBuilder

Coord = Tuple[int, int]

ESTRATEGIAS = {
    "ORDEN": EstrategiaRuteo.ORDEN_PEDIDOS_DIJKSTRA,
    "CERCANIA": EstrategiaRuteo.CERCANIA_DIJKSTRA_MULTIDESTINO,
}
NOMBRE_ESTRATEGIA = {"ORDEN": "Orden de pedidos", "CERCANIA": "Cercanía"}
VERSION_SESION = 2
MAX_PASOS_TANDA = 5000
INTERVALO_COPIA = 20
CELDAS_POR_TURNO_BUSQUEDA = 12
TURNOS_BUSQUEDA_MIN, TURNOS_BUSQUEDA_MAX = 4, 30


class Plan(dict):
    """Ruta planificada de un picker. Es inmutable una vez creada y se comparte en el historial."""

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


class EstadoSimulacion:
    """Agrupa todo el estado mutable de un turno de simulación."""

    def __init__(self, warehouse) -> None:
        self.warehouse = warehouse
        self.gestor_waves: Optional[WaveManager] = None
        self.colisiones = TurnAndCollisionManager(max_turnos_bloqueo_recalculo=2)
        self.paso = 0
        self.tandas: List[Dict[str, Any]] = []
        self.por_recoger: Dict[str, Dict[Coord, List[Tuple[str, int, str]]]] = {}
        self.planes: Dict[str, Dict[str, Any]] = {}
        self.eventos: List[str] = ListaDeInmutables()
        self.entregas: List[Dict[str, Any]] = []
        self.pasos_movidos: Dict[str, int] = {}
        self.esperas: Dict[str, int] = {}
        self.siguiente_pedido = 1
        self.mirando: Dict[str, Coord] = {}


class Simulador:
    def __init__(self, datos: Dict[str, Any]) -> None:
        datos = deepcopy(datos)
        sesion = datos.pop("_sesion", None)
        datos.pop("_interfaz", None)
        self.datos_base = datos
        cfg = datos.get("configuracion", {})
        self.config = {
            "wave_max_pedidos": int(cfg.get("wave_max_pedidos", 3)),
            "wave_max_productos": int(cfg.get("wave_max_productos", 15)),
            "max_pickers_por_wave": int(cfg.get("max_pickers_por_wave", 2)),
            "estrategia_waves": str(cfg.get("estrategia_waves", "CERCANIA")),
        }
        self.estrategia = "CERCANIA"
        self.pickers_por_wave = 1
        self.acciones: List[List[Any]] = []
        self.historial: List[Optional[EstadoSimulacion]] = []
        self._inicio_tanda: Dict[int, Tuple[EstadoSimulacion, EstadoSimulacion]] = {}
        self._pre_waves: Optional[EstadoSimulacion] = None
        self.tiempo_waves_ms: float = 0.0
        self.estrategia_waves_efectiva: str = self.config["estrategia_waves"]
        self.ultima_comparacion_armado: Optional[Dict[str, Dict[str, Any]]] = None

        warehouse = GraphBuilder.construir_warehouse_desde_dict(datos)
        for pedido in warehouse.pedidos.values():
            if pedido.estado in (EstadoPedido.EN_WAVE, EstadoPedido.EN_PREPARACION):
                pedido.estado = EstadoPedido.PENDIENTE
        self.advertencias = list(warehouse.advertencias)
        self.estado = EstadoSimulacion(warehouse)
        self.estado.siguiente_pedido = self._numero_siguiente_pedido(warehouse)
        self._preparar_datos_fijos(warehouse)

        if sesion:
            self._reproducir(sesion)

    # ------------------------------------------------------------------
    # Datos estáticos del almacén y precomputación de distancias
    # ------------------------------------------------------------------
    def _preparar_datos_fijos(self, wh) -> None:
        grafo = wh.grafo_pasillos
        self.ancho, self.alto = wh.ancho_x, wh.largo_y
        self.celdas: Dict[Coord, Tuple[str, str, Optional[str]]] = {}
        for x in range(self.ancho):
            for y in range(self.alto):
                celda = wh.obtener_celda(x, y)
                sentido = getattr(celda, "sentido", None)
                self.celdas[(x, y)] = (
                    celda.tipo.value,
                    sentido.value if sentido else "AMBOS",
                    celda.elemento_id,
                )

        vecinos_no_dirigidos: Dict[Coord, set] = {c: set() for c in grafo.nodos}
        for origen, destinos in grafo.lista_adyacencia.items():
            for destino in destinos:
                vecinos_no_dirigidos[origen].add(destino)
                vecinos_no_dirigidos[destino].add(origen)

        self.intersecciones = set()
        for (x, y), vecinos in vecinos_no_dirigidos.items():
            horizontal = (x - 1, y) in vecinos or (x + 1, y) in vecinos
            vertical = (x, y - 1) in vecinos or (x, y + 1) in vecinos
            if horizontal and vertical and len(vecinos) >= 3:
                ids = {grafo.nodos[v].pasillo_id for v in vecinos} | {
                    grafo.nodos[(x, y)].pasillo_id
                }
                if len(ids - {None}) >= 2:
                    self.intersecciones.add((x, y))

        self.n_nodos = len(grafo.nodos)
        self.n_aristas = sum(len(v) for v in grafo.lista_adyacencia.values())

        inicio = time.perf_counter()
        coords = {p.coordenadas_xy for p in wh.catalogo_productos.values()}
        self.matriz_distancias = Pathfinding.construir_matriz_distancias_productos(
            coords, grafo, wh
        )
        self.tiempo_matriz_ms = (time.perf_counter() - inicio) * 1000
        self._inmutables = [
            grafo.nodos,
            grafo.lista_adyacencia,
            wh.obstaculos,
            wh.racks,
            wh.puertas,
            wh.acceso_rack_a_pasillo,
            wh.accesos_rack_a_pasillo,
            wh.accesos_zona_a_pasillo,
            wh.warehouse_raw,
            self.matriz_distancias,
        ]

    @staticmethod
    def _numero_siguiente_pedido(wh) -> int:
        numeros = [
            int(m.group(1)) for pid in wh.pedidos if (m := re.search(r"(\d+)$", pid))
        ]
        return max(numeros, default=0) + 1

    def _copiar(self, estado: EstadoSimulacion) -> EstadoSimulacion:
        memo = {id(obj): obj for obj in self._inmutables}
        return deepcopy(estado, memo)

    # ------------------------------------------------------------------
    # Propiedades de consulta rápida
    # ------------------------------------------------------------------
    @property
    def warehouse(self):
        return self.estado.warehouse

    @property
    def waves(self):
        gestor = self.estado.gestor_waves
        return list(gestor.waves_creadas) if gestor else []

    @property
    def tanda_actual(self) -> Optional[Dict[str, Any]]:
        return self.estado.tandas[-1] if self.estado.tandas else None

    def pickers_activos(self) -> List[Any]:
        return [
            p
            for p in self.warehouse.pickers
            if p.id_wave_actual is not None or p.ruta_asignada
        ]

    @property
    def en_curso(self) -> bool:
        return bool(self.pickers_activos())

    @property
    def waves_iniciadas(self) -> bool:
        return any(w.estado != EstadoWave.PENDIENTE for w in self.waves)

    def _registrar(self, nombre: str, *args) -> None:
        if nombre == "avanzar" and self.acciones and self.acciones[-1][0] == "avanzar":
            self.acciones[-1][1][0] += 1
        else:
            self.acciones.append([nombre, list(args)])

    def _evento(self, texto: str) -> None:
        self.estado.eventos.append(f"[t={self.estado.paso}] {texto}")

    # ------------------------------------------------------------------
    # Configuración y alta de pedidos
    # ------------------------------------------------------------------
    def _volver_antes_de_waves(self) -> None:
        if self.waves_iniciadas:
            raise ValueError(
                "Ya hay waves en ejecución o terminadas. Esto solo se puede modificar antes de iniciar waves."
            )
        if self._pre_waves is not None:
            self.estado = self._copiar(self._pre_waves)
            self._pre_waves = None
            self.historial.clear()

    def configurar(
        self,
        wave_max_pedidos: int,
        wave_max_productos: int,
        max_pickers_por_wave: int,
        estrategia_waves: Optional[str] = None,
    ) -> None:
        valores = [
            int(wave_max_pedidos),
            int(wave_max_productos),
            int(max_pickers_por_wave),
        ]
        if (
            not 1 <= valores[0] <= 50
            or not 1 <= valores[1] <= 500
            or not 1 <= valores[2] <= 10
        ):
            raise ValueError(
                "Rangos válidos: pedidos por wave 1-50, productos por wave 1-500, pickers por wave 1-10."
            )
        estrategia_waves = estrategia_waves or self.config["estrategia_waves"]
        if estrategia_waves not in OPCIONES_ESTRATEGIA_ARMADO:
            raise ValueError("Estrategia de armado desconocida.")
        self._volver_antes_de_waves()
        self.config.update(
            wave_max_pedidos=valores[0],
            wave_max_productos=valores[1],
            max_pickers_por_wave=valores[2],
            estrategia_waves=estrategia_waves,
        )
        self._registrar("configurar", *valores, estrategia_waves)

    @staticmethod
    def interpretar_items(texto: str) -> List[Tuple[str, int]]:
        items: Dict[str, int] = {}
        for parte in re.split(r"[,;]+", texto):
            parte = parte.strip()
            if not parte:
                continue
            m = re.fullmatch(r"([A-Za-z0-9_\-]+?)\s*(?:[xX\*]\s*(\d+))?", parte)
            if not m:
                raise ValueError(
                    f"No entiendo '{parte}'. Usá el formato P001x2, P004x1."
                )
            pid, cant = m.group(1).upper(), int(m.group(2) or 1)
            if cant < 1:
                raise ValueError("Las cantidades deben ser mayores que 0.")
            items[pid] = items.get(pid, 0) + cant
        if not items:
            raise ValueError("El pedido no tiene productos.")
        return list(items.items())

    def agregar_pedido(self, prioridad: int, items: List[Tuple[str, int]]) -> str:
        prioridad = int(prioridad)
        if not 1 <= prioridad <= 5:
            raise ValueError("La prioridad va de 1 a 5.")
        wh = self.warehouse
        for pid, cant in items:
            if wh.buscar_producto_O1(pid) is None:
                raise ValueError(f"El producto {pid} no existe.")
            if int(cant) < 1:
                raise ValueError("Las cantidades deben ser mayores que 0.")
        self._volver_antes_de_waves()
        wh = self.warehouse
        nuevo_id = f"PED_{self.estado.siguiente_pedido:02d}"
        while nuevo_id in wh.pedidos:
            self.estado.siguiente_pedido += 1
            nuevo_id = f"PED_{self.estado.siguiente_pedido:02d}"
        self.estado.siguiente_pedido += 1
        wh.pedidos[nuevo_id] = Pedido(
            id_pedido=nuevo_id,
            prioridad=prioridad,
            items=[DetallePedido(str(pid), int(c)) for pid, c in items],
        )
        self._evento(f"Pedido {nuevo_id} creado (prioridad {prioridad}).")
        self._registrar("agregar_pedido", prioridad, [list(i) for i in items])
        return nuevo_id

    # ------------------------------------------------------------------
    # Generación y asignación de waves
    # ------------------------------------------------------------------
    def generar_waves(
        self,
        auto_seleccionar_mejor: bool = False,
        estrategia_guardada: Optional[str] = None,
    ) -> List[Any]:
        self._volver_antes_de_waves()
        self._pre_waves = self._copiar(self.estado)
        wh = self.warehouse

        self.ultima_comparacion_armado = None
        estrategia_elegida = estrategia_guardada or self.config["estrategia_waves"]
        if (
            estrategia_guardada is not None
            and estrategia_guardada not in ESTRATEGIAS_ARMADO
        ):
            raise ValueError("Estrategia guardada inválida.")
        if estrategia_guardada is None and (
            auto_seleccionar_mejor or estrategia_elegida == "AUTO"
        ):
            mejor_clave, comp = EvaluadorEstrategias.elegir_mejor_estrategia_armado(
                self
            )
            self.ultima_comparacion_armado = comp
            estrategia_elegida = mejor_clave
            _, motivo = EvaluadorEstrategias.clasificar_armado(comp)
            self._evento(
                f"Armado automático: {ESTRATEGIAS_ARMADO[mejor_clave]} por {motivo}."
            )

        self.estrategia_waves_efectiva = estrategia_elegida

        gestor = WaveManager(
            wave_max_pedidos=self.config["wave_max_pedidos"],
            wave_max_productos=self.config["wave_max_productos"],
            max_pickers_por_wave=self.config["max_pickers_por_wave"],
            proveedor_distancias=self.matriz_distancias,
            estrategia_armado=estrategia_elegida,
        )
        inicio = time.perf_counter()
        waves = gestor.generar_waves(wh, proveedor_distancias=self.matriz_distancias)
        self.tiempo_waves_ms = (time.perf_counter() - inicio) * 1000
        self.estado.gestor_waves = gestor
        self._evento(
            f"{len(waves)} waves generadas con {ESTRATEGIAS_ARMADO[estrategia_elegida]} "
            f"en {self.tiempo_waves_ms:.2f} ms "
            f"(máx. {self.config['wave_max_pedidos']} pedidos y "
            f"{self.config['wave_max_productos']} productos por wave)."
        )
        for error in gestor.errores_validacion:
            self._evento(error)
        if not waves:
            raise ValueError(
                "No se pudo armar ninguna wave. "
                + ("; ".join(gestor.errores_validacion) or "No hay pedidos pendientes.")
            )
        self._registrar("generar_waves", False, estrategia_elegida)
        return waves

    def _construir_plan(
        self,
        warehouse,
        wave,
        picker,
        tarea: TareaWavePicker,
        estrategia: str,
        res: Optional[RutaResultado] = None,
    ) -> Plan:
        """Arma el diccionario inmutable Plan a partir del resultado de Dijkstra."""
        grafo = warehouse.grafo_pasillos
        destinos = list(tarea.destinos_recoleccion_pasillo)
        if res is None:
            origen = (
                tarea.ruta_calculada[0]
                if tarea.ruta_calculada
                else picker.posicion_actual
            )
            if estrategia == "ORDEN":
                res = Pathfinding.calcular_estrategia_orden_pedidos(
                    grafo, origen, destinos, tarea.destino_despacho_pasillo, warehouse
                )
            else:
                res = Pathfinding.calcular_estrategia_cercania_multidestino(
                    grafo, origen, destinos, tarea.destino_despacho_pasillo, warehouse
                )

        orden_visita: List[Coord] = []
        pendientes = set(destinos)
        for celda in res.camino_completo:
            if celda in pendientes:
                orden_visita.append(celda)
                pendientes.discard(celda)

        return Plan(
            {
                "wave": wave.id_wave,
                "estrategia": estrategia,
                "ruta": list(res.camino_completo),
                "explorados": list(res.nodos_explorados),
                "destinos": orden_visita,
                "despacho": tarea.destino_despacho_pasillo,
                "distancia": res.distancia_total,
                "aristas": res.aristas_recorridas,
                "nodos_visitados": len(set(res.camino_completo)),
                "nodos_explorados": len(res.nodos_explorados),
                "expansiones": res.expansiones,
                "tiempo_ms": round(res.tiempo_ejecucion_ms, 4),
                "inalcanzables": list(res.destinos_inalcanzables),
                "orden_exploracion": list(res.orden_exploracion),
            }
        )

    def iniciar_waves(
        self,
        ids_waves: List[str],
        estrategia: Optional[str] = None,
        pickers_por_wave: Optional[int] = None,
    ) -> Dict[str, Any]:
        gestor = self.estado.gestor_waves
        if gestor is None:
            raise ValueError("Primero generá las waves.")
        estrategia = estrategia or self.estrategia
        if estrategia not in ESTRATEGIAS:
            raise ValueError("Estrategia desconocida.")
        en_espera = {w for t in self.estado.tandas for w in t["en_espera"]}
        pendientes = [
            w
            for w in dict.fromkeys(ids_waves)
            if w in gestor.waves_por_id
            and gestor.waves_por_id[w].estado == EstadoWave.PENDIENTE
            and w not in en_espera
        ]
        if not pendientes:
            raise ValueError("Elegí al menos una wave pendiente.")
        if not gestor.obtener_pickers_libres(self.warehouse.pickers):
            raise ValueError("No hay pickers libres. Esperá a que terminen su wave.")
        if pickers_por_wave is not None and not 1 <= int(pickers_por_wave) <= 10:
            raise ValueError("Pickers por wave: de 1 a 10.")

        antes = self._copiar(self.estado)
        self.historial.append(antes)
        tanda = {
            "numero": len(self.estado.tandas) + 1,
            "waves": [],
            "en_espera": [],
            "estrategia": estrategia,
            "paso_inicio": self.estado.paso,
            "paso_fin": None,
            "pickers_por_wave": int(pickers_por_wave or self.pickers_por_wave),
            "planes": [],
        }
        self._asignar(tanda, pendientes)
        if not tanda["waves"]:
            self.estado = self.historial.pop()
            raise ValueError(
                "Ninguna wave pudo asignarse: no hay pickers libres con capacidad suficiente."
            )
        for wid in tanda["en_espera"]:
            self._evento(f"{wid} queda en espera hasta que se libere un picker.")
        self.estado.tandas.append(tanda)
        self._inicio_tanda[len(self.estado.tandas) - 1] = (
            antes,
            self._copiar(self.estado),
        )
        self._registrar(
            "iniciar_waves", list(ids_waves), estrategia, tanda["pickers_por_wave"]
        )
        return tanda

    def _asignar(self, tanda: Dict[str, Any], ids: List[str]) -> None:
        gestor = self.estado.gestor_waves
        wh = self.warehouse
        estrategia = tanda["estrategia"]
        posiciones = {p.id_picker: p.posicion_actual for p in wh.pickers}
        resultado = gestor.asignar_y_ejecutar_waves_seleccionadas(
            ids, wh, ESTRATEGIAS[estrategia], tanda.get("pickers_por_wave", 1)
        )
        tanda["en_espera"] = list(resultado["waves_sin_picker_disponible"])
        pickers = {p.id_picker: p for p in wh.pickers}

        for asig in resultado["asignaciones"]:
            wave = gestor.waves_por_id[asig["id_wave"]]
            tanda["waves"].append(wave.id_wave)
            resultados_ruta = asig.get("resultados_ruta_por_picker", {})

            for pid in asig["ids_pickers"]:
                picker = pickers[pid]
                tarea_ruta = asig["rutas_por_picker"][pid]
                res_precalculado = resultados_ruta.get(pid)
                tarea = TareaWavePicker(
                    id_wave=wave.id_wave,
                    id_zona_despacho=wave.id_zona_despacho,
                    destino_despacho_pasillo=(
                        tarea_ruta[-1] if tarea_ruta else posiciones[pid]
                    ),
                    pedidos_asignados=wave.pedidos_por_picker.get(pid, []),
                    destinos_recoleccion_pasillo=[
                        Pathfinding.obtener_celda_acceso_pasillo(
                            c, wh.grafo_pasillos, wh
                        )
                        for c in wave.destinos_xy_por_picker.get(pid, [])
                    ],
                    peso_lote_kg=wave.peso_por_picker.get(pid, 0.0),
                    ruta_calculada=tarea_ruta,
                    resultado_ruta=res_precalculado,
                )
                plan = self._construir_plan(
                    wh, wave, picker, tarea, estrategia, res=res_precalculado
                )
                plan["ruta"] = list(tarea_ruta)
                plan["pedidos"] = list(tarea.pedidos_asignados)
                plan["distancia_inicial"] = asig["distancias_picker_a_wave"].get(pid, 0)

                celdas = len(set(plan["orden_exploracion"]))
                turnos = max(
                    TURNOS_BUSQUEDA_MIN,
                    min(TURNOS_BUSQUEDA_MAX, -(-celdas // CELDAS_POR_TURNO_BUSQUEDA)),
                )
                plan["turnos_busqueda"] = turnos
                picker.ruta_asignada[0:0] = [picker.posicion_actual] * turnos
                picker.turnos_busqueda = turnos
                self.estado.planes[pid] = plan

                resumen = {
                    k: plan[k]
                    for k in (
                        "wave",
                        "distancia",
                        "aristas",
                        "nodos_visitados",
                        "nodos_explorados",
                        "expansiones",
                        "tiempo_ms",
                    )
                }
                resumen["picker"] = pid
                tanda["planes"].append(resumen)

                por_celda: Dict[Coord, List[Tuple[str, int, str]]] = {}
                for id_ped in tarea.pedidos_asignados:
                    pedido = wh.buscar_pedido_O1(id_ped)
                    pedido.estado = EstadoPedido.EN_PREPARACION
                    for item in pedido.items:
                        prod = wh.buscar_producto_O1(item.producto_id)
                        celda = Pathfinding.obtener_celda_acceso_pasillo(
                            prod.coordenadas_xy, wh.grafo_pasillos, wh
                        )
                        por_celda.setdefault(celda, []).append(
                            (item.producto_id, item.cantidad, id_ped)
                        )
                self.estado.por_recoger[pid] = por_celda
                picker.productos_recogidos = {}
                self.estado.pasos_movidos.setdefault(pid, 0)
                self.estado.esperas.setdefault(pid, 0)
                self._evento(
                    f"{pid} toma {wave.id_wave} ({NOMBRE_ESTRATEGIA[estrategia]}): "
                    f"{plan['distancia']} pasos planificados, {plan['nodos_explorados']} nodos explorados."
                )
                self._recoger(picker)

    def cambiar_estrategia(self, estrategia: str) -> bool:
        if estrategia not in ESTRATEGIAS:
            raise ValueError("Estrategia desconocida.")
        self.estrategia = estrategia
        tanda = self.tanda_actual
        indice = len(self.estado.tandas) - 1
        if (
            tanda is not None
            and tanda["estrategia"] != estrategia
            and tanda["paso_inicio"] == self.estado.paso
            and indice in self._inicio_tanda
        ):
            ids = tanda["waves"] + tanda["en_espera"]
            self.estado = self._copiar(self._inicio_tanda[indice][0])
            del self._inicio_tanda[indice]
            if self.historial:
                self.historial.pop()
            self._registrar("cambiar_estrategia", estrategia)
            self.iniciar_waves(ids, estrategia, tanda.get("pickers_por_wave", 1))
            self.acciones.pop()
            return True
        self._registrar("cambiar_estrategia", estrategia)
        return False

    # ------------------------------------------------------------------
    # Avance paso a paso e historial
    # ------------------------------------------------------------------
    def _recoger(self, picker) -> None:
        pendientes = self.estado.por_recoger.get(picker.id_picker)
        if not pendientes:
            return
        items = pendientes.pop(picker.posicion_actual, None)
        if not items:
            return
        for prod_id, cant, id_ped in items:
            picker.productos_recogidos[prod_id] = (
                picker.productos_recogidos.get(prod_id, 0) + cant
            )
            prod = self.warehouse.buscar_producto_O1(prod_id)
            self.estado.mirando[picker.id_picker] = prod.coordenadas_xy
            self._evento(
                f"{picker.id_picker} recoge {cant}× {prod_id} ({prod.nombre}) "
                f"del nivel z={prod.z} para {id_ped}."
            )

    def avanzar(self, guardar_historial: bool = True) -> bool:
        if not self.en_curso:
            return False
        if guardar_historial:
            copia = self.estado.paso % INTERVALO_COPIA == 0 or not self.historial
            self.historial.append(self._copiar(self.estado) if copia else None)

        est = self.estado
        wh = est.warehouse
        antes = {p.id_picker: (p.posicion_actual, p.id_wave_actual) for p in wh.pickers}
        trabajando = {
            p.id_picker
            for p in wh.pickers
            if p.turnos_pausa > 0
            or p.turnos_busqueda > 0
            or (p.id_wave_actual is not None and not p.ruta_asignada)
        }

        est.colisiones.avanzar_un_turno_simulacion(
            pickers=wh.pickers,
            paso_actual=est.paso,
            grafo=wh.grafo_pasillos,
            gestor_waves=est.gestor_waves,
            catalogo=wh,
        )
        est.paso += 1

        alguien_descargo = False
        for p in wh.pickers:
            pos_antes, wave_antes = antes[p.id_picker]
            if wave_antes is None and p.id_wave_actual is None:
                continue
            if p.posicion_actual != pos_antes:
                est.pasos_movidos[p.id_picker] = (
                    est.pasos_movidos.get(p.id_picker, 0) + 1
                )
            elif wave_antes is not None and p.id_picker not in trabajando:
                est.esperas[p.id_picker] = est.esperas.get(p.id_picker, 0) + 1
            self._recoger(p)
            if wave_antes is not None and p.id_wave_actual is None:
                self._entregar(p, wave_antes)
                alguien_descargo = True

        est.eventos.extend(
            f"[t={est.paso}] {e}" for e in self._eventos_colision_nuevos()
        )

        tanda = self.tanda_actual
        if tanda and tanda["en_espera"] and alguien_descargo and est.gestor_waves:
            esperando = list(tanda["en_espera"])
            self._asignar(tanda, esperando)
            for wid in esperando:
                if wid not in tanda["en_espera"] and wid in tanda["waves"]:
                    self._evento(f"{wid} sale de la espera: se liberó un picker.")

        for tanda_iter in est.tandas:
            if (
                tanda_iter["paso_fin"] is None
                and not tanda_iter["en_espera"]
                and all(
                    est.gestor_waves.waves_por_id[w].estado == EstadoWave.FINALIZADA
                    for w in tanda_iter["waves"]
                )
            ):
                tanda_iter["paso_fin"] = est.paso
                self._evento(
                    f"Tanda {tanda_iter['numero']} terminada en {est.paso - tanda_iter['paso_inicio']} turnos."
                )

        if guardar_historial:
            self._registrar("avanzar", 1)
        return True

    def _eventos_colision_nuevos(self) -> List[str]:
        col = self.estado.colisiones
        vistos = getattr(col, "_eventos_informados", 0)
        nuevos = col.eventos_colision[vistos:]
        col._eventos_informados = len(col.eventos_colision)
        return nuevos

    def _entregar(self, picker, id_wave: str) -> None:
        est = self.estado
        faltantes = est.por_recoger.pop(picker.id_picker, {})
        entregado = dict(picker.productos_recogidos)
        est.entregas.append(
            {
                "picker": picker.id_picker,
                "wave": id_wave,
                "productos": entregado,
                "paso": est.paso,
            }
        )
        zona = est.gestor_waves.waves_por_id[id_wave].id_zona_despacho
        unidades = sum(entregado.values())
        self._evento(
            f"{picker.id_picker} descarga {unidades} unidades de {id_wave} en {zona}."
        )
        if faltantes:
            perdidos = [f"{p}×{c}" for items in faltantes.values() for p, c, _ in items]
            self._evento(
                f"ATENCIÓN: {picker.id_picker} no pudo recoger {', '.join(perdidos)}."
            )
        picker.productos_recogidos = {}
        wave = est.gestor_waves.waves_por_id[id_wave]
        if wave.estado == EstadoWave.FINALIZADA:
            self._evento(
                f"{id_wave} FINALIZADA: pedidos {', '.join(p.id_pedido for p in wave.pedidos)} PREPARADOS."
            )

    def avanzar_hasta_terminar(self, max_pasos: int = MAX_PASOS_TANDA) -> int:
        pasos = 0
        while pasos < max_pasos and self.avanzar():
            pasos += 1
        return pasos

    def retroceder(self) -> bool:
        if not self.historial:
            return False
        entrada = self.historial.pop()
        if entrada is not None:
            self.estado = entrada
        else:
            objetivo = self.estado.paso - 1
            base = next(e for e in reversed(self.historial) if e is not None)
            self.estado = self._copiar(base)
            while self.estado.paso < objetivo and self.avanzar(guardar_historial=False):
                pass
        for indice in [i for i in self._inicio_tanda if i >= len(self.estado.tandas)]:
            del self._inicio_tanda[indice]
        self._registrar("retroceder")
        return True

    def reiniciar(self) -> bool:
        indice = len(self.estado.tandas) - 1
        if indice not in self._inicio_tanda:
            return False
        antes, despues = self._inicio_tanda[indice]
        while self.historial and (
            self.historial[-1] is None or len(self.historial[-1].tandas) > indice
        ):
            self.historial.pop()
        if not self.historial:
            self.historial.append(self._copiar(antes))
        self.estado = self._copiar(despues)
        self._registrar("reiniciar")
        return True

    # ------------------------------------------------------------------
    # Comparación de estrategias y explicación del armado (delegadas)
    # ------------------------------------------------------------------
    def comparar_estrategias(
        self,
        ids_waves: Optional[List[str]] = None,
        pickers_por_wave: Optional[int] = None,
    ) -> Dict[str, Dict[str, Any]]:
        return EvaluadorEstrategias.comparar_estrategias(
            self, ids_waves, pickers_por_wave
        )

    def explicar_armado(self, id_wave: str) -> Dict[str, Any]:
        return EvaluadorEstrategias.explicar_armado(self, id_wave)

    def comparar_armado(self) -> Dict[str, Dict[str, Any]]:
        return EvaluadorEstrategias.comparar_armado(self)

    # ------------------------------------------------------------------
    # Resúmenes para la interfaz gráfica
    # ------------------------------------------------------------------
    def productos(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": p.id_producto,
                "nombre": p.nombre,
                "rack": p.rack_id,
                "x": p.x,
                "y": p.y,
                "z": p.z,
                "stock": p.cantidad_disponible,
                "peso": p.peso_kg,
            }
            for p in self.warehouse.obtener_todos_los_productos()
        ]

    def pedidos(self) -> List[Dict[str, Any]]:
        wave_de = {}
        for w in self.waves:
            for ped in w.pedidos:
                wave_de[ped.id_pedido] = w.id_wave
        return [
            {
                "id": p.id_pedido,
                "prioridad": p.prioridad,
                "estado": p.estado.value,
                "items": [(i.producto_id, i.cantidad) for i in p.items],
                "wave": wave_de.get(p.id_pedido),
            }
            for p in self.warehouse.obtener_todos_los_pedidos()
        ]

    def resumen_waves(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": w.id_wave,
                "estado": w.estado.value,
                "pedidos": [p.id_pedido for p in w.pedidos],
                "unidades": w.unidades_totales,
                "peso": w.peso_total_kg,
                "zona": w.id_zona_despacho,
                "pickers": list(w.ids_pickers_asignados),
                "ubicaciones": sorted(w.ubicaciones_xy),
                "costo": w.costo_mst_total,
            }
            for w in self.waves
        ]

    def resumen_pickers(self) -> List[Dict[str, Any]]:
        est = self.estado
        salida = []
        for p in self.warehouse.pickers:
            carga = sum(
                self.warehouse.buscar_producto_O1(k).peso_kg * v
                for k, v in p.productos_recogidos.items()
            )
            pendientes = [
                (prod, cant)
                for items in est.por_recoger.get(p.id_picker, {}).values()
                for prod, cant, _ in items
            ]
            salida.append(
                {
                    "id": p.id_picker,
                    "pos": p.posicion_actual,
                    "capacidad": p.capacidad_carga_kg,
                    "carga": round(carga, 2),
                    "wave": p.id_wave_actual,
                    "recogidos": dict(p.productos_recogidos),
                    "pendientes": pendientes,
                    "ruta_restante": list(p.ruta_asignada),
                    "recorrido": list(p.historial_recorrido),
                    "estado": (
                        "buscando ruta"
                        if p.turnos_busqueda > 0
                        else (
                            "cargando"
                            if p.turnos_pausa > 0
                            else (
                                "descargando"
                                if p.id_wave_actual and not p.ruta_asignada
                                else (
                                    "esperando"
                                    if p.turnos_bloqueado > 0
                                    else "caminando" if p.id_wave_actual else "libre"
                                )
                            )
                        )
                    ),
                    "mirando": (
                        est.mirando.get(p.id_picker) if p.turnos_pausa > 0 else None
                    ),
                    "busqueda_restante": p.turnos_busqueda,
                    "pasos": est.pasos_movidos.get(p.id_picker, 0),
                    "esperas": est.esperas.get(p.id_picker, 0),
                    "plan": est.planes.get(p.id_picker) if p.id_wave_actual else None,
                }
            )
        return salida

    def metricas(self) -> Dict[str, Any]:
        est = self.estado
        tanda = self.tanda_actual
        return {
            "paso": est.paso,
            "nodos": self.n_nodos,
            "aristas": self.n_aristas,
            "waves": len(self.waves),
            "waves_finalizadas": sum(
                w.estado == EstadoWave.FINALIZADA for w in self.waves
            ),
            "pedidos_preparados": sum(
                p.estado == EstadoPedido.PREPARADO
                for p in self.warehouse.pedidos.values()
            ),
            "pedidos": len(self.warehouse.pedidos),
            "esperas": est.colisiones.total_esperas_aplicadas,
            "desvios": est.colisiones.total_desvios_recalculados,
            "pasos_totales": sum(est.pasos_movidos.values()),
            "tanda": tanda,
        }

    # ------------------------------------------------------------------
    # Guardado y restauración determinista de sesiones
    # ------------------------------------------------------------------
    def a_json(self) -> Dict[str, Any]:
        datos = deepcopy(self.datos_base)
        datos["_sesion"] = {
            "version": VERSION_SESION,
            "config": dict(self.config),
            "estrategia": self.estrategia,
            "pickers_por_wave": self.pickers_por_wave,
            "acciones": deepcopy(self.acciones),
        }
        return datos

    def guardar(self, ruta) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(
            json.dumps(self.a_json(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporal.replace(ruta)
        return ruta

    @classmethod
    def cargar(cls, ruta) -> "Simulador":
        return cls(json.loads(Path(ruta).read_text(encoding="utf-8-sig")))

    def _reproducir(self, sesion: Dict[str, Any]) -> None:
        if sesion.get("version") != VERSION_SESION:
            raise ValueError("Versión de sesión no soportada.")
        acciones = sesion.get("acciones", [])
        if not isinstance(acciones, list):
            raise ValueError("Historial de sesión inválido.")
        self.config.update(sesion.get("config", {}))
        permitidas = {
            "configurar": self.configurar,
            "agregar_pedido": lambda prio, items: self.agregar_pedido(
                prio, [tuple(i) for i in items]
            ),
            "generar_waves": self.generar_waves,
            "iniciar_waves": self.iniciar_waves,
            "cambiar_estrategia": self.cambiar_estrategia,
            "avanzar": None,
            "retroceder": self.retroceder,
            "reiniciar": self.reiniciar,
        }
        for accion in acciones:
            if (
                not isinstance(accion, list)
                or len(accion) != 2
                or accion[0] not in permitidas
                or not isinstance(accion[1], list)
            ):
                raise ValueError("Acción de sesión inválida.")
            nombre, args = accion
            if nombre == "avanzar":
                for _ in range(int(args[0])):
                    self.avanzar()
            else:
                permitidas[nombre](*args)
        self.estrategia = sesion.get("estrategia", self.estrategia)
        self.pickers_por_wave = int(
            sesion.get("pickers_por_wave", self.pickers_por_wave)
        )
