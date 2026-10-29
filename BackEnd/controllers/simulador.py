"""Capa de simulación: orquesta Warehouse -> WaveManager -> Pathfinding -> Turnos.

La interfaz gráfica (FrontEnd) y los experimentos solo hablan con esta clase.
Toda la lógica algorítmica es la del equipo:

- ``GraphBuilder`` arma el dígrafo de pasillos (Laureano).
- ``WaveManager`` arma las waves con Max-Heap + costo marginal y las asigna a
  los pickers más cercanos (Exequiel).
- ``Pathfinding`` calcula los recorridos con Dijkstra según la estrategia y
  ``TurnAndCollisionManager`` mueve a todos los pickers a la vez evitando
  choques (Leonel).

Esta capa agrega lo que necesita una simulación interactiva:

- registrar qué productos recoge cada picker y cuándo los entrega;
- avanzar, retroceder y reiniciar paso a paso (historial de estados);
- comparar estrategias sobre las mismas waves sin tocar la simulación real;
- guardar la sesión y retomarla después (se guarda el escenario inicial y la
  lista de acciones, y al cargar se vuelven a ejecutar: la simulación es
  determinista, así que se llega exactamente al mismo estado).
"""

from copy import deepcopy
import json
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.controllers.path_finding import Pathfinding
from BackEnd.controllers.turn_collision_manager import TurnAndCollisionManager
from BackEnd.controllers.wave_manager import WaveManager
from BackEnd.enums.enums import EstadoPedido, EstadoWave, EstrategiaRuteo
from BackEnd.models.entities import DetallePedido, Pedido, TareaWavePicker
from BackEnd.utils.graph_builder import GraphBuilder

Coord = Tuple[int, int]

ESTRATEGIAS = {
    "ORDEN": EstrategiaRuteo.ORDEN_PEDIDOS_DIJKSTRA,
    "CERCANIA": EstrategiaRuteo.CERCANIA_DIJKSTRA_MULTIDESTINO,
}
NOMBRE_ESTRATEGIA = {"ORDEN": "Orden de pedidos", "CERCANIA": "Cercanía"}
VERSION_SESION = 2
MAX_PASOS_TANDA = 5000
# Cada cuántos turnos se guarda una copia completa del estado. Para retroceder
# a un turno intermedio se parte de la copia anterior y se re-simula (la
# simulación es determinista), así el historial ocupa ~10 veces menos memoria.
INTERVALO_COPIA = 10


class Plan(dict):
    """Ruta planificada de un picker. No cambia después de creada, por eso
    las copias del historial la comparten en lugar de duplicarla."""

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


class EstadoSimulacion:
    """Todo lo que cambia durante la simulación. Se copia para el historial."""

    def __init__(self, warehouse) -> None:
        self.warehouse = warehouse
        self.gestor_waves: Optional[WaveManager] = None
        self.colisiones = TurnAndCollisionManager(max_turnos_bloqueo_recalculo=2)
        self.paso = 0
        self.tandas: List[Dict[str, Any]] = []
        # picker -> celda de pasillo -> [(producto, cantidad, pedido)] por recoger
        self.por_recoger: Dict[str, Dict[Coord, List[Tuple[str, int, str]]]] = {}
        self.planes: Dict[str, Dict[str, Any]] = {}
        self.eventos: List[str] = []
        self.entregas: List[Dict[str, Any]] = []
        self.pasos_movidos: Dict[str, int] = {}
        self.esperas: Dict[str, int] = {}
        self.siguiente_pedido = 1


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
        }
        self.estrategia = "CERCANIA"
        self.acciones: List[List[Any]] = []
        # None = turno sin copia (se reconstruye desde la copia anterior).
        self.historial: List[Optional[EstadoSimulacion]] = []
        self._inicio_tanda: Dict[int, Tuple[EstadoSimulacion, EstadoSimulacion]] = {}
        self._pre_waves: Optional[EstadoSimulacion] = None

        warehouse = GraphBuilder.construir_warehouse_desde_dict(datos)
        # Un pedido que quedó "en wave" en un archivo exportado vuelve a estar
        # pendiente: al cargar todavía no existe ninguna wave.
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
    # Datos que no cambian durante la simulación
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
        # Intersección: pasillo con salida/entrada en ambos ejes.
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
                # Se cruzan al menos dos pasillos declarados distintos.
                ids = {grafo.nodos[v].pasillo_id for v in vecinos} | {grafo.nodos[(x, y)].pasillo_id}
                if len(ids - {None}) >= 2:
                    self.intersecciones.add((x, y))
        self.n_nodos = len(grafo.nodos)
        self.n_aristas = sum(len(v) for v in grafo.lista_adyacencia.values())
        # Matriz de distancias entre productos (Dijkstra desde cada acceso).
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
            int(m.group(1))
            for pid in wh.pedidos
            if (m := re.search(r"(\d+)$", pid))
        ]
        return max(numeros, default=0) + 1

    def _copiar(self, estado: EstadoSimulacion) -> EstadoSimulacion:
        """Copia profunda que comparte lo que nunca cambia (grafo, obstáculos)."""
        memo = {id(obj): obj for obj in self._inmutables}
        return deepcopy(estado, memo)

    # ------------------------------------------------------------------
    # Accesos rápidos
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
    # Pedidos y configuración (antes de iniciar waves)
    # ------------------------------------------------------------------
    def _volver_antes_de_waves(self) -> None:
        if self.waves_iniciadas:
            raise ValueError(
                "Ya hay waves en ejecución o terminadas. Esto solo se puede antes de iniciar waves."
            )
        if self._pre_waves is not None:
            self.estado = self._copiar(self._pre_waves)
            self._pre_waves = None
            self.historial.clear()

    def configurar(
        self, wave_max_pedidos: int, wave_max_productos: int, max_pickers_por_wave: int
    ) -> None:
        valores = [int(wave_max_pedidos), int(wave_max_productos), int(max_pickers_por_wave)]
        if not 1 <= valores[0] <= 50 or not 1 <= valores[1] <= 500 or not 1 <= valores[2] <= 10:
            raise ValueError(
                "Rangos válidos: pedidos por wave 1-50, productos por wave 1-500, pickers por wave 1-10."
            )
        self._volver_antes_de_waves()
        self.config.update(
            wave_max_pedidos=valores[0],
            wave_max_productos=valores[1],
            max_pickers_por_wave=valores[2],
        )
        self._registrar("configurar", *valores)

    @staticmethod
    def interpretar_items(texto: str) -> List[Tuple[str, int]]:
        """'P001x2, P004 x 1' -> [('P001', 2), ('P004', 1)]"""
        items: Dict[str, int] = {}
        for parte in re.split(r"[,;]+", texto):
            parte = parte.strip()
            if not parte:
                continue
            m = re.fullmatch(r"([A-Za-z0-9_\-]+?)\s*(?:[xX\*]\s*(\d+))?", parte)
            if not m:
                raise ValueError(f"No entiendo '{parte}'. Usá el formato P001x2, P004x1.")
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
    # Waves
    # ------------------------------------------------------------------
    def generar_waves(self) -> List[Any]:
        self._volver_antes_de_waves()
        self._pre_waves = self._copiar(self.estado)
        wh = self.warehouse
        gestor = WaveManager(
            wave_max_pedidos=self.config["wave_max_pedidos"],
            wave_max_productos=self.config["wave_max_productos"],
            max_pickers_por_wave=self.config["max_pickers_por_wave"],
            proveedor_distancias=self.matriz_distancias,
        )
        inicio = time.perf_counter()
        waves = gestor.generar_waves(wh, proveedor_distancias=self.matriz_distancias)
        self.tiempo_waves_ms = (time.perf_counter() - inicio) * 1000
        self.estado.gestor_waves = gestor
        self._evento(
            f"{len(waves)} waves generadas en {self.tiempo_waves_ms:.2f} ms "
            f"(máx. {self.config['wave_max_pedidos']} pedidos y "
            f"{self.config['wave_max_productos']} productos por wave)."
        )
        for error in gestor.errores_validacion:
            self._evento(error)
        self._registrar("generar_waves")
        if not waves:
            raise ValueError(
                "No se pudo armar ninguna wave. "
                + ("; ".join(gestor.errores_validacion) or "No hay pedidos pendientes.")
            )
        return waves

    def _planificar(self, warehouse, wave, picker, tarea, estrategia: str) -> Dict[str, Any]:
        """Recalcula la ruta de la tarea con la estrategia para medir sus métricas."""
        grafo = warehouse.grafo_pasillos
        origen = tarea.ruta_calculada[0] if tarea.ruta_calculada else picker.posicion_actual
        destinos = list(tarea.destinos_recoleccion_pasillo)
        if estrategia == "ORDEN":
            res = Pathfinding.calcular_estrategia_orden_pedidos(
                grafo, origen, destinos, tarea.destino_despacho_pasillo, warehouse
            )
        else:
            res = Pathfinding.calcular_estrategia_cercania_multidestino(
                grafo, origen, destinos, tarea.destino_despacho_pasillo, warehouse
            )
        # Orden en que la ruta visita cada destino (para dibujarlo numerado).
        orden_visita: List[Coord] = []
        pendientes = set(destinos)
        for celda in res.camino_completo:
            if celda in pendientes:
                orden_visita.append(celda)
                pendientes.discard(celda)
        return Plan({
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
        })

    def iniciar_waves(self, ids_waves: List[str], estrategia: Optional[str] = None) -> Dict[str, Any]:
        """Asigna las waves elegidas a los pickers libres más cercanos.

        Las que no consiguen picker quedan EN ESPERA dentro de la tanda y se
        asignan solas en cuanto un picker termina y descarga.
        """
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

        antes = self._copiar(self.estado)
        self.historial.append(antes)
        tanda = {
            "numero": len(self.estado.tandas) + 1,
            "waves": [],
            "en_espera": [],
            "estrategia": estrategia,
            "paso_inicio": self.estado.paso,
            "paso_fin": None,
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
        self._inicio_tanda[len(self.estado.tandas) - 1] = (antes, self._copiar(self.estado))
        self._registrar("iniciar_waves", list(ids_waves), estrategia)
        return tanda

    def _asignar(self, tanda: Dict[str, Any], ids: List[str]) -> None:
        """Llama al WaveManager y registra plan, productos a recoger y eventos."""
        gestor = self.estado.gestor_waves
        wh = self.warehouse
        estrategia = tanda["estrategia"]
        posiciones = {p.id_picker: p.posicion_actual for p in wh.pickers}
        resultado = gestor.asignar_y_ejecutar_waves_seleccionadas(ids, wh, ESTRATEGIAS[estrategia])
        tanda["en_espera"] = list(resultado["waves_sin_picker_disponible"])
        pickers = {p.id_picker: p for p in wh.pickers}
        for asig in resultado["asignaciones"]:
            wave = gestor.waves_por_id[asig["id_wave"]]
            tanda["waves"].append(wave.id_wave)
            for pid in asig["ids_pickers"]:
                picker = pickers[pid]
                tarea_ruta = asig["rutas_por_picker"][pid]
                tarea = TareaWavePicker(
                    id_wave=wave.id_wave,
                    id_zona_despacho=wave.id_zona_despacho,
                    destino_despacho_pasillo=tarea_ruta[-1] if tarea_ruta else posiciones[pid],
                    pedidos_asignados=wave.pedidos_por_picker.get(pid, []),
                    destinos_recoleccion_pasillo=[
                        Pathfinding.obtener_celda_acceso_pasillo(c, wh.grafo_pasillos, wh)
                        for c in wave.destinos_xy_por_picker.get(pid, [])
                    ],
                    peso_lote_kg=wave.peso_por_picker.get(pid, 0.0),
                    ruta_calculada=tarea_ruta,
                )
                plan = self._planificar(wh, wave, picker, tarea, estrategia)
                plan["ruta"] = list(tarea_ruta)
                plan["pedidos"] = list(tarea.pedidos_asignados)
                plan["distancia_inicial"] = asig["distancias_picker_a_wave"].get(pid, 0)
                self.estado.planes[pid] = plan
                resumen = {
                    k: plan[k]
                    for k in ("wave", "distancia", "aristas", "nodos_visitados", "nodos_explorados", "expansiones", "tiempo_ms")
                }
                resumen["picker"] = pid
                tanda["planes"].append(resumen)
                # Qué producto se recoge en cada celda de pasillo.
                por_celda: Dict[Coord, List[Tuple[str, int, str]]] = {}
                for id_ped in tarea.pedidos_asignados:
                    pedido = wh.buscar_pedido_O1(id_ped)
                    pedido.estado = EstadoPedido.EN_PREPARACION
                    for item in pedido.items:
                        prod = wh.buscar_producto_O1(item.producto_id)
                        celda = Pathfinding.obtener_celda_acceso_pasillo(prod.coordenadas_xy, wh.grafo_pasillos, wh)
                        por_celda.setdefault(celda, []).append((item.producto_id, item.cantidad, id_ped))
                self.estado.por_recoger[pid] = por_celda
                picker.productos_recogidos = {}
                self.estado.pasos_movidos.setdefault(pid, 0)
                self.estado.esperas.setdefault(pid, 0)
                self._evento(
                    f"{pid} toma {wave.id_wave} ({NOMBRE_ESTRATEGIA[estrategia]}): "
                    f"{plan['distancia']} pasos planificados, {plan['nodos_explorados']} nodos explorados."
                )
                # Si un producto está justo donde arranca el picker, se recoge ya.
                self._recoger(picker)

    def cambiar_estrategia(self, estrategia: str) -> bool:
        """Cambia la estrategia. Si la tanda actual no avanzó, la vuelve a planificar."""
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
            self.iniciar_waves(ids, estrategia)
            # La re-planificación ya quedó registrada dentro de cambiar_estrategia.
            self.acciones.pop()
            return True
        self._registrar("cambiar_estrategia", estrategia)
        return False

    # ------------------------------------------------------------------
    # Simulación paso a paso
    # ------------------------------------------------------------------
    def _recoger(self, picker) -> None:
        pendientes = self.estado.por_recoger.get(picker.id_picker)
        if not pendientes:
            return
        items = pendientes.pop(picker.posicion_actual, None)
        if not items:
            return
        for prod_id, cant, id_ped in items:
            picker.productos_recogidos[prod_id] = picker.productos_recogidos.get(prod_id, 0) + cant
            prod = self.warehouse.buscar_producto_O1(prod_id)
            self._evento(
                f"{picker.id_picker} recoge {cant}× {prod_id} ({prod.nombre}) "
                f"del nivel z={prod.z} para {id_ped}."
            )

    def avanzar(self, guardar_historial: bool = True) -> bool:
        """Avanza un turno para todos los pickers. Devuelve False si no hay nada que mover."""
        if not self.en_curso:
            return False
        if guardar_historial:
            copia = self.estado.paso % INTERVALO_COPIA == 0 or not self.historial
            self.historial.append(self._copiar(self.estado) if copia else None)
        est = self.estado
        wh = est.warehouse
        antes = {
            p.id_picker: (p.posicion_actual, p.id_wave_actual) for p in wh.pickers
        }
        est.colisiones.avanzar_un_turno_simulacion(
            pickers=wh.pickers,
            paso_actual=est.paso,
            grafo=wh.grafo_pasillos,
            gestor_waves=est.gestor_waves,
            catalogo=wh,
        )
        est.paso += 1
        for p in wh.pickers:
            pos_antes, wave_antes = antes[p.id_picker]
            if wave_antes is None and p.id_wave_actual is None:
                continue
            if p.posicion_actual != pos_antes:
                est.pasos_movidos[p.id_picker] = est.pasos_movidos.get(p.id_picker, 0) + 1
            elif wave_antes is not None:
                est.esperas[p.id_picker] = est.esperas.get(p.id_picker, 0) + 1
            self._recoger(p)
            if wave_antes is not None and p.id_wave_actual is None:
                self._entregar(p, wave_antes)
        est.eventos.extend(f"[t={est.paso}] {e}" for e in self._eventos_colision_nuevos())
        tanda = self.tanda_actual
        if tanda and tanda["en_espera"] and est.gestor_waves.obtener_pickers_libres(wh.pickers):
            esperando = list(tanda["en_espera"])
            self._asignar(tanda, esperando)
            for wid in esperando:
                if wid not in tanda["en_espera"] and wid in tanda["waves"]:
                    self._evento(f"{wid} sale de la espera: se liberó un picker.")
        for tanda in est.tandas:
            if tanda["paso_fin"] is None and not tanda["en_espera"] and all(
                est.gestor_waves.waves_por_id[w].estado == EstadoWave.FINALIZADA
                for w in tanda["waves"]
            ):
                tanda["paso_fin"] = est.paso
                self._evento(
                    f"Tanda {tanda['numero']} terminada en {est.paso - tanda['paso_inicio']} turnos."
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
            {"picker": picker.id_picker, "wave": id_wave, "productos": entregado, "paso": est.paso}
        )
        zona = est.gestor_waves.waves_por_id[id_wave].id_zona_despacho
        unidades = sum(entregado.values())
        self._evento(f"{picker.id_picker} descarga {unidades} unidades de {id_wave} en {zona}.")
        if faltantes:
            perdidos = [f"{p}×{c}" for items in faltantes.values() for p, c, _ in items]
            self._evento(f"ATENCIÓN: {picker.id_picker} no pudo recoger {', '.join(perdidos)}.")
        picker.productos_recogidos = {}
        wave = est.gestor_waves.waves_por_id[id_wave]
        if wave.estado == EstadoWave.FINALIZADA:
            self._evento(f"{id_wave} FINALIZADA: pedidos {', '.join(p.id_pedido for p in wave.pedidos)} PREPARADOS.")

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
        """Vuelve al comienzo de la tanda actual (recién asignadas las waves)."""
        indice = len(self.estado.tandas) - 1
        if indice not in self._inicio_tanda:
            return False
        antes, despues = self._inicio_tanda[indice]
        # El historial queda como si se acabara de iniciar la tanda.
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
    # Comparación de estrategias (no modifica la simulación real)
    # ------------------------------------------------------------------
    def comparar_estrategias(self, ids_waves: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """Corre las mismas waves con cada estrategia sobre una copia del estado.

        Si no se indican waves, usa las de la tanda actual partiendo del mismo
        estado inicial de esa tanda.
        """
        indice = len(self.estado.tandas) - 1
        if ids_waves is None:
            tanda = self.tanda_actual
            if tanda is None or indice not in self._inicio_tanda:
                raise ValueError("Seleccioná waves (o iniciá una tanda) para comparar.")
            ids_waves = tanda["waves"] + tanda["en_espera"]
            base = self._inicio_tanda[indice][0]
        else:
            base = self.estado
        resultados: Dict[str, Dict[str, Any]] = {}
        for clave in ESTRATEGIAS:
            clon = Simulador.__new__(Simulador)
            clon.__dict__.update(self.__dict__)
            clon.estado = self._copiar(base)
            clon.historial = []
            clon._inicio_tanda = {}
            clon.acciones = []
            clon.estrategia = clave
            inicio = time.perf_counter()
            tanda = clon.iniciar_waves(ids_waves, clave)
            tiempo_plan = (time.perf_counter() - inicio) * 1000
            clon.historial = []  # la copia no necesita poder retroceder
            pasos = 0
            while pasos < MAX_PASOS_TANDA and clon.avanzar(guardar_historial=False):
                pasos += 1
            planes = tanda["planes"]
            resultados[clave] = {
                "nombre": NOMBRE_ESTRATEGIA[clave],
                "waves": tanda["waves"],
                "pickers": len({p["picker"] for p in planes}),
                "viajes": len(planes),
                "distancia": sum(p["distancia"] for p in planes),
                "aristas": sum(p["aristas"] for p in planes),
                "nodos_visitados": sum(p["nodos_visitados"] for p in planes),
                "nodos_explorados": sum(p["nodos_explorados"] for p in planes),
                "expansiones": sum(p["expansiones"] for p in planes),
                "tiempo_ms": round(sum(p["tiempo_ms"] for p in planes), 3),
                "tiempo_total_ms": round(tiempo_plan, 3),
                "turnos": pasos,
                "esperas": clon.estado.colisiones.total_esperas_aplicadas
                - base.colisiones.total_esperas_aplicadas,
                "desvios": clon.estado.colisiones.total_desvios_recalculados
                - base.colisiones.total_desvios_recalculados,
            }
        return resultados

    # ------------------------------------------------------------------
    # Datos para mostrar
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
            "waves_finalizadas": sum(w.estado == EstadoWave.FINALIZADA for w in self.waves),
            "pedidos_preparados": sum(
                p.estado == EstadoPedido.PREPARADO for p in self.warehouse.pedidos.values()
            ),
            "pedidos": len(self.warehouse.pedidos),
            "esperas": est.colisiones.total_esperas_aplicadas,
            "desvios": est.colisiones.total_desvios_recalculados,
            "pasos_totales": sum(est.pasos_movidos.values()),
            "tanda": tanda,
        }

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------
    def a_json(self) -> Dict[str, Any]:
        datos = deepcopy(self.datos_base)
        datos["_sesion"] = {
            "version": VERSION_SESION,
            "config": dict(self.config),
            "estrategia": self.estrategia,
            "acciones": deepcopy(self.acciones),
        }
        return datos

    def guardar(self, ruta) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(json.dumps(self.a_json(), ensure_ascii=False, indent=2), encoding="utf-8")
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
            "agregar_pedido": lambda prio, items: self.agregar_pedido(prio, [tuple(i) for i in items]),
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
