from BackEnd.models.enums import EstadoWave, EstadoPedido
from BackEnd.models import Wave


class WaveManager:
    def __init__(self, inventory_manager, pathfinding_service):
        """
        Inyectamos las dependencias necesarias para acceder a las ubicaciones en O(1)
        y calcular las distancias en el grafo.
        """
        self.inventory_manager = inventory_manager
        self.pathfinding = pathfinding_service

    def ordenar_por_prioridad(self, pedidos):
        """
        Ordena la lista de pedidos descendente: de mayor (5) a menor (1) prioridad.
        """
        return sorted(pedidos, key=lambda p: p.prioridad, reverse=True)

    def _calcular_distancia_minima_a_pedido(self, nodo_origen, pedido):
        """
        Evalúa la dispersión de stock: Busca en qué estantes (múltiples) está el producto
        y calcula la distancia real por los pasillos desde la posición del operario
        hasta la estantería más cercana que contenga el ítem.
        """
        distancia_mas_corta = float("inf")

        # Iteramos sobre los detalles (productos) que componen este pedido
        for detalle in pedido.detalles:
            # Búsqueda O(1) de todas las ubicaciones donde hay stock de este producto
            ubicaciones_stock = self.inventory_manager.buscar_producto_O1(
                detalle.id_producto
            )

            for stock in ubicaciones_stock:
                # Nodo físico de la estantería para esta ubicación específica
                nodo_destino = self.pathfinding.grafo.obtener_nodo(stock.id_nodo)

                if not nodo_destino:
                    continue

                # Usamos el servicio de Pathfinding (Dijkstra/BFS) para trazar la ruta transitable
                ruta = self.pathfinding.calcular_ruta_dijkstra(
                    nodo_origen, nodo_destino
                )

                # Si existe un camino y es más corto que los evaluados anteriormente, lo guardamos
                if ruta and len(ruta) < distancia_mas_corta:
                    distancia_mas_corta = len(ruta)

        return distancia_mas_corta

    def crear_wave_greedy(
        self, pedidos_pendientes, limite_peso, id_nodo_inicio="0,0,0"
    ):
        """
        Implementación de la heurística Voraz (Greedy) para agrupar pedidos.
        """
        if not pedidos_pendientes:
            return None

        # 1. Ordenamiento estricto por prioridad
        pedidos_ordenados = self.ordenar_por_prioridad(pedidos_pendientes)

        # 2. Inicialización de la nueva Wave
        # Se genera con la restricción de límite de peso del picker
        nueva_wave = Wave(
            id_wave="W-" + str(id(self))[-4:],  # ID auto-generado simple
            capacidad_max_peso=limite_peso,
            estado=EstadoWave.PENDIENTE,
        )
        peso_acumulado = 0.0

        # 3. Anclaje: Tomar el pedido de mayor prioridad como inicio de la Wave
        pedido_ancla = pedidos_ordenados.pop(0)
        peso_ancla = pedido_ancla.obtener_peso_total()

        # Validamos que el pedido inicial no supere por sí solo la capacidad del operario
        if peso_ancla <= limite_peso:
            nueva_wave.agregar_pedido(pedido_ancla)
            peso_acumulado += peso_ancla
            pedido_ancla.estado = EstadoPedido.EN_WAVE
        else:
            print(
                f"Error: El pedido {pedido_ancla.id_pedido} excede el límite de peso físico."
            )
            return None

        # Obtenemos el nodo donde arranca el operario (usualmente la ZONA_DESPACHO)
        nodo_actual = self.pathfinding.grafo.obtener_nodo(id_nodo_inicio)

        # 4. Búsqueda Voraz por Cercanía y Stock Disperso
        # Mientras queden pedidos y el picker siga teniendo capacidad de carga en kg.
        while pedidos_ordenados and peso_acumulado < limite_peso:
            pedido_candidato_elegido = None
            menor_distancia_encontrada = float("inf")

            # Escaneamos los pedidos restantes para encontrar el más cercano geográficamente
            for pedido in pedidos_ordenados:
                peso_pedido = pedido.obtener_peso_total()

                # Condición 1: ¿Soporta el peso restante del carro?
                if peso_acumulado + peso_pedido <= limite_peso:

                    # Condición 2: Evaluar la dispersión de ubicaciones y medir distancia
                    distancia_calculada = self._calcular_distancia_minima_a_pedido(
                        nodo_actual, pedido
                    )

                    # Selección Greedy: Nos quedamos con el que represente menor esfuerzo de traslado
                    if distancia_calculada < menor_distancia_encontrada:
                        menor_distancia_encontrada = distancia_calculada
                        pedido_candidato_elegido = pedido

            # 5. Adhesión del candidato ganador a la Wave
            if pedido_candidato_elegido:
                nueva_wave.agregar_pedido(pedido_candidato_elegido)
                peso_acumulado += pedido_candidato_elegido.obtener_peso_total()
                pedido_candidato_elegido.estado = EstadoPedido.EN_WAVE

                # Lo removemos de los pendientes para no volver a evaluarlo
                pedidos_ordenados.remove(pedido_candidato_elegido)
            else:
                # Si ningún pedido restante cabe por peso (o todos son inalcanzables),
                # cortamos el ciclo y cerramos la Wave actual.
                break

        # Seteamos la carga total final antes de retornar
        nueva_wave.capacidad_max_peso = peso_acumulado
        return nueva_wave
