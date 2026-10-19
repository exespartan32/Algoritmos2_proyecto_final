"""Sesión de una wave: conecta los modelos reales con una vista independiente.

Se ejecuta una wave seleccionada a la vez. Los demás pickers permanecen como
obstáculos: no se permite atravesarlos ni teletransportar al picker activo.
"""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from FrontEnd.services.backend_adapter import AdaptadorGrafo
from BackEnd.controllers.pathfinding import Pathfinding
from BackEnd.controllers.wave_manager import WaveManager
from BackEnd.enums.enums import EstadoPedido, EstadoWave
from BackEnd.models.catalog_manager import CatalogManager
from BackEnd.utils.graph_builder import GraphBuilder
from FrontEnd.services.scenarios import validate


class Session:
    def __init__(self, data):
        saved = data.get("_interfaz")
        source = deepcopy(saved["escenario_inicial"] if saved else data)
        source.pop("_interfaz", None)
        validate(source)
        self.data = source
        self.warehouse = GraphBuilder.construir_warehouse_desde_dict(source)
        # El parser del catálogo recibe una ruta; el temporal no altera ejemplos.
        with TemporaryDirectory() as folder:
            path = Path(folder) / "entrada.json"
            path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
            self.catalog = CatalogManager(1009, 999983, 42, folder)
            self.catalog.cargar_escenario_json(str(path))
        # Matriz y catálogo comparten los mismos Product: una sola fuente de stock.
        for product in self.catalog.obtener_todos_los_productos():
            self.warehouse.catalogo_productos[product.id_producto] = product
            self.warehouse.matriz[product.x][product.y].apilar_producto(
                product.z, product
            )
        self.wh = source["warehouse"]
        self.width = self.warehouse.ancho_x
        self.height = self.warehouse.largo_y
        self.grid = {}
        for x in range(self.width):
            for y in range(self.height):
                cell = self.warehouse.matriz[x][y]
                kind = cell.tipo.value.replace("ZONA_DESPACHO", "DESPACHO")
                sense = getattr(cell, "sentido", None)
                self.grid[x, y] = (
                    kind,
                    sense.value if sense else "AMBOS",
                    cell.elemento_id,
                )
        self.backend_waves = []
        self.selected = 0
        self.strategy = "Orden"
        self.results = {}
        self.step = 0
        self.picked = []
        self.finished = False
        self.history = []
        self.baseline = None
        self.zone_load = {z: 0.0 for z in self.warehouse.zonas_despacho}
        self.events = []
        self.alerts = []
        if saved:
            if saved.get("version") != 1:
                raise ValueError("Versión de sesión no soportada.")
            events = saved.get("acciones", [])
            if not isinstance(events, list) or len(events) > 100000:
                raise ValueError("Historial de sesión inválido o demasiado grande.")
            allowed = {
                "generate_waves",
                "select",
                "set_strategy",
                "advance",
                "back",
                "reset",
            }
            for event in events:
                if (
                    not isinstance(event, list)
                    or len(event) != 2
                    or event[0] not in allowed
                ):
                    raise ValueError("Acción de sesión inválida.")
                getattr(self, event[0])(*event[1])

    @property
    def products(self):
        return {p["id"]: p for p in self.catalog.decodificar_productos_a_json()}

    @property
    def orders(self):
        return {p["id"]: p for p in self.catalog.decodificar_pedidos_a_json()}

    @property
    def pickers(self):
        return {p.id_picker: p.to_dict() for p in self.catalog.pickers}

    @property
    def stock(self):
        return {
            p.id_producto: p.cantidad_disponible
            for p in self.catalog.obtener_todos_los_productos()
        }

    @property
    def status(self):
        return {
            o.id_pedido: o.estado.value
            for o in self.catalog.obtener_todos_los_pedidos()
        }

    @property
    def positions(self):
        return {p.id_picker: p.posicion_actual for p in self.catalog.pickers}

    @property
    def cargo(self):
        return {p.id_picker: p.productos_recogidos for p in self.catalog.pickers}

    @property
    def waves(self):
        return [
            {
                "id": w.id_wave,
                "picker": w.id_picker_asignado,
                "pedidos": [p.id_pedido for p in w.pedidos],
                "zona": w.id_zona_despacho,
                "peso": w.peso_total_kg,
                "estado": w.estado.value,
            }
            for w in self.backend_waves
        ]

    @property
    def wave(self):
        return self.waves[self.selected] if self.waves else None

    @property
    def route(self):
        return self.results.get(self.strategy, {}).get("ruta", [])

    def picker(self):
        return next(
            p for p in self.catalog.pickers if p.id_picker == self.wave["picker"]
        )

    def generate_waves(self):
        if self.backend_waves:
            raise ValueError("Las waves ya están generadas.")
        manager = WaveManager("KRUSKAL", "WAVE")
        self.backend_waves = manager.generar_waves(
            self.catalog, descontar_stock_inmediato=False
        )
        self.alerts = manager.alertas_peso.copy()
        if not self.backend_waves:
            raise ValueError(
                "; ".join(self.alerts) or "No hay pedidos pendientes viables."
            )
        self.events.append(["generate_waves", []])

    def quantities(self):
        quantities = {}
        for order in self.backend_waves[self.selected].pedidos:
            for item in order.items:
                quantities[item.producto_id] = (
                    quantities.get(item.producto_id, 0) + item.cantidad
                )
        return quantities

    def targets(self):
        targets = {}
        for pid in self.quantities():
            target = self.warehouse.obtener_nodo_acceso_producto(pid)
            if target is None:
                raise ValueError(f"Producto {pid}: no tiene pasillo de acceso.")
            targets[pid] = target
        return targets

    def _calculate(self):
        picker = self.picker()
        blocked = {p.posicion_actual for p in self.catalog.pickers if p != picker}
        graph = AdaptadorGrafo(self.warehouse.grafo_pasillos, blocked)
        targets = list(dict.fromkeys(self.targets().values()))
        if any(p in blocked for p in targets):
            raise ValueError(
                "Otro picker ocupa un acceso a producto. Ejecutá primero su wave."
            )
        zone = self.wave["zona"]
        access = [
            coord
            for coord, node in self.warehouse.grafo_pasillos.nodos.items()
            if zone in node.zonas_despacho_adyacentes and coord not in blocked
        ]
        if not access:
            raise ValueError("El despacho no tiene acceso libre.")
        results = {}
        for strategy in ("Orden", "Cercanía"):
            start = perf_counter()
            current = picker.posicion_actual
            pending = targets.copy()
            route = [current]
            explored = set()
            # Se llaman los algoritmos reales por tramo para detectar destinos
            # imposibles; sus envoltorios actuales los omiten silenciosamente.
            while pending:
                if strategy == "Orden":
                    target = pending[0]
                    path, seen = Pathfinding.calcular_ruta_dijkstra(
                        current, target, graph
                    )
                else:
                    path, target, seen = Pathfinding.calcular_ruta_greedy(
                        current, pending, graph
                    )
                explored.update(seen)
                if not path:
                    raise ValueError(
                        "Un producto es inalcanzable con el sentido de los pasillos y los pickers estacionados."
                    )
                route.extend(path[1:])
                current = target
                pending.remove(target)
            path, target, seen = Pathfinding.calcular_ruta_greedy(
                current, access, graph
            )
            explored.update(seen)
            if not path:
                raise ValueError("No existe un recorrido hasta el despacho asignado.")
            route.extend(path[1:])
            results[strategy] = {
                "ruta": route,
                "distancia": len(route) - 1,
                "aristas": len(route) - 1,
                "nodos": len(explored),
                "explorados": sorted(explored),
                "tiempo": round((perf_counter() - start) * 1000, 3),
            }
        return results

    def select(self, index):
        if self.step and not self.finished:
            raise ValueError("Terminá o reiniciá la wave actual antes de cambiar.")
        if not 0 <= index < len(self.backend_waves):
            raise ValueError("Wave inexistente.")
        if self.backend_waves[index].estado == EstadoWave.FINALIZADA:
            raise ValueError("Esta wave ya fue preparada.")
        previous = self.selected
        self.selected = index
        try:
            results = self._calculate()
        except Exception:
            self.selected = previous
            raise
        self.results = results
        self.step, self.picked, self.finished = 0, [], False
        self.history = []
        self.baseline = self.snapshot()
        self.events.append(["select", [index]])

    def set_strategy(self, strategy):
        if self.step or self.finished:
            raise ValueError("Reiniciá la wave antes de cambiar de estrategia.")
        if strategy not in ("Orden", "Cercanía"):
            raise ValueError("Estrategia desconocida.")
        self.strategy = strategy
        self.events.append(["set_strategy", [strategy]])

    def snapshot(self):
        return deepcopy(
            {
                "stock": self.stock,
                "status": self.status,
                "cargo": self.cargo,
                "positions": self.positions,
                "zone_load": self.zone_load,
                "step": self.step,
                "picked": self.picked,
                "finished": self.finished,
                "wave_states": [w.estado.value for w in self.backend_waves],
            }
        )

    def restore(self, state):
        for pid, stock in state["stock"].items():
            self.catalog.buscar_producto_O1(pid).cantidad_disponible = stock
        for oid, status in state["status"].items():
            self.catalog.actualizar_estado_pedido_O1(oid, EstadoPedido(status))
        for picker in self.catalog.pickers:
            pid = picker.id_picker
            picker.posicion_actual = tuple(state["positions"][pid])
            picker.productos_recogidos = deepcopy(state["cargo"][pid])
            picker.peso_actual_kg = sum(
                self.catalog.buscar_producto_O1(k).peso_kg * v
                for k, v in picker.productos_recogidos.items()
            )
        for wave, status in zip(self.backend_waves, state["wave_states"]):
            wave.estado = EstadoWave(status)
        for key in ("zone_load", "step", "picked", "finished"):
            setattr(self, key, deepcopy(state[key]))

    def _collect(self):
        picker = self.picker()
        quantities = self.quantities()
        for pid, target in self.targets().items():
            if target != picker.posicion_actual or pid in self.picked:
                continue
            quantity = quantities[pid]
            weight = self.catalog.buscar_producto_O1(pid).peso_kg * quantity
            if not picker.puede_cargar(weight):
                raise ValueError("La carga excedería la capacidad del picker.")
            if not self.catalog.descontar_stock(pid, quantity):
                raise ValueError(f"Stock insuficiente de {pid}.")
            picker.productos_recogidos[pid] = quantity
            picker.peso_actual_kg += weight
            self.picked.append(pid)

    def advance(self):
        if not self.route:
            raise ValueError("Generá waves y seleccioná una para calcular su ruta.")
        if self.finished:
            return
        before = self.snapshot()
        try:
            wave = self.backend_waves[self.selected]
            wave.estado = EstadoWave.EN_EJECUCION
            self._collect()
            self.step = min(self.step + 1, len(self.route) - 1)
            next_position = self.route[self.step]
            picker = self.picker()
            if any(
                p != picker and p.posicion_actual == next_position
                for p in self.catalog.pickers
            ):
                raise ValueError("Paso bloqueado por otro picker.")
            picker.posicion_actual = next_position
            self._collect()
            if self.step == len(self.route) - 1:
                if set(self.picked) != set(self.quantities()):
                    raise ValueError("La ruta no recogió todos los productos.")
                zone = self.warehouse.zonas_despacho[wave.id_zona_despacho]
                if (
                    self.zone_load[zone.id] + wave.peso_total_kg
                    > zone.peso_max_kg + 1e-8
                ):
                    raise ValueError("El despacho no tiene capacidad disponible.")
                self.zone_load[zone.id] += wave.peso_total_kg
                picker.productos_recogidos = {}
                picker.peso_actual_kg = 0
                wave.estado = EstadoWave.FINALIZADA
                for order in wave.pedidos:
                    order.estado = EstadoPedido.PREPARADO
                self.finished = True
            self.history.append(before)
            self.events.append(["advance", []])
        except Exception:
            self.restore(before)
            raise

    def back(self):
        if self.history:
            self.restore(self.history.pop())
            self.events.append(["back", []])

    def reset(self):
        if self.baseline:
            self.restore(self.baseline)
            self.history = []
            self.events.append(["reset", []])

    def save(self, path):
        data = deepcopy(self.data)
        data["productos"] = self.catalog.decodificar_productos_a_json()
        data["pedidos"] = self.catalog.decodificar_pedidos_a_json()
        data["pickers"] = [p.to_dict() for p in self.catalog.pickers]
        # Registro de acciones validado al cargar: reconstruye también el undo.
        data["_interfaz"] = {
            "version": 1,
            "escenario_inicial": self.data,
            "acciones": self.events,
        }
        path = Path(path)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(path)
