# Interfaz Pygame de Wave Picking

Interfaz conectada al backend de `origin/integracion` (base `78b2bb3`). Los cambios
de esta entrega están en `FrontEnd`, el lanzador, pruebas y documentación.
No se modifican archivos de `BackEnd`, `main.py` ni el `requirements.txt` original.

## Ejecutar en esta computadora

Abrir `iniciar_gui.bat`, o desde PowerShell:

```powershell
cd D:\Proyecto-Algoritmos2
.\.venv\Scripts\python.exe gui.py
```

El entorno local ya tiene Pygame instalado. Para instalar en otra computadora con
Python 3.12 (incluido Tkinter para el selector de archivos):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-gui.txt
.\.venv\Scripts\python.exe gui.py
```

También se puede abrir directamente un escenario:

```powershell
.\.venv\Scripts\python.exe gui.py --escenario BackEnd/data/escenario_basico.json
```

## Recorrido para probarla

1. En Inicio, abrir el escenario básico. Los ejemplos se copian una sola vez a
   `biblioteca/`; los originales del backend nunca se editan.
2. Pulsar **Generar Waves**, **Seleccionar Wave** y seleccionar una.
3. Alternar **Orden / Cercanía** o abrir **Comparar Estrategias**.
4. Pulsar **Paso Adelante** hasta una recogida: baja el stock y sube la carga.
5. Pulsar **Paso Atrás**: se restauran posición, stock, estados y carga.
6. Usar **Iniciar**, **Pausar** y **Continuar** para animar el recorrido.
7. Al llegar a despacho, la wave finaliza, los pedidos quedan preparados y se
   vacía el carrito. Seleccionar otra wave para continuar.
8. **Guardar Escenario**, volver a Inicio y abrir el archivo `estado_...json`.
   Se recupera la sesión, incluido el historial para retroceder.
9. **Reiniciar** restaura la wave seleccionada, no las waves anteriores.

Crear Escenario permite importar JSON o usar el generador del equipo. También se
puede arrastrar un JSON sobre la ventana. Eliminar pide confirmación y sólo borra
el archivo de la biblioteca. Flecha derecha/izquierda avanza/retrocede; Espacio
pausa/continúa; Escape cierra un cuadro. La ventana se puede redimensionar.

## Alcance y límites actuales

- Se ejecuta **una wave seleccionada a la vez**. Se muestran todos los pickers y
  los estacionados se consideran obstáculos. No incluye un coordinador de
  movimiento simultáneo, esperas ni replanificación entre varias waves.
- Se consumen los algoritmos actuales del equipo: Dijkstra por tramo y búsqueda
  del destino más cercano, además de WaveManager con Kruskal. No se etiqueta el
  buscador como BFS porque la implementación actual usa una cola de prioridad.
- El celeste muestra el conjunto de nodos explorados. No representa el orden
  temporal de exploración: el backend devuelve un conjunto sin esa información.
- La distancia y las aristas cuentan los movimientos de la ruta. Los nodos son
  únicos entre búsquedas. El tiempo corresponde al cálculo completo de esa
  estrategia, no a la animación, y varía entre ejecuciones.
- Se validan estructura, límites, referencias y posiciones al importar. La
  accesibilidad se comprueba al calcular una wave; si un picker estacionado
  impide la ruta, se informa y se puede ejecutar antes la wave de ese picker.
- El escenario grande deja dos pedidos pendientes con los límites actuales del
  backend. Se muestran los avisos; no se fuerzan pedidos inviables ni se altera
  el criterio de agrupamiento del equipo.
- La reserva de stock ocurre al generar waves; el descuento real se realiza al
  recoger. Las waves se generan una sola vez por sesión.
- Guardar escribe datos actuales y una sección `_interfaz` con escenario inicial
  y acciones. El backend por sí solo no reanuda esa sección: la reanudación se
  realiza desde `gui.py`. Se rechazan pedidos EN_WAVE sin historial de sesión.

## Integración con las ramas del grupo

La rama `interfaz-pygame` parte de `integracion`, que contiene avances no presentes
en el `main` revisado (`7acee94`). **Integrar primero esa base de backend** antes de
llevar la interfaz a main. Copiar sólo FrontEnd sobre el main antiguo no alcanza:
los modelos y las firmas de sus métodos son distintos.

Revisar el cambio de interfaz con:

```powershell
git diff origin/integracion...interfaz-pygame --stat
git diff origin/integracion...interfaz-pygame -- BackEnd main.py requirements.txt
```

La segunda comparación debe quedar vacía. La interfaz ocupa los cinco archivos
que estaban vacíos en FrontEnd y agrega `FrontEnd/services`. Los archivos de
ejemplos, la biblioteca local y el entorno virtual no forman parte del commit.
No se realizó push. No puede garantizarse ausencia de conflictos si las ramas
remotas cambian posteriormente.

Hay dos adaptaciones temporales **dentro de FrontEnd**:

1. `AdaptadorGrafo` traduce `obtener_vecinos` a `obtener_vecinos_validos` para que
   el buscador consuma el grafo real y filtre posiciones de pickers estacionados.
2. El generador conserva un import a `BackEnd.controllers.bfs`, que ya no está en
   integración. Al abrir el generador se ofrece ese nombre sólo en memoria si
   falta, sin crear ni modificar archivos del backend. `generar_escenario_dict`
   no usa ese buscador. Retirar este puente cuando el grupo repare el import.

Estos puentes no arreglan el lanzador de consola `main.py`; su revisión corresponde
al trabajo de integración del grupo.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas de vista usan un controlador de video virtual y simulan clics en los
botones. Las capturas quedan en `test-output/`, excluido de Git. Las pruebas de
sesión recorren los tres escenarios con ambas estrategias y comprueban stock,
estados, ausencia de superposición, undo, reinicio, persistencia, validación y
errores de rutas. Los ejemplos del equipo no se modifican.

Explicación de código: [docs/GUI-PASO-A-PASO.md](docs/GUI-PASO-A-PASO.md).
