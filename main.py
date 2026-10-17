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
import time
import argparse
from dataclasses import dataclass
from typing import Optional, List

from BackEnd.models.catalog_manager import CatalogManager
from BackEnd.controllers.wave_manager import WaveManager
from BackEnd.enums.enums import EstadoPedido, EstadoWave


# =============================================================================
# PANEL CENTRAL DE PARÁMETROS DE EJECUCIÓN (MODIFICAR ÚNICAMENTE AQUÍ)
# =============================================================================
@dataclass
class ConfiguracionSimulacion:
    # 1. Directorio y Archivos JSON de Entrada / Salida
    directorio_datos: Optional[str] = None  # None = usa "BackEnd/data" automáticamente
    archivo_entrada: str = (
        "escenario_basico.json"  # Ej: "escenario_basico.json", "escenario_grande.json", "estado_guardado.json"
    )
    archivo_salida: str = (
        "estado_guardado.json"  # Archivo donde se guarda la Tabla Hash decodificada
    )

    # 2. Parámetros del Gestor de Waves (Cercanía Espacial MST y Filtros)
    metodo_mst: str = "KRUSKAL"  # Opciones: "KRUSKAL" (usa disjoint_set.py) o "PRIM"
    prefijo_id_wave: str = "WAVE"  # Prefijo para nombrar las olas (ej. WAVE_01)
    prioridad_minima_pedidos: int = (
        1  # Filtra pedidos con prioridad >= a este valor (1 a 5)
    )

    # 3. Parámetros de Capacidad de las Waves (None = usa los del JSON cargado)
    wave_max_pedidos: Optional[int] = None  # Ej: None, 2, 4, 6
    wave_max_productos: Optional[int] = None  # Ej: None, 10, 20, 30

    # 4. Parámetros Físicos de Pickers y Zonas de Despacho (None = usa los del JSON)
    capacidad_carga_picker_kg: Optional[float] = (
        None  # Sobrescribe capacidad_carga_kg de los pickers
    )
    peso_max_zona_despacho_kg: Optional[float] = (
        None  # Sobrescribe peso_max_kg de las zonas de despacho
    )
    ids_pickers_activos: Optional[List[str]] = (
        None  # Ej: ["PK_01"] o None para usar todos los del JSON
    )
    ids_zonas_activas: Optional[List[str]] = (
        None  # Ej: ["ZONA_A"] o None para usar todas las de salida
    )

    # 5. Parámetros de la Tabla Hash Universal (CatalogManager)
    tamano_tabla_hash: int = 1009  # Cantidad de listas enlazadas (m)
    primo_p_hash: int = 999983  # Número primo p > m para Hashing Universal
    semilla_hash: Optional[int] = (
        42  # Semilla para coeficientes a y b (None = aleatoria)
    )

    # 6. Control de Simulación y Descuento de Stock
    descontar_stock_al_crear_wave: bool = (
        False  # True = descuenta en Tabla Hash al armar la Wave
    )
    modo_ejecucion_waves: str = (
        "SOLO_PRIMERA"  # Opciones: "TODAS", "SOLO_PRIMERA", "NINGUNA"
    )
    cantidad_waves_a_ejecutar: Optional[int] = (
        None  # Si defines un número (ej. 2), ejecuta exactamente 2 waves
    )
    mostrar_detalle_productos_stock: bool = (
        True  # Muestra tabla de cambios de stock en consola
    )


# =============================================================================
# CONFIGURACIÓN ACTIVA (CAMBIA LOS VALORES AQUÍ PARA TUS PRUEBAS)
# =============================================================================
PARAMETROS_EJECUCION = ConfiguracionSimulacion(
    archivo_entrada="escenario_basico.json",
    archivo_salida="estado_guardado.json",
    metodo_mst="KRUSKAL",
    prefijo_id_wave="WAVE",
    prioridad_minima_pedidos=1,
    wave_max_pedidos=None,
    wave_max_productos=None,
    capacidad_carga_picker_kg=None,
    peso_max_zona_despacho_kg=None,
    ids_pickers_activos=None,
    ids_zonas_activas=None,
    tamano_tabla_hash=1009,
    primo_p_hash=999983,
    semilla_hash=42,
    descontar_stock_al_crear_wave=False,
    modo_ejecucion_waves="SOLO_PRIMERA",
    cantidad_waves_a_ejecutar=None,
    mostrar_detalle_productos_stock=True,
)


# =============================================================================
# MOTOR DE EJECUCIÓN PARAMETRIZADO (100% INDEPENDIENTE DEL GRAFO)
# =============================================================================
def aplicar_parametros_personalizados(
    catalogo: CatalogManager, config: ConfiguracionSimulacion
) -> None:
    if config.capacidad_carga_picker_kg is not None:
        for picker in catalogo.pickers:
            picker.capacidad_carga_kg = float(config.capacidad_carga_picker_kg)

    if config.peso_max_zona_despacho_kg is not None:
        for zd in catalogo.warehouse_raw.get("zonas_despacho", []):
            zd["peso_max_kg"] = float(config.peso_max_zona_despacho_kg)


def ejecutar_simulacion(config: ConfiguracionSimulacion) -> None:
    t_inicio_total = time.perf_counter()

    # 1. Inicializar CatalogManager y cargar el JSON en las Tablas Hash O(1)
    catalogo = CatalogManager(
        tamano_tabla=config.tamano_tabla_hash,
        primo_p=config.primo_p_hash,
        semilla_hash=config.semilla_hash,
        directorio_datos=config.directorio_datos,
    )
    ruta_entrada = catalogo.cargar_escenario_json(config.archivo_entrada)

    aplicar_parametros_personalizados(catalogo, config)

    max_ped_efectivo = config.wave_max_pedidos or catalogo.wave_max_pedidos
    max_prod_efectivo = config.wave_max_productos or catalogo.wave_max_productos
    zonas_json = [z["id"] for z in catalogo.warehouse_raw.get("zonas_despacho", [])]

    print("=" * 75)
    print("1. CONFIGURACIÓN ACTIVA Y CARGA EN TABLAS HASH O(1)")
    print("=" * 75)
    print(f"  * Archivo de Entrada          : {ruta_entrada}")
    print(f"  * Archivo de Salida           : {config.archivo_salida}")
    print(f"  * Método Gestor de Waves (MST): {config.metodo_mst.upper()}")
    print(
        f"  * Límites por Wave            : máx {max_ped_efectivo} pedidos | máx {max_prod_efectivo} unidades"
    )
    print(f"  * Prioridad Mínima Pedidos    : >= {config.prioridad_minima_pedidos}")
    print(f"  * Zonas Despacho (del JSON)   : {zonas_json}")
    print(
        f"  * Pickers en Escenario        : {[(p.id_picker, f'{p.capacidad_carga_kg}kg') for p in catalogo.pickers]}"
    )
    print(
        f"  * Productos en Tabla Hash     : {catalogo.productos_hash.cantidad_elementos} (m={config.tamano_tabla_hash})"
    )
    print(
        f"  * Pedidos en Tabla Hash       : {catalogo.pedidos_hash.cantidad_elementos} "
        f"({len(catalogo.obtener_pedidos_pendientes(config.prioridad_minima_pedidos))} PENDIENTES elegibles)"
    )

    stock_inicial = {
        p.id_producto: p.cantidad_disponible
        for p in catalogo.obtener_todos_los_productos()
    }

    # 2. Ejecutar el Gestor de Waves usando únicamente CatalogManager
    t_inicio_waves = time.perf_counter()
    gestor_waves = WaveManager(
        metodo_mst=config.metodo_mst,
        prefijo_id_wave=config.prefijo_id_wave,
        wave_max_pedidos=config.wave_max_pedidos,
        wave_max_productos=config.wave_max_productos,
    )

    waves = gestor_waves.generar_waves(
        catalogo=catalogo,
        descontar_stock_inmediato=config.descontar_stock_al_crear_wave,
        prioridad_minima=config.prioridad_minima_pedidos,
        ids_pickers_activos=config.ids_pickers_activos,
        ids_zonas_activas=config.ids_zonas_activas,
    )
    t_waves_ms = (time.perf_counter() - t_inicio_waves) * 1000.0

    print("\n" + "=" * 75)
    print(
        f"2. RESULTADO DEL ARMADO DE WAVES ({len(waves)} olas en {t_waves_ms:.3f} ms)"
    )
    print("=" * 75)
    for w in waves:
        pedidos_info = [f"{p.id_pedido}(P:{p.prioridad})" for p in w.pedidos]
        print(
            f"  -> {w.id_wave} | Picker: {w.id_picker_asignado} | Zona: {w.id_zona_despacho} | "
            f"Peso: {w.peso_total_kg:6.2f} kg | Unid: {w.unidades_totales:2d} | Pedidos: {pedidos_info}"
        )

    if gestor_waves.alertas_peso:
        print("\n  [Alertas de Restricciones Físicas y Capacidad]:")
        for alerta in gestor_waves.alertas_peso:
            print(f"    ! {alerta}")

    # 3. Simular recolección y modificación de stock en O(1) en la Tabla Hash
    modo = config.modo_ejecucion_waves.upper()
    if config.cantidad_waves_a_ejecutar is not None:
        waves_a_procesar = waves[: config.cantidad_waves_a_ejecutar]
    elif modo == "TODAS":
        waves_a_procesar = waves
    elif modo == "SOLO_PRIMERA":
        waves_a_procesar = waves[:1]
    else:
        waves_a_procesar = []

    if waves_a_procesar:
        print("\n" + "=" * 75)
        print(
            f"3. SIMULACIÓN DE RECOLECCIÓN Y DESCUENTO EN TABLA HASH ({len(waves_a_procesar)} waves)"
        )
        print("=" * 75)
        for w in waves_a_procesar:
            w.estado = EstadoWave.FINALIZADA
            for pedido in w.pedidos:
                if not config.descontar_stock_al_crear_wave:
                    for item in pedido.items:
                        catalogo.descontar_stock(item.producto_id, item.cantidad)
                catalogo.actualizar_estado_pedido_O1(
                    pedido.id_pedido, EstadoPedido.PREPARADO
                )
            print(
                f"  * {w.id_wave} completada -> Pedidos {[p.id_pedido for p in w.pedidos]} marcados como PREPARADO."
            )

    if config.mostrar_detalle_productos_stock:
        print("\n  [Cambios de Stock registrados en la Tabla Hash O(1)]:")
        hubo_cambios = False
        for prod in sorted(
            catalogo.obtener_todos_los_productos(), key=lambda x: x.id_producto
        ):
            ant = stock_inicial[prod.id_producto]
            act = prod.cantidad_disponible
            if ant != act:
                hubo_cambios = True
                print(
                    f"    - {prod.id_producto} ({prod.nombre}): {ant} -> {act} unidades (-{ant - act})"
                )
        if not hubo_cambios:
            print("    - Sin descuentos de stock en esta ejecución.")

    # 4. Decodificar las Tablas Hash y guardar en el archivo JSON de salida
    ruta_salida = catalogo.guardar_estado_simulacion_json(
        nombre_archivo_salida=config.archivo_salida
    )
    t_total_ms = (time.perf_counter() - t_inicio_total) * 1000.0

    print("\n" + "=" * 75)
    print("4. PERSISTENCIA Y DECODIFICACIÓN DE TABLA HASH A JSON")
    print("=" * 75)
    print(f"  * Estado guardado en : {ruta_salida}")
    print(f"  * Tiempo total       : {t_total_ms:.3f} ms")
    print("=" * 75)


def leer_argumentos_consola(
    config_base: ConfiguracionSimulacion,
) -> ConfiguracionSimulacion:
    parser = argparse.ArgumentParser(
        description="Ejecutor parametrizado de Tablas Hash y Wave Picking"
    )
    parser.add_argument("-i", "--input", type=str, help="Archivo JSON de entrada")
    parser.add_argument("-o", "--output", type=str, help="Archivo JSON de salida")
    parser.add_argument(
        "-m", "--metodo", type=str, choices=["KRUSKAL", "PRIM"], help="Método MST"
    )
    parser.add_argument("--max-pedidos", type=int, help="Sobrescribir wave_max_pedidos")
    parser.add_argument(
        "--max-productos", type=int, help="Sobrescribir wave_max_productos"
    )
    parser.add_argument(
        "--prio-min", type=int, help="Prioridad mínima de pedidos (1..5)"
    )
    parser.add_argument(
        "--cap-picker", type=float, help="Capacidad de carga del picker en kg"
    )
    parser.add_argument(
        "--modo",
        type=str,
        choices=["TODAS", "SOLO_PRIMERA", "NINGUNA"],
        help="Waves a recolectar",
    )

    args = parser.parse_args()
    if args.input:
        config_base.archivo_entrada = args.input
    if args.output:
        config_base.archivo_salida = args.output
    if args.metodo:
        config_base.metodo_mst = args.metodo
    if args.max_pedidos is not None:
        config_base.wave_max_pedidos = args.max_pedidos
    if args.max_productos is not None:
        config_base.wave_max_productos = args.max_productos
    if args.prio_min is not None:
        config_base.prioridad_minima_pedidos = args.prio_min
    if args.cap_picker is not None:
        config_base.capacidad_carga_picker_kg = args.cap_picker
    if args.modo:
        config_base.modo_ejecucion_waves = args.modo

    return config_base


if __name__ == "__main__":
    config_final = leer_argumentos_consola(PARAMETROS_EJECUCION)
    ejecutar_simulacion(config_final)
