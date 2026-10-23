from BackEnd.utils.file_parser import FileParser
from BackEnd.utils.graph_builder import GraphBuilder
from BackEnd.utils.scenario_generator import ScenarioGenerator


def mostrar_resumen(titulo, wh):
    grafo = wh.grafo_pasillos
    cant_aristas = sum(len(v) for v in grafo.lista_adyacencia.values())
    componentes = GraphBuilder.componentes_fuertemente_conexas(wh)
    print(f"\n=== {titulo} ===")
    print(f"Dimensiones: {wh.ancho_x}x{wh.largo_y}")
    print(f"Nodos (pasillos): {len(grafo.nodos)} | Aristas dirigidas: {cant_aristas} | "
          f"Obstáculos (racks, zonas, puertas): {len(wh.obstaculos)}")
    print(f"Racks: {len(wh.racks)} | Productos: {len(wh.catalogo_productos)} | "
          f"Componentes fuertemente conexas: {len(componentes)}")
    if wh.advertencias:
        print("Advertencias:")
        for adv in wh.advertencias:
            print(f"  - {adv}")
    else:
        print("Sin advertencias.")


if __name__ == "__main__":
    # 1. Escenario del Anexo A (archivo JSON)
    wh = FileParser.cargar_warehouse_desde_json("BackEnd/data/escenario.json")
    mostrar_resumen("ESCENARIO DEL ANEXO A", wh)
    for prod_id in wh.catalogo_productos:
        prod = wh.catalogo_productos[prod_id]
        print(f"  {prod_id} en rack ({prod.x},{prod.y}, z={prod.z}) -> se recoge desde {wh.obtener_nodos_acceso_producto(prod_id)}")
    for zona_id in wh.zonas_despacho:
        print(f"  {zona_id}: {len(wh.obtener_nodos_acceso_zona(zona_id))} pasillos de acceso")
    accesos = [wh.obtener_nodo_acceso_producto(p) for p in wh.catalogo_productos]
    wh.imprimir_mapa(camino_bfs=accesos)  # '*' = dónde frena el picker para cada producto

    # 2. Escenario generado automáticamente (Sección 16)
    wh_auto, valido = ScenarioGenerator.generar_y_validar_warehouse(
        ruta_guardado_json="BackEnd/data/escenario_generado.json",
        cantidad_estantes=5,
        cantidad_pasillos=8,
        cantidad_productos=20,
        modo_localizacion="ALEATORIO",  # "ALEATORIO", "CERCA_DESPACHO" o "DISPERSO"
        cantidad_pedidos=8,
        max_productos_por_pedido=3,
        wave_max_pedidos=3
    )
    mostrar_resumen("ESCENARIO GENERADO (SECCIÓN 16)", wh_auto)
    print(f"¿Escenario válido (una sola red conexa, todo accesible)?: {valido}")
