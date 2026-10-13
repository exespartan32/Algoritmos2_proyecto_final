from typing import List, Tuple
from BackEnd.enums.enums import (
    EstadoSimulacion,
    EstrategiaRuteo,
    EstadoPedido,
    EstadoWave,
)
from BackEnd.models.warehouse_models import Warehouse
from BackEnd.models.catalog_manager import CatalogManager
from BackEnd.models.entities import Picker, Wave
from BackEnd.controllers.wave_manager import WaveManager
from BackEnd.controllers.pathfinding import Pathfinding
from BackEnd.controllers.turn_collision_manager import TurnAndCollisionManager
from BackEnd.controllers.metrics_manager import MetricsManager
from BackEnd.controllers.persistence_generator import PersistenceAndGenerator


class SimulatorController:
    def __init__(
        self,
        warehouse: Warehouse,
        catalogo: CatalogManager,
        pickers: List[Picker],
        ruta_guardado_json: str = "BackEnd/data/estado_guardado.json",
    ):
        self.warehouse = warehouse
        self.catalogo = catalogo
        self.pickers = pickers
        self.ruta_guardado_json = ruta_guardado_json

        self.estado_actual = EstadoSimulacion.DETENIDO
        self.paso_actual = 0
        self.estrategia_activa = EstrategiaRuteo.CERCANIA_DIJKSTRA_MULTIDESTINO

        self.wave_manager = WaveManager()
        self.pathfinding = Pathfinding()
        self.collision_manager = TurnAndCollisionManager()
        self.metrics_manager = MetricsManager()
        self.persistence = PersistenceAndGenerator()
        self.waves_activas: List[Wave] = []

    def preparar_waves_y_rutas(self) -> None:
        self.waves_activas = self.wave_manager.generar_waves(
            self.warehouse, self.catalogo, self.pickers
        )

        for wave in self.waves_activas:
            origen_despacho = self.warehouse.obtener_celda_acceso_despacho(
                wave.id_zona_despacho
            )
            if not origen_despacho:
                continue

            destinos_pasillo: List[Tuple[int, int]] = []
            for pedido in wave.pedidos:
                pedido.estado = EstadoPedido.EN_PREPARACION
                for item in pedido.items:
                    prod = self.catalogo.buscar_producto_O1(item.producto_id)
                    if prod:
                        acceso = self.warehouse.obtener_celda_acceso_pasillo(
                            prod.ubicacion_x, prod.ubicacion_y
                        )
                        if acceso and acceso not in destinos_pasillo:
                            destinos_pasillo.append(acceso)

                        # Descuento de stock en O(1) directamente en la Tabla Hash
                        if self.catalogo.descontar_stock(
                            prod.id_producto, item.cantidad
                        ):
                            picker_asig = next(
                                (
                                    p
                                    for p in self.pickers
                                    if p.id_picker == wave.id_picker_asignado
                                ),
                                None,
                            )
                            if picker_asig:
                                picker_asig.productos_recogidos[prod.id_producto] = (
                                    picker_asig.productos_recogidos.get(
                                        prod.id_producto, 0
                                    )
                                    + item.cantidad
                                )
                                picker_asig.peso_actual_kg += (
                                    prod.peso_kg * item.cantidad
                                )

            # Evaluar Estrategia A (Orden de Pedidos) y Estrategia B (Cercanía Multidestino)
            res_orden = self.pathfinding.calcular_estrategia_orden_pedidos(
                self.warehouse.grafo, origen_despacho, destinos_pasillo
            )
            self.metrics_manager.registrar_metrica(
                wave.id_wave,
                EstrategiaRuteo.ORDEN_PEDIDOS_DIJKSTRA,
                res_orden.distancia_total,
                len(res_orden.nodos_explorados),
                res_orden.aristas_recorridas,
                res_orden.tiempo_ejecucion_ms,
            )

            res_cercania = self.pathfinding.calcular_estrategia_cercania_multidestino(
                self.warehouse.grafo, origen_despacho, destinos_pasillo
            )
            self.metrics_manager.registrar_metrica(
                wave.id_wave,
                EstrategiaRuteo.CERCANIA_DIJKSTRA_MULTIDESTINO,
                res_cercania.distancia_total,
                len(res_cercania.nodos_explorados),
                res_cercania.aristas_recorridas,
                res_cercania.tiempo_ejecucion_ms,
            )

            ruta_elegida = (
                res_cercania.camino_completo
                if self.estrategia_activa
                == EstrategiaRuteo.CERCANIA_DIJKSTRA_MULTIDESTINO
                else res_orden.camino_completo
            )
            wave.recorrido_calculado = ruta_elegida
            wave.estado = EstadoWave.EN_EJECUCION

            picker_obj = next(
                (p for p in self.pickers if p.id_picker == wave.id_picker_asignado),
                None,
            )
            if picker_obj:
                picker_obj.posicion_actual = origen_despacho
                picker_obj.ruta_asignada = list(ruta_elegida[1:])

    def iniciar(self) -> None:
        if not self.waves_activas:
            self.preparar_waves_y_rutas()
        self.estado_actual = EstadoSimulacion.EJECUTANDO

    def pausar(self) -> None:
        self.estado_actual = EstadoSimulacion.PAUSADO
        self.persistence.guardar_escenario_json(
            self.ruta_guardado_json,
            self.warehouse,
            self.catalogo,
            self.pickers,
            self.waves_activas,
            self,
        )

    def continuar(self) -> None:
        if self.estado_actual in (
            EstadoSimulacion.PAUSADO,
            EstadoSimulacion.PASO_A_PASO,
        ):
            self.estado_actual = EstadoSimulacion.EJECUTANDO

    def avanzar_paso_a_paso(self) -> None:
        self.estado_actual = EstadoSimulacion.PASO_A_PASO
        self._ejecutar_tick_simulacion()

    def _ejecutar_tick_simulacion(self) -> None:
        self.collision_manager.validar_movimiento_simultaneo(
            self.pickers, self.paso_actual, self.warehouse.grafo
        )

        alguno_en_movimiento = False
        for picker in self.pickers:
            if picker.ruta_asignada:
                picker.posicion_actual = picker.ruta_asignada.pop(0)
                alguno_en_movimiento = True

        self.paso_actual += 1

        if not alguno_en_movimiento:
            for w in self.waves_activas:
                w.estado = EstadoWave.FINALIZADA
                for ped in w.pedidos:
                    ped.estado = EstadoPedido.PREPARADO
            self.finalizar()

    def finalizar(self) -> None:
        self.estado_actual = EstadoSimulacion.FINALIZADO
        self.persistence.guardar_escenario_json(
            self.ruta_guardado_json,
            self.warehouse,
            self.catalogo,
            self.pickers,
            self.waves_activas,
            self,
        )
