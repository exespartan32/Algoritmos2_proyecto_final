from typing import List, Optional, Tuple, Set, Any, Dict
from BackEnd.models.entities import Pedido, Wave
from BackEnd.enums.enums import EstadoWave, EstadoPedido
from BackEnd.data_structures.max_heap_pedidos import MaxHeapPedidos
from BackEnd.controllers.path_finding import Pathfinding

CoordXY = Tuple[int, int]


class WaveManager:
    """
    Controlador de Generación de Waves mediante Max-Heap y Costo Marginal Promedio
    (Average Linkage) utilizando las distancias dirigidas reales sobre el Dígrafo
    provistas por el módulo Pathfinding de Leonel.
    Garantiza que NO se modifique el stock físico (cantidad_disponible) al armar las Waves.
    """

    def __init__(
        self,
        wave_max_pedidos: int,
        wave_max_productos: int,
        prefijo_id_wave: str = "WAVE",
        incluir_altura_z_unica: bool = True,
        proveedor_distancias: Optional[Any] = None,
    ) -> None:
        self.cola_prioridad = MaxHeapPedidos()
        self.wave_max_pedidos = wave_max_pedidos
        self.wave_max_productos = wave_max_productos
        self.prefijo_id_wave = prefijo_id_wave
        self.incluir_altura_z_unica = incluir_altura_z_unica
        self.proveedor_distancias = proveedor_distancias

        self.errores_validacion: List[str] = []
        self.pedidos_descartados: List[Pedido] = []
        # Traza detallada por wave: {id_wave: [diccionarios con paso, pedido, score, etc.]}
        self.traza_armado: Dict[str, List[Dict[str, Any]]] = {}

    # =========================================================================
    # 0. INTEGRACIÓN CON EL DÍGRAFO Y PATHFINDING DE LEONEL (CONSULTA O(1))
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
            if hasattr(fuente, "distancia_entre_ubicaciones"):
                return float(fuente.distancia_entre_ubicaciones(origen, destino))

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
    # 1. VALIDACIÓN DE ENTRADA Y CONTROL DE STOCK VIRTUAL (SIN DESCONTAR STOCK)
    # =========================================================================
    def _tiene_stock_suficiente_sin_modificar(
        self,
        pedido: Pedido,
        tabla_productos: Any,
        stock_comprometido: Dict[str, int],
    ) -> bool:
        """
        Comprueba en O(1) por ítem que la cantidad disponible en el catálogo alcance
        para cubrir el pedido considerando lo reservado virtualmente por otras Waves,
        PERO SIN MODIFICAR producto.cantidad_disponible.
        """
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
        """Anota en memoria local del WaveManager las unidades comprometidas sin tocar Producto."""
        for item in pedido.items:
            stock_comprometido[item.producto_id] = (
                stock_comprometido.get(item.producto_id, 0) + item.cantidad
            )

    def validar_pedidos_entrada(
        self,
        pedidos: List[Pedido],
        tabla_productos: Any = None,
        catalogo: Any = None,
    ) -> List[Pedido]:
        pedidos_validos: List[Pedido] = []

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
    # 3. FLUJO PRINCIPAL DE CREACIÓN DE WAVES (SIN MODIFICAR STOCK REAL)
    # =========================================================================
    def generar_waves(
        self,
        pedidos: Optional[List[Pedido]] = None,
        tabla_productos: Any = None,
        catalogo: Any = None,
        proveedor_distancias: Optional[Any] = None,
    ) -> List[Wave]:
        self.errores_validacion.clear()
        self.pedidos_descartados.clear()
        self.traza_armado.clear()

        if (
            pedidos is None
            and catalogo is not None
            and hasattr(catalogo, "obtener_todos_los_pedidos")
        ):
            pedidos = catalogo.obtener_todos_los_pedidos()
        if tabla_productos is None and catalogo is not None:
            tabla_productos = catalogo
        if (
            proveedor_distancias is None
            and catalogo is not None
            and getattr(catalogo, "digrafo", None) is not None
        ):
            proveedor_distancias = catalogo.digrafo

        if not pedidos:
            return []

        pedidos_validos = self.validar_pedidos_entrada(
            pedidos, tabla_productos=tabla_productos, catalogo=catalogo
        )
        if not pedidos_validos:
            return []

        fuente_dist = self._preparar_fuente_distancias_O1(
            pedidos_validos, tabla_productos, proveedor_distancias
        )

        self.cola_prioridad.construir_monticulo(pedidos_validos)

        waves_generadas: List[Wave] = []
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
            nueva_wave = Wave(
                id_wave=id_wave_actual,
                estado=EstadoWave.PENDIENTE,
                wave_max_pedidos=self.wave_max_pedidos,
                wave_max_productos=self.wave_max_productos,
            )

            nueva_wave.agregar_pedido(pedido_raiz, tabla_productos, catalogo=catalogo)
            self._registrar_compromiso_virtual(pedido_raiz, stock_comprometido_virtual)

            self.traza_armado[id_wave_actual] = [
                {
                    "rol": "RAIZ_MAX_HEAP",
                    "id_pedido": pedido_raiz.id_pedido,
                    "prioridad": pedido_raiz.prioridad,
                    "unidades": pedido_raiz.obtener_cantidad_productos(),
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
                        "score_marginal": mejor_score,
                        "candidatos_evaluados": evaluados_validos,
                    }
                )

            waves_generadas.append(nueva_wave)
            contador_wave += 1

        return waves_generadas
