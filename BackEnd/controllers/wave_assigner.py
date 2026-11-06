from typing import Any, Dict, List, Optional, Set, Tuple

from BackEnd.controllers.path_finding import Pathfinding, RutaResultado
from BackEnd.controllers.wave_builder import WaveBuilder
from BackEnd.enums.enums import EstadoPedido, EstadoWave, EstrategiaRuteo
from BackEnd.models.entities import Pedido, Picker, TareaWavePicker, Wave
from BackEnd.models.warehouse import Warehouse

CoordXY = Tuple[int, int]


class WaveAssigner:
    """Asigna waves a equipos de pickers libres, planifica sus rutas y gestiona las descargas."""

    def __init__(self, max_pickers_por_wave: int = 2) -> None:
        self.max_pickers_por_wave = max(1, int(max_pickers_por_wave))
        self.pickers_pendientes_descarga: Dict[str, Set[str]] = {}

    @staticmethod
    def obtener_pickers_libres(pickers: List[Picker]) -> List[Picker]:
        return [p for p in pickers if p.id_wave_actual is None]

    @staticmethod
    def calcular_distancia_picker_a_wave(
        picker: Picker,
        wave: Wave,
        warehouse: Warehouse,
    ) -> float:
        if not wave.ubicaciones_xy:
            return 0.0

        grafo = warehouse.grafo_pasillos
        orig_pasillo = Pathfinding.obtener_celda_acceso_pasillo(
            picker.posicion_actual, grafo, warehouse
        )
        mapa_dist = Pathfinding.calcular_mapa_distancias_desde(orig_pasillo, grafo)
        dist_min = float("inf")
        for coord_rack in wave.ubicaciones_xy:
            celda_acceso = Pathfinding.obtener_celda_acceso_pasillo(
                coord_rack, grafo, warehouse
            )
            d = mapa_dist.get(celda_acceso, float("inf"))
            if d < dist_min:
                dist_min = d
        return dist_min

    @staticmethod
    def equipo_puede_cargar(
        pedidos: List[Pedido], equipo: List[Picker], warehouse: Warehouse
    ) -> bool:
        """Verifica mediante reparto goloso si el equipo puede cargar todos los pedidos."""
        cargas = [0.0] * len(equipo)
        for peso in sorted(
            (p.obtener_peso_total(warehouse) for p in pedidos), reverse=True
        ):
            validos = [
                i
                for i in range(len(equipo))
                if cargas[i] + peso <= equipo[i].capacidad_carga_kg
            ]
            if not validos:
                return False
            i = min(validos, key=lambda j: cargas[j])
            cargas[i] += peso
        return True

    @staticmethod
    def elegir_celda_despacho(
        accesos: List[CoordXY],
        picker: Picker,
        destinos: List[CoordXY],
        pickers: List[Picker],
        warehouse: Warehouse,
    ) -> Optional[CoordXY]:
        """Selecciona una celda adyacente a la zona de despacho evitando apilar pickers."""
        if not accesos:
            return None
        ocupadas = set()
        for otro in pickers:
            if otro is picker:
                continue
            if otro.id_wave_actual is None and not otro.ruta_asignada:
                ocupadas.add(otro.posicion_actual)
            elif otro.destino_despacho_actual is not None:
                ocupadas.add(otro.destino_despacho_actual)
        libres = [c for c in accesos if c not in ocupadas] or list(accesos)
        ref = destinos[-1] if destinos else picker.posicion_actual
        nodos = warehouse.grafo_pasillos.nodos
        ady = warehouse.grafo_pasillos.lista_adyacencia
        return min(
            libres,
            key=lambda c: (
                len(ady.get(c, [])) < 2,
                nodos[c].pasillo_id is not None if c in nodos else True,
                abs(c[0] - ref[0]) + abs(c[1] - ref[1]),
                c,
            ),
        )

    def asignar_y_ejecutar(
        self,
        ids_waves_seleccionadas: List[str],
        waves_por_id: Dict[str, Wave],
        warehouse: Warehouse,
        estrategia_ruteo: EstrategiaRuteo = EstrategiaRuteo.CERCANIA_DIJKSTRA_MULTIDESTINO,
        pickers_por_wave: int = 1,
    ) -> Dict[str, Any]:
        grafo = warehouse.grafo_pasillos
        pickers = warehouse.pickers

        waves_elegidas: List[Wave] = []
        for wid in ids_waves_seleccionadas:
            w = waves_por_id.get(wid)
            if (
                w is not None
                and w.estado == EstadoWave.PENDIENTE
                and w not in waves_elegidas
            ):
                waves_elegidas.append(w)

        pickers_libres = self.obtener_pickers_libres(pickers)

        resultado: Dict[str, Any] = {
            "waves_iniciadas": [],
            "asignaciones": [],
            "waves_sin_picker_disponible": [],
        }

        if not waves_elegidas or not pickers_libres:
            resultado["waves_sin_picker_disponible"] = [
                w.id_wave for w in waves_elegidas
            ]
            return resultado

        dist_picker_wave: Dict[Tuple[str, str], float] = {}
        for pk in pickers_libres:
            for w in waves_elegidas:
                dist_picker_wave[(pk.id_picker, w.id_wave)] = (
                    self.calcular_distancia_picker_a_wave(pk, w, warehouse)
                )

        for w in waves_elegidas:
            if not pickers_libres:
                resultado["waves_sin_picker_disponible"].append(w.id_wave)
                continue

            candidatos_cercanos = sorted(
                pickers_libres,
                key=lambda pk: (
                    dist_picker_wave.get((pk.id_picker, w.id_wave), float("inf")),
                    -pk.capacidad_carga_kg,
                    pk.id_picker,
                ),
            )

            equipo_elegido: List[Picker] = []
            cantidad = max(
                1, min(int(pickers_por_wave), len(w.pedidos), len(candidatos_cercanos))
            )
            if cantidad > 1:
                equipo = candidatos_cercanos[:cantidad]
                if self.equipo_puede_cargar(w.pedidos, equipo, warehouse):
                    equipo_elegido = equipo

            if not equipo_elegido:
                if candidatos_cercanos[0].capacidad_carga_kg >= w.peso_total_kg:
                    equipo_elegido = [candidatos_cercanos[0]]
                else:
                    for pk in candidatos_cercanos:
                        if pk.capacidad_carga_kg >= w.peso_total_kg:
                            equipo_elegido = [pk]
                            break
                    if not equipo_elegido:
                        factible, equipo_multi = (
                            WaveBuilder.es_repartible_en_equipo_pickers(
                                w.pedidos,
                                candidatos_cercanos,
                                warehouse,
                                self.max_pickers_por_wave,
                            )
                        )
                        if factible and equipo_multi:
                            equipo_elegido = equipo_multi

            if not equipo_elegido:
                resultado["waves_sin_picker_disponible"].append(w.id_wave)
                continue

            for pk in equipo_elegido:
                pickers_libres = [q for q in pickers_libres if q is not pk]

            w.asignar_equipo_pickers(equipo_elegido, warehouse)
            w.estado = EstadoWave.EN_EJECUCION
            self.pickers_pendientes_descarga[w.id_wave] = {
                p.id_picker for p in equipo_elegido
            }

            accesos_despacho = warehouse.obtener_nodos_acceso_zona(w.id_zona_despacho)

            rutas_por_picker: Dict[str, List[CoordXY]] = {}
            resultados_ruta_por_picker: Dict[str, RutaResultado] = {}

            for pk in equipo_elegido:
                destinos_rack = w.destinos_xy_por_picker.get(pk.id_picker, [])
                destinos_pasillo = [
                    Pathfinding.obtener_celda_acceso_pasillo(c, grafo, warehouse)
                    for c in destinos_rack
                ]
                nodo_despacho = (
                    self.elegir_celda_despacho(
                        accesos_despacho, pk, destinos_pasillo, pickers, warehouse
                    )
                    or pk.posicion_actual
                )

                if estrategia_ruteo == EstrategiaRuteo.ORDEN_PEDIDOS_DIJKSTRA:
                    res_ruta = Pathfinding.calcular_estrategia_orden_pedidos(
                        grafo,
                        pk.posicion_actual,
                        destinos_pasillo,
                        destino_retorno=nodo_despacho,
                        warehouse=warehouse,
                    )
                else:
                    res_ruta = Pathfinding.calcular_estrategia_cercania_multidestino(
                        grafo,
                        pk.posicion_actual,
                        destinos_pasillo,
                        destino_retorno=nodo_despacho,
                        warehouse=warehouse,
                    )

                tarea = TareaWavePicker(
                    id_wave=w.id_wave,
                    id_zona_despacho=w.id_zona_despacho or "ZONA_A",
                    destino_despacho_pasillo=nodo_despacho,
                    pedidos_asignados=w.pedidos_por_picker.get(pk.id_picker, []),
                    destinos_recoleccion_pasillo=destinos_pasillo,
                    peso_lote_kg=w.peso_por_picker.get(pk.id_picker, 0.0),
                    ruta_calculada=res_ruta.camino_completo,
                    resultado_ruta=res_ruta,
                )
                pk.cola_waves_asignadas.append(tarea)
                pk.iniciar_siguiente_tarea_en_cola()
                rutas_por_picker[pk.id_picker] = res_ruta.camino_completo
                resultados_ruta_por_picker[pk.id_picker] = res_ruta

            resultado["waves_iniciadas"].append(w)
            resultado["asignaciones"].append(
                {
                    "id_wave": w.id_wave,
                    "ids_pickers": [p.id_picker for p in equipo_elegido],
                    "distancias_picker_a_wave": {
                        p.id_picker: dist_picker_wave.get((p.id_picker, w.id_wave), 0.0)
                        for p in equipo_elegido
                    },
                    "pedidos_por_picker": dict(w.pedidos_por_picker),
                    "peso_por_picker": dict(w.peso_por_picker),
                    "destinos_xy_por_picker": dict(w.destinos_xy_por_picker),
                    "rutas_por_picker": rutas_por_picker,
                    "resultados_ruta_por_picker": resultados_ruta_por_picker,
                }
            )

        return resultado

    def notificar_picker_descargo_en_despacho(
        self,
        id_wave: str,
        id_picker: str,
        waves_por_id: Dict[str, Wave],
        warehouse: Optional[Warehouse] = None,
    ) -> None:
        w = waves_por_id.get(id_wave)
        if w is None:
            return

        pendientes = self.pickers_pendientes_descarga.get(id_wave, set())
        pendientes.discard(id_picker)

        if warehouse is not None:
            peso_descargado = w.peso_por_picker.get(id_picker, 0.0)
            zona_obj = warehouse.zonas_despacho.get(w.id_zona_despacho)
            if zona_obj is not None:
                zona_obj.registrar_descarga_fisica(peso_descargado)

            ids_ped_picker = set(w.pedidos_por_picker.get(id_picker, []))
            for ped in w.pedidos:
                if (
                    ped.id_pedido in ids_ped_picker
                    and ped.estado != EstadoPedido.PREPARADO
                ):
                    for item in ped.items:
                        warehouse.descontar_stock(item.producto_id, item.cantidad)
                    warehouse.actualizar_estado_pedido_O1(
                        ped.id_pedido, EstadoPedido.PREPARADO
                    )

        if not pendientes:
            w.estado = EstadoWave.FINALIZADA
