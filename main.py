from BackEnd.utils.file_parser import FileParser
from BackEnd.controllers.bfs import BuscadorBFS

if __name__ == "__main__":
    # 1. Cargar escenario y construir Matriz + Digrafo
    ruta = "BackEnd/data/escenario_grande.json"
    wh = FileParser.cargar_warehouse_desde_json(ruta)

    print(f"Warehouse creado: {wh.ancho_x}x{wh.largo_y}")
    print(f"Total nodos de pasillo en el Digrafo: {len(wh.grafo_pasillos.nodos)}")
    print(f"Total productos cargados en Racks: {len(wh.catalogo_productos)}")

    # 2. Probar que el producto P001 (en rack x=50, y=14) nos da el nodo de pasillo de al lado
    origen_picker = (5, 4)  # Posición inicial de PK_01 en escenario_grande.json
    destino_pasillo = wh.obtener_nodo_acceso_producto("P001")
    print(f"\nProducto P001 está en Rack (50, 14) -> Se accede desde Pasillo: {destino_pasillo}")

    # 3. Correr BFS desde el Picker hasta el nodo de acceso del Rack
    resultado = BuscadorBFS.buscar_camino(wh.grafo_pasillos, origen_picker, destino_pasillo)

    if resultado:
        print(f"¡Camino encontrado con BFS!")
        print(f" - Distancia total: {resultado.distancia_total} pasos")
        print(f" - Nodos visitados por BFS: {resultado.cantidad_nodos_visitados}")
        print(f" - Aristas recorridas: {resultado.cantidad_aristas_recorridas}")
        print(f" - Tiempo: {resultado.tiempo_ejecucion_ms:.3f} ms")
        print(f" - Primeros 5 pasos: {resultado.secuencia_pasos[:5]} ... Últimos 3: {resultado.secuencia_pasos[-3:]}")