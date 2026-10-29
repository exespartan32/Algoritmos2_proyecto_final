# UML del proyecto

Diagramas de clases armados a partir del código actual de la rama `laure`.
Están divididos en cuatro partes para que se puedan leer:

1. **Vista general**: los paquetes y quién usa a quién.
2. **Modelo**: el almacén, el dígrafo y las entidades (productos, pedidos, waves, pickers).
3. **Lógica**: construcción del grafo, waves, recorridos, colisiones y simulación.
4. **Interfaz**: la aplicación Pygame.

Las imágenes están en `docs/uml/`. Este archivo tiene el código fuente
(Mermaid), que GitHub muestra directamente.

**Convenciones:**

- Visibilidad: `+` público, `-` privado (en Python empieza con `_`).
- `$` marca un método estático.
- `<<dataclass>>` es una clase de datos de Python, `<<enum>>` una enumeración
  y `<<módulo>>` un archivo con funciones sueltas.
- Relaciones:
  - `*--` composición: la parte no existe sin el todo.
  - `o--` agregación: tiene referencias a objetos que existen por su cuenta.
  - `<|--` herencia.
  - `..>` dependencia: usa, crea o recibe.
- `Coord` es `Tuple[int, int]`.

---

## 1. Vista general (paquetes)

![Vista general](uml/1_vista_general.png)

```mermaid
flowchart LR
    subgraph FrontEnd["FrontEnd (Visualization)"]
        gui["gui.py"]
        App["views.App"]
        Mapa["views.VistaMapa"]
        UI["views.UIElements"]
        Bib["services.Biblioteca"]
        Spr["sprites (celdas y pickers)"]
        Inp["events.input_handler"]
    end
    subgraph Sim["Simulation"]
        S["controllers.Simulador"]
        T["controllers.TurnAndCollisionManager"]
    end
    subgraph PF["Pathfinding"]
        P["controllers.Pathfinding"]
    end
    subgraph WM["Wave Manager"]
        W["controllers.WaveManager"]
        H["data_structures.MaxHeapPedidos"]
    end
    subgraph WH["Warehouse + Products / Orders"]
        GB["utils.GraphBuilder"]
        Wh["models.Warehouse / Digrafo"]
        E["models.entities"]
        En["enums"]
    end
    subgraph IO["Entrada y salida"]
        FP["utils.FileParser"]
        Gen["utils.ScenarioGenerator"]
        Val["utils.validador_escenario"]
    end
    main["main.py (consola)"]

    gui --> App
    App --> Mapa & UI & Bib & Inp & Spr
    Bib --> S & Gen & Val
    S --> W & P & T & GB
    T --> P
    W --> H & P & Wh
    GB --> Wh & E
    Wh --> E & En
    Gen --> GB & Val
    FP --> GB
    main --> FP & W & P & T
```

---

## 2. Modelo: almacén, dígrafo y entidades

![Modelo](uml/2_modelo.png)

```mermaid
classDiagram
    direction LR

    class SentidoCirculacion {
        <<enum>>
        N
        S
        E
        O
        AMBOS
        NINGUNO
    }
    class TipoCelda {
        <<enum>>
        PASILLO
        RACK
        PUERTA
        ZONA_DESPACHO
    }
    class TipoPuerta {
        <<enum>>
        INBOUND
        OUTBOUND
        AMBOS
    }
    class EstadoPedido {
        <<enum>>
        PENDIENTE
        EN_WAVE
        EN_PREPARACION
        PREPARADO
        IRREALIZABLE
    }
    class EstadoWave {
        <<enum>>
        PENDIENTE
        EN_EJECUCION
        FINALIZADA
        CANCELADA
    }
    class EstrategiaRuteo {
        <<enum>>
        ORDEN_PEDIDOS_DIJKSTRA
        CERCANIA_DIJKSTRA_MULTIDESTINO
    }

    class Warehouse {
        +int ancho_x
        +int largo_y
        +Digrafo grafo_pasillos
        +Dict~Coord, Celda~ obstaculos
        +Dict~str, Rack~ racks
        +Dict~str, ZonaDespacho~ zonas_despacho
        +Dict~str, Puerta~ puertas
        +Dict~str, Producto~ catalogo_productos
        +Dict~str, Pedido~ pedidos
        +List~Picker~ pickers
        +int wave_max_pedidos
        +int wave_max_productos
        +Dict~Coord, Coord~ acceso_rack_a_pasillo
        +Dict~Coord, List~ accesos_rack_a_pasillo
        +Dict~str, List~ accesos_zona_a_pasillo
        +List~str~ advertencias
        +dentro(x, y) bool
        +obtener_celda(x, y) Celda
        +buscar_producto_O1(id) Producto
        +buscar_pedido_O1(id) Pedido
        +obtener_todos_los_productos() List
        +obtener_todos_los_pedidos() List
        +actualizar_estado_pedido_O1(id, estado) bool
        +descontar_stock(id, cantidad) bool
        +obtener_celda_acceso_pasillo(x, y) Coord
        +obtener_nodo_acceso_producto(id) Coord
        +obtener_nodos_acceso_producto(id) List
        +obtener_nodos_acceso_zona(id) List
        +imprimir_mapa(camino)
    }
    class Digrafo {
        +Dict~Coord, NodoGrafo~ nodos
        +Dict~Coord, List~ lista_adyacencia
        +Dict bloqueos_temporales
        +Set~Coord~ nodos_evasion_actual
        +agregar_nodo(x, y, sentido, pasillo_id) NodoGrafo
        +agregar_arista_dirigida(origen, destino)
        +obtener_vecinos(coord) List
        +obtener_vecinos_validos(coord, paso, picker) List
        +bloquear_celda_temporal(coord, paso, picker)
        +limpiar_bloqueos_antiguos(paso)
    }
    class NodoGrafo {
        +int x
        +int y
        +SentidoCirculacion sentido_permitido
        +str pasillo_id
        +List~CeldaRack~ racks_adyacentes
        +List~str~ zonas_despacho_adyacentes
    }

    class Celda {
        +int x
        +int y
        +TipoCelda tipo
        +str elemento_id
    }
    class CeldaPasillo {
        +SentidoCirculacion sentido
    }
    class CeldaRack {
        +Dict~int, Producto~ productos_en_z
        +apilar_producto(z, producto)
    }
    class ElementoRectangular {
        +str id
        +int x
        +int y
        +int ancho
        +int alto
    }
    class Rack {
        +int niveles
    }
    class ZonaDespacho {
        +str puerta_id
        +float peso_max_kg
        +float peso_actual_kg
        +float peso_comprometido_waves_kg
        +puede_recibir_carga(peso) bool
        +comprometer_carga_wave(peso)
        +registrar_descarga_fisica(peso)
    }
    class Puerta {
        +str id
        +TipoPuerta tipo
        +int x
        +int y
        +permite_despacho_salida() bool
    }

    class Producto {
        <<dataclass>>
        +str id_producto
        +str nombre
        +str rack_id
        +int ubicacion_x
        +int ubicacion_y
        +int ubicacion_z
        +int cantidad_disponible
        +float peso_kg
        +coordenadas_xy() Coord
        +coordenadas_xyz() Tuple
    }
    class DetallePedido {
        <<dataclass>>
        +str producto_id
        +int cantidad
    }
    class Pedido {
        <<dataclass>>
        +str id_pedido
        +int prioridad
        +List~DetallePedido~ items
        +EstadoPedido estado
        +Set~str~ waves_asignadas
        +obtener_cantidad_productos() int
        +obtener_peso_total(fuente) float
        +obtener_ubicaciones_xyz(fuente) Set
    }
    class Wave {
        <<dataclass>>
        +str id_wave
        +EstadoWave estado
        +int wave_max_pedidos
        +int wave_max_productos
        +List~Pedido~ pedidos
        +str id_zona_despacho
        +float peso_total_kg
        +int unidades_totales
        +List~str~ ids_pickers_asignados
        +Dict pedidos_por_picker
        +Dict destinos_xy_por_picker
        +Set~Coord~ ubicaciones_xy
        +puede_agregar_pedido(pedido) bool
        +agregar_pedido(pedido) bool
        +asignar_equipo_pickers(pickers)
    }
    class Picker {
        <<dataclass>>
        +str id_picker
        +float capacidad_carga_kg
        +Coord posicion_actual
        +float peso_actual_kg
        +str id_wave_actual
        +Coord destino_despacho_actual
        +List~Coord~ ruta_asignada
        +List~Coord~ objetivos_pendientes
        +List~TareaWavePicker~ cola_waves_asignadas
        +Dict~str, int~ productos_recogidos
        +int turnos_bloqueado
        +int turnos_pausa
        +int turnos_busqueda
        +int turnos_descargando
        +ListaDeInmutables historial_recorrido
        +puede_cargar(peso) bool
        +iniciar_siguiente_tarea_en_cola() TareaWavePicker
    }
    class TareaWavePicker {
        <<dataclass>>
        +str id_wave
        +str id_zona_despacho
        +Coord destino_despacho_pasillo
        +List~str~ pedidos_asignados
        +List~Coord~ destinos_recoleccion_pasillo
        +float peso_lote_kg
        +List~Coord~ ruta_calculada
    }
    class ListaDeInmutables {
        <<list>>
        +__deepcopy__(memo)
    }

    Warehouse *-- "1" Digrafo : grafo_pasillos
    Digrafo *-- "0..*" NodoGrafo : nodos
    Warehouse *-- "0..*" Celda : obstaculos
    Warehouse o-- "0..*" Rack
    Warehouse o-- "0..*" ZonaDespacho
    Warehouse o-- "0..*" Puerta
    Warehouse o-- "0..*" Producto : catalogo_productos
    Warehouse o-- "0..*" Pedido : pedidos
    Warehouse o-- "0..*" Picker : pickers
    Celda <|-- CeldaPasillo
    Celda <|-- CeldaRack
    ElementoRectangular <|-- Rack
    ElementoRectangular <|-- ZonaDespacho
    CeldaRack o-- "0..*" Producto : productos_en_z
    NodoGrafo o-- "0..*" CeldaRack : racks_adyacentes
    Pedido *-- "1..*" DetallePedido : items
    Wave o-- "1..*" Pedido : pedidos
    Picker *-- "0..*" TareaWavePicker : cola
    Picker *-- ListaDeInmutables : historial
    ZonaDespacho ..> Puerta : puerta_id
    NodoGrafo --> SentidoCirculacion
    Celda --> TipoCelda
    Puerta --> TipoPuerta
    Pedido --> EstadoPedido
    Wave --> EstadoWave
```

---

## 3. Lógica: grafo, waves, recorridos, colisiones y simulación

![Lógica](uml/3_logica.png)

```mermaid
classDiagram
    direction TB

    class GraphBuilder {
        <<static>>
        +construir_warehouse_desde_dict(data)$ Warehouse
        +componentes_fuertemente_conexas(wh)$ List
        +validar_grafo(wh, pickers)$ List
        -_construir_digrafo(wh, pasillos)$
        -_direcciones_segun_sentido(sentido)$ List
        -_es_contramano(dx, dy, sentido)$ bool
        -_dirs_acceso(rack, x, y)$ List
    }
    class FileParser {
        <<static>>
        +resolver_ruta(nombre)$ str
        +leer_json(ruta)$ Dict
        +cargar_warehouse_desde_json(ruta)$ Warehouse
        +guardar_estado_warehouse_json(wh, nombre)$ str
    }
    class ScenarioGenerator {
        <<static>>
        +validar_parametros(params)$ Dict
        +generar_escenario_dict(estantes, pasillos, productos, localizacion, pedidos, max_por_pedido, wave_pedidos, wave_unidades, pickers)$ Dict
        +verificar(datos)$ Warehouse
        +generar_y_guardar(ruta, params)$ Dict
        -_celdas_ordenadas(racks, zonas, localizacion)$ List
        -_coprimo(n)$ int
    }
    class validador_escenario {
        <<módulo>>
        +validar_escenario(data)
        +celdas(item) List
    }

    class MaxHeapPedidos {
        -List~Pedido~ _heap
        +construir_monticulo(pedidos)
        +insertar(pedido)
        +extraer_maximo() Pedido
        +eliminar_pedido(id) bool
        +obtener_candidatos_factibles(capacidad) List
        +esta_vacio() bool
        +tamano() int
        -_max_heapify(i)
        -_tiene_mayor_prioridad(a, b) bool
    }
    class WaveManager {
        +str estrategia_armado
        +int wave_max_pedidos
        +int wave_max_productos
        +int max_pickers_por_wave
        +MaxHeapPedidos cola_prioridad
        +Dict proveedor_distancias
        +List~Wave~ waves_creadas
        +Dict~str, Wave~ waves_por_id
        +List~str~ errores_validacion
        +Dict traza_armado
        +generar_waves(wh, distancias) List~Wave~
        +validar_pedidos_entrada(pedidos, wh) List
        +calcular_costo_marginal_promedio(wave, pedido, wh, dist) float
        +seleccionar_zona_despacho_para_wave(wh, pedido) ZonaDespacho
        +asignar_y_ejecutar_waves_seleccionadas(ids, wh, estrategia, pickers_por_wave) Dict
        +calcular_distancia_picker_a_wave(picker, wave, wh) float
        +notificar_picker_descargo_en_despacho(wave, picker, pickers, wh)
        +obtener_waves_disponibles() List
        +obtener_pickers_libres(pickers)$ List
        -_pasillos_de(pedido, wh)$ Set
        -_elegir_celda_despacho(accesos, picker, destinos, pickers, wh)$ Coord
        -_equipo_puede_cargar(pedidos, equipo, wh)$ bool
        -_es_repartible_en_equipo_pickers(pedidos, pickers, wh) Tuple
        -_tiene_stock_suficiente_sin_modificar(pedido, wh, comprometido) bool
    }

    class Pathfinding {
        <<static>>
        +calcular_ruta_dijkstra(origen, destino, grafo, ...)$ Tuple
        +calcular_ruta_greedy(origen, destinos, grafo, ...)$ Tuple
        +calcular_estrategia_orden_pedidos(grafo, origen, destinos, retorno, wh)$ RutaResultado
        +calcular_estrategia_cercania_multidestino(grafo, origen, destinos, retorno, wh)$ RutaResultado
        +calcular_mapa_distancias_desde(origen, grafo)$ Dict
        +construir_matriz_distancias_productos(coords, grafo, wh)$ Dict
        +obtener_celda_acceso_pasillo(coord, grafo, wh)$ Coord
        +proximo_objetivo_en_ruta(picker)$ Coord
        +desviar_por(picker, celda, grafo)$ List
        +recalcular_evitando_obstaculo(grafo, picker, paso, bloqueadas) List
    }
    class RutaResultado {
        +List~Coord~ camino_completo
        +List~Coord~ nodos_explorados
        +List~Coord~ orden_exploracion
        +int distancia_total
        +int aristas_recorridas
        +int expansiones
        +float tiempo_ejecucion_ms
        +List~Coord~ destinos_inalcanzables
    }

    class TurnAndCollisionManager {
        +int max_turnos_bloqueo_recalculo
        +int turnos_para_ceder
        +int turnos_estela
        +int turnos_recogida
        +int turnos_descarga
        +Dict~Coord, Tuple~ estela
        +Dict reservas_celdas
        +List~str~ eventos_colision
        +int total_esperas_aplicadas
        +int total_desvios_recalculados
        +avanzar_un_turno_simulacion(pickers, paso, grafo, gestor, wh) int
        +validar_movimiento_simultaneo(pickers, paso, grafo)
        +resolver_conflicto(prioritario, cedente, grafo, paso, ocupadas)
        +detectar_cruce_o_colision(p1, p2) bool
        -_buscar_celda_evasion_lateral(picker, prohibidas, grafo) Coord
    }

    class Simulador {
        +Dict datos_base
        +Dict config
        +str estrategia
        +int pickers_por_wave
        +EstadoSimulacion estado
        +List historial
        +List acciones
        +Dict matriz_distancias
        +Dict celdas
        +Set~Coord~ intersecciones
        +configurar(pedidos, unidades, pickers, estrategia_waves)
        +agregar_pedido(prioridad, items) str
        +interpretar_items(texto)$ List
        +generar_waves() List~Wave~
        +iniciar_waves(ids, estrategia, pickers_por_wave) Dict
        +cambiar_estrategia(estrategia) bool
        +avanzar(guardar_historial) bool
        +avanzar_hasta_terminar(max) int
        +retroceder() bool
        +reiniciar() bool
        +comparar_estrategias(ids, pickers_por_wave) Dict
        +comparar_armado() Dict
        +productos() List
        +pedidos() List
        +resumen_waves() List
        +resumen_pickers() List
        +metricas() Dict
        +a_json() Dict
        +guardar(ruta) Path
        +cargar(ruta)$ Simulador
        -_asignar(tanda, ids)
        -_planificar(wh, wave, picker, tarea, estrategia) Plan
        -_recoger(picker)
        -_entregar(picker, wave)
        -_copiar(estado) EstadoSimulacion
        -_reproducir(sesion)
    }
    class EstadoSimulacion {
        +Warehouse warehouse
        +WaveManager gestor_waves
        +TurnAndCollisionManager colisiones
        +int paso
        +List~Dict~ tandas
        +Dict por_recoger
        +Dict~str, Plan~ planes
        +ListaDeInmutables eventos
        +List entregas
        +Dict mirando
    }
    class Plan {
        <<dict inmutable>>
        ruta, destinos, despacho
        orden_exploracion, explorados
        distancia, aristas, nodos_visitados
        expansiones, tiempo_ms, turnos_busqueda
    }

    WaveManager *-- MaxHeapPedidos : cola_prioridad
    WaveManager o-- "0..*" Wave : waves_creadas
    WaveManager ..> Pathfinding : rutas y distancias
    WaveManager ..> Warehouse
    Pathfinding ..> RutaResultado : devuelve
    Pathfinding ..> Digrafo : recorre
    TurnAndCollisionManager ..> Pathfinding : desvíos
    TurnAndCollisionManager ..> Picker : mueve
    TurnAndCollisionManager ..> WaveManager : avisa descargas
    Simulador *-- EstadoSimulacion : estado
    Simulador o-- "0..*" EstadoSimulacion : historial
    EstadoSimulacion *-- Warehouse
    EstadoSimulacion *-- WaveManager
    EstadoSimulacion *-- TurnAndCollisionManager
    EstadoSimulacion o-- "0..*" Plan
    Simulador ..> GraphBuilder : construye
    Simulador ..> Pathfinding : planifica y matriz
    GraphBuilder ..> Warehouse : crea y valida
    FileParser ..> GraphBuilder
    ScenarioGenerator ..> GraphBuilder : verifica
    ScenarioGenerator ..> validador_escenario
```

---

## 4. Interfaz (Pygame)

![Interfaz](uml/4_interfaz.png)

```mermaid
classDiagram
    direction LR

    class UIElements {
        <<mixin>>
        +fuente(tam, negrita) Font
        +texto(valor, x, y, ...)
        +parrafo(valor, x, y, ancho, ...) int
        +caja(x, y, w, h, color) Rect
        +boton(etiqueta, x, y, w, accion, ...) Rect
        +casilla(x, y, marcada, accion)
        +campo(x, y, w, valor, enfocado, accion)
        +zona_clic(rect, accion)
        +paginador(atributo, total, por_pagina, x, y)
    }
    class App {
        +Surface ventana
        +Surface lienzo
        +Simulador sim
        +Biblioteca biblioteca
        +VistaMapa mapa
        +str pagina
        +dialogo
        +str pestana
        +bool reproduciendo
        +int velocidad
        +Set seleccion
        +str picker_foco
        +Dict animacion
        +Dict angulos
        +Dict comparacion
        +Dict comparacion_armado
        +run(cuadros)
        +dibujar()
        +accion(accion)
        +cargar(ruta)
        +importar(ruta)
        +mover(funcion, duracion) any
        +posicion_animada(pid, pos) Tuple
        +busquedas_activas() Dict
        +paso_automatico(dt)
        +a_lienzo(pos) Coord
        +pantalla_inicio()
        +pantalla_simulacion()
        +panel_productos() / panel_pedidos() / panel_waves()
        +panel_pickers() / panel_metricas() / panel_eventos()
        +dialogo_waves() / dialogo_comparar() / dialogo_armado()
        +dialogo_generador() / dialogo_pedido() / dialogo_config()
        -_a_*() acciones de botones
    }
    class VistaMapa {
        +App app
        +Rect area
        +float zoom
        +List desplazamiento
        +dibujar()
        +dibujar_busqueda(color, plan, progreso, lado) Tuple
        +leyenda(x, y)
        +zoom_en(pos, factor)
        +mover(dx, dy)
        +centrar()
        +geometria() Tuple
        +rect_celda(coord) Rect
        +centro(coord) Tuple
        +celda_en(pos) Coord
        +visibles() Tuple
        +orden_unico(plan) List
        -_fondo(plan, explorados) Surface
        -_limitar()
    }
    class Biblioteca {
        +Path carpeta
        +archivos() List~Path~
        +abrir(ruta)$ Simulador
        +leer(ruta)$ Dict
        +es_sesion(ruta)$ bool
        +importar(ruta) Path
        +generar(params) Path
        +guardar_sesion(sim, nombre) Path
        +eliminar(ruta)
    }
    class input_handler {
        <<módulo>>
        +manejar_evento(app, evento)
    }
    class node_sprite {
        <<módulo>>
        +dibujar_celda(superficie, rect, tipo, sentido, ...)
    }
    class picker_sprite {
        <<módulo>>
        +dibujar_picker(superficie, centro, lado, indice, angulo, nombre, ...)
        +sprite(indice, angulo, lado) Surface
        +angulo_para(dx, dy, anterior) int
        +color_picker(indice) Color
    }
    class gui {
        <<módulo>>
        +main()
    }

    UIElements <|-- App
    App *-- VistaMapa : mapa
    App *-- Biblioteca : biblioteca
    App o-- Simulador : sim
    App ..> input_handler : eventos
    VistaMapa ..> node_sprite
    VistaMapa ..> picker_sprite
    Biblioteca ..> Simulador : crea
    Biblioteca ..> ScenarioGenerator
    gui ..> App
```

---

## Clases que no usa nadie

Siguen en el repositorio, pero ningún módulo las importa:

| Clase | Archivo | Observación |
|---|---|---|
| `CatalogManager`, `HashTableUniversal`, `NodoHash` | `BackEnd/models/catalog_manager.py` | Catálogo con hashing universal de una versión anterior. Hoy el `Warehouse` guarda productos y pedidos en diccionarios. |
| `GrafoWarehouse` | `BackEnd/data_structures/grafo_warehouse.py` | Grafo anterior basado en una grilla. Importa `BackEnd.models.warehouse_models`, que no existe. |
| `EstadoSimulacion` (enum) | `BackEnd/enums/enums.py` | No tiene nada que ver con la clase `EstadoSimulacion` del simulador, que es la que sí se usa. |
