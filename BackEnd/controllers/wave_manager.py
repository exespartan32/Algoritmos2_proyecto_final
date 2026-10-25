from typing import List, Optional, Tuple, Set, Any, Dict
from BackEnd.models.entities import Pedido, Wave, Picker, ZonaDespacho, TareaWavePicker
from BackEnd.models.warehouse import Warehouse
from BackEnd.enums.enums import EstadoWave, EstadoPedido, EstrategiaRuteo
from BackEnd.data_structures.max_heap_pedidos import MaxHeapPedidos
from BackEnd.controllers.path_finding import Pathfinding

CoordXY = Tuple[int, int]


class WaveManager:
    """
    Controlador de Generación, Selección Interactiva y Asignación de Waves:
    - Consume directamente el objeto Warehouse de Laureano (sin CatalogManager).
    - Usa Max-Heap O(log N) + Costo Marginal Promedio (Average Linkage) con matriz APSP O(1).
    - NO modifica el stock real al armar las Waves (el descuento ocurre recién al descargar en despacho).
    - PROHÍBE mezclar dos Waves en un mismo viaje de un Picker (1 Wave por Picker activo).
    """

    def __init__(
        self,
        wave_max_pedidos: int,
        wave_max_productos: int,
        prefijo_id_wave: str = "WAVE",
        incluir_altura_z_unica: bool = True,
        max_pickers_por_wave: int = 2,
        proveedor_distancias: Optional[Any] = None,
    ) -> None:
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

        self.waves_creadas: List[Wave] = []
        self.waves_por_id: Dict[str, Wave] = {}
        self._pickers_pendientes_descarga: Dict[str, Set[str]] = {}

    def _preparar_fuente_distancias_O1(
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

    def _obtener_distancia_dirigida(
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

    def _distancia_enlace_digrafo(
        self,
        p_xy: CoordXY,
        u_xy: CoordXY,
        proveedor: Optional[Any] = None,
    ) -> float:
        d_ida = self._obtener_distancia_dirigida(u_xy, p_xy, proveedor)
        d_vuelta = self._obtener_distancia_dirigida(p_xy, u_xy, proveedor)
        return min(d_ida, d_vuelta)

    def _es_pedido_internamente_alcanzable(
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
            if self._distancia_enlace_digrafo(otra, ancla, fuente) == float("inf"):
                return False
        return True

    def obtener_zonas_despacho_salida(self, warehouse: Warehouse) -> List[ZonaDespacho]:
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

    def _tiene_stock_suficiente_sin_modificar(
        self,
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

    def _registrar_compromiso_virtual(
        self, pedido: Pedido, stock_comprometido: Dict[str, int]
    ) -> None:
        for item in pedido.items:
            stock_comprometido[item.producto_id] = (
                stock_comprometido.get(item.producto_id, 0) + item.cantidad
            )

    def _es_repartible_en_equipo_pickers(
        self,
        pedidos_wave: List[Pedido],
        pickers_disponibles: List[Picker],
        warehouse: Warehouse,
    ) -> Tuple[bool, List[Picker]]:
        if not pickers_disponibles:
            return True, []

        pesos_pedidos = sorted(
            [p.obtener_peso_total(warehouse) for p in pedidos_wave],
            reverse=True,
        )
        pickers_ordenados = sorted(
            pickers_disponibles, key=lambda pk: pk.capacidad_carga_kg, reverse=True
        )
        k_max = min(self.max_pickers_por_wave, len(pickers_ordenados))

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
                    f"Error de Caso Borde: El pedido '{pedido.id_pedido}' solicita "
                    f"{cant_productos} productos, fuera del rango permitido (1..{self.wave_max_productos}).",
                    warehouse,
                )
                continue

            ubicaciones = pedido.obtener_ubicaciones_xyz(warehouse)
            if not ubicaciones:
                self._marcar_pedido_irrealizable(
                    pedido,
                    f"Error de Datos: El pedido '{pedido.id_pedido}' no tiene ubicaciones válidas.",
                    warehouse,
                )
                continue

            peso_ped = pedido.obtener_peso_total(warehouse)
            if peso_ped > max_cap_individual:
                self._marcar_pedido_irrealizable(
                    pedido,
                    f"Error de Peso Físico: El pedido '{pedido.id_pedido}' pesa {peso_ped:.2f} kg "
                    f"y supera la capacidad del mayor picker ({max_cap_individual:.2f} kg).",
                    warehouse,
                )
                continue

            if not self._tiene_stock_suficiente_sin_modificar(pedido, warehouse, {}):
                self._marcar_pedido_irrealizable(
                    pedido,
                    f"Error de Stock: El pedido '{pedido.id_pedido}' supera el stock disponible.",
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
                        self._distancia_enlace_digrafo(
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

    def generar_waves(
        self,
        warehouse: Warehouse,
        proveedor_distancias: Optional[Any] = None,
    ) -> List[Wave]:
        self.errores_validacion.clear()
        self.pedidos_descartados.clear()
        self.traza_armado.clear()
        self.waves_creadas.clear()
        self.waves_por_id.clear()

        pedidos = warehouse.obtener_todos_los_pedidos()
        if not pedidos:
            return []

        for zd in warehouse.zonas_despacho.values():
            zd.peso_comprometido_waves_kg = 0.0

        pedidos_validos = self.validar_pedidos_entrada(pedidos, warehouse)
        if not pedidos_validos:
            return []

        fuente_dist = self._preparar_fuente_distancias_O1(
            pedidos_validos, warehouse, proveedor_distancias
        )

        self.cola_prioridad.construir_monticulo(pedidos_validos)

        stock_comprometido_virtual: Dict[str, int] = {}
        contador_wave = 1

        while not self.cola_prioridad.esta_vacio():
            pedido_raiz = self.cola_prioridad.extraer_maximo()
            if pedido_raiz is None:
                break

            if not self._es_pedido_internamente_alcanzable(
                pedido_raiz, warehouse, fuente_dist
            ):
                self._marcar_pedido_irrealizable(
                    pedido_raiz,
                    f"Error de Topología: El pedido '{pedido_raiz.id_pedido}' contiene ubicaciones inalcanzables.",
                    warehouse,
                )
                continue

            if not self._tiene_stock_suficiente_sin_modificar(
                pedido_raiz, warehouse, stock_comprometido_virtual
            ):
                self._marcar_pedido_irrealizable(
                    pedido_raiz,
                    f"Stock Insuficiente: El pedido '{pedido_raiz.id_pedido}' excede el stock remanente.",
                    warehouse,
                )
                continue

            zona_obj = self.seleccionar_zona_despacho_para_wave(warehouse, pedido_raiz)
            if zona_obj is None:
                self.errores_validacion.append(
                    f"Capacidad de Despacho Agotada para el pedido '{pedido_raiz.id_pedido}'."
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
            self._registrar_compromiso_virtual(pedido_raiz, stock_comprometido_virtual)
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

            while True:
                if len(nueva_wave.pedidos) >= self.wave_max_pedidos:
                    break

                capacidad_restante = (
                    self.wave_max_productos - nueva_wave.unidades_totales
                )
                if capacidad_restante <= 0:
                    break

                candidatos_factibles = self.cola_prioridad.obtener_candidatos_factibles(
                    capacidad_restante
                )
                if not candidatos_factibles:
                    break

                mejor_candidato: Optional[Pedido] = None
                mejor_tupla_criterio: Optional[Tuple[float, int, str]] = None
                mejor_score: float = float("inf")
                evaluados_validos = 0

                for cand in candidatos_factibles:
                    if not self._tiene_stock_suficiente_sin_modificar(
                        cand, warehouse, stock_comprometido_virtual
                    ):
                        continue

                    peso_cand = cand.obtener_peso_total(warehouse)
                    if not zona_obj.puede_recibir_carga(peso_cand):
                        continue

                    if warehouse.pickers:
                        es_repartible, _ = self._es_repartible_en_equipo_pickers(
                            nueva_wave.pedidos + [cand], warehouse.pickers, warehouse
                        )
                        if not es_repartible:
                            continue

                    score = self.calcular_costo_marginal_promedio(
                        nueva_wave, cand, warehouse, fuente_dist
                    )
                    if score == float("inf"):
                        continue

                    evaluados_validos += 1
                    criterio_actual = (score, -cand.prioridad, cand.id_pedido)
                    if (
                        mejor_tupla_criterio is None
                        or criterio_actual < mejor_tupla_criterio
                    ):
                        mejor_tupla_criterio = criterio_actual
                        mejor_candidato = cand
                        mejor_score = score

                if mejor_candidato is None:
                    break

                peso_mejor = mejor_candidato.obtener_peso_total(warehouse)
                nueva_wave.agregar_pedido(mejor_candidato, warehouse_o_tabla=warehouse)
                self._registrar_compromiso_virtual(
                    mejor_candidato, stock_comprometido_virtual
                )
                zona_obj.comprometer_carga_wave(peso_mejor)

                nueva_wave.costo_mst_total = round(
                    nueva_wave.costo_mst_total + mejor_score, 4
                )
                self.cola_prioridad.eliminar_pedido(mejor_candidato.id_pedido)

                self.traza_armado[id_wave_actual].append(
                    {
                        "rol": "CERCANIA_DIGRAFO",
                        "id_pedido": mejor_candidato.id_pedido,
                        "prioridad": mejor_candidato.prioridad,
                        "unidades": mejor_candidato.obtener_cantidad_productos(),
                        "peso_kg": peso_mejor,
                        "score_marginal": mejor_score,
                        "candidatos_evaluados": evaluados_validos,
                    }
                )

            self.waves_creadas.append(nueva_wave)
            self.waves_por_id[nueva_wave.id_wave] = nueva_wave
            contador_wave += 1

        return self.waves_creadas

    def obtener_waves_disponibles(self) -> List[Wave]:
        return [w for w in self.waves_creadas if w.estado == EstadoWave.PENDIENTE]

    def obtener_waves_en_ejecucion(self) -> List[Wave]:
        return [w for w in self.waves_creadas if w.estado == EstadoWave.EN_EJECUCION]

    @staticmethod
    def obtener_pickers_libres(pickers: List[Picker]) -> List[Picker]:
        return [p for p in pickers if p.id_wave_actual is None]

    def calcular_distancia_picker_a_wave(
        self,
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

    def asignar_y_ejecutar_waves_seleccionadas(
        self,
        ids_waves_seleccionadas: List[str],
        warehouse: Warehouse,
        estrategia_ruteo: EstrategiaRuteo = EstrategiaRuteo.CERCANIA_DIJKSTRA_MULTIDESTINO,
    ) -> Dict[str, Any]:
        grafo = warehouse.grafo_pasillos
        pickers = warehouse.pickers

        waves_elegidas: List[Wave] = []
        for wid in ids_waves_seleccionadas:
            w = self.waves_por_id.get(wid)
            if (
                w is not None
                and w.estado == EstadoWave.PENDIENTE
                and w not in waves_elegidas
            ):
                waves_elegidas.append(w)

        pickers_libres = self.obtener_pickers_libres(pickers)

        resultado = {
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
            if candidatos_cercanos[0].capacidad_carga_kg >= w.peso_total_kg:
                equipo_elegido = [candidatos_cercanos[0]]
            else:
                for pk in candidatos_cercanos:
                    if pk.capacidad_carga_kg >= w.peso_total_kg:
                        equipo_elegido = [pk]
                        break
                if not equipo_elegido:
                    factible, equipo_multi = self._es_repartible_en_equipo_pickers(
                        w.pedidos, candidatos_cercanos, warehouse
                    )
                    if factible and equipo_multi:
                        equipo_elegido = equipo_multi

            if not equipo_elegido:
                resultado["waves_sin_picker_disponible"].append(w.id_wave)
                continue

            for pk in equipo_elegido:
                pickers_libres.remove(pk)

            w.asignar_equipo_pickers(equipo_elegido, warehouse)
            w.estado = EstadoWave.EN_EJECUCION
            self._pickers_pendientes_descarga[w.id_wave] = {
                p.id_picker for p in equipo_elegido
            }

            accesos_despacho = warehouse.obtener_nodos_acceso_zona(w.id_zona_despacho)

            rutas_por_picker: Dict[str, List[CoordXY]] = {}
            for idx_pk, pk in enumerate(equipo_elegido):
                destinos_rack = w.destinos_xy_por_picker.get(pk.id_picker, [])
                destinos_pasillo = [
                    Pathfinding.obtener_celda_acceso_pasillo(c, grafo, warehouse)
                    for c in destinos_rack
                ]
                nodo_despacho = (
                    accesos_despacho[idx_pk % len(accesos_despacho)]
                    if accesos_despacho
                    else pk.posicion_actual
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
                )
                pk.cola_waves_asignadas.append(tarea)
                pk.iniciar_siguiente_tarea_en_cola()
                rutas_por_picker[pk.id_picker] = res_ruta.camino_completo

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
                }
            )

        return resultado

    def notificar_picker_descargo_en_despacho(
        self,
        id_wave: str,
        id_picker: str,
        pickers: List[Picker],
        warehouse: Optional[Warehouse] = None,
    ) -> None:
        w = self.waves_por_id.get(id_wave)
        if w is None:
            return

        pendientes = self._pickers_pendientes_descarga.get(id_wave, set())
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
