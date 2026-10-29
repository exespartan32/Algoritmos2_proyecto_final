# Arquitectura

## Capas

El enunciado pide separar como mínimo
**Warehouse → Products/Orders → Wave Manager → Pathfinding → Simulation → Visualization**.
Cada capa está en un módulo propio, y una capa solo usa las que están arriba
de ella en la lista:

| Capa | Módulo | Responsabilidad |
|---|---|---|
| Warehouse | `BackEnd/models/warehouse.py`, `BackEnd/utils/graph_builder.py` | Dígrafo de pasillos, obstáculos, accesos a racks y zonas, validación con Kosaraju. |
| Products / Orders | `BackEnd/models/entities.py` | `Producto`, `Pedido`, `DetallePedido`, `Picker`, `Wave`, `ZonaDespacho`, `Puerta`. El `Warehouse` los indexa en diccionarios (O(1)). |
| Wave Manager | `BackEnd/controllers/wave_manager.py`, `BackEnd/data_structures/max_heap_pedidos.py` | Arma las waves (Max-Heap por prioridad + costo marginal en el dígrafo) y las asigna a los pickers más cercanos. |
| Pathfinding | `BackEnd/controllers/path_finding.py` | Dijkstra punto a punto y multidestino, y las estrategias *Orden de pedidos* y *Cercanía*. |
| Simulation | `BackEnd/controllers/turn_collision_manager.py`, `BackEnd/controllers/simulador.py` | Mueve a todos los pickers un paso por turno evitando choques. El `Simulador` orquesta todo y agrega historial, comparación y sesiones. |
| Visualization | `FrontEnd/` | Pygame. Solo llama al `Simulador` (a través de `FrontEnd/services/biblioteca.py`). |

Entrada y salida:

- `BackEnd/utils/file_parser.py` lee y escribe los JSON.
- `BackEnd/utils/validador_escenario.py` valida un JSON antes de construirlo.
- `BackEnd/utils/scenario_generator.py` genera escenarios de forma determinista.

## Diagrama de clases

```mermaid
classDiagram
    direction LR

    class Warehouse {
        +int ancho_x
        +int largo_y
        +Digrafo grafo_pasillos
        +Dict obstaculos
        +Dict racks
        +Dict zonas_despacho
        +Dict puertas
        +Dict catalogo_productos
        +Dict pedidos
        +List pickers
        +Dict acceso_rack_a_pasillo
        +Dict accesos_zona_a_pasillo
        +List advertencias
        +obtener_celda(x, y)
        +obtener_celda_acceso_pasillo(x, y)
        +buscar_producto_O1(id)
        +buscar_pedido_O1(id)
        +descontar_stock(id, cant)
    }
    class Digrafo {
        +Dict nodos
        +Dict lista_adyacencia
        +Dict bloqueos_temporales
        +agregar_nodo()
        +agregar_arista_dirigida()
        +obtener_vecinos(coord)
        +obtener_vecinos_validos(coord, paso, picker)
    }
    class NodoGrafo {
        +int x
        +int y
        +SentidoCirculacion sentido_permitido
        +str pasillo_id
        +List racks_adyacentes
        +List zonas_despacho_adyacentes
    }
    class GraphBuilder {
        <<static>>
        +construir_warehouse_desde_dict(data)$
        +componentes_fuertemente_conexas(wh)$
        +validar_grafo(wh, pickers)$
    }
    class Producto {
        +str id_producto
        +str nombre
        +int ubicacion_x
        +int ubicacion_y
        +int ubicacion_z
        +int cantidad_disponible
        +float peso_kg
    }
    class Pedido {
        +str id_pedido
        +int prioridad
        +List items
        +EstadoPedido estado
    }
    class Wave {
        +str id_wave
        +EstadoWave estado
        +List pedidos
        +int unidades_totales
        +float peso_total_kg
        +str id_zona_despacho
        +Dict pedidos_por_picker
        +agregar_pedido()
        +asignar_equipo_pickers()
    }
    class Picker {
        +str id_picker
        +float capacidad_carga_kg
        +Coord posicion_actual
        +List ruta_asignada
        +List objetivos_pendientes
        +Dict productos_recogidos
        +int turnos_bloqueado
    }
    class MaxHeapPedidos {
        +construir_monticulo(pedidos)
        +extraer_maximo()
        +eliminar_pedido(id)
        +obtener_candidatos_factibles(cap)
    }
    class WaveManager {
        +generar_waves(wh, distancias)
        +asignar_y_ejecutar_waves_seleccionadas(ids, wh, estrategia)
        +notificar_picker_descargo_en_despacho()
    }
    class Pathfinding {
        <<static>>
        +calcular_ruta_dijkstra()$
        +calcular_ruta_greedy()$
        +calcular_estrategia_orden_pedidos()$
        +calcular_estrategia_cercania_multidestino()$
        +construir_matriz_distancias_productos()$
        +desviar_por(picker, celda, grafo)$
    }
    class TurnAndCollisionManager {
        +validar_movimiento_simultaneo()
        +resolver_conflicto()
        +avanzar_un_turno_simulacion()
    }
    class Simulador {
        +EstadoSimulacion estado
        +List historial
        +generar_waves()
        +iniciar_waves(ids, estrategia)
        +avanzar()
        +retroceder()
        +reiniciar()
        +comparar_estrategias(ids)
        +guardar(ruta)
    }
    class EstadoSimulacion {
        +Warehouse warehouse
        +WaveManager gestor_waves
        +TurnAndCollisionManager colisiones
        +int paso
        +List tandas
        +Dict por_recoger
        +List eventos
    }
    class App {
        <<Pygame>>
        +Simulador sim
        +Biblioteca biblioteca
        +VistaMapa mapa
    }

    Warehouse *-- Digrafo
    Digrafo *-- NodoGrafo
    Warehouse o-- Producto
    Warehouse o-- Pedido
    Warehouse o-- Picker
    Wave o-- Pedido
    GraphBuilder ..> Warehouse : construye y valida
    WaveManager *-- MaxHeapPedidos
    WaveManager o-- Wave
    WaveManager ..> Pathfinding
    TurnAndCollisionManager ..> Pathfinding
    Simulador *-- EstadoSimulacion
    EstadoSimulacion *-- Warehouse
    EstadoSimulacion *-- WaveManager
    EstadoSimulacion *-- TurnAndCollisionManager
    App --> Simulador
```

## Flujo de una simulación

```mermaid
sequenceDiagram
    participant UI as Interfaz (App)
    participant S as Simulador
    participant G as GraphBuilder
    participant W as WaveManager
    participant P as Pathfinding
    participant T as TurnAndCollisionManager

    UI->>S: Simulador(json)
    S->>G: construir_warehouse_desde_dict
    G-->>S: Warehouse (dígrafo validado con Kosaraju)
    S->>P: construir_matriz_distancias_productos
    UI->>S: generar_waves()
    S->>W: generar_waves(wh, matriz)
    UI->>S: iniciar_waves(ids, estrategia)
    S->>W: asignar_y_ejecutar_waves_seleccionadas
    W->>P: estrategia Orden o Cercanía (Dijkstra)
    loop cada turno
        UI->>S: avanzar()
        S->>T: avanzar_un_turno_simulacion
        T->>P: desvíos si hay conflicto
        S-->>UI: recogidas, descargas, eventos
    end
```

## Decisiones de la capa de simulación

- **Historial para retroceder.** Cada 10 turnos se guarda una copia completa
  del estado. El grafo, los obstáculos y la matriz de distancias no se
  copian, porque no cambian. Para volver a un turno intermedio se parte de la
  copia anterior y se re-simula; la simulación es determinista, así que se
  llega exactamente al mismo estado. El historial ocupa unas 10 veces menos
  memoria y retroceder un paso cuesta a lo sumo 9 turnos de simulación.
- **Sesiones.** Al guardar se escribe el escenario inicial más la lista de
  acciones (generar waves, iniciar, avanzar *n*, retroceder…). Al cargar, las
  acciones se repiten y se llega al mismo turno, con el historial completo.
- **Comparación.** `comparar_estrategias` copia el estado, corre las mismas
  waves con cada estrategia hasta el final y devuelve las métricas. La
  simulación real no se modifica.
- **Cola de espera.** Si se eligen más waves que pickers libres, las que
  sobran quedan en espera. Se asignan solas cuando un picker descarga.
