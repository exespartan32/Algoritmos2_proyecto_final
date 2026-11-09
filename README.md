# Sistema de Wave Picking

**Proyecto semestral de Algoritmos y Estructuras de Datos II**

**Integrantes**

Laureano Petri, Exequiel Mayorga, Leonel Chadi y Martín Merlo.

El sistema simula la preparación de pedidos en un almacén. Agrupa pedidos en *waves*, asigna operarios (*pickers*), calcula sus rutas y ejecuta la recogida y el despacho por turnos. La interfaz permite seguir cómo se forma una wave, observar la búsqueda de un camino y comparar las estrategias bajo las mismas condiciones.

## Instalación y ejecución

Se requiere Python 3.10 o superior. Ejecutá estos comandos en PowerShell desde la raíz del repositorio.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe gui.py
```

En Windows también se puede abrir [iniciar_gui.bat](iniciar_gui.bat) después de instalar la dependencia. En Linux o macOS se usa `.venv/bin/python` en lugar de `.\.venv\Scripts\python.exe`. El paquete `pygame-ce` proporciona la ventana y el dibujo mediante `import pygame`. El selector de archivos usa Tkinter. También se puede arrastrar un JSON sobre la ventana.

También se puede abrir un escenario directamente o ejecutar el flujo por consola.

```powershell
.\.venv\Scripts\python.exe gui.py --escenario biblioteca/escenario_basico.json
.\.venv\Scripts\python.exe main.py -i biblioteca/escenario_basico.json -w WAVE_01
```

En consola, `-w` admite varios identificadores separados por comas. Si se omite, el programa solicita la selección. La consola exporta el estado del almacén a `BackEnd/data/estado_guardado.json`. Para guardar una sesión interactiva con historial se usa **Guardar sesión** en la interfaz.

## Demostración de la interfaz

1. **Abrir un almacén.** Cargar [escenario_basico.json](biblioteca/escenario_basico.json) desde la biblioteca. **Crear escenario** permite importar un JSON o configurar el generador automático.
2. **Inspeccionar el escenario.** En **Productos** se ve el stock, el peso unitario y la ubicación `(x, y, z)` de cada producto. Se puede seleccionar una celda, acercar el mapa con la rueda o desplazarlo arrastrando. **Nuevo pedido** admite una prioridad y una lista como `P001x2, P004x1`.
3. **Generar las waves.** En **Capacidad de waves** se definen los límites. El selector **Armado de waves** alterna entre Automática, Cercanía en el dígrafo, Por pasillo y Solo prioridad. Tras generar, el selector muestra el criterio aplicado. **Ver cómo se armó** presenta el pedido raíz, los candidatos y el cierre del grupo.
4. **Comparar.** En **Seleccionar waves**, marcar las waves pendientes y pulsar **Comparar estrategias** para comparar sus recorridos. **Comparar armado** prueba los tres criterios de agrupamiento y explica debajo de la tabla qué criterio decidió el resultado o si hubo empate.
5. **Simular la recogida.** Usar **Asignar e iniciar** para asignar la selección y **Iniciar** para reproducir la tanda. La búsqueda de Dijkstra se representa en el mapa con las celdas exploradas, la ruta y las paradas numeradas. **Pickers** muestra lo recogido y lo pendiente. **Eventos** registra recogidas, descargas y conflictos de tráfico.
6. **Controlar y retomar.** Se puede pausar, continuar, avanzar o retroceder un turno y reiniciar la tanda. Las flechas izquierda y derecha recorren los pasos y Espacio controla la reproducción. **Guardar sesión** confirma el guardado y se vuelve a habilitar al continuar o reiniciar. La sesión se reabre desde la biblioteca.

## Modelo, algoritmos y decisiones

**Representación del almacén.** El JSON define racks, puertas, zonas de despacho y pasillos mediante coordenadas y dimensiones. El origen `(0, 0)` está abajo a la izquierda. Cada celda transitable es un nodo del dígrafo y cada arista representa un movimiento ortogonal permitido. La lista de adyacencia almacena solo los vecinos disponibles. Los productos tienen coordenadas `(x, y, z)` y el picker los recoge desde una celda de pasillo adyacente.

**Validación.** Se comprueban tipos, rangos, identificadores, geometría, referencias de productos y pedidos y posiciones de los pickers. El constructor calcula los accesos a racks y despachos y usa Kosaraju para analizar las componentes fuertemente conexas. Un escenario sin un recorrido válido de ida y vuelta para los accesos necesarios puede rechazarse antes de iniciar la simulación.

**Armado de waves.** Un Max-Heap propio permite extraer el pedido de mayor prioridad para abrir una wave. Cada candidato se evalúa con los límites de pedidos, unidades, stock, zona de despacho y capacidad de carga. El stock se reserva durante el armado. La vista registra los productos al recogerlos y el inventario se descuenta al confirmar la descarga del pedido.

| Criterio de armado | Qué favorece |
| --- | --- |
| Cercanía en el dígrafo | Pedidos con menor costo marginal respecto de las ubicaciones ya incluidas. Usa las distancias del dígrafo y considera la altura. |
| Por pasillo | Pedidos que incorporan menos pasillos nuevos a la wave. |
| Solo prioridad | Pedidos factibles con mayor prioridad, con desempate por identificador. |
| Automática | Compara los tres criterios sobre copias del escenario. Prioriza menor distancia planificada, luego menos turnos, menos pasillos por wave y menor tiempo de armado. |

**Recorrido y simulación.** Dijkstra usa un Min-Heap propio. **Orden de pedidos** planifica tramos según la secuencia de los pedidos y **Cercanía** usa una búsqueda multidestino para visitar la ubicación pendiente más próxima. Según la capacidad y disponibilidad, una wave puede repartirse entre varios pickers. La simulación avanza por turnos y puede aplicar esperas o desvíos cuando detecta un conflicto de movimiento.

**Costo y alcance.** Para `V` celdas transitables y `E` aristas, la lista de adyacencia ocupa `O(V + E)`. Los recorridos de Kosaraju toman `O(V + E)`, sin contar el ordenamiento de las componentes. En el grafo ralo del almacén, una búsqueda de Dijkstra con montículo tiene un costo de referencia de `O((V + E) log V)`. El tiempo de una wave también depende de los candidatos de armado, de la cantidad de tramos y de los posibles recálculos. Cercanía es una heurística de orden de visita y no garantiza el recorrido global óptimo.

**Persistencia e interfaz.** La sesión gráfica conserva los datos iniciales, la configuración y el registro de acciones en JSON. Al abrirla se reconstruye la ejecución. La interfaz separa el tiempo visual del turno lógico y reutiliza el fondo del mapa mientras la vista permanece igual.

## Escenarios y casos de prueba

Los ejemplos están en [biblioteca/](biblioteca/). Los archivos básicos y generados permiten variar el tamaño del almacén y la carga de trabajo.

| Escenario | Tamaño | Productos | Pedidos | Pickers |
| --- | --- | ---: | ---: | ---: |
| [Básico](biblioteca/escenario_basico.json) | 18 × 16 | 8 | 3 | 2 |
| [Grande](biblioteca/escenario_grande.json) | 60 × 40 | 170 | 40 | 4 |
| [Generado chico](biblioteca/escenario_gen_chico.json) | 10 × 29 | 30 | 12 | 2 |
| [Generado mediano](biblioteca/escenario_gen_mediano.json) | 26 × 37 | 200 | 40 | 4 |
| [Generado cerca de despacho](biblioteca/escenario_gen_cerca_despacho.json) | 26 × 37 | 200 | 40 | 4 |
| [Generado grande](biblioteca/escenario_gen_grande.json) | 42 × 85 | 600 | 150 | 6 |

Para revisar casos específicos se pueden abrir los escenarios de [congestión](biblioteca/escenario_prueba_congestion.json), [asimetría direccional](biblioteca/escenario_prueba_asimetria_direccional.json) y [falta de stock](biblioteca/escenario_prueba_sin_stock_falta_despacho.json). Los casos de [inconsistencia de datos](biblioteca/escenario_prueba_inconsistencia_datos.json), [trampa topológica](biblioteca/escenario_prueba_trampa_topologica.json) y [violación estructural](biblioteca/escenario_prueba_violacion_estructural.json) sirven para demostrar mensajes de rechazo.

## Experimentos y resultados

El [script de experimentos](experimentos/ejecutar_experimentos.py) parte de una configuración reproducible. Varía la cantidad de estantes, pedidos, productos o pasillos y la distribución de los productos. Las comparaciones registran distancia planificada, nodos visitados y explorados, expansiones, tiempo de cálculo, turnos y esperas. La pestaña **Métricas** distingue los pasos efectivos de la simulación de la distancia planificada.

```powershell
.\.venv\Scripts\python.exe -m pip install matplotlib openpyxl
.\.venv\Scripts\python.exe experimentos/ejecutar_experimentos.py --rapido
```

`--rapido` limita a tres valores las series de recorrido. Para ejecutarlas completas se puede omitir. Las dependencias de este bloque son opcionales y se usan para exportar gráficos PNG con `matplotlib` y el libro Excel con `openpyxl`. El script actualiza los resultados en [docs/experimentos/](docs/experimentos/).

- [Tablas y resultados](docs/experimentos/resultados.md)
- [CSV de recorridos](docs/experimentos/resultados.csv) y [CSV de armado](docs/experimentos/armado.csv)
- [Libro Excel con comparaciones](docs/experimentos/resultados.xlsx) y [gráfico de escalabilidad](docs/experimentos/escalabilidad.png)

En la corrida publicada de **10 pedidos**, Cercanía redujo la distancia planificada de **458 a 300 pasos**, pero registró **15 esperas** frente a **4** de Orden. La comparación muestra por qué conviene leer varias métricas antes de elegir una estrategia. Los tiempos de ejecución pueden variar al repetir el experimento.

## Organización del código

| Ruta | Responsabilidad |
| --- | --- |
| [BackEnd/models/](BackEnd/models/) | Almacén, entidades, catálogo y estados del dominio. |
| [BackEnd/data_structures/](BackEnd/data_structures/) | Dígrafo de pasillos y Max-Heap de pedidos. |
| [BackEnd/utils/](BackEnd/utils/) | Lectura y validación de JSON, construcción del grafo y generación de escenarios. |
| [BackEnd/controllers/](BackEnd/controllers/) | Armado, asignación, rutas, colisiones, simulación y comparación de estrategias. |
| [FrontEnd/](FrontEnd/) | Pantallas, mapa, paneles, eventos de entrada y biblioteca de sesiones. |
| [gui.py](gui.py) y [main.py](main.py) | Puntos de entrada para la interfaz gráfica y la consola. |
| [biblioteca/](biblioteca/) | Escenarios de ejemplo, casos de prueba y sesiones de la interfaz. |
| [experimentos/](experimentos/) y [docs/experimentos/](docs/experimentos/) | Script de medición y resultados publicados. |
