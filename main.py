import os
from BackEnd.controllers.persistence_generator import PersistenceAndGenerator
from BackEnd.controllers.simulator_controller import SimulatorController


def main():
    ruta_entrada = os.path.join("BackEnd", "data", "escenario.json")
    ruta_salida = os.path.join("BackEnd", "data", "estado_guardado.json")

    persistencia = PersistenceAndGenerator()
    warehouse, catalogo, pickers = persistencia.cargar_escenario_json(ruta_entrada)

    print("=== 1. ESCENARIO CARGADO EN TABLAS HASH O(1) ===")
    print(f"Dimensiones Warehouse: {warehouse.ancho_x}x{warehouse.largo_y}")
    print(f"Zonas de despacho totales: {list(warehouse.zonas_despacho.keys())}")
    prod_test = catalogo.buscar_producto_O1("P001")
    if prod_test:
        print(
            f"Stock inicial de {prod_test.id_producto} ({prod_test.nombre}): {prod_test.cantidad_disponible}"
        )

    simulador = SimulatorController(warehouse, catalogo, pickers, ruta_salida)
    simulador.iniciar()

    print("\n=== 2. WAVES GENERADAS Y COMPARACIÓN DE ESTRATEGIAS ===")
    for wave in simulador.waves_activas:
        print(
            f"Wave: {wave.id_wave} | Picker: {wave.id_picker_asignado} | "
            f"Zona Despacho: {wave.id_zona_despacho} | Peso Total: {wave.peso_total_kg} kg"
        )
        metricas = simulador.metrics_manager.comparar_estrategias(wave.id_wave)
        for est, met in metricas.items():
            print(
                f"  -> {est.value}: Distancia={met.distancia_total}m, "
                f"Nodos Explorados={met.nodos_visitados}, Tiempo={met.tiempo_ms} ms"
            )

    # Simulamos pasos hasta finalizar o pausar para volcar la Tabla Hash a JSON
    while simulador.estado_actual.value != "FINALIZADO":
        simulador.avanzar_paso_a_paso()

    print("\n=== 3. STOCK ACTUALIZADO EN TABLA HASH Y GUARDADO EN JSON ===")
    prod_post = catalogo.buscar_producto_O1("P001")
    if prod_post:
        print(
            f"Stock final de {prod_post.id_producto} tras simulación: {prod_post.cantidad_disponible}"
        )
    print(f"Archivo JSON exportado exitosamente en: {ruta_salida}")


if __name__ == "__main__":
    main()
