from typing import List, Optional, Tuple
from BackEnd.data_structures.max_heap_pedidos import MaxHeapPedidos
from BackEnd.models.warehouse_models import Warehouse, ZonaDespacho
from BackEnd.models.catalog_manager import CatalogManager
from BackEnd.models.entities import Order, Picker, Wave
from BackEnd.enums.enums import EstadoPedido, EstadoWave


class WaveManager:
    def __init__(self, wave_max_pedidos: int = 3, wave_max_productos: int = 15):
        self.cola_prioridad = MaxHeapPedidos()
        self.wave_max_pedidos = wave_max_pedidos
        self.wave_max_productos = wave_max_productos

    def obtener_zonas_habilitadas(self, warehouse: Warehouse) -> List[ZonaDespacho]:
        zonas_validas = []
        for zona in warehouse.zonas_despacho.values():
            puerta = warehouse.puertas.get(zona.puerta_id)
            if puerta and puerta.permite_despacho_salida():
                zonas_validas.append(zona)
        return zonas_validas

    def seleccionar_zona_despacho_optima(
        self, warehouse: Warehouse, picker: Picker, peso_requerido: float
    ) -> Optional[ZonaDespacho]:
        zonas_candidatas = self.obtener_zonas_habilitadas(warehouse)
        mejor_zona = None
        menor_distancia = float("inf")
        px, py = picker.posicion_actual

        for zona in zonas_candidatas:
            if not zona.puede_recibir_carga(peso_requerido):
                continue

            celda_acceso = warehouse.obtener_celda_acceso_despacho(zona.id_zona)
            if not celda_acceso:
                continue

            dist = abs(px - celda_acceso[0]) + abs(py - celda_acceso[1])
            if dist < menor_distancia:
                menor_distancia = dist
                mejor_zona = zona

        return mejor_zona

    def evaluar_cercania_mst_kruskal_prim(
        self, pedidos_candidatos: List[Order], catalogo: CatalogManager
    ) -> float:
        puntos: List[Tuple[int, int]] = []
        for ped in pedidos_candidatos:
            for item in ped.items:
                prod = catalogo.buscar_producto_O1(item.producto_id)
                if prod:
                    coord = (prod.ubicacion_x, prod.ubicacion_y)
                    if coord not in puntos:
                        puntos.append(coord)

        n = len(puntos)
        if n <= 1:
            return 0.0

        # Algoritmo de Prim sobre las coordenadas de recolección
        visitados = [False] * n
        dist_min = [float("inf")] * n
        dist_min[0] = 0.0
        costo_mst = 0.0

        for _ in range(n):
            u = -1
            for i in range(n):
                if not visitados[i] and (u == -1 or dist_min[i] < dist_min[u]):
                    u = i

            visitados[u] = True
            costo_mst += dist_min[u]

            for v in range(n):
                if not visitados[v]:
                    d = abs(puntos[u][0] - puntos[v][0]) + abs(
                        puntos[u][1] - puntos[v][1]
                    )
                    if d < dist_min[v]:
                        dist_min[v] = d

        return costo_mst

    def generar_waves(
        self, warehouse: Warehouse, catalogo: CatalogManager, pickers: List[Picker]
    ) -> List[Wave]:
        for ped in catalogo.obtener_todos_los_pedidos():
            if ped.estado == EstadoPedido.PENDIENTE:
                self.cola_prioridad.insertar(ped)

        waves_generadas: List[Wave] = []
        if not pickers:
            return waves_generadas

        contador_wave = 1
        idx_picker = 0
        pedidos_extraidos: List[Order] = []

        while not self.cola_prioridad.esta_vacio():
            p = self.cola_prioridad.extraer_maximo()
            if p:
                pedidos_extraidos.append(p)

        visitados = set()

        for i, pedido_ancla in enumerate(pedidos_extraidos):
            if pedido_ancla.id_pedido in visitados:
                continue

            picker_actual = pickers[idx_picker % len(pickers)]
            peso_ancla = pedido_ancla.obtener_peso_total(catalogo)

            zona_optima = self.seleccionar_zona_despacho_optima(
                warehouse, picker_actual, peso_ancla
            )
            if not zona_optima:
                continue

            nueva_wave = Wave(
                id_wave=f"WAVE_{contador_wave:02d}",
                estado=EstadoWave.PENDIENTE,
                id_picker_asignado=picker_actual.id_picker,
                id_zona_despacho=zona_optima.id_zona,
                wave_max_pedidos=self.wave_max_pedidos,
                wave_max_productos=self.wave_max_productos,
            )

            if nueva_wave.agregar_pedido(
                pedido_ancla, picker_actual.capacidad_carga_kg, zona_optima, catalogo
            ):
                visitados.add(pedido_ancla.id_pedido)

                # Ordenar candidatos restantes por menor incremento en el MST (cercanía geográfica)
                candidatos = [
                    p
                    for p in pedidos_extraidos[i + 1 :]
                    if p.id_pedido not in visitados
                ]
                candidatos.sort(
                    key=lambda cand: self.evaluar_cercania_mst_kruskal_prim(
                        nueva_wave.pedidos + [cand], catalogo
                    )
                )

                for cand in candidatos:
                    if nueva_wave.agregar_pedido(
                        cand, picker_actual.capacidad_carga_kg, zona_optima, catalogo
                    ):
                        visitados.add(cand.id_pedido)

                waves_generadas.append(nueva_wave)
                contador_wave += 1
                idx_picker += 1

        return waves_generadas
