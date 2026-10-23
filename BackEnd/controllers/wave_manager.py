from typing import List, Optional, Tuple, Dict, Any
from BackEnd.models.catalog_manager import CatalogManager
from BackEnd.models.entity import Order, Picker, Wave
from BackEnd.enums.enums import EstadoWave, EstadoPedido
from BackEnd.data_structures.disjoint_set import DisjointSet
from BackEnd.data_structures.max_heap_pedidos import MaxHeapPedidos


class WaveManager:
    """
    Controlador de Generación de Waves 100% parametrizado (Sin dependencia del módulo de Laureano):
    - Paso 1: Pre-filtro de imposibilidad física (peso_pedido > capacidad_max_picker).
    - Paso 2: Selección de pedido ancla desde Max-Heap validando capacidad de picker y zona.
    - Paso 3: Agrupamiento voraz (Greedy + MST) saltando pedidos pesados para evaluar más livianos.
    - Paso 4: Cierre de ola, re-inserción en Max-Heap y reporte de remanentes por capacidad agotada.
    """

    def __init__(
        self,
        metodo_mst: str,
        prefijo_id_wave: str,
        wave_max_pedidos: Optional[int] = None,
        wave_max_productos: Optional[int] = None,
    ):
        self.cola_prioridad = MaxHeapPedidos()
        self.wave_max_pedidos_override = wave_max_pedidos
        self.wave_max_productos_override = wave_max_productos
        self.metodo_mst = metodo_mst.upper()
        self.prefijo_id_wave = prefijo_id_wave

        self.alertas_peso: List[str] = []
        self.pedidos_irrealizables: List[Order] = []
        self.pedidos_remanentes_capacidad: List[Order] = []

    def _mst_kruskal(self, puntos: List[Tuple[int, int]]) -> int:
        n = len(puntos)
        if n <= 1:
            return 0

        aristas = [
            (abs(puntos[i][0] - puntos[j][0]) + abs(puntos[i][1] - puntos[j][1]), i, j)
            for i in range(n)
            for j in range(i + 1, n)
        ]
        aristas.sort(key=lambda a: a[0])

        conjuntos_disjuntos = DisjointSet(n)
        peso_mst = 0
        aristas_usadas = 0

        for peso, u, v in aristas:
            if conjuntos_disjuntos.unir(u, v):
                peso_mst += peso
                aristas_usadas += 1
                if aristas_usadas == n - 1:
                    break

        return peso_mst

    def _mst_prim(self, puntos: List[Tuple[int, int]]) -> float:
        n = len(puntos)
        if n <= 1:
            return 0.0

        visitados = [False] * n
        dist_min = [float("inf")] * n
        dist_min[0] = 0.0
        peso_mst = 0.0

        for _ in range(n):
            u = -1
            menor = float("inf")
            for i in range(n):
                if not visitados[i] and dist_min[i] < menor:
                    menor = dist_min[i]
                    u = i

            visitados[u] = True
            peso_mst += menor

            ux, uy = puntos[u]
            for v in range(n):
                if not visitados[v]:
                    vx, vy = puntos[v]
                    d = float(abs(ux - vx) + abs(uy - vy))
                    if d < dist_min[v]:
                        dist_min[v] = d

        return peso_mst

    def calcular_costo_mst_puntos(self, puntos: List[Tuple[int, int]]) -> float:
        if self.metodo_mst == "PRIM":
            return self._mst_prim(puntos)
        return float(self._mst_kruskal(puntos))

    def evaluar_cercania_mst_kruskal_prim(
        self,
        pedidos_candidatos: List[Order],
        catalogo: CatalogManager,
        coord_despacho: Optional[Tuple[int, int]] = None,
    ) -> float:
        puntos: List[Tuple[int, int]] = []
        vistos = set()
        if coord_despacho is not None:
            vistos.add(coord_despacho)
            puntos.append(coord_despacho)

        for ped in pedidos_candidatos:
            for pt in ped.obtener_coordenadas_unicas(catalogo):
                if pt not in vistos:
                    vistos.add(pt)
                    puntos.append(pt)

        return self.calcular_costo_mst_puntos(puntos)

    def _obtener_zonas_despacho_disponibles(
        self, catalogo: CatalogManager, ids_zonas_activas: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        zonas_info: List[Dict[str, Any]] = []
        filtro_zonas = set(ids_zonas_activas) if ids_zonas_activas else None

        wh_raw = catalogo.warehouse_raw
        puertas_salida = {
            p["id"]
            for p in wh_raw.get("puertas", [])
            if p.get("tipo", "OUTBOUND") in ("OUTBOUND", "AMBOS")
        }

        for zd in wh_raw.get("zonas_despacho", []):
            id_zd = str(zd["id"])
            if filtro_zonas and id_zd not in filtro_zonas:
                continue
            if not puertas_salida or zd.get("puerta_id") in puertas_salida:
                ux = int(zd["ubicacion"]["x"])
                uy = int(zd["ubicacion"]["y"])
                peso_max = float(zd.get("peso_max_kg", float("inf")))
                zonas_info.append(
                    {
                        "id": id_zd,
                        "coord_acceso": (ux, uy),
                        "peso_max_kg": peso_max,
                        "peso_disponible": peso_max,
                    }
                )

        if not zonas_info:
            zonas_info.append(
                {
                    "id": "ZONA_DEFAULT",
                    "coord_acceso": (0, 0),
                    "peso_max_kg": float("inf"),
                    "peso_disponible": float("inf"),
                }
            )

        return zonas_info

    def _seleccionar_mejor_zona(
        self,
        zonas_info: List[Dict[str, Any]],
        picker: Picker,
        pedido_ancla: Order,
        catalogo: CatalogManager,
    ) -> Optional[Dict[str, Any]]:
        peso_ancla = pedido_ancla.obtener_peso_total(catalogo)
        coords_ancla = pedido_ancla.obtener_coordenadas_unicas(catalogo)
        mejor_zona = None
        menor_costo = float("inf")
        px, py = picker.posicion_actual

        for z in zonas_info:
            if z["peso_disponible"] < peso_ancla:
                continue

            cx, cy = z["coord_acceso"]
            dist_picker = abs(px - cx) + abs(py - cy)
            puntos_eval = [(cx, cy)] + [pt for pt in coords_ancla if pt != (cx, cy)]
            costo_total = dist_picker + self.calcular_costo_mst_puntos(puntos_eval)

            if costo_total < menor_costo:
                menor_costo = costo_total
                mejor_zona = z

        return mejor_zona

    def _hay_stock_para_pedido(
        self,
        pedido: Order,
        catalogo: CatalogManager,
        stock_comprometido: Dict[str, int],
    ) -> bool:
        for item in pedido.items:
            prod = catalogo.buscar_producto_O1(item.producto_id)
            if prod is None:
                return False
            if (
                prod.cantidad_disponible - stock_comprometido.get(item.producto_id, 0)
            ) < item.cantidad:
                return False
        return True

    def _comprometer_stock_pedido(
        self,
        pedido: Order,
        catalogo: CatalogManager,
        stock_comprometido: Dict[str, int],
        descontar_en_tabla_hash: bool,
    ) -> None:
        for item in pedido.items:
            stock_comprometido[item.producto_id] = (
                stock_comprometido.get(item.producto_id, 0) + item.cantidad
            )
            if descontar_en_tabla_hash:
                catalogo.descontar_stock(item.producto_id, item.cantidad)

    def validar_viabilidad_inicial_pedidos(
        self,
        pedidos: List[Order],
        lista_pickers: List[Picker],
        zonas_info: List[Dict[str, Any]],
        max_productos_wave: float,
        catalogo: CatalogManager,
        marcar_estado_irrealizable: bool = False,
    ) -> List[Order]:
        max_cap_picker = max(p.capacidad_carga_kg for p in lista_pickers)
        max_cap_zona = max(z["peso_max_kg"] for z in zonas_info)
        pedidos_viables: List[Order] = []

        for ped in pedidos:
            peso_ped = ped.obtener_peso_total(catalogo)
            unidades_ped = ped.obtener_cantidad_unidades()

            if peso_ped > max_cap_picker:
                msg = (
                    f"Error: El pedido {ped.id_pedido} ({peso_ped:.2f} kg) excede el límite "
                    f"de carga física máxima de los pickers ({max_cap_picker:.2f} kg)."
                )
                self.alertas_peso.append(msg)
                self.pedidos_irrealizables.append(ped)
                if marcar_estado_irrealizable:
                    catalogo.actualizar_estado_pedido_O1(
                        ped.id_pedido, EstadoPedido.IRREALIZABLE
                    )
                continue

            if peso_ped > max_cap_zona:
                msg = (
                    f"Error: El pedido {ped.id_pedido} ({peso_ped:.2f} kg) excede la capacidad "
                    f"máxima de cualquier zona de despacho ({max_cap_zona:.2f} kg)."
                )
                self.alertas_peso.append(msg)
                self.pedidos_irrealizables.append(ped)
                if marcar_estado_irrealizable:
                    catalogo.actualizar_estado_pedido_O1(
                        ped.id_pedido, EstadoPedido.IRREALIZABLE
                    )
                continue

            if unidades_ped > max_productos_wave:
                msg = (
                    f"Error: El pedido {ped.id_pedido} ({unidades_ped} unid.) excede el límite "
                    f"máximo de productos por wave ({max_productos_wave} unid.)."
                )
                self.alertas_peso.append(msg)
                self.pedidos_irrealizables.append(ped)
                if marcar_estado_irrealizable:
                    catalogo.actualizar_estado_pedido_O1(
                        ped.id_pedido, EstadoPedido.IRREALIZABLE
                    )
                continue

            pedidos_viables.append(ped)

        return pedidos_viables

    def generar_waves(
        self,
        catalogo: CatalogManager,
        pickers: Optional[List[Picker]] = None,
        descontar_stock_inmediato: bool = False,
        prioridad_minima: int = 1,
        ids_pickers_activos: Optional[List[str]] = None,
        ids_zonas_activas: Optional[List[str]] = None,
        marcar_irrealizables_en_catalogo: bool = False,
    ) -> List[Wave]:
        self.alertas_peso.clear()
        self.pedidos_irrealizables.clear()
        self.pedidos_remanentes_capacidad.clear()

        lista_pickers = pickers if pickers is not None else catalogo.pickers
        if ids_pickers_activos:
            filtro_pk = set(ids_pickers_activos)
            lista_pickers = [p for p in lista_pickers if p.id_picker in filtro_pk]

        if not lista_pickers:
            return []

        max_pedidos = (
            self.wave_max_pedidos_override or catalogo.wave_max_pedidos or float("inf")
        )
        max_productos = (
            self.wave_max_productos_override
            or catalogo.wave_max_productos
            or float("inf")
        )

        zonas_info = self._obtener_zonas_despacho_disponibles(
            catalogo, ids_zonas_activas
        )
        stock_comprometido: Dict[str, int] = {}

        # Paso 1: Pre-filtro de Imposibilidad
        pedidos_pendientes = catalogo.obtener_pedidos_pendientes(
            prioridad_minima=prioridad_minima
        )
        pedidos_viables = self.validar_viabilidad_inicial_pedidos(
            pedidos=pedidos_pendientes,
            lista_pickers=lista_pickers,
            zonas_info=zonas_info,
            max_productos_wave=max_productos,
            catalogo=catalogo,
            marcar_estado_irrealizable=marcar_irrealizables_en_catalogo,
        )

        self.cola_prioridad.construir_monticulo(pedidos_viables)

        waves_generadas: List[Wave] = []
        contador_wave = 1
        idx_picker = 0

        # Paso 2: Selección del Pedido Ancla
        while not self.cola_prioridad.esta_vacio():
            pedido_ancla = self.cola_prioridad.extraer_maximo()
            if pedido_ancla is None:
                break

            if not self._hay_stock_para_pedido(
                pedido_ancla, catalogo, stock_comprometido
            ):
                self.pedidos_remanentes_capacidad.append(pedido_ancla)
                self.alertas_peso.append(
                    f"Aviso: Pedido {pedido_ancla.id_pedido} permanece PENDIENTE por stock insuficiente."
                )
                continue

            peso_ancla = pedido_ancla.obtener_peso_total(catalogo)

            picker_actual: Optional[Picker] = None
            for offset in range(len(lista_pickers)):
                pk_candidato = lista_pickers[(idx_picker + offset) % len(lista_pickers)]
                if pk_candidato.capacidad_carga_kg >= peso_ancla:
                    picker_actual = pk_candidato
                    idx_picker = idx_picker + offset
                    break

            if picker_actual is None:
                self.pedidos_remanentes_capacidad.append(pedido_ancla)
                continue

            zona_elegida = self._seleccionar_mejor_zona(
                zonas_info, picker_actual, pedido_ancla, catalogo
            )
            if zona_elegida is None:
                self.pedidos_remanentes_capacidad.append(pedido_ancla)
                self.alertas_peso.append(
                    f"Aviso: Pedido {pedido_ancla.id_pedido} ({peso_ancla:.2f} kg) permanece PENDIENTE "
                    f"por capacidad insuficiente en zonas de despacho."
                )
                continue

            coord_despacho = zona_elegida["coord_acceso"]

            nueva_wave = Wave(
                id_wave=f"{self.prefijo_id_wave}_{contador_wave:02d}",
                estado=EstadoWave.PENDIENTE,
                id_picker_asignado=picker_actual.id_picker,
                id_zona_despacho=zona_elegida["id"],
                wave_max_pedidos=max_pedidos,
                wave_max_productos=max_productos,
            )

            nueva_wave.agregar_pedido(
                pedido_ancla, picker_actual.capacidad_carga_kg, catalogo
            )
            zona_elegida["peso_disponible"] -= peso_ancla
            self._comprometer_stock_pedido(
                pedido_ancla, catalogo, stock_comprometido, descontar_stock_inmediato
            )

            coords_wave_lista: List[Tuple[int, int]] = [coord_despacho]
            coords_wave_set = {coord_despacho}
            for pt in pedido_ancla.obtener_coordenadas_unicas(catalogo):
                if pt not in coords_wave_set:
                    coords_wave_set.add(pt)
                    coords_wave_lista.append(pt)

            candidatos_restantes: List[Order] = []
            while not self.cola_prioridad.esta_vacio():
                cand = self.cola_prioridad.extraer_maximo()
                if cand is not None:
                    candidatos_restantes.append(cand)

            # Paso 3: Agrupamiento Voraz (Greedy)
            while len(nueva_wave.pedidos) < max_pedidos and candidatos_restantes:
                costo_mst_base = self.calcular_costo_mst_puntos(coords_wave_lista)
                mejor_candidato: Optional[Order] = None
                menor_delta_mst = float("inf")

                for cand in candidatos_restantes:
                    if not self._hay_stock_para_pedido(
                        cand, catalogo, stock_comprometido
                    ):
                        continue

                    if not nueva_wave.puede_agregar_pedido(
                        cand,
                        picker_actual.capacidad_carga_kg,
                        catalogo,
                        zona_elegida["peso_disponible"],
                    ):
                        continue

                    nuevos_pts = [
                        pt
                        for pt in cand.obtener_coordenadas_unicas(catalogo)
                        if pt not in coords_wave_set
                    ]
                    if not nuevos_pts:
                        delta_mst = 0.0
                    else:
                        costo_mst_nuevo = self.calcular_costo_mst_puntos(
                            coords_wave_lista + nuevos_pts
                        )
                        delta_mst = costo_mst_nuevo - costo_mst_base

                    if delta_mst < menor_delta_mst:
                        menor_delta_mst = delta_mst
                        mejor_candidato = cand
                        if delta_mst == 0.0:
                            break

                if mejor_candidato is not None:
                    nueva_wave.agregar_pedido(
                        mejor_candidato, picker_actual.capacidad_carga_kg, catalogo
                    )
                    zona_elegida[
                        "peso_disponible"
                    ] -= mejor_candidato.obtener_peso_total(catalogo)
                    self._comprometer_stock_pedido(
                        mejor_candidato,
                        catalogo,
                        stock_comprometido,
                        descontar_stock_inmediato,
                    )
                    for pt in mejor_candidato.obtener_coordenadas_unicas(catalogo):
                        if pt not in coords_wave_set:
                            coords_wave_set.add(pt)
                            coords_wave_lista.append(pt)
                    candidatos_restantes.remove(mejor_candidato)
                else:
                    break

            # Paso 4: Cierre de la Ola y Re-inserción de Remanentes
            for ped_restante in candidatos_restantes:
                self.cola_prioridad.insertar(ped_restante)

            waves_generadas.append(nueva_wave)
            contador_wave += 1
            idx_picker += 1

        return waves_generadas
