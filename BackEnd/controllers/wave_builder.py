from typing import Any, Dict, List, Optional, Set, Tuple

from BackEnd.controllers.path_finding import Pathfinding
from BackEnd.data_structures.max_heap_pedidos import MaxHeapPedidos
from BackEnd.enums.enums import EstadoPedido, EstadoWave
from BackEnd.models.entities import Pedido, Picker, Wave, ZonaDespacho
from BackEnd.models.warehouse import Warehouse

CoordXY = Tuple[int, int]

ESTRATEGIAS_ARMADO = {
    "CERCANIA": "Cercanía en el dígrafo (costo marginal promedio)",
    "PASILLO": "Por pasillo (el que agrega menos pasillos nuevos)",
    "PRIORIDAD": "Solo prioridad (sin mirar la ubicación)",
}

OPCIONES_ESTRATEGIA_ARMADO = {
    "AUTO": "Automática (compara las 3 y elige la mejor)",
    **ESTRATEGIAS_ARMADO,
}


class WaveBuilder:
    """Agrupa pedidos pendientes en waves usando un Max-Heap y criterios de afinidad espacial."""

    def __init__(
        self,
        wave_max_pedidos: int,
        wave_max_productos: int,
        prefijo_id_wave: str = "WAVE",
        incluir_altura_z_unica: bool = True,
        max_pickers_por_wave: int = 2,
        proveedor_distancias: Optional[Any] = None,
        estrategia_armado: str = "CERCANIA",
    ) -> None:
        if estrategia_armado not in ESTRATEGIAS_ARMADO:
            raise ValueError(
                "Estrategia de armado desconocida: " + str(estrategia_armado)
            )
        self.estrategia_armado = estrategia_armado
        self.cola_prioridad = MaxHeapPedidos()
        self.wave_max_pedidos = wave_max_pedidos
        self.wave_max_productos = wave_max_productos
        self.prefijo_id_wave = prefijo_id_wave
        self.incluir_altura_z_unica = incluir_altura_z_unica
        self.max_pickers_por_wave = max(1, int(max_pickers_por_wave))
        self.proveedor_distancias = proveedor_distancias

        self.errores_validacion: List[str] = []
        self.pedidos_descartados: List[Pedido] = []
        self.traza_armado: Dict[str, List[Dict[str, Any]]] = {}

    def preparar_fuente_distancias_O1(
        self,
        pedidos_validos: List[Pedido],
        warehouse: Warehouse,
        proveedor: Optional[Any],
    ) -> Any:
        fuente = proveedor if proveedor is not None else self.proveedor_distancias
        if fuente is None:
            fuente = warehouse.grafo_pasillos

        es_grafo_directo = hasattr(fuente, "obtener_vecinos_validos") or hasattr(
            fuente, "lista_adyacencia"
        )
        if not es_grafo_directo:
            return fuente

        coords_xy_requeridas: Set[CoordXY] = set()
        for pedido in pedidos_validos:
            for x, y, _ in pedido.obtener_ubicaciones_xyz(warehouse):
                coords_xy_requeridas.add((x, y))

        if not coords_xy_requeridas:
            return {}

        return Pathfinding.construir_matriz_distancias_productos(
            coordenadas_productos_xy=coords_xy_requeridas,
            grafo=fuente,
            warehouse=warehouse,
        )

    def obtener_distancia_dirigida(
        self,
        origen: CoordXY,
        destino: CoordXY,
        proveedor: Optional[Any] = None,
    ) -> float:
        if origen == destino:
            return 0.0

        fuente = proveedor if proveedor is not None else self.proveedor_distancias
        if fuente is not None and isinstance(fuente, dict):
            if (origen, destino) in fuente:
                return float(fuente[(origen, destino)])
            if origen in fuente and isinstance(fuente[origen], dict):
                return float(fuente[origen].get(destino, float("inf")))
            return float("inf")

        return float(abs(origen[0] - destino[0]) + abs(origen[1] - destino[1]))

    def distancia_enlace_digrafo(
        self,
        p_xy: CoordXY,
        u_xy: CoordXY,
        proveedor: Optional[Any] = None,
    ) -> float:
        d_ida = self.obtener_distancia_dirigida(u_xy, p_xy, proveedor)
        d_vuelta = self.obtener_distancia_dirigida(p_xy, u_xy, proveedor)
        return min(d_ida, d_vuelta)

    def es_pedido_internamente_alcanzable(
        self,
        pedido: Pedido,
        warehouse: Warehouse,
        proveedor: Optional[Any] = None,
    ) -> bool:
        fuente = proveedor if proveedor is not None else self.proveedor_distancias
        if fuente is None:
            return True

        coords_xy = list(
            {(x, y) for x, y, _ in pedido.obtener_ubicaciones_xyz(warehouse)}
        )
        if len(coords_xy) <= 1:
            return True

        ancla = coords_xy[0]
        for otra in coords_xy[1:]:
            if self.distancia_enlace_digrafo(otra, ancla, fuente) == float("inf"):
                return False
        return True

    @staticmethod
    def obtener_zonas_despacho_salida(warehouse: Warehouse) -> List[ZonaDespacho]:
        if warehouse is None or not hasattr(warehouse, "zonas_despacho"):
            return []
        zonas_salida: List[ZonaDespacho] = []
        for zd in warehouse.zonas_despacho.values():
            puerta = warehouse.puertas.get(zd.puerta_id)
            if puerta is None or puerta.permite_despacho_salida():
                zonas_salida.append(zd)
        return zonas_salida if zonas_salida else list(warehouse.zonas_despacho.values())

    def seleccionar_zona_despacho_para_wave(
        self,
        warehouse: Warehouse,
        pedido_semilla: Pedido,
    ) -> Optional[ZonaDespacho]:
        zonas = self.obtener_zonas_despacho_salida(warehouse)
        if not zonas:
            return None

        peso_semilla = pedido_semilla.obtener_peso_total(warehouse)
        ubics = list(pedido_semilla.obtener_ubicaciones_xyz(warehouse))
        cx = sum(x for x, _, _ in ubics) / len(ubics) if ubics else 0.0
        cy = sum(y for _, y, _ in ubics) / len(ubics) if ubics else 0.0

        zonas_con_capacidad = [z for z in zonas if z.puede_recibir_carga(peso_semilla)]
        if not zonas_con_capacidad:
            return None

        return min(
            zonas_con_capacidad,
            key=lambda z: (
                abs(z.x - cx) + abs(z.y - cy),
                z.peso_comprometido_waves_kg,
            ),
        )

    @staticmethod
    def tiene_stock_suficiente_sin_modificar(
        pedido: Pedido,
        warehouse: Warehouse,
        stock_comprometido: Dict[str, int],
    ) -> bool:
        acumulado_pedido: Dict[str, int] = {}
        for item in pedido.items:
            acumulado_pedido[item.producto_id] = (
                acumulado_pedido.get(item.producto_id, 0) + item.cantidad
            )

        for prod_id, cant_solicitada in acumulado_pedido.items():
            prod = warehouse.buscar_producto_O1(prod_id)
            if prod is None:
                return False
            reservado = stock_comprometido.get(prod_id, 0)
            if (prod.cantidad_disponible - reservado) < cant_solicitada:
                return False
        return True

    @staticmethod
    def registrar_compromiso_virtual(
        pedido: Pedido, stock_comprometido: Dict[str, int]
    ) -> None:
        for item in pedido.items:
            stock_comprometido[item.producto_id] = (
                stock_comprometido.get(item.producto_id, 0) + item.cantidad
            )

    @staticmethod
    def es_repartible_en_equipo_pickers(
        pedidos_wave: List[Pedido],
        pickers_disponibles: List[Picker],
        warehouse: Warehouse,
        max_pickers_por_wave: int,
        pesos_precalculados: Optional[List[float]] = None,
    ) -> Tuple[bool, List[Picker]]:
        if not pickers_disponibles:
            return True, []

        if pesos_precalculados is not None:
            pesos_pedidos = sorted(pesos_precalculados, reverse=True)
        else:
            pesos_pedidos = sorted(
                [p.obtener_peso_total(warehouse) for p in pedidos_wave],
                reverse=True,
            )

        pickers_ordenados = sorted(
            pickers_disponibles, key=lambda pk: pk.capacidad_carga_kg, reverse=True
        )
        k_max = min(max_pickers_por_wave, len(pickers_ordenados))

        for cant_pickers in range(1, k_max + 1):
            equipo = pickers_ordenados[:cant_pickers]
            cargas = [0.0] * cant_pickers
            exito = True

            for peso in pesos_pedidos:
                indices_validos = [
                    i
                    for i in range(cant_pickers)
                    if (cargas[i] + peso) <= equipo[i].capacidad_carga_kg
                ]
                if not indices_validos:
                    exito = False
                    break
                mejor_idx = min(indices_validos, key=lambda i: cargas[i])
                cargas[mejor_idx] += peso

            if exito:
                return True, equipo

        return False, []

    def validar_pedidos_entrada(
        self,
        pedidos: List[Pedido],
        warehouse: Warehouse,
    ) -> List[Pedido]:
        pedidos_validos: List[Pedido] = []
        max_cap_individual = (
            max((p.capacidad_carga_kg for p in warehouse.pickers), default=float("inf"))
            if warehouse.pickers
            else float("inf")
        )

        for pedido in pedidos:
            if pedido.estado != EstadoPedido.PENDIENTE:
                continue

            cant_productos = pedido.obtener_cantidad_productos()
            if cant_productos <= 0 or cant_productos > self.wave_max_productos:
                self._marcar_pedido_irrealizable(
                    pedido,
                    f"El pedido '{pedido.id_pedido}' solicita {cant_productos} unidades "
                    f"(el máximo por wave es {self.wave_max_productos}).",
                    warehouse,
                )
                continue

            ubicaciones = pedido.obtener_ubicaciones_xyz(warehouse)
            if not ubicaciones:
                self._marcar_pedido_irrealizable(
                    pedido,
                    f"El pedido '{pedido.id_pedido}' contiene productos sin ubicación válida.",
                    warehouse,
                )
                continue

            peso_ped = pedido.obtener_peso_total(warehouse)
            if peso_ped > max_cap_individual:
                self._marcar_pedido_irrealizable(
                    pedido,
                    f"El pedido '{pedido.id_pedido}' pesa {peso_ped:.2f} kg y supera la "
                    f"capacidad máxima de un picker ({max_cap_individual:.2f} kg).",
                    warehouse,
                )
                continue

            if not self.tiene_stock_suficiente_sin_modificar(pedido, warehouse, {}):
                self._marcar_pedido_irrealizable(
                    pedido,
                    f"El pedido '{pedido.id_pedido}' supera el stock total disponible en el almacén.",
                    warehouse,
                )
                continue

            pedidos_validos.append(pedido)

        return pedidos_validos

    def _marcar_pedido_irrealizable(
        self, pedido: Pedido, mensaje_error: str, warehouse: Warehouse
    ) -> None:
        self.errores_validacion.append(mensaje_error)
        self.pedidos_descartados.append(pedido)
        pedido.estado = EstadoPedido.IRREALIZABLE
        warehouse.actualizar_estado_pedido_O1(
            pedido.id_pedido, EstadoPedido.IRREALIZABLE
        )

    def calcular_costo_marginal_promedio(
        self,
        wave: Wave,
        pedido_candidato: Pedido,
        warehouse: Warehouse,
        proveedor_distancias: Optional[Any] = None,
    ) -> float:
        u_cand = pedido_candidato.obtener_ubicaciones_xyz(warehouse)
        if not u_cand:
            return float("inf")

        u_wave_xyz = wave.ubicaciones_xyz
        u_wave_xy = wave.ubicaciones_xy

        if not u_wave_xy:
            return 0.0

        suma_distancias_minimas = 0.0

        for px, py, pz in u_cand:
            if (px, py, pz) in u_wave_xyz:
                dist_p = 0.0
            else:
                if (px, py) in u_wave_xy:
                    dist_xy_min = 0.0
                else:
                    dist_xy_min = min(
                        self.distancia_enlace_digrafo(
                            (px, py), (ux, uy), proveedor_distancias
                        )
                        for ux, uy in u_wave_xy
                    )

                if dist_xy_min == float("inf"):
                    return float("inf")

                costo_z_unico = float(pz) if self.incluir_altura_z_unica else 0.0
                dist_p = dist_xy_min + costo_z_unico

            suma_distancias_minimas += dist_p

        return round(suma_distancias_minimas / len(u_cand), 6)

    @staticmethod
    def pasillos_de(pedido: Pedido, warehouse: Warehouse) -> Set[str]:
        """Identificadores de pasillo desde los que se accede a los productos del pedido."""
        pasillos: Set[str] = set()
        for x, y, _ in pedido.obtener_ubicaciones_xyz(warehouse):
            acceso = warehouse.obtener_celda_acceso_pasillo(x, y)
            nodo = warehouse.grafo_pasillos.nodos.get(acceso) if acceso else None
            pasillos.add(nodo.pasillo_id if nodo and nodo.pasillo_id else f"x{x}")
        return pasillos

    def generar_waves(
        self,
        warehouse: Warehouse,
        proveedor_distancias: Optional[Any] = None,
    ) -> Tuple[List[Wave], Dict[str, Wave]]:
        self.errores_validacion.clear()
        self.pedidos_descartados.clear()
        self.traza_armado.clear()
        waves_creadas: List[Wave] = []
        waves_por_id: Dict[str, Wave] = {}

        pedidos = warehouse.obtener_todos_los_pedidos()
        if not pedidos:
            return waves_creadas, waves_por_id

        for zd in warehouse.zonas_despacho.values():
            zd.peso_comprometido_waves_kg = 0.0

        pedidos_validos = self.validar_pedidos_entrada(pedidos, warehouse)
        if not pedidos_validos:
            return waves_creadas, waves_por_id

        fuente_dist = self.preparar_fuente_distancias_O1(
            pedidos_validos, warehouse, proveedor_distancias
        )

        self.cola_prioridad.construir_monticulo(pedidos_validos)

        stock_comprometido_virtual: Dict[str, int] = {}
        contador_wave = 1

        while not self.cola_prioridad.esta_vacio():
            pedido_raiz = self.cola_prioridad.extraer_maximo()
            if pedido_raiz is None:
                break

            if not self.es_pedido_internamente_alcanzable(
                pedido_raiz, warehouse, fuente_dist
            ):
                self._marcar_pedido_irrealizable(
                    pedido_raiz,
                    f"El pedido '{pedido_raiz.id_pedido}' tiene productos en pasillos desconectados.",
                    warehouse,
                )
                continue

            if not self.tiene_stock_suficiente_sin_modificar(
                pedido_raiz, warehouse, stock_comprometido_virtual
            ):
                self._marcar_pedido_irrealizable(
                    pedido_raiz,
                    f"Stock insuficiente para '{pedido_raiz.id_pedido}' tras reservar "
                    f"unidades para pedidos de mayor prioridad.",
                    warehouse,
                )
                continue

            zona_obj = self.seleccionar_zona_despacho_para_wave(warehouse, pedido_raiz)
            if zona_obj is None:
                self.errores_validacion.append(
                    f"Capacidad de zonas de despacho agotada al intentar ubicar '{pedido_raiz.id_pedido}'."
                )
                continue

            id_wave_actual = f"{self.prefijo_id_wave}_{contador_wave:02d}"
            peso_raiz = pedido_raiz.obtener_peso_total(warehouse)

            nueva_wave = Wave(
                id_wave=id_wave_actual,
                estado=EstadoWave.PENDIENTE,
                wave_max_pedidos=self.wave_max_pedidos,
                wave_max_productos=self.wave_max_productos,
                id_zona_despacho=zona_obj.id,
            )

            nueva_wave.agregar_pedido(pedido_raiz, warehouse_o_tabla=warehouse)
            self.registrar_compromiso_virtual(pedido_raiz, stock_comprometido_virtual)
            zona_obj.comprometer_carga_wave(peso_raiz)

            self.traza_armado[id_wave_actual] = [
                {
                    "rol": "RAIZ_MAX_HEAP",
                    "id_pedido": pedido_raiz.id_pedido,
                    "prioridad": pedido_raiz.prioridad,
                    "unidades": pedido_raiz.obtener_cantidad_productos(),
                    "peso_kg": peso_raiz,
                    "score_marginal": 0.0,
                    "candidatos_evaluados": 1,
                }
            ]

            motivo_fin = ""
            while True:
                if len(nueva_wave.pedidos) >= self.wave_max_pedidos:
                    motivo_fin = (
                        f"Llegó al máximo de {self.wave_max_pedidos} pedidos por wave."
                    )
                    break

                capacidad_restante = (
                    self.wave_max_productos - nueva_wave.unidades_totales
                )
                if capacidad_restante <= 0:
                    motivo_fin = (
                        f"Llegó al máximo de {self.wave_max_productos} unidades."
                    )
                    break

                candidatos_factibles = self.cola_prioridad.obtener_candidatos_factibles(
                    capacidad_restante
                )
                if not candidatos_factibles:
                    motivo_fin = (
                        f"Ningún pedido pendiente entra en las {capacidad_restante} unidades libres."
                        if self.cola_prioridad.tamano()
                        else "No quedan pedidos pendientes."
                    )
                    break

                pasillos_wave: Set[str] = set()
                if self.estrategia_armado == "PASILLO":
                    for ped in nueva_wave.pedidos:
                        pasillos_wave |= self.pasillos_de(ped, warehouse)

                mejor_candidato: Optional[Pedido] = None
                mejor_tupla_criterio: Optional[Tuple[float, int, str]] = None
                mejor_score: float = float("inf")
                evaluados_validos = 0
                ranking: List[Tuple[Tuple[float, int, str], Pedido]] = []

                pesos_wave_base = [p.obtener_peso_total(warehouse) for p in nueva_wave.pedidos]

                for cand in candidatos_factibles:
                    if not self.tiene_stock_suficiente_sin_modificar(
                        cand, warehouse, stock_comprometido_virtual
                    ):
                        continue

                    peso_cand = cand.obtener_peso_total(warehouse)
                    if not zona_obj.puede_recibir_carga(peso_cand):
                        continue

                    if warehouse.pickers:
                        pesos_evaluacion = pesos_wave_base + [peso_cand]
                        es_repartible, _ = self.es_repartible_en_equipo_pickers(
                            [],
                            warehouse.pickers,
                            warehouse,
                            self.max_pickers_por_wave,
                            pesos_precalculados=pesos_evaluacion
                        )
                        if not es_repartible:
                            continue

                    if self.estrategia_armado == "CERCANIA":
                        score = self.calcular_costo_marginal_promedio(
                            nueva_wave, cand, warehouse, fuente_dist
                        )
                    elif self.estrategia_armado == "PASILLO":
                        score = float(
                            len(self.pasillos_de(cand, warehouse) - pasillos_wave)
                        )
                    else:
                        score = 0.0

                    if score == float("inf"):
                        continue

                    evaluados_validos += 1
                    criterio_actual = (score, -cand.prioridad, cand.id_pedido)
                    ranking.append((criterio_actual, cand))
                    if (
                        mejor_tupla_criterio is None
                        or criterio_actual < mejor_tupla_criterio
                    ):
                        mejor_tupla_criterio = criterio_actual
                        mejor_candidato = cand
                        mejor_score = score

                if mejor_candidato is None:
                    motivo_fin = (
                        "Los pedidos que entran no tienen stock remanente, no caben en la zona "
                        "o exceden la capacidad de carga de los pickers."
                    )
                    break

                peso_mejor = mejor_candidato.obtener_peso_total(warehouse)
                nueva_wave.agregar_pedido(mejor_candidato, warehouse_o_tabla=warehouse)
                self.registrar_compromiso_virtual(
                    mejor_candidato, stock_comprometido_virtual
                )
                zona_obj.comprometer_carga_wave(peso_mejor)

                nueva_wave.costo_mst_total = round(
                    nueva_wave.costo_mst_total + mejor_score, 4
                )
                self.cola_prioridad.eliminar_pedido(mejor_candidato.id_pedido)

                self.traza_armado[id_wave_actual].append(
                    {
                        "rol": self.estrategia_armado,
                        "id_pedido": mejor_candidato.id_pedido,
                        "prioridad": mejor_candidato.prioridad,
                        "unidades": mejor_candidato.obtener_cantidad_productos(),
                        "peso_kg": peso_mejor,
                        "score_marginal": mejor_score,
                        "candidatos_evaluados": evaluados_validos,
                        "factibles": len(candidatos_factibles),
                        "ranking": [
                            {
                                "id_pedido": c.id_pedido,
                                "score": crit[0],
                                "prioridad": c.prioridad,
                            }
                            for crit, c in sorted(ranking, key=lambda t: t[0])[:6]
                        ],
                    }
                )

            self.traza_armado[id_wave_actual].append(
                {"rol": "FIN", "motivo": motivo_fin}
            )
            waves_creadas.append(nueva_wave)
            waves_por_id[nueva_wave.id_wave] = nueva_wave
            contador_wave += 1

        return waves_creadas, waves_por_id
