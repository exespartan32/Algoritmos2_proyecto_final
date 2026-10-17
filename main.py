from BackEnd.utils.scenario_generator import ScenarioGenerator
from BackEnd.controllers.bfs import BuscadorBFS

if __name__ == "__main__":
    print("=== GENERANDO ESCENARIO AUTOMÁTICO (SECCIÓN 16) ===")
    wh_auto, valido = ScenarioGenerator.generar_y_validar_warehouse(
        ruta_guardado_json="BackEnd/data/escenario_generado.json",
        cantidad_estantes=5,          # Probá cambiar la cantidad de racks (ej: 3, 5, 8)
        cantidad_pasillos=8,
        cantidad_productos=20,
        modo_localizacion="ALEATORIO", # "ALEATORIO", "CERCA_DESPACHO" o "DISPERSO"
        cantidad_pedidos=8,
        max_productos_por_pedido=3,
        wave_max_pedidos=3
    )

    print(f"¿Escenario 100% válido y conexo (ida/vuelta con BFS)?: {valido}")
    print(f"Dimensiones generadas: {wh_auto.ancho_x}x{wh_auto.largo_y}")
    print(f"Total Racks: {len(wh_auto.racks)} | Total Productos: {len(wh_auto.catalogo_productos)}")

    # Probar un camino BFS hasta el primer producto generado (P001)
    origen = (1, 3)
    destino = wh_auto.obtener_nodo_acceso_producto("P001")
    res = BuscadorBFS.buscar_camino(wh_auto.grafo_pasillos, origen, destino)

    if res:
        wh_auto.imprimir_mapa(camino_bfs=res.secuencia_pasos)
        print(f"Camino a P001 en {destino} -> Distancia: {res.distancia_total} pasos | Tiempo: {res.tiempo_ejecucion_ms:.3f} ms")