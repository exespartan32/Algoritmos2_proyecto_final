from BackEnd.utils.file_parser import FileParser
from BackEnd.controllers.bfs import BuscadorBFS

if __name__ == "__main__":
    ruta = "BackEnd/data/escenario_grande.json"
    wh = FileParser.cargar_warehouse_desde_json(ruta)

    print(f"Warehouse creado: {wh.ancho_x}x{wh.largo_y}")
    print(f"Total nodos de pasillo en el Digrafo: {len(wh.grafo_pasillos.nodos)}")
    print(f"Total productos cargados en Racks: {len(wh.catalogo_productos)}")

    origen_picker = (5, 4)  # Posición inicial de PK_01
    destino_pasillo = wh.obtener_nodo_acceso_producto("P001")
    print(f"\nProducto P001 está en Rack (50, 14) -> Se accede desde Pasillo: {destino_pasillo}")

    resultado = BuscadorBFS.buscar_camino(wh.grafo_pasillos, origen_picker, destino_pasillo)

    if resultado:
        # Imprime la matriz con el camino del BFS marcado con '*'
        wh.imprimir_mapa(camino_bfs=resultado.secuencia_pasos)

        print(f"¡Camino encontrado con BFS!")
        print(f" - Distancia total: {resultado.distancia_total} pasos")
        print(f" - Nodos visitados por BFS: {resultado.cantidad_nodos_visitados}")
        print(f" - Aristas recorridas: {resultado.cantidad_aristas_recorridas}")
        print(f" - Tiempo: {resultado.tiempo_ejecucion_ms:.3f} ms")