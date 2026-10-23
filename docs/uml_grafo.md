# Diagrama de clases del grafo del almacén

Generado a partir de `BackEnd/enums/enums.py`, `BackEnd/models/entity.py`, `BackEnd/models/warehouse.py` y `BackEnd/utils/graph_builder.py`. De `entity.py` se muestran solo las clases que usa el grafo (también tiene `Order`, `Picker`, `Wave` y `DetallePedido`, que son del equipo). `Sentido` es un alias de `SentidoCirculacion`.
`Coord` es un alias de tipo para `Tuple[int, int]`.

```mermaid
classDiagram
    direction LR

    class SentidoCirculacion {
        <<enumeration>>
        N
        S
        E
        O
        AMBOS
        NINGUNO
    }

    class TipoCelda {
        <<enumeration>>
        PASILLO
        RACK
        ZONA_DESPACHO
        PUERTA
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
        +Dict~int, Product~ productos_en_z
        +apilar_producto(z, producto)
    }

    class Product {
        <<dataclass>>
        +str id_producto
        +str nombre
        +str rack_id
        +int ubicacion_x
        +int ubicacion_y
        +int altura_z
        +int cantidad_disponible
        +float peso_kg
        +id() str
        +x() int
        +y() int
        +z() int
    }

    class ElementoRectangular {
        +str id
        +int x
        +int y
        +int ancho
        +int alto
    }

    class Rack

    class ZonaDespacho {
        +str puerta_id
        +float peso_max_kg
        +float peso_actual_kg
        +registrar_carga(peso)
    }

    class Puerta {
        +str id
        +str tipo
        +int x
        +int y
    }

    class NodoGrafo {
        +int x
        +int y
        +SentidoCirculacion sentido_permitido
        +str pasillo_id
        +List~CeldaRack~ racks_adyacentes
        +List~str~ zonas_despacho_adyacentes
    }

    class Digrafo {
        +Dict~Coord, NodoGrafo~ nodos
        +Dict~Coord, List~ lista_adyacencia
        +agregar_nodo(x, y, sentido, pasillo_id) NodoGrafo
        +agregar_arista_dirigida(origen, destino)
        +obtener_vecinos(coord) List
    }

    class Warehouse {
        +int ancho_x
        +int largo_y
        +Digrafo grafo_pasillos
        +Dict~Coord, Celda~ obstaculos
        +Dict~str, Rack~ racks
        +Dict~str, ZonaDespacho~ zonas_despacho
        +Dict~str, Puerta~ puertas
        +Dict~str, Product~ catalogo_productos
        +Dict~Coord, Coord~ acceso_rack_a_pasillo
        +Dict~Coord, List~ accesos_rack_a_pasillo
        +Dict~str, List~ accesos_zona_a_pasillo
        +List~str~ advertencias
        +dentro(x, y) bool
        +obtener_celda(x, y) Celda
        +obtener_nodo_acceso_producto(prod_id) Coord
        +obtener_nodos_acceso_producto(prod_id) List
        +obtener_nodos_acceso_zona(zona_id) List
        +imprimir_mapa(camino_bfs)
    }

    class GraphBuilder {
        <<static>>
        +construir_warehouse_desde_dict(data)$ Warehouse
        +validar_grafo(wh, posiciones_pickers)$ List
        +componentes_fuertemente_conexas(wh)$ List
        -_construir_digrafo(wh, pasillos_declarados)$
        -_direcciones_segun_sentido(sentido)$ List
        -_es_contramano(dx, dy, sentido_destino)$ bool
        -_dirs_acceso(rack, x, y)$ List
    }

    Celda <|-- CeldaPasillo
    Celda <|-- CeldaRack
    ElementoRectangular <|-- Rack
    ElementoRectangular <|-- ZonaDespacho

    Celda --> TipoCelda
    NodoGrafo --> SentidoCirculacion
    CeldaPasillo --> SentidoCirculacion
    CeldaRack o-- "0..*" Product : productos_en_z
    NodoGrafo o-- "0..*" CeldaRack : racks_adyacentes
    Digrafo *-- "0..*" NodoGrafo : nodos
    Warehouse *-- "1" Digrafo : grafo_pasillos
    Warehouse *-- "0..*" Celda : obstaculos
    Warehouse o-- "0..*" Rack
    Warehouse o-- "0..*" ZonaDespacho
    Warehouse o-- "0..*" Puerta
    Warehouse o-- "0..*" Product : catalogo_productos
    ZonaDespacho ..> Puerta : puerta_id
    GraphBuilder ..> Warehouse : construye y valida
    Warehouse ..> CeldaPasillo : obtener_celda la arma al vuelo
```

## ¿Qué es nodo y qué no?

No hay una matriz con todas las celdas. Cada coordenada `(x, y)` del almacén está en **uno solo** de estos dos diccionarios: `grafo_pasillos.nodos` (pasillos) o `obstaculos` (lo demás).

| Celda / elemento | ¿Es nodo del grafo? | Dónde se guarda y cómo se relaciona con el grafo |
|---|---|---|
| Pasillo declarado (N, S, E, O, AMBOS) | **Sí** | `grafo_pasillos.nodos`, con `pasillo_id` y su sentido. Sus aristas salientes dependen de su sentido y del sentido del destino (sin contramano). |
| Celda no declarada | **Sí** | `grafo_pasillos.nodos`, con sentido AMBOS y `pasillo_id = None` (enunciado 3.5). |
| Pasillo con sentido NINGUNO | Sí, pero aislado | No tiene aristas de salida y nadie puede entrar (siempre es contramano). |
| Rack (`CeldaRack`) | **No** | `obstaculos`, con su pila `productos_en_z`. Cada celda se recoge desde el pasillo de su costado largo: `accesos_rack_a_pasillo`, `NodoGrafo.racks_adyacentes`. |
| Zona de despacho | **No** | `obstaculos` (tipo `ZONA_DESPACHO`). Sus pasillos pegados están en `accesos_zona_a_pasillo` y en `NodoGrafo.zonas_despacho_adyacentes`. |
| Puerta | **No** | `obstaculos` (tipo `PUERTA`) y `wh.puertas`. No interviene en el grafo. |
