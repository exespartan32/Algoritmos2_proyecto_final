# Cómo está implementado el grafo del almacén

Este documento explica el código de `BackEnd/models/warehouse.py` y `BackEnd/utils/graph_builder.py`, que usan las clases de celdas y elementos de `BackEnd/models/entity.py` y los enums `TipoCelda` y `SentidoCirculacion` (alias `Sentido`) de `BackEnd/enums/enums.py`. Todo lo que se describe acá está en ese código y está probado en `tests/test_grafo.py`.

**Mi parte del trabajo** es la estructura que modela el almacén: leer el JSON, armar el dígrafo de pasillos, calcular dónde se recoge cada producto y validar que el mapa sea transitable. Los algoritmos de recorrido (BFS, Dijkstra), las waves y la simulación los hacen mis compañeros, usando esta estructura.

---

## 1. Resumen en 5 líneas

1. El almacén se modela como un **grafo dirigido (dígrafo)** que se construye **directamente desde el JSON**, sin armar antes una matriz con todas las celdas.
2. **Nodo** = una celda de **pasillo** `(x, y)`, que es donde puede pararse un picker. Toda coordenada del almacén que no esté ocupada por un obstáculo es un pasillo.
3. **Arista** = un movimiento permitido de **1 paso** (costo 1) entre dos pasillos ortogonalmente vecinos. Es dirigida porque los pasillos tienen sentido de circulación (N, S, E, O, AMBOS).
4. **No son nodos** los racks, las zonas de despacho ni las puertas: son obstáculos que el picker no atraviesa (enunciado 3.6). Se guardan aparte, en un diccionario `obstaculos`, y a racks y zonas se los "toca" desde el pasillo de al lado.
5. Después de construirlo, el grafo se valida con **Kosaraju**: si no queda una sola componente fuertemente conexa, hay pasillos de los que no se puede volver (trampas), y se avisa con advertencias.

---

## 2. Estructuras de datos

### 2.1 Qué se guarda (no hay matriz)

Cada coordenada `(x, y)` del almacén está en **exactamente uno** de estos dos diccionarios:

| Estructura | Clave → valor | Qué guarda |
|---|---|---|
| `wh.grafo_pasillos.nodos` | `(x, y)` → `NodoGrafo` | Las celdas de **pasillo**: su sentido, el id del pasillo declarado (o `None` si es una celda libre), y qué racks y zonas tiene al costado. |
| `wh.obstaculos` | `(x, y)` → `Celda` | Las celdas que **no** son nodo: `CeldaRack` (con su pila de productos `productos_en_z`), o una `Celda` de tipo `ZONA_DESPACHO` o `PUERTA`. |

La conectividad está en `wh.grafo_pasillos.lista_adyacencia`: `(x, y)` → lista de nodos a los que se puede ir en un paso.

Además, `Warehouse` guarda índices de acceso ya calculados:

- `accesos_rack_a_pasillo[(x_rack, y_rack)] -> [pasillos]`: desde qué pasillos se recoge esa celda de rack.
- `acceso_rack_a_pasillo[(x_rack, y_rack)] -> pasillo`: el primero de esa lista (compatibilidad con código anterior).
- `accesos_zona_a_pasillo[zona_id] -> [pasillos]`: los pasillos pegados a esa zona de despacho.
- `racks`, `zonas_despacho`, `puertas`, `catalogo_productos`: los elementos del JSON, indexados por id.
- `advertencias`: lista de textos con los problemas detectados del mapa.

**¿Por qué sin matriz?** La primera versión creaba una matriz `ancho_x × largo_y` con todas las celdas y después recorría esa matriz para armar el dígrafo. Eso guardaba **dos veces** la información de los pasillos: como celda en la matriz y como nodo en el grafo. Ahora el pasillo existe una sola vez, como `NodoGrafo`, y la matriz no hace falta: para saber qué hay en `(x, y)` alcanza con mirar si está en `obstaculos` o en `nodos`, en O(1).

Para el código que antes leía `matriz[x][y]` (por ejemplo, la interfaz), `Warehouse.obtener_celda(x, y)` devuelve lo mismo sin guardar una matriz: si es obstáculo, la celda real (una `CeldaRack` con su pila de productos, una zona o una puerta); si es pasillo, arma en el momento una `CeldaPasillo` con el sentido del nodo; si está fuera del almacén, `None`. Cuesta O(1).

### 2.2 ¿Por qué lista de adyacencia y no matriz de adyacencia?

- El grafo es **ralo**. Como los movimientos son solo ortogonales, cada nodo tiene **como máximo 4 vecinos**, así que **E ≤ 4N**.
- Una matriz de adyacencia ocuparía **N²**. En el escenario grande (N = 1898) son unas 3,6 millones de celdas, casi todas en 0, cuando las aristas reales son 6048.
- La lista de adyacencia ocupa **O(N + E) = O(N)**. Recorrer los vecinos de un nodo cuesta O(grado) ≤ 4, que es la operación central de cualquier recorrido (BFS, Dijkstra). Con una matriz habría que barrer toda una fila: O(N).

### 2.3 ¿Por qué un `dict` indexado por coordenadas?

- La identidad natural de un nodo es su posición `(x, y)`. Productos, pickers y racks vienen del JSON con coordenadas, así que el nodo se encuentra **directo** con `nodos[(x, y)]`, en O(1) promedio, sin una tabla de traducción coordenada→índice.
- Como no todas las celdas son nodos, un arreglo tendría huecos. El diccionario guarda **solo** los pasillos, y `obstaculos` guarda **solo** los obstáculos.
- Una tupla `(x, y)` es inmutable y hasheable, por eso sirve como clave.

### 2.4 ¿Por qué aristas dirigidas?

- Los pasillos tienen **sentido de circulación** (enunciado 3.5). En un pasillo `N` se puede pasar de `(0,5)` a `(0,6)`, pero no volver de `(0,6)` a `(0,5)`. Un grafo no dirigido no puede representar eso.
- Cuando dos pasillos permiten ir y volver (por ejemplo, dos celdas `AMBOS`), simplemente hay dos aristas: `a→b` y `b→a`.

### 2.5 Respuestas a las preguntas del informe

**Pregunta 1: ¿Cómo fue modelado el Warehouse?**
Como un **dígrafo de pasillos** construido directamente desde el JSON. El almacén es una grilla `ancho_x × largo_y` (eje y hacia arriba), pero no se guarda como matriz. Cada coordenada es:
- un **nodo de pasillo** (`NodoGrafo`), con su sentido de circulación. Si no fue declarada en el JSON, es pasillo `AMBOS`.
- o un **obstáculo** en el diccionario `obstaculos`: celda de rack (`CeldaRack`, con un diccionario `productos_en_z` que funciona como pila por niveles), de zona de despacho o de puerta.

Las aristas, de costo 1, unen pasillos ortogonalmente vecinos respetando el sentido de circulación. Racks y zonas no son nodos: cada nodo de pasillo guarda qué celdas de rack y qué zonas tiene al costado, y el `Warehouse` guarda el índice inverso (rack→pasillo, zona→pasillos) para saber dónde frenar.

**Pregunta 2: ¿Qué representación utilizaron y por qué?**
Un **dígrafo con lista de adyacencia** implementado por nosotros (`Digrafo`), con diccionarios indexados por coordenada `(x, y)`.
- Es **dirigido** porque los pasillos tienen sentido.
- Usa **lista de adyacencia** porque el grafo es ralo (E ≤ 4N): ocupa O(N + E) contra O(N²) de una matriz, y obtener los vecinos cuesta O(1) (a lo sumo 4).
- Usa **diccionarios por coordenada** para llegar de una posición del JSON al nodo en O(1).
- Los obstáculos están en un diccionario aparte, así cada celda se guarda una sola vez y no hace falta una matriz paralela al grafo.

---

## 3. Pseudocódigo

### 3.a Construcción del almacén desde el JSON (`construir_warehouse_desde_dict`)

```
función CONSTRUIR_WAREHOUSE(data):
    W ← data.warehouse.dimensiones.ancho_x
    H ← data.warehouse.dimensiones.largo_y
    wh ← nuevo Warehouse(W, H)              // grafo vacío y obstaculos vacío
    advertencias ← lista vacía
    ocupado_por ← diccionario vacío          // celda → id del elemento declarado que la ocupa
    pasillos_declarados ← diccionario vacío  // celda → (sentido, id del pasillo)

    procedimiento OCUPAR(x, y, id):
        si x ∉ [0, W) o y ∉ [0, H) entonces
            lanzar ERROR "el elemento id ocupa (x,y), fuera del almacén"
        si (x,y) ∈ ocupado_por y ocupado_por[(x,y)] ≠ id entonces
            agregar a advertencias "id pisa a ocupado_por[(x,y)] en (x,y)"
        ocupado_por[(x,y)] ← id

    procedimiento OCUPAR_OBSTACULO(x, y, celda, id):
        OCUPAR(x, y, id)
        wh.obstaculos[(x,y)] ← celda

    // 1. Pasillos declarados
    para cada pasillo p en data.pasillos:
        si p.sentido no es N, S, E, O, AMBOS ni NINGUNO entonces
            lanzar ERROR "sentido inválido; valores válidos: ..."
        para cada celda (x,y) del rectángulo de p:
            OCUPAR(x, y, p.id)
            pasillos_declarados[(x,y)] ← (p.sentido, p.id)

    // 2. Puertas (obstáculo, no hacen nada en el grafo)
    para cada puerta d en data.puertas:
        OCUPAR_OBSTACULO(d.x, d.y, Celda(PUERTA), d.id)
        wh.puertas[d.id] ← d

    // 3. Zonas de despacho (obstáculo)
    para cada zona z en data.zonas_despacho:
        para cada celda (x,y) del rectángulo de z:
            OCUPAR_OBSTACULO(x, y, Celda(ZONA_DESPACHO), z.id)
        wh.zonas_despacho[z.id] ← z

    // 4. Racks (obstáculo)
    para cada rack r en data.racks:
        si r.ancho ≠ 2 y r.alto ≠ 2 entonces
            agregar a advertencias "ningún lado vale 2"
        para cada celda (x,y) del rectángulo de r:
            OCUPAR_OBSTACULO(x, y, CeldaRack(x, y, r.id), r.id)
        wh.racks[r.id] ← r

    // 5. Productos
    para cada producto q en data.productos:
        si (q.x, q.y) está fuera del almacén entonces lanzar ERROR
        wh.catalogo_productos[q.id] ← q
        celda ← wh.obstaculos[(q.x, q.y)]   (o nada)
        si celda es CeldaRack entonces
            si celda.rack_id ≠ q.rack_id entonces agregar advertencia
            celda.productos_en_z[q.z] ← q
        si no
            agregar a advertencias "q no está en una celda de rack"

    // 6. Dígrafo
    CONSTRUIR_DIGRAFO(wh, pasillos_declarados)

    // 7. Validación
    pickers ← [(pk.id, pk.posicion_inicial) para cada pk en data.pickers]
    advertencias ← advertencias + VALIDAR_GRAFO(wh, pickers)
    wh.advertencias ← advertencias
    devolver wh
```

**¿Quién gana si un obstáculo cae sobre un pasillo declarado?** El obstáculo. Al crear los nodos (3.b, paso A), toda celda que esté en `obstaculos` se saltea, aunque también figure en `pasillos_declarados`. Entre dos obstáculos gana el último que se procesó: los racks van al final. En cualquier superposición se agrega la advertencia "X pisa a Y en (x,y)".

### 3.b Construcción del dígrafo (`_construir_digrafo`)

```
procedimiento CONSTRUIR_DIGRAFO(wh, pasillos_declarados):
    G ← wh.grafo_pasillos

    // Paso A: nodos = todo lo que no es obstáculo
    para x desde 0 hasta W-1:
        para y desde 0 hasta H-1:
            si (x,y) ∈ wh.obstaculos entonces continuar
            (sentido, id) ← pasillos_declarados[(x,y)]  si existe,
                            si no (AMBOS, nada)           // enunciado 3.5
            G.agregar_nodo(x, y, sentido, id)

    // Paso B: accesos y aristas
    para cada nodo (x,y) de G:
        // a) racks y zonas al costado (ver 3.c)
        DETECTAR_ACCESOS(wh, nodo)

        // b) aristas
        para cada (dx,dy) en DIRECCIONES_SEGUN_SENTIDO(nodo.sentido):
            destino ← G.nodos[(x+dx, y+dy)]   (nada si es obstáculo o está fuera)
            si destino existe y no ES_CONTRAMANO(dx, dy, destino.sentido) entonces
                G.agregar_arista_dirigida((x,y), (x+dx, y+dy))

función DIRECCIONES_SEGUN_SENTIDO(s):
    según s:
        N:       devolver [(0,+1), (-1,0), (+1,0)]     // avanza al norte o se corre de costado
        S:       devolver [(0,-1), (-1,0), (+1,0)]
        E:       devolver [(+1,0), (0,+1), (0,-1)]
        O:       devolver [(-1,0), (0,+1), (0,-1)]
        AMBOS:   devolver las 4 direcciones
        NINGUNO: devolver lista vacía

función ES_CONTRAMANO(dx, dy, sentido_destino):
    si sentido_destino = NINGUNO entonces devolver VERDADERO
    devolver (dy = +1 y sentido_destino = S)
          o  (dy = -1 y sentido_destino = N)
          o  (dx = +1 y sentido_destino = O)
          o  (dx = -1 y sentido_destino = E)
```

Para que exista la arista `a → b` se tienen que cumplir **tres cosas**:
1. `b` es un nodo, es decir, un pasillo dentro del almacén.
2. El sentido del **origen** permite moverse en esa dirección (avanzar o ir de costado).
3. Ese movimiento no va **de frente contra** el sentido del **destino** (no se entra en contramano).

Como el destino se busca directamente en `G.nodos`, no hace falta chequear los bordes del almacén aparte: una coordenada fuera del almacén nunca es un nodo.

### 3.c Acceso a racks (por el costado) y a zonas de despacho

```
procedimiento DETECTAR_ACCESOS(wh, nodo en (x,y)):
    para cada (dx,dy) en [(0,1), (0,-1), (1,0), (-1,0)]:
        (nx,ny) ← (x+dx, y+dy)
        vecina ← wh.obstaculos[(nx,ny)]   (nada si es pasillo o está fuera)
        si no hay vecina entonces continuar

        si vecina es CeldaRack entonces
            rack ← wh.racks[vecina.rack_id]
            // dirección que va desde la celda de rack hacia el pasillo
            si (x-nx, y-ny) ∈ DIRS_ACCESO(rack, nx, ny) entonces
                agregar vecina a nodo.racks_adyacentes
                agregar (x,y) a wh.accesos_rack_a_pasillo[(nx,ny)]
                si (nx,ny) ∉ wh.acceso_rack_a_pasillo entonces
                    wh.acceso_rack_a_pasillo[(nx,ny)] ← (x,y)

        si no, si vecina es ZONA_DESPACHO entonces
            si vecina.zona_id ∉ nodo.zonas_despacho_adyacentes entonces
                agregar vecina.zona_id a nodo.zonas_despacho_adyacentes
                agregar (x,y) a wh.accesos_zona_a_pasillo[vecina.zona_id]

función DIRS_ACCESO(rack, x, y):          // (x,y) es una celda del rack
    si rack.ancho = 2 y rack.alto ≠ 2 entonces       // rack vertical: se accede por izquierda/derecha
        si x = rack.x entonces devolver [(-1,0)]     // columna izquierda: desde la izquierda
        si no               devolver [(+1,0)]        // columna derecha: desde la derecha
    si rack.alto = 2 y rack.ancho ≠ 2 entonces       // rack horizontal: se accede por abajo/arriba
        si y = rack.y entonces devolver [(0,-1)]
        si no               devolver [(0,+1)]
    devolver las 4 direcciones                       // 2x2 o rack inválido
```

Como el lado que vale 2 es el que tiene dos columnas (o dos filas) de celdas, cada celda del rack queda pegada a **uno** de los costados largos. Por ese costado se la recoge. Los **extremos** (arriba y abajo de un rack vertical) no sirven: la dirección `(0,-1)` no está en la lista.

### 3.d Kosaraju iterativo (`componentes_fuertemente_conexas`)

Una **componente fuertemente conexa** (CFC) es un grupo de nodos en el que desde cualquiera se llega a cualquier otro **y se puede volver**.

```
función KOSARAJU(G):
    // 1ª pasada: DFS en G, anotando los nodos en orden de finalización
    visitado ← conjunto vacío
    orden_fin ← lista vacía
    para cada nodo s de G:
        si s ∈ visitado entonces continuar
        agregar s a visitado
        pila ← [(s, 0)]                      // (nodo, índice del próximo vecino a mirar)
        mientras pila no vacía:
            (u, i) ← tope de pila
            si i < cantidad de vecinos de u entonces
                tope de pila ← (u, i+1)
                v ← i-ésimo vecino de u
                si v ∉ visitado entonces
                    agregar v a visitado
                    apilar (v, 0)
            si no
                desapilar
                agregar u al final de orden_fin   // u terminó

    // Grafo transpuesto: se invierten todas las aristas
    GT ← para cada arista u→v de G, agregar v→u

    // 2ª pasada: DFS en GT, tomando los nodos en orden de finalización decreciente
    asignado ← conjunto vacío
    componentes ← lista vacía
    para cada r en orden_fin recorrido de atrás hacia adelante:
        si r ∈ asignado entonces continuar
        agregar r a asignado
        comp ← lista vacía
        pila ← [r]
        mientras pila no vacía:
            u ← desapilar
            agregar u a comp
            para cada v vecino de u en GT:
                si v ∉ asignado entonces
                    agregar v a asignado
                    apilar v
        agregar comp a componentes

    ordenar componentes por tamaño, de mayor a menor
    devolver componentes
```

**¿Por qué iterativo?** Un DFS recursivo en un almacén grande puede pasar las ~1000 llamadas que Python permite por defecto (`RecursionError`). Con una pila explícita no hay límite de profundidad. En la primera pasada se guarda `(nodo, índice)` para saber por qué vecino seguir cuando se vuelve a un nodo. Así se reproduce exactamente el momento en que un nodo **termina**, que es lo que necesita Kosaraju.

**¿Cómo detecta trampas?** Si todo está bien diseñado, desde cualquier pasillo se puede ir a cualquier otro y volver, y hay **una sola CFC**. Si un pasillo de un solo sentido termina contra una pared o un obstáculo, el picker puede entrar pero no salir. Esas celdas quedan en CFC distintas de la principal, que es la más grande.

### 3.e Validación (`validar_grafo`)

```
función VALIDAR_GRAFO(wh, posiciones_pickers):
    adv ← lista vacía
    comps ← KOSARAJU(wh.grafo_pasillos)
    principal ← conjunto con los nodos de comps[0]   (vacío si no hay nodos)

    si cantidad(comps) > 1 entonces
        fuera ← todos los nodos de comps[1..]
        agregar a adv "hay k CFC: |fuera| celdas no pertenecen a la red principal
                       (x = min..max, y = min..max)"

    para cada producto q:
        accesos ← wh.accesos_rack_a_pasillo[(q.x, q.y)]
        si accesos vacío entonces agregar "q no tiene pasillo de acceso"
        si no, si ningún acceso ∈ principal entonces agregar "q no tiene acceso en la red principal"

    para cada zona z:
        accesos ← wh.accesos_zona_a_pasillo[z]
        si accesos vacío entonces agregar "z no tiene pasillos adyacentes"
        si no, si ningún acceso ∈ principal entonces agregar "z no tiene pasillo en la red principal"

    para cada (id, pos) en posiciones_pickers:
        si pos no es nodo entonces agregar "Picker id arranca en pos, que no es pasillo"
        si no, si pos ∉ principal entonces agregar "Picker id arranca fuera de la red principal"

    devolver adv
```

`validar_grafo` **no modifica** el `Warehouse`: solo devuelve la lista. El constructor (paso 7) es el que la guarda en `wh.advertencias`.

Si `wh.advertencias` queda vacía, el mapa es correcto: desde cualquier pasillo se llega a cualquier otro y se vuelve, y todos los productos, zonas y pickers están en esa red. Eso es lo que usa `ScenarioGenerator` para decidir si un escenario generado es válido.

---

## 4. Ejemplo paso a paso con el escenario del Anexo A

Datos: almacén de 18×16. Rack R1 en (3,5) de 2×6, así que ocupa x = 3..4 e y = 5..10. PAS_V0 en (0,5) de 3×6 con sentido N (x = 0..2, y = 5..10). PAS_V1 en (5,5) de 3×6 con sentido S. PAS_H_INF en (0,3) de 18×2 con sentido AMBOS (y = 3..4).

Resultado:
- **58 obstáculos**: 36 celdas de rack, 20 de zonas y 2 puertas.
- **230 nodos**: 288 celdas − 58 obstáculos.
- **692 aristas** y una sola CFC, sin advertencias.

### 4.1 ¿Por qué P001 se recoge desde (2,5)?

1. P001 está en (3,5). En `obstaculos[(3,5)]` hay una `CeldaRack` de R1, y P001 queda apilado en su `productos_en_z[1]`.
2. R1 tiene `ancho = 2` y `alto = 6 ≠ 2`, así que es un rack vertical.
3. `x = 3 = rack.x` (columna izquierda), así que `DIRS_ACCESO` devuelve `[(-1,0)]`: se accede solo desde la izquierda.
4. Al procesar el nodo (2,5), la vecina (3,5) es rack y la dirección rack→pasillo es `(2−3, 5−5) = (−1,0)`, que **está** en la lista. Entonces (2,5) se registra como acceso.
5. Resultado: `obtener_nodos_acceso_producto("P001") == [(2,5)]`.

Lo mismo con P003 en (4,7): `x = 4 ≠ rack.x`, así que la lista es `[(1,0)]` y el acceso es (5,7).

### 4.2 ¿Por qué (3,4) no sirve para acceder al rack?

(3,4) está **debajo** de (3,5), en PAS_H_INF. La dirección rack→pasillo es `(3−3, 4−5) = (0,−1)`, que **no** está en `[(-1,0)]`. Es el extremo inferior del rack, así que no se registra como acceso.

### 4.3 ¿Por qué existe (0,5)→(0,6) pero no (0,6)→(0,5)?

- Arista **(0,5)→(0,6)**: el origen (0,5) es N, así que `(0,+1)` está permitido. (0,6) es un nodo N, y `ES_CONTRAMANO(0, +1, N)` da falso. **Se agrega.**
- Arista **(0,6)→(0,5)**: el origen (0,6) es N y solo permite `(0,+1)`, `(−1,0)` y `(+1,0)`. Moverse `(0,−1)` **no está permitido**, así que no se agrega.
- Lateral **(0,7)→(1,7)** y **(1,7)→(0,7)**: un pasillo N permite moverse de costado en x, y el destino también es N (no O ni E), así que no hay contramano. **Existen las dos.**
- **(5,4)→(5,5)**: el origen (5,4) es AMBOS y permite `(0,+1)`, pero el destino (5,5) es S. `ES_CONTRAMANO(0, +1, S)` da verdadero, así que **no se agrega**: no se puede entrar a PAS_V1 por abajo.
- **(2,5)→(3,5)**: no existe, porque (3,5) está en `obstaculos` y no es nodo.

### 4.4 ¿Qué pasa si PAS_H_INF se pone en sentido S?

Las celdas y = 3..4 pasan a permitir solo `(0,−1)` y los laterales. Desde ahí **nadie puede subir** a los pasillos verticales, porque `(0,+1)` no está permitido en un pasillo S. En cambio, desde PAS_V1 y PAS_V3 (S) se baja sin problema. Entonces se puede llegar abajo pero no volver a subir.

Con el código real:
- La CFC principal queda formada por las 90 celdas de PAS_H_SUP.
- Aparecen 30 CFC en total, y la advertencia dice *"140 celdas de pasillo no pertenecen a la red principal (x=0..17, y=0..10)"*.
- Además, P001, P003 y P006 quedan sin acceso en la red principal, ZONA_A y ZONA_B también, y los dos pickers (1,3) y (16,3) arrancan fuera de la red principal.
- Las aristas bajan de 692 a 660.

El caso real equivalente es el **escenario grande** (`escenario_grande.json`), que tenía dos problemas de diseño en la esquina izquierda, al lado de ZONA_D:

- **Trampa:** PAS_VB00 (x 0..3, y 20..29) con sentido S desemboca contra ZONA_D y deja **41 celdas** atrapadas (x=0..3, y=19..29). Kosaraju la detecta: 12 CFC y la advertencia de 41 celdas fuera de la red principal.
- **Rincón con una sola salida:** PAS_VA00 (x 0..3, y 6..15) con sentido N termina en un rincón (x=0..3, y=15..17) cuya **única salida** es la celda (3,16), que además es el acceso a ZONA_D. El grafo es fuertemente conexo, así que Kosaraju no lo marca. Pero si un picker queda estacionado en (3,16), cualquier otro picker que entre al rincón (por ejemplo, para recoger un producto en (3,15)) queda encerrado. La simulación de la interfaz lo encontró al ejecutar todas las waves.

Con el grafo anterior ninguno de los dos se notaba, porque permitía entrar en contramano. Se corrigieron en el archivo poniendo **PAS_VA00 y PAS_VB00 en AMBOS**. Resultado: 1898 nodos, **6048 aristas**, una sola CFC y ninguna advertencia. Los tests simulan en memoria las dos versiones viejas para mostrar cada problema.

---

## 5. Complejidad

Notación: W = ancho_x, H = largo_y, N = nodos (pasillos), B = celdas de obstáculo (N + B = W·H), E = aristas ≤ 4N, P = productos, R = racks, Z = zonas, K = pickers, A = suma de las áreas de los elementos declarados.

| Parte | Tiempo | Espacio | Por qué |
|---|---|---|---|
| Leer pasillos, puertas, zonas y racks (pasos 1-4) | Θ(A) | O(A) en `ocupado_por` y `pasillos_declarados`, Θ(B) en `obstaculos` | Cada celda de cada elemento declarado se procesa una vez. Sin superposiciones, A ≤ W·H. |
| Productos (paso 5) | Θ(P) | Θ(P) | Lookup O(1) en `obstaculos` y apilado O(1) en el dict `productos_en_z`. |
| Dígrafo, paso A (nodos) | Θ(W·H) | Θ(N) | Hay que recorrer todas las coordenadas, porque las celdas **no declaradas** también son nodos (pasillo AMBOS). |
| Dígrafo, paso B (accesos y aristas) | Θ(N) | Θ(E) + accesos | Por nodo: 4 lookups en `obstaculos` y ≤ 4 lookups en `nodos`. `agregar_arista_dirigida` es O(1), porque revisar duplicados es sobre una lista de ≤ 4. |
| Kosaraju | Θ(N + E) = Θ(N) | Θ(N + E) | Dos DFS que pasan una vez por cada nodo y arista, más el transpuesto. Ordenar C componentes cuesta O(C log C), con C ≤ N. |
| Resto de la validación | O(P + N + K) | O(N) para el conjunto `principal` | Cada producto tiene ≤ 4 accesos (normalmente 1). Los accesos de las zonas suman ≤ N. |
| **Construcción completa** | **Θ(W·H + A + P)**, en la práctica **O(W·H + P)** | **Θ(N + B + P) = Θ(W·H + P)** | Todo es lineal en el tamaño del mapa. |

**Mejor y peor caso:**
- **Mejor caso:** casi todo el almacén son obstáculos, con N chico. El paso A igual recorre las W·H coordenadas, pero el paso B, Kosaraju y la validación cuestan O(N).
- **Peor caso:** todo es pasillo AMBOS. Entonces N = W·H y E = 4WH − 2W − 2H ≈ 4N. Sigue siendo **lineal** en el área.
- **Al crecer el almacén**, el costo crece **linealmente con el área** W·H. Si se duplica el ancho, se duplica el tiempo. No hay ninguna parte cuadrática (con matriz de adyacencia el espacio sería O(N²)).
- **Respecto de la versión con matriz:** el orden es el mismo, porque una celda libre igual tiene que convertirse en nodo. Lo que se ahorra es la estructura duplicada: antes había W·H celdas en la matriz **más** N nodos en el grafo. Ahora hay N nodos más B obstáculos, que suman exactamente W·H.

**Consultas una vez construido:**

| Consulta | Costo |
|---|---|
| `grafo.obtener_vecinos((x,y))` | O(1) promedio: lookup en el dict, y la lista tiene ≤ 4 elementos. Devuelve la lista interna, sin copiarla. |
| `grafo.nodos[(x,y)]`, `(x,y) in grafo.nodos` | O(1) promedio |
| `wh.obstaculos.get((x,y))`: ¿qué hay en esta celda? | O(1) promedio |
| `obtener_nodo_acceso_producto(id)` | O(1): dos lookups en diccionarios |
| `obtener_nodos_acceso_producto(id)` | O(1): copia una lista de ≤ 4 |
| `obtener_nodos_acceso_zona(id)` | O(k), con k = pasillos pegados a la zona (copia de la lista) |
| `imprimir_mapa()` | Θ(W·H) |

---

## 6. Decisiones de diseño y alternativas

| Decisión | Alternativa | Por qué elegimos así |
|---|---|---|
| **El dígrafo se arma directo desde el JSON, sin matriz.** Los obstáculos van en un dict aparte. | Crear primero una matriz W×H con todas las celdas y después recorrerla. | Con la matriz, cada pasillo se guardaba dos veces (celda y nodo) y había que mantener las dos estructuras coherentes. Ahora cada coordenada vive en un solo lugar (nodo **u** obstáculo) y la consulta "¿qué hay en (x,y)?" sigue siendo O(1). El costo asintótico no cambia. |
| **Racks y zonas son obstáculos, no nodos.** El nodo de pasillo guarda qué tiene al costado. | Hacer que cada celda de rack sea un nodo con una arista "de entrada". | El enunciado 3.6 dice que el picker no atraviesa racks. Si fueran nodos, un recorrido podría armar caminos *a través* de un rack, y habría que filtrarlos. Así, cualquier camino del grafo es físicamente válido y el destino de un pedido es directamente el nodo de acceso. |
| **Las puertas no hacen nada en el grafo.** Quedan en `obstaculos` (tipo `PUERTA`) y en `wh.puertas`. | Modelarlas como nodos o como accesos a zonas. | El enunciado no le da a la puerta un rol en el recorrido del picker: el picker deja la mercadería en la zona. Mantenerlas fuera evita casos raros (por ejemplo, contarlas como acceso a ZONA_A, que el test verifica que no pasa). |
| **Advertencias en vez de excepciones para los problemas del mapa** (superposiciones, trampas, rack sin lado 2, productos o pickers mal ubicados). | Lanzar una excepción ante cualquier problema. | El almacén se puede construir igual y el usuario ve **todos** los problemas juntos, no solo el primero. Se reserva `ValueError` para lo que hace imposible construir: sentido inválido o algo fuera del almacén. Esto deja cargar escenarios "con defectos" para analizarlos, como el grande original. |
| **`acceso_rack_a_pasillo` (un valor) junto a `accesos_rack_a_pasillo` (lista).** | Dejar solo la lista. | Un rack 2×2 o inválido puede tener más de un acceso, así que la lista es lo correcto. Pero quien solo necesita **un** punto donde frenar (`obtener_nodo_acceso_producto`) lo obtiene directo. |
| **Kosaraju iterativo.** | Tarjan, o DFS recursivo. | Kosaraju es fácil de explicar (dos DFS más el transpuesto) y la versión iterativa evita el límite de recursión de Python. |
| **Aristas de costo 1, sin pesos.** | Pesos por tipo de pasillo. | Todos los movimientos cuestan un paso. Quien recorra el grafo (BFS) obtiene el camino mínimo directamente. |

---

## 7. Las 10 preguntas más probables del profesor

1. **¿Qué es un nodo?** Una celda de pasillo `(x, y)`: toda coordenada que no sea rack, zona ni puerta.
2. **¿Qué es una arista?** Un paso permitido entre dos pasillos vecinos (arriba, abajo, izquierda o derecha), con costo 1 y dirigido según el sentido.
3. **¿Por qué dirigido?** Porque los pasillos tienen sentido de circulación: en un pasillo N existe `(0,5)→(0,6)` pero no `(0,6)→(0,5)`.
4. **¿Por qué lista de adyacencia?** Porque el grafo es ralo, con ≤ 4 vecinos por nodo y E ≤ 4N. Ocupa O(N+E) contra O(N²), y obtener los vecinos es O(1).
5. **¿Por qué no usan una matriz del almacén?** Porque sería una copia de lo que ya está en el grafo. Cada coordenada es un nodo (en `grafo.nodos`) o un obstáculo (en `obstaculos`), y las dos consultas son O(1).
6. **¿Cómo sabe el picker dónde frenar para un producto?** Por `accesos_rack_a_pasillo[(x,y) del producto]`, que se calcula al construir el grafo mirando el costado accesible del rack (`_dirs_acceso`). Consultarlo es O(1).
7. **¿Por qué no se puede recoger desde el extremo del rack?** Porque `_dirs_acceso` solo devuelve el costado largo que le corresponde a la celda. En el Anexo A, (3,4) no es acceso de (3,5).
8. **¿Qué pasa si dos elementos se superponen?** Los obstáculos le ganan a los pasillos y, entre obstáculos, gana el último procesado (los racks). Se agrega la advertencia "X pisa a Y en (x,y)" y la carga no se corta.
9. **¿Cómo detectan que un pasillo es una trampa?** Con las componentes fuertemente conexas (Kosaraju). Si hay más de una, las celdas fuera de la más grande son lugares a los que se puede entrar pero de los que no se puede volver, o islas.
10. **¿Qué complejidad tiene construir el grafo?** Lineal en el área: O(W·H + P) en tiempo y espacio. Kosaraju es O(N+E) = O(N).

---

## 8. Cómo explicarlo en 2 minutos (guion)

> "Mi parte es la estructura que modela el almacén. Leo el JSON y armo **directamente un dígrafo**, sin pasar por una matriz.
>
> Cada coordenada del almacén es una de dos cosas. Si es rack, zona de despacho o puerta, es un **obstáculo**: va a un diccionario `obstaculos`, y la celda de rack guarda su pila de productos por nivel z. Todo lo demás es **pasillo** y es un **nodo** del grafo, con el sentido que declara el JSON, o doble sentido si no estaba declarado.
>
> Las **aristas** unen pasillos vecinos en las 4 direcciones, con costo 1, y son **dirigidas**: un pasillo Norte deja avanzar hacia el norte o correrse de costado, pero no retroceder, y además no dejamos entrar a un pasillo en contramano.
>
> Usamos **lista de adyacencia** indexada por coordenada porque cada nodo tiene como mucho 4 vecinos: el grafo es ralo, ocupa O(N) y los vecinos se obtienen en O(1).
>
> Para los productos, cada pasillo mira si tiene un rack al costado y si ese costado es accesible. Los racks se acceden por el lado largo, nunca por los extremos. Eso queda en un diccionario rack→pasillo, así que saber dónde frenar es O(1). Por ejemplo, P001 en (3,5) se recoge desde (2,5).
>
> Al final validamos con **Kosaraju iterativo**: si el grafo no es una sola componente fuertemente conexa, hay pasillos de los que no se puede volver, y lo informamos como advertencia junto con productos, zonas y pickers que quedan afuera. Así encontramos una trampa de 41 celdas en el escenario grande y la corregimos, junto con un rincón que tenía una sola salida.
>
> Todo es lineal en el tamaño del almacén: O(ancho × largo + productos). Los recorridos, como BFS, los hacen mis compañeros sobre este grafo."

---

## 9. Integración con el resto del proyecto

El grafo vive en la misma rama que el trabajo de mis compañeros: waves (`wave_manager`), búsqueda de caminos (`pathfinding`), catálogo (`catalog_manager`) e interfaz (`FrontEnd/`). Esto es lo que ellos usan del grafo, y se mantuvo igual:

| Lo usa | Qué usa |
|---|---|
| Interfaz (`FrontEnd/services/session.py`) | `GraphBuilder.construir_warehouse_desde_dict`, `obtener_nodo_acceso_producto`, `grafo_pasillos.nodos[...].zonas_despacho_adyacentes`, `grafo_pasillos.obtener_vecinos` y `obtener_celda(x, y)` (antes `matriz[x][y]`). |
| Búsqueda de caminos (`pathfinding`, a través de `AdaptadorGrafo`) | `grafo_pasillos.obtener_vecinos`. |
| Generador (`scenario_generator.py`) | `construir_warehouse_desde_dict` y `wh.advertencias` para decidir si un escenario es válido. |

Los productos del catálogo son el modelo del equipo `Product` (en `entity.py`): tiene `id_producto`, `ubicacion_x`, `ubicacion_y` y `altura_z`, y además las propiedades `id`, `x`, `y`, `z`, que son las que usa el grafo.

Cambios mínimos que hizo falta hacer fuera del grafo:

- `enums.py`: se agregó `NINGUNO` a `SentidoCirculacion`.
- `FrontEnd/services/session.py`: las 2 lecturas de `matriz[x][y]` pasaron a `obtener_celda(x, y)`.
- `main.py` y `scenario_generator.py`: se quitó el import de `BackEnd.controllers.bfs`, que ya no existe.
- `escenario_grande.json`: PAS_VA00 y PAS_VB00 en AMBOS (sección 4.4).

