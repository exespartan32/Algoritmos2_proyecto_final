# Interfaz de Wave Picking

Interfaz en Python 3.12 y Pygame, compatible con el backend de la rama
`integracion`. Ejecuta una wave seleccionada a la vez.

## Instalación y ejecución

Desde la carpeta del proyecto, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-gui.txt
.\.venv\Scripts\python.exe gui.py
```

Después de instalar, también se puede abrir con `iniciar_gui.bat`.
El selector de archivos usa Tkinter, incluido en la instalación habitual de
Python para Windows. También se pueden arrastrar archivos JSON a la ventana.

## Uso

1. Cargar un escenario o crear uno desde JSON o con el generador.
2. Generar waves y seleccionar una para calcular su recorrido.
3. Elegir Orden o Cercanía y comparar sus métricas.
4. Iniciar, pausar o avanzar y retroceder paso a paso.
5. Guardar el escenario para continuar después desde la biblioteca.

Reiniciar restaura la wave seleccionada. Los demás pickers permanecen quietos y
se consideran obstáculos. Las flechas derecha e izquierda avanzan y retroceden;
Espacio pausa o continúa.

## Organización

| Archivo o carpeta | Responsabilidad |
|---|---|
| `gui.py` | Iniciar la aplicación. |
| `FrontEnd/views/` | Pantallas, paneles y botones. |
| `FrontEnd/events/` | Eventos de mouse y teclado. |
| `FrontEnd/sprites/` | Dibujar celdas y pickers. |
| `FrontEnd/services/session.py` | Coordinar la sesión, historial y guardado. |
| `FrontEnd/services/scenarios.py` | Validar entradas y llamar al generador. |
| `FrontEnd/services/backend_adapter.py` | Adaptar las interfaces del backend. |
| `biblioteca/` | Escenarios del usuario; se crea localmente y no se sube a Git. |

## Integración con el grupo

La interfaz depende de los modelos de `integracion`; esa base debe incorporarse
antes de llevarla al `main` antiguo. Los archivos del backend no se modifican.

El adaptador traduce los métodos del grafo y ofrece en memoria el import BFS que
el generador todavía referencia. Puede retirarse ese puente cuando el equipo
corrija el import. Los recorridos usan el Dijkstra existente del backend.

Guardar agrega la sección `_interfaz` al JSON para recuperar la sesión y su
historial desde `gui.py`. El programa de consola no interpreta esa sección.
El celeste del mapa muestra los nodos explorados, sin animar su orden temporal.
La coordinación de varias waves simultáneas queda pendiente de integración.
