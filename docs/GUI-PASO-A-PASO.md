# Cómo funciona la interfaz, paso a paso

## 1. La idea general

La interfaz tiene dos responsabilidades: recibir acciones del usuario y mostrar
el estado del sistema. No redefine los productos, pedidos, pickers ni el algoritmo
de waves. Usa los modelos y algoritmos del backend del grupo.

El recorrido de una acción es:

```text
clic o tecla → input_handler → App.action → Session → backend
                                             ↓
pantalla ← App.draw ← propiedades del estado actualizado
```

`Session` reúne las operaciones necesarias para una simulación por wave, porque
esa coordinación todavía no está disponible en la rama de integración. Es una
capa sin Pygame: se puede probar sin abrir una ventana. En un futuro puede
delegar estas operaciones a un controlador de simulación común del grupo.

## 2. El arranque: gui.py

`main()` lee opciones como `--escenario` y `--biblioteca`, crea un objeto `App`
y llama `run()`. `finally: pygame.quit()` libera la ventana aunque haya un error.
`--frames` sirve para una prueba breve de arranque.

El archivo `main.py` del equipo permanece separado. Así la consola y la interfaz
tienen entradas distintas y no se pisan al integrar cambios.

## 3. La ventana: FrontEnd/views/pygame_engine.py

`App.__init__` inicia Pygame y crea una superficie lógica de 1520 × 960. La opción
SCALED ajusta esa superficie a la ventana; los botones siguen usando coordenadas
lógicas. Crea además estas variables:

| Variable | Para qué sirve |
|---|---|
| `page` | Elegir entre Inicio y Simulación. |
| `dialog` | Saber si está abierto el generador, comparador o selector de waves. |
| `model` | Referencia a la sesión activa. |
| `playing` | Indicar si el tiempo debe hacer avanzar al picker. |
| `buttons` | Rectángulo, acción y habilitación de cada botón visible. |
| `*_page` | Página visible de productos, pedidos, waves o biblioteca. |
| `cart` | Picker cuyo carrito se muestra en el panel. |

`home()` dibuja la biblioteca. `simulation()` dibuja mapa, controles y paneles.
`modal()` dibuja un cuadro sobre la pantalla y reemplaza la lista de botones
activos: un clic dentro del cuadro no activa accidentalmente un botón de atrás.

`action()` traduce nombres como `waves`, `forward` y `save` a operaciones. Por
ejemplo, `forward` pausa la reproducción y llama `model.advance()`. Si falla una
operación, muestra el error y pausa en lugar de cerrar toda la aplicación.

`run()` es el bucle principal: procesa eventos, avanza si corresponde, dibuja y
limita la frecuencia a 30 cuadros por segundo. Cada 0,18 segundos solicita un
paso cuando `playing` es verdadero. Dibujar 30 veces por segundo no significa
que el picker haga 30 movimientos por segundo: son tiempos separados.

## 4. Eventos y elementos gráficos

`FrontEnd/events/input_handler.py` tiene `handle_event`. Para un clic, recorre
los botones visibles y busca cuál contiene el punto del mouse. Para una tecla,
traduce flechas o Espacio a las mismas acciones usadas por los botones. También
recibe texto del formulario y archivos arrastrados.

`FrontEnd/views/ui_elements.py` contiene métodos compartidos para fuentes,
texto, texto en varias líneas, paneles y botones. `button()` dibuja el botón y
registra su rectángulo junto a su acción. Por eso el dibujo y el clic coinciden.

`node_sprite.py` dibuja una celda y su sentido. `picker_sprite.py` dibuja un
picker con color e indica el seleccionado. Son funciones de dibujo, no clases
del modelo de negocio; el nombre de los archivos respeta la estructura inicial.

## 5. La matriz y el mapa

El backend construye `warehouse.matriz[x][y]`. Cada casilla indica si hay pasillo,
rack, puerta o despacho. La interfaz recorre esa matriz una vez para preparar
`grid`, una representación sencilla usada sólo para dibujar el mapa estático.

La posición en pantalla se calcula así:

```python
pantalla_x = izquierda + x * tamaño_celda
pantalla_y = arriba + (alto_mapa - 1 - y) * tamaño_celda
```

Se invierte Y porque Pygame tiene el origen arriba a la izquierda, mientras que
el depósito lo tiene abajo a la izquierda. La matriz responde «qué hay acá»;
el grafo del backend responde «desde acá, a qué celdas puedo avanzar».

Los pickers y la ruta se dibujan encima de las celdas. El mapa no modifica el
grafo ni decide si un movimiento está permitido.

## 6. Cargar y validar escenarios

`scenarios.validate()` comprueba dimensiones, números, identificadores,
superposiciones, racks, productos, stock, pedidos, pickers y despachos. Rechaza
datos inconsistentes antes de construir el modelo. No convierte un decimal en
una cantidad entera silenciosamente.

`Session.__init__` usa `GraphBuilder` para construir el Warehouse y el parser
de `CatalogManager` para cargar sus tablas hash. El catálogo exige un archivo:
se usa un archivo temporal, que se elimina al terminar de cargar.

Después se comparten los mismos objetos Product entre catálogo y matriz. Si
se descuenta stock en la tabla hash, la celda del rack referencia el mismo
producto. No hay dos cantidades diferentes compitiendo como fuente de verdad.

Las propiedades `stock`, `orders`, `cargo` y `positions` leen los objetos reales
para que la vista los muestre. La interfaz no guarda una segunda base de datos.

`generate()` utiliza `ScenarioGenerator.generar_escenario_dict` del equipo. El
formulario sólo transforma el texto de los tres campos en sus parámetros.

## 7. Generar waves y calcular recorridos

`generate_waves()` llama al WaveManager existente con Kruskal y pide no
descontar stock inmediatamente. El backend asigna pedidos y reserva cantidades.
Los avisos de pedidos inviables se muestran al usuario.

`select(index)` selecciona una wave y calcula ambas estrategias desde la
posición real del picker. No lo mueve al origen del recorrido artificialmente.
Los demás pickers se mantienen quietos y sus posiciones se excluyen del grafo
que recibe el buscador.

`quantities()` suma las unidades pedidas de cada producto. `targets()` pregunta
al Warehouse cuál es el pasillo desde el que se recoge cada producto. El picker
se acerca al rack: no entra en él.

`_calculate()` llama a los algoritmos existentes por tramos:

- Orden: Dijkstra hasta cada acceso en el orden de los pedidos.
- Cercanía: búsqueda con cola de prioridad hasta el destino pendiente más cercano.
- Finalmente: búsqueda hasta un acceso disponible al despacho asignado.

Se concatenan los tramos omitiendo la primera celda repetida. Si algún tramo no
existe, se rechaza la ruta completa y se conserva la selección anterior. Se
llaman las funciones por tramo porque los envoltorios actuales del backend
pueden omitir destinos inaccesibles sin avisar.

`set_strategy()` permite elegir entre las rutas ya calculadas antes de empezar.
No recalcula cada cuadro de la animación. La comparación corresponde a la misma
wave, mismas posiciones y mismos productos.

## 8. Avanzar, retroceder y reiniciar

`advance()` hace una operación completa:

1. Guarda una copia del estado anterior con `snapshot()`.
2. Marca la wave como EN_EJECUCION.
3. Recoge si el picker ya está junto a un producto requerido.
4. Avanza una celda y verifica que no haya otro picker allí.
5. Recoge los productos que correspondan en esa nueva posición.
6. Al terminar, verifica que recogió todo y que el despacho tiene capacidad;
   vacía el carrito y marca los pedidos como PREPARADO.
7. Añade el estado anterior al historial.

`_collect()` es quien llama a `catalog.descontar_stock()`, suma la carga y anota
el producto en `picked`. Esa lista evita descontarlo de nuevo si la ruta pasa
dos veces por el mismo punto.

Si algo falla, `restore()` vuelve al estado anterior. Así no queda un picker
movido con stock parcialmente descontado después de un error.

El historial funciona como una pila: `back()` saca el último estado con `pop()`.
`reset()` restaura `baseline`, que es el estado al seleccionar la wave. Incluye
stock, estados, posiciones, carritos, pesos del despacho y progreso. Al deshacer
el último paso también se deshace la entrega, evitando contabilizarla dos veces.

## 9. Guardar y recuperar

`save()` escribe los productos, pedidos y pickers actuales en JSON. Añade
`_interfaz`, que contiene el escenario inicial y una lista de acciones válidas.
Primero escribe un archivo temporal y luego lo reemplaza para no dejar un JSON
parcial si falla la escritura.

Al reabrir, la sesión reproduce esas acciones sobre el escenario inicial. Esto
reconstruye las waves, la posición y el historial. Sólo admite una lista cerrada
de operaciones: no ejecuta código ni nombres arbitrarios del JSON. Los tiempos
de cálculo pueden cambiar al reabrir, porque se vuelven a medir.

Esta persistencia es propia de la interfaz. El grupo deberá acordar un formato
compartido si después desea reanudar también desde el programa de consola.

## 10. Qué explicar al profesor

«La interfaz dibuja la matriz del depósito y consulta los objetos del backend
para mostrar stock, pedidos y carga. Las rutas se calculan sobre el grafo dirigido.
Los botones llaman a una sesión separada del dibujo, por eso puedo probar la
lógica sin ventana. Cada paso guarda el estado anterior para poder retroceder.
Esta entrega ejecuta una wave por vez; falta integrar la coordinación simultánea
de pickers y la animación del orden de exploración del algoritmo».

Preguntas útiles para el grupo y el profesor:

- ¿Qué controlador común debe ser dueño del estado cuando integremos concurrencia?
- ¿El formato de guardado debe reanudarse también desde consola?
- ¿Qué debe hacer el sistema si un picker bloquea el acceso de otro?
- ¿El algoritmo de rutas debe devolver una secuencia de exploración para animarla?
- ¿El criterio de cercanía entre pedidos puede anteponerse a su prioridad?

## 11. Qué comprueban los tests

`test_gui_session.py` usa los modelos reales: recorre los tres escenarios con
ambas estrategias y verifica las cantidades finales, la legalidad de los pasos,
la restauración del estado y la persistencia. También provoca fallas para
comprobar que no se registran entregas imposibles.

`test_gui_views.py` genera clics de Pygame sobre los rectángulos de los botones,
comprueba el cambio de estado y guarda capturas. Usa video virtual para correr
sin intervención manual. Esto prueba el flujo de la interfaz, aunque no sustituye
probarla con el grupo en la computadora de la presentación.
