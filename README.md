# Wave Picking · Algoritmos II

Sistema para simular y gestionar la preparación de pedidos en un almacén:
modela el almacén como un **dígrafo de pasillos**, agrupa los pedidos en
**waves**, calcula los **recorridos** de los pickers con dos estrategias y los
**simula** paso a paso en una aplicación visual hecha con Pygame.

## Instalación

Requiere **Python 3.10 o superior** (probado con 3.12 y 3.13).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

En Linux o macOS: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.

`requirements.txt` solo tiene `pygame`. Para los gráficos de los experimentos
hace falta además `matplotlib` (opcional).

## Ejecución

| Qué | Comando |
|---|---|
| Interfaz gráfica | `python gui.py` (o doble clic en `iniciar_gui.bat`) |
| Abrir un escenario directo | `python gui.py --escenario BackEnd/data/escenario_basico.json` |
| Versión de consola | `python main.py -i escenario_grande.json -w WAVE_01,WAVE_02` |
| Tests | `python -m pytest tests` (o `python -m unittest discover -t . -s tests`) |
| Experimentos del informe | `python experimentos/ejecutar_experimentos.py` |

## Cómo se usa la interfaz (demostración)

1. **Crear o cargar un warehouse.** En *Inicio*, *Crear escenario* abre el
   generador automático o importa un JSON. También se puede arrastrar un JSON
   a la ventana. La biblioteca guarda escenarios y sesiones.
2. **Ver los productos.** La pestaña *Productos* muestra ubicación `<x,y,z>`,
   peso y stock. Con un clic en el mapa se ve qué hay en cada celda.
3. **Crear o cargar pedidos.** Los pedidos vienen en el escenario. Con
   *Nuevo pedido* se agregan otros (por ejemplo `P001x2, P004x1`).
4. **Generar waves.** *Capacidad de waves* define el máximo de pedidos y de
   unidades. *Generar waves* las arma.
5. **Seleccionar waves.** Se marcan una o varias y se pulsa *Asignar e
   iniciar*: cada wave va al picker libre más cercano y las que no tienen
   picker quedan en espera.
6. **Ejecutar y ver los algoritmos.** En el mapa se ven la ruta planificada,
   los destinos numerados en orden de visita y las celdas que exploró
   Dijkstra (celeste).
7. **Recorrido del picker.** Se controla con *Iniciar*, *Pausar*,
   *Continuar*, *Paso adelante* (→), *Paso atrás* (←) y *Reiniciar*. La
   barra espaciadora pausa y continúa.
8. **Productos recogidos.** La pestaña *Pickers* muestra la carga, lo
   recogido y lo que falta. *Eventos* registra cada recogida y descarga.
9. **Comparar estrategias.** *Estrategia* alterna entre *Orden de pedidos*
   y *Cercanía*. *Comparar estrategias* corre las mismas waves con las dos.
10. **Métricas.** La pestaña *Métricas* muestra la distancia, los nodos
    visitados, las aristas, los nodos explorados y el tiempo de cada picker.
11. **Persistencia.** *Guardar sesión* deja un archivo en la biblioteca. Al
    abrirlo, la simulación sigue en el mismo turno.

## Estructura

```
BackEnd/
  models/        warehouse.py (Warehouse, Digrafo, NodoGrafo), entities.py (Producto, Pedido, Wave, Picker…)
  utils/         graph_builder.py (JSON → dígrafo + Kosaraju), file_parser.py,
                 scenario_generator.py (generador determinista), validador_escenario.py
  data_structures/ max_heap_pedidos.py (Max-Heap propio)
  controllers/   wave_manager.py (waves), path_finding.py (Dijkstra y estrategias),
                 turn_collision_manager.py (turnos y colisiones), simulador.py (orquestador)
  data/          escenarios de ejemplo y de prueba (JSON)
FrontEnd/
  views/         pygame_engine.py (pantallas), mapa.py, ui_elements.py
  events/        input_handler.py (mouse y teclado)
  sprites/       node_sprite.py, picker_sprite.py
  services/      biblioteca.py (escenarios y sesiones guardadas)
tests/           pruebas automáticas (grafo, algoritmos, simulador, generador, interfaz)
experimentos/    script de experimentos (tablas y gráficos en docs/experimentos)
docs/            ARQUITECTURA.md, EXPLICACION_GRAFO.md, INFORME.md, experimentos/
```

La lógica algorítmica (BackEnd) está separada de la interfaz (FrontEnd). La
interfaz solo usa `Simulador`, que encadena
**Warehouse → Productos/Pedidos → WaveManager → Pathfinding → Simulación**.

## Formato del escenario (JSON)

```json
{
  "warehouse": {
    "dimensiones": {"ancho_x": 18, "largo_y": 16},
    "puertas": [{"id": "PUERTA_OUT_1", "tipo": "OUTBOUND", "ubicacion": {"x": 4, "y": 0}}],
    "zonas_despacho": [{"id": "ZONA_A", "puerta_id": "PUERTA_OUT_1", "ubicacion": {"x": 2, "y": 1},
                        "ancho": 5, "alto": 2, "peso_max_kg": 500}],
    "racks": [{"id": "R1", "ubicacion": {"x": 3, "y": 5}, "ancho": 2, "alto": 6}],
    "pasillos": [{"id": "PAS_V0", "ubicacion": {"x": 0, "y": 5}, "ancho": 3, "alto": 6, "sentido": "N"}]
  },
  "pickers": [{"id": "PK_01", "posicion_inicial": {"x": 1, "y": 3}, "capacidad_carga_kg": 150}],
  "productos": [{"id": "P001", "nombre": "Monitor", "rack_id": "R1", "ubicacion": {"x": 3, "y": 5, "z": 1},
                 "cantidad_disponible": 20, "peso_kg": 6.5}],
  "pedidos": [{"id": "PED_01", "prioridad": 5, "items": [{"producto_id": "P001", "cantidad": 2}]}],
  "configuracion": {"wave_max_pedidos": 3, "wave_max_productos": 15}
}
```

- El eje `y` crece hacia arriba y el origen `(0,0)` está abajo a la izquierda.
- Toda celda que no sea rack, zona o puerta es pasillo. Si no se declara, es
  de doble sentido (`AMBOS`).
- Cada rack tiene un lado de 2 celdas y se recoge desde el costado largo.
- El sentido de un pasillo puede ser `N`, `S`, `E`, `O`, `AMBOS` o `NINGUNO`.

## Escenarios de prueba

En `BackEnd/data`:

| Archivo | Tamaño | Productos | Pedidos | Pickers |
|---|---|---|---|---|
| `escenario_basico.json` | 18 × 16 | 8 | 3 | 2 |
| `escenario_grande.json` | 60 × 40 | 170 | 40 | 4 |
| `escenario_gen_chico.json` | 10 × 29 | 30 | 12 | 2 |
| `escenario_gen_mediano.json` | 26 × 37 | 200 | 40 | 4 |
| `escenario_gen_cerca_despacho.json` | 26 × 37 | 200 | 40 | 4 |
| `escenario_gen_grande.json` | 42 × 85 | 600 | 150 | 6 |

## Documentación

- `docs/ARQUITECTURA.md`: módulos, diagrama de clases y flujo de una simulación.
- `docs/EXPLICACION_GRAFO.md`: el modelo del almacén (dígrafo, accesos, Kosaraju).
- `docs/INFORME.md`: análisis algorítmico, complejidad, experimentos y respuestas
  a las preguntas del enunciado.
- `docs/experimentos/`: resultados (CSV y tablas) y gráficos.
