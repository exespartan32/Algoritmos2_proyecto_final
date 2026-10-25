from typing import List, Optional, Tuple, Set, Any, Dict
from BackEnd.models.entities import Pedido, Wave, Picker
from BackEnd.enums.enums import EstadoWave, EstadoPedido
from BackEnd.data_structures.max_heap_pedidos import MaxHeapPedidos
from BackEnd.controllers.path_finding import Pathfinding

CoordXY = Tuple[int, int]


class WaveManager:
    """
    Controlador de Generación, Selección Interactiva yAsignación de Waves:
    1. generar_waves(): Arma todas las Waves en estado PENDIENTE (sin descontar stock).
    2. obtener_waves_disponibles(): Lista las Waves en estado PENDIENTE para mostrar en UI/Consola.
    3. asignar_y_ejecutar_waves_seleccionadas(): Recibe los IDs de las Waves elegidas por el
       usuario y las asigna a los Pickers libres MÁS CERCANOS en el dígrafo.
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

        # Almacén interno de todas las Waves generadas para consulta desde Pygame o Consola
        self.waves_creadas: List[Wave] = []
        self.waves_por_id: Dict[str, Wave] = {}

    # =========================================================================
    # 0. INTEGRACIÓN CON EL DÍGRAFO Y PATHFINDING (CONSULTA O(1))
    # =========================================================================
    def _preparar_fuente_distancias_O1(
        self,
        pedidos_validos: List[Pedido],
        tabla_productos: Any,
        proveedor: Optional[Any],
    ) -> Any:
        fuente = proveedor if proveedor is not None else self.proveedor_distancias
        if fuente is None:
            return None

        es_grafo_directo = hasattr(fuente, "obtener_vecinos_validos") or hasattr(
            fuente, "lista_adyacencia"
        )
        if not es_grafo_directo:
            return fuente

        coords_xy_requeridas: Set[CoordXY] = set()
        for pedido in pedidos_validos:
            for x, y, _ in pedido.obtener_ubicaciones_xyz(tabla_productos):
                coords_xy_requeridas.add((x, y))

        if not coords_xy_requeridas:
            return {}

        return Pathfinding.construir_matriz_distancias_productos(
            coordenadas_productos_xy=coords_xy_requeridas,
            grafo=fuente,
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

        if fuente is not None:
            if isinstance(fuente, dict):
                if (origen, destino) in fuente:
                    return float(fuente[(origen, destino)])
                if origen in fuente and isinstance(fuente[origen], dict):
                    return float(fuente[origen].get(destino, float("inf")))
                return float("inf")

            if hasattr(fuente, "obtener_distancia"):
                return float(fuente.obtener_distancia(origen, destino))

            if callable(fuente):
                return float(fuente(origen, destino))

            if hasattr(fuente, "obtener_vecinos_validos") or hasattr(
                fuente, "lista_adyacencia"
            ):
                orig_pasillo = Pathfinding.obtener_celda_acceso_pasillo(origen, fuente)
                dest_pasillo = Pathfinding.obtener_celda_acceso_pasillo(destino, fuente)
                if orig_pasillo == dest_pasillo:
                    return 0.0
                ruta, _ = Pathfinding.calcular_ruta_dijkstra(
                    orig_pasillo, dest_pasillo, fuente
                )
                return float(len(ruta) - 1) if ruta else float("inf")

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
        tabla_productos: Any,
        proveedor: Optional[Any] = None,
    ) -> bool:
        fuente = proveedor if proveedor is not None else self.proveedor_distancias
        if fuente is None:
            return True

        coords_xy = list(
            {(x, y) for x, y, _ in pedido.obtener_ubicaciones_xyz(tabla_productos)}
        )
        if len(coords_xy) <= 1:
            return True

        ancla = coords_xy[0]
        for otra in coords_xy[1:]:
            if self._distancia_enlace_digrafo(otra, ancla, fuente) == float("inf"):
                return False
        return True

    # =========================================================================
    # 1. VALIDACIÓN DE STOCK VIRTUAL Y FACTIBILIDAD DE PESO
    # =========================================================================
    def _tiene_stock_suficiente_sin_modificar(
        self,
        pedido: Pedido,
        tabla_productos: Any,
        stock_comprometido: Dict[str, int],
    ) -> bool:
        if tabla_productos is None:
            return True

        acumulado_pedido: Dict[str, int] = {}
        for item in pedido.items:
            acumulado_pedido[item.producto_id] = (
                acumulado_pedido.get(item.producto_id, 0) + item.cantidad
            )

        for prod_id, cant_solicitada in acumulado_pedido.items():
            prod = Pedido._buscar_producto(tabla_productos, prod_id)
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
        tabla_productos: Any,
    ) -> Tuple[bool, List[Picker]]:
        if not pickers_disponibles or tabla_productos is None:
            return True, []

        pesos_pedidos = sorted(
            [p.obtener_peso_total(tabla_productos) for p in pedidos_wave],
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
        tabla_productos: Any = None,
        catalogo: Any = None,
        pickers: Optional[List[Picker]] = None,
    ) -> List[Pedido]:
        pedidos_validos: List[Pedido] = []
        max_cap_individual = (
            max((p.capacidad_carga_kg for p in pickers), default=float("inf"))
            if pickers
            else float("inf")
        )

        for pedido in pedidos:
            if pedido.estado != EstadoPedido.PENDIENTE:
                continue

            cant_productos = pedido.obtener_cantidad_productos()
            if cant_productos <= 0 or cant_productos > self.wave_max_productos:
                mensaje_error = (
                    f"Error de Caso Borde: El pedido '{pedido.id_pedido}' solicita "
                    f"{cant_productos} productos, fuera del rango permitido "
                    f"(1..{self.wave_max_productos})."
                )
                self._marcar_pedido_irrealizable(pedido, mensaje_error, catalogo)
                continue

            if tabla_productos is not None:
                ubicaciones = pedido.obtener_ubicaciones_xyz(tabla_productos)
                if not ubicaciones:
                    mensaje_error = (
                        f"Error de Datos: El pedido '{pedido.id_pedido}' no tiene "
                        f"ubicaciones válidas en el catálogo."
                    )
                    self._marcar_pedido_irrealizable(pedido, mensaje_error, catalogo)
                    continue

                peso_ped = pedido.obtener_peso_total(tabla_productos)
                if peso_ped > max_cap_individual:
                    mensaje_error = (
                        f"Error de Peso Físico: El pedido '{pedido.id_pedido}' pesa "
                        f"{peso_ped:.2f} kg y supera la capacidad del mayor picker ({max_cap_individual:.2f} kg)."
                    )
                    self._marcar_pedido_irrealizable(pedido, mensaje_error, catalogo)
                    continue

                if not self._tiene_stock_suficiente_sin_modificar(
                    pedido, tabla_productos, {}
                ):
                    mensaje_error = (
                        f"Error de Stock: El pedido '{pedido.id_pedido}' solicita "
                        f"más unidades que el stock total inicial del Warehouse."
                    )
                    self._marcar_pedido_irrealizable(pedido, mensaje_error, catalogo)
                    continue

            pedidos_validos.append(pedido)

        return pedidos_validos

    def _marcar_pedido_irrealizable(
        self, pedido: Pedido, mensaje_error: str, catalogo: Any = None
    ) -> None:
        self.errores_validacion.append(mensaje_error)
        self.pedidos_descartados.append(pedido)
        pedido.estado = EstadoPedido.IRREALIZABLE

        if catalogo is not None and hasattr(catalogo, "actualizar_estado_pedido_O1"):
            catalogo.actualizar_estado_pedido_O1(
                pedido.id_pedido, EstadoPedido.IRREALIZABLE
            )

    # =========================================================================
    # 2. ALGORITMO DE CERCANÍA: COSTO MARGINAL PROMEDIO EN DÍGRAFO
    # =========================================================================
    def calcular_costo_marginal_promedio(
        self,
        wave: Wave,
        pedido_candidato: Pedido,
        tabla_productos: Any,
        proveedor_distancias: Optional[Any] = None,
    ) -> float:
        u_cand: Set[Tuple[int, int, int]] = pedido_candidato.obtener_ubicaciones_xyz(
            tabla_productos
        )
        if not u_cand:
            return float("inf")

        u_wave_xyz: Set[Tuple[int, int, int]] = wave.ubicaciones_xyz
        u_wave_xy: Set[CoordXY] = wave.ubicaciones_xy

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

        score = suma_distancias_minimas / len(u_cand)
        return round(score, 6)

    # =========================================================================
    # 3. ETAPA 1: ARMAR LAS WAVES (TODAS QUEDAN DISPONIBLES EN ESTADO PENDIENTE)
    # =========================================================================
    def generar_waves(
        self,
        pedidos: Optional[List[Pedido]] = None,
        tabla_productos: Any = None,
        catalogo: Any = None,
        pickers: Optional[List[Picker]] = None,
        proveedor_distancias: Optional[Any] = None,
    ) -> List[Wave]:
        """
        Paso 1 del flujo: Construye todas las Waves a partir de los pedidos pendientes
        y las deja en estado PENDIENTE (sin ejecutarlas todavía), listas para que el
        usuario o la interfaz de Pygame consulte las disponibles y seleccione cuáles lanzar.
        """
        self.errores_validacion.clear()
        self.pedidos_descartados.clear()
        self.traza_armado.clear()
        self.waves_creadas.clear()
        self.waves_por_id.clear()

        if (
            pedidos is None
            and catalogo is not None
            and hasattr(catalogo, "obtener_todos_los_pedidos")
        ):
            pedidos = catalogo.obtener_todos_los_pedidos()
        if tabla_productos is None and catalogo is not None:
            tabla_productos = catalogo
        if pickers is None and catalogo is not None:
            pickers = getattr(catalogo, "pickers", None)
        if (
            proveedor_distancias is None
            and catalogo is not None
            and getattr(catalogo, "digrafo", None) is not None
        ):
            proveedor_distancias = catalogo.digrafo

        if not pedidos:
            return []

        pedidos_validos = self.validar_pedidos_entrada(
            pedidos,
            tabla_productos=tabla_productos,
            catalogo=catalogo,
            pickers=pickers,
        )
        if not pedidos_validos:
            return []

        fuente_dist = self._preparar_fuente_distancias_O1(
            pedidos_validos, tabla_productos, proveedor_distancias
        )

        zonas_ids = (
            list(catalogo.digrafo.zonas_despacho.keys())
            if (catalogo is not None and getattr(catalogo, "digrafo", None) is not None)
            else ["ZONA_A"]
        )

        self.cola_prioridad.construir_monticulo(pedidos_validos)

        stock_comprometido_virtual: Dict[str, int] = {}
        contador_wave = 1

        while not self.cola_prioridad.esta_vacio():
            pedido_raiz = self.cola_prioridad.extraer_maximo()
            if pedido_raiz is None:
                break

            if not self._es_pedido_internamente_alcanzable(
                pedido_raiz, tabla_productos, fuente_dist
            ):
                self._marcar_pedido_irrealizable(
                    pedido_raiz,
                    f"Error de Topología: El pedido '{pedido_raiz.id_pedido}' "
                    f"contiene ubicaciones inalcanzables en el dígrafo.",
                    catalogo,
                )
                continue

            if not self._tiene_stock_suficiente_sin_modificar(
                pedido_raiz, tabla_productos, stock_comprometido_virtual
            ):
                self._marcar_pedido_irrealizable(
                    pedido_raiz,
                    f"Stock Insuficiente: El pedido '{pedido_raiz.id_pedido}' "
                    f"excede el stock remanente tras las Waves anteriores.",
                    catalogo,
                )
                continue

            id_wave_actual = f"{self.prefijo_id_wave}_{contador_wave:02d}"
            zona_asignada = (
                zonas_ids[(contador_wave - 1) % len(zonas_ids)]
                if zonas_ids
                else "ZONA_A"
            )

            nueva_wave = Wave(
                id_wave=id_wave_actual,
                estado=EstadoWave.PENDIENTE,
                wave_max_pedidos=self.wave_max_pedidos,
                wave_max_productos=self.wave_max_productos,
                id_zona_despacho=zona_asignada,
            )

            nueva_wave.agregar_pedido(pedido_raiz, tabla_productos, catalogo=catalogo)
            self._registrar_compromiso_virtual(pedido_raiz, stock_comprometido_virtual)

            self.traza_armado[id_wave_actual] = [
                {
                    "rol": "RAIZ_MAX_HEAP",
                    "id_pedido": pedido_raiz.id_pedido,
                    "prioridad": pedido_raiz.prioridad,
                    "unidades": pedido_raiz.obtener_cantidad_productos(),
                    "peso_kg": pedido_raiz.obtener_peso_total(tabla_productos),
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
                        cand, tabla_productos, stock_comprometido_virtual
                    ):
                        continue

                    if pickers:
                        es_repartible, _ = self._es_repartible_en_equipo_pickers(
                            nueva_wave.pedidos + [cand], pickers, tabla_productos
                        )
                        if not es_repartible:
                            continue

                    score = self.calcular_costo_marginal_promedio(
                        nueva_wave, cand, tabla_productos, fuente_dist
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

                nueva_wave.agregar_pedido(
                    mejor_candidato, tabla_productos, catalogo=catalogo
                )
                self._registrar_compromiso_virtual(
                    mejor_candidato, stock_comprometido_virtual
                )
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
                        "peso_kg": mejor_candidato.obtener_peso_total(tabla_productos),
                        "score_marginal": mejor_score,
                        "candidatos_evaluados": evaluados_validos,
                    }
                )

            self.waves_creadas.append(nueva_wave)
            self.waves_por_id[nueva_wave.id_wave] = nueva_wave
            contador_wave += 1

        return self.waves_creadas

    # =========================================================================
    # 4. ETAPA 2: CONSULTAR WAVES DISPONIBLES Y PICKERS LIBRES (PARA UI/CONSOLA)
    # =========================================================================
    def obtener_waves_disponibles(self) -> List[Wave]:
        """Devuelve todas las Waves armadas que están en estado PENDIENTE listas para seleccionarse."""
        return [w for w in self.waves_creadas if w.estado == EstadoWave.PENDIENTE]

    def obtener_waves_en_ejecucion(self) -> List[Wave]:
        """Devuelve las Waves que se están ejecutando simultáneamente en este momento."""
        return [w for w in self.waves_creadas if w.estado == EstadoWave.EN_EJECUCION]

    @staticmethod
    def obtener_pickers_libres(pickers: List[Picker]) -> List[Picker]:
        """Devuelve los Pickers que no tienen ninguna Wave en curso actualmente."""
        return [p for p in pickers if p.id_wave_actual is None]

    # =========================================================================
    # 5. ETAPA 3 Y 4: SELECCIONAR WAVES Y ASIGNARLAS A LOS PICKERS MÁS CERCANOS
    # =========================================================================
    def calcular_distancia_picker_a_wave(
        self,
        picker: Picker,
        wave: Wave,
        grafo: Any = None,
    ) -> float:
        """
        Calcula la distancia real en el dígrafo desde la posición actual del Picker
        hasta la ubicación de recolección más cercana de la Wave (el punto de entrada
        del Picker a la Wave). Si no hay grafo, usa distancia Manhattan.
        """
        if not wave.ubicaciones_xy:
            return 0.0

        if grafo is not None:
            orig_pasillo = Pathfinding.obtener_celda_acceso_pasillo(
                picker.posicion_actual, grafo
            )
            mapa_dist = Pathfinding.calcular_mapa_distancias_desde(orig_pasillo, grafo)
            dist_min = float("inf")
            for coord_rack in wave.ubicaciones_xy:
                celda_acceso = Pathfinding.obtener_celda_acceso_pasillo(
                    coord_rack, grafo
                )
                d = mapa_dist.get(celda_acceso, float("inf"))
                if d < dist_min:
                    dist_min = d
            return dist_min

        px, py = picker.posicion_actual
        return float(min(abs(px - ux) + abs(py - uy) for ux, uy in wave.ubicaciones_xy))

    def asignar_y_ejecutar_waves_seleccionadas(
        self,
        ids_waves_seleccionadas: List[str],
        pickers: List[Picker],
        catalogo: Any = None,
        grafo: Any = None,
        repartir_pickers_sobrantes: bool = False,
    ) -> Dict[str, Any]:
        """
        Recibe la lista de IDs de las Waves que el usuario seleccionó para ejecutar
        al mismo tiempo, busca los Pickers libres MÁS CERCANOS en el dígrafo a cada
        una de esas Waves, les asigna la Wave e inicia su ejecución simultánea.

        Retorna un diccionario con el detalle de la asignación para mostrar en
        Consola o en la interfaz gráfica de Pygame:
        {
            "waves_iniciadas": [Wave, ...],
            "asignaciones": [
                {
                    "id_wave": str,
                    "ids_pickers": [str, ...],
                    "distancias_picker_a_wave": {id_picker: float},
                    "pedidos_por_picker": {id_picker: [id_pedido, ...]},
                }, ...
            ],
            "waves_sin_picker_disponible": [str, ...]
        }
        """
        if grafo is None and catalogo is not None:
            grafo = getattr(catalogo, "digrafo", None)

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

        # Precalcular la distancia en el dígrafo desde cada Picker libre hacia cada Wave seleccionada
        dist_picker_wave: Dict[Tuple[str, str], float] = {}
        for pk in pickers_libres:
            for w in waves_elegidas:
                dist_picker_wave[(pk.id_picker, w.id_wave)] = (
                    self.calcular_distancia_picker_a_wave(pk, w, grafo)
                )

        equipos_asignados: Dict[str, List[Picker]] = {}
        waves_activas: List[Wave] = []

        # 1. Para cada Wave seleccionada, elegir el Picker (o equipo mínimo si pesa mucho) MÁS CERCANO
        for w in waves_elegidas:
            if not pickers_libres:
                resultado["waves_sin_picker_disponible"].append(w.id_wave)
                continue

            # Ordenar los pickers libres por menor distancia real en el dígrafo hacia esta Wave
            # (En caso de empate en distancia, priorizar el de mayor capacidad de carga)
            candidatos_cercanos = sorted(
                pickers_libres,
                key=lambda pk: (
                    dist_picker_wave.get((pk.id_picker, w.id_wave), float("inf")),
                    -pk.capacidad_carga_kg,
                    pk.id_picker,
                ),
            )

            # Verificar si el picker más cercano puede llevar toda la Wave solo
            equipo_elegido: List[Picker] = []
            for pk in candidatos_cercanos:
                if pk.capacidad_carga_kg >= w.peso_total_kg:
                    equipo_elegido = [pk]
                    break

            # Si un solo picker no alcanza por peso, armar un equipo con los más cercanos
            if not equipo_elegido:
                factible, equipo_multi = self._es_repartible_en_equipo_pickers(
                    w.pedidos, candidatos_cercanos, catalogo
                )
                if factible and equipo_multi:
                    # Reordenar por cercanía entre los que cumplen el peso
                    equipo_elegido = equipo_multi

            if not equipo_elegido:
                resultado["waves_sin_picker_disponible"].append(w.id_wave)
                continue

            equipos_asignados[w.id_wave] = equipo_elegido
            waves_activas.append(w)
            for pk in equipo_elegido:
                pickers_libres.remove(pk)

        # 2. (Opcional) Si el usuario desea que los pickers libres restantes refuercen a las Waves
        #    seleccionadas, se asigna cada picker libre restante a la Wave seleccionada más cercana.
        if repartir_pickers_sobrantes and pickers_libres and waves_activas:
            for pk_extra in list(pickers_libres):
                waves_reforzables = [
                    w
                    for w in waves_activas
                    if len(equipos_asignados[w.id_wave]) < self.max_pickers_por_wave
                    and len(equipos_asignados[w.id_wave]) < len(w.pedidos)
                ]
                if not waves_reforzables:
                    break
                wave_mas_cercana = min(
                    waves_reforzables,
                    key=lambda w: dist_picker_wave.get(
                        (pk_extra.id_picker, w.id_wave), float("inf")
                    ),
                )
                equipos_asignados[wave_mas_cercana.id_wave].append(pk_extra)
                pickers_libres.remove(pk_extra)

        # 3. Formalizar la asignación en las entidades Wave y Picker y pasar a EN_EJECUCION
        for w in waves_activas:
            equipo = equipos_asignados[w.id_wave]
            w.asignar_equipo_pickers(equipo, catalogo)
            w.estado = EstadoWave.EN_EJECUCION

            for pk in equipo:
                pk.id_wave_actual = w.id_wave

            resultado["waves_iniciadas"].append(w)
            resultado["asignaciones"].append(
                {
                    "id_wave": w.id_wave,
                    "ids_pickers": [p.id_picker for p in equipo],
                    "distancias_picker_a_wave": {
                        p.id_picker: dist_picker_wave.get((p.id_picker, w.id_wave), 0.0)
                        for p in equipo
                    },
                    "pedidos_por_picker": dict(w.pedidos_por_picker),
                    "destinos_xy_por_picker": dict(w.destinos_xy_por_picker),
                }
            )

        return resultado

    def finalizar_wave_en_ejecucion(self, id_wave: str, pickers: List[Picker]) -> bool:
        """
        Marca una Wave como FINALIZADA y libera a los Pickers que la estaban realizando
        para que queden disponibles para la siguiente selección de Waves en Pygame/Consola.
        """
        w = self.waves_por_id.get(id_wave)
        if w is None or w.estado != EstadoWave.EN_EJECUCION:
            return False

        w.estado = EstadoWave.FINALIZADA
        ids_liberados = set(w.ids_pickers_asignados)
        for pk in pickers:
            if pk.id_picker in ids_liberados or pk.id_wave_actual == id_wave:
                pk.id_wave_actual = None
                pk.peso_actual_kg = 0.0
        return True
