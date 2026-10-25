import time
import argparse
from typing import Optional, List, Dict

from BackEnd.utils.file_parser import FileParser
from BackEnd.models.warehouse import Warehouse
from BackEnd.models.entities import Wave
from BackEnd.controllers.wave_manager import WaveManager
from BackEnd.controllers.path_finding import Pathfinding
from BackEnd.controllers.turn_collision_manager import TurnAndCollisionManager
from BackEnd.enums.enums import EstrategiaRuteo

# =============================================================================
# PARÁMETROS DE EJECUCIÓN (DEFINIDOS UNA ÚNICA VEZ AQUÍ)
# =============================================================================
ESCENARIO_A_CARGAR: str = (
    "escenario_grande.json"  # "escenario_basico.json" o "escenario_grande.json"
)
ARCHIVO_SALIDA_JSON: str = "estado_guardado.json"

SELECCIONAR_WAVES_INTERACTIVAMENTE: bool = True
WAVES_A_EJECUTAR_SIMULTANEAMENTE: List[str] = [
    "WAVE_01",
    "WAVE_02",
    "WAVE_03",
    "WAVE_04",
]

MAX_PICKERS_POR_WAVE: int = 2
WAVE_MAX_PEDIDOS: Optional[int] = None
WAVE_MAX_PRODUCTOS: Optional[int] = None


def mostrar_waves_disponibles_y_pickers(
    gestor_waves: WaveManager, warehouse: Warehouse
) -> List[Wave]:
    waves_disponibles = gestor_waves.obtener_waves_disponibles()
    pickers_libres = gestor_waves.obtener_pickers_libres(warehouse.pickers)

    print("\n" + "=" * 95)
    print(
        f" PASO 2: WAVES DISPONIBLES PARA SELECCIONAR ({len(waves_disponibles)} Waves en estado PENDIENTE)"
    )
    print("=" * 95)
    for idx, w in enumerate(waves_disponibles, start=1):
        ids_ped = [f"{p.id_pedido}(P:{p.prioridad})" for p in w.pedidos]
        print(
            f"  [{idx:2d}] {w.id_wave} | Estado: {w.estado.value:9s} | "
            f"Pedidos ({len(w.pedidos)}/{w.wave_max_pedidos}): {ids_ped} | "
            f"Unidades: {w.unidades_totales:2d}/{w.wave_max_productos} | "
            f"Peso: {w.peso_total_kg:6.2f} kg | Zona: {w.id_zona_despacho}"
        )

    print("-" * 95)
    print(f" PICKERS LIBRES ({len(pickers_libres)}/{len(warehouse.pickers)}):")
    for pk in pickers_libres:
        print(
            f"  * {pk.id_picker} -> Posición actual: {pk.posicion_actual} | "
            f"Capacidad máx: {pk.capacidad_carga_kg:.1f} kg | Wave activa: {pk.id_wave_actual}"
        )
    print("=" * 95)
    return waves_disponibles


def solicitar_seleccion_waves_usuario(
    waves_disponibles: List[Wave], seleccion_por_defecto: List[str]
) -> List[str]:
    if not waves_disponibles:
        return []
    if not SELECCIONAR_WAVES_INTERACTIVAMENTE:
        return seleccion_por_defecto

    print("\n" + "=" * 95)
    print(" PASO 3: SELECCIÓN DE LAS WAVES A EJECUTAR EN SIMULTÁNEO")
    print("=" * 95)
    try:
        entrada = input(
            f"  Ingrese números (ej: 1, 2, 3) o IDs (Enter para {seleccion_por_defecto}): "
        ).strip()
    except EOFError:
        return seleccion_por_defecto

    if not entrada:
        return seleccion_por_defecto

    partes = [
        p.strip().upper() for p in entrada.replace(";", ",").split(",") if p.strip()
    ]
    ids_elegidos: List[str] = []

    for token in partes:
        if token.isdigit():
            indice = int(token) - 1
            if 0 <= indice < len(waves_disponibles):
                ids_elegidos.append(waves_disponibles[indice].id_wave)
        else:
            if not token.startswith("WAVE_"):
                posible_num = token.replace("WAVE", "").strip("_")
                if posible_num.isdigit():
                    token = f"WAVE_{int(posible_num):02d}"
            ids_elegidos.append(token)

    return ids_elegidos if ids_elegidos else seleccion_por_defecto


def ejecutar_orquestador(
    archivo_entrada: str,
    waves_preseleccionadas: List[str],
) -> None:
    # -------------------------------------------------------------------------
    # 1. CARGAR WAREHOUSE, DÍGRAFO, PRODUCTOS Y PEDIDOS CON EL PARSER DE LAUREANO
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    ruta_cargada = FileParser.resolver_ruta(archivo_entrada)
    warehouse = FileParser.cargar_warehouse_desde_json(ruta_cargada)
    t_carga_ms = (time.perf_counter() - t0) * 1000.0

    stock_antes_waves: Dict[str, int] = {
        p.id_producto: p.cantidad_disponible
        for p in warehouse.obtener_todos_los_productos()
    }

    max_pedidos = (
        WAVE_MAX_PEDIDOS if WAVE_MAX_PEDIDOS is not None else warehouse.wave_max_pedidos
    )
    max_productos = (
        WAVE_MAX_PRODUCTOS
        if WAVE_MAX_PRODUCTOS is not None
        else warehouse.wave_max_productos
    )

    # Precalcular matriz APSP sobre los productos en el Dígrafo de Laureano
    t_pre = time.perf_counter()
    coords_productos = {
        p.coordenadas_xy for p in warehouse.obtener_todos_los_productos()
    }
    matriz_distancias = Pathfinding.construir_matriz_distancias_productos(
        coordenadas_productos_xy=coords_productos,
        grafo=warehouse.grafo_pasillos,
        warehouse=warehouse,
    )
    t_pre_ms = (time.perf_counter() - t_pre) * 1000.0

    # -------------------------------------------------------------------------
    # PASO 1: ARMAR LAS WAVES (MAX-HEAP + AVERAGE LINKAGE EN DÍGRAFO)
    # -------------------------------------------------------------------------
    t_wave = time.perf_counter()
    gestor_waves = WaveManager(
        wave_max_pedidos=max_pedidos,
        wave_max_productos=max_productos,
        max_pickers_por_wave=MAX_PICKERS_POR_WAVE,
        proveedor_distancias=matriz_distancias,
    )

    waves_armadas = gestor_waves.generar_waves(
        warehouse=warehouse,
        proveedor_distancias=matriz_distancias,
    )
    t_wave_ms = (time.perf_counter() - t_wave) * 1000.0

    alterados_en_armado = sum(
        1
        for p in warehouse.obtener_todos_los_productos()
        if p.cantidad_disponible != stock_antes_waves[p.id_producto]
    )

    print("=" * 95)
    print(
        " PASO 1: ARMADO DE WAVES DIRECTAMENTE SOBRE EL WAREHOUSE DE LAUREANO (SIN CATALOG_MANAGER)"
    )
    print("=" * 95)
    print(f"  * Escenario cargado           : {ruta_cargada} ({t_carga_ms:.2f} ms)")
    print(
        f"  * Nodos de Pasillo (Laureano) : {len(warehouse.grafo_pasillos.nodos)} celdas | "
        f"Zonas Despacho: {list(warehouse.zonas_despacho.keys())}"
    )
    print(
        f"  * Catálogo O(1) en Warehouse  : {len(warehouse.catalogo_productos)} productos | "
        f"{len(warehouse.pedidos)} pedidos"
    )
    print(
        f"  * Matriz APSP Dígrafo         : {len(matriz_distancias)} pares en {t_pre_ms:.2f} ms"
    )
    print(
        f"  * Waves armadas (PENDIENTE)   : {len(waves_armadas)} olas en {t_wave_ms:.3f} ms"
    )
    print(
        f"  * Stock modificado al armar   : {alterados_en_armado} productos (Invariancia 100% cumplida)"
    )

    # -------------------------------------------------------------------------
    # PASO 2 Y 3: VER WAVES DISPONIBLES Y SELECCIONAR CUÁLES EJECUTAR
    # -------------------------------------------------------------------------
    waves_disponibles = mostrar_waves_disponibles_y_pickers(gestor_waves, warehouse)
    ids_seleccionados = solicitar_seleccion_waves_usuario(
        waves_disponibles, waves_preseleccionadas
    )
    print(
        f"\n  -> Waves seleccionadas para ejecutar al mismo tiempo: {ids_seleccionados}"
    )

    # -------------------------------------------------------------------------
    # PASO 4: ASIGNAR A PICKERS MÁS CERCANOS (SIN MEZCLAR WAVES POR PICKER)
    # -------------------------------------------------------------------------
    resultado = gestor_waves.asignar_y_ejecutar_waves_seleccionadas(
        ids_waves_seleccionadas=ids_seleccionados,
        warehouse=warehouse,
        estrategia_ruteo=EstrategiaRuteo.CERCANIA_DIJKSTRA_MULTIDESTINO,
    )

    print("\n" + "=" * 95)
    print(" PASO 4: ASIGNACIÓN A LOS PICKERS MÁS CERCANOS (1 WAVE POR PICKER ACTIVO)")
    print("=" * 95)
    mapa_pickers = {p.id_picker: p for p in warehouse.pickers}

    for asig in resultado["asignaciones"]:
        wid = asig["id_wave"]
        w_obj = gestor_waves.waves_por_id[wid]
        print(
            f"\n  [EN_EJECUCION] {wid} -> Zona: {w_obj.id_zona_despacho} | "
            f"Peso Total: {w_obj.peso_total_kg:.2f} kg | Pickers asignados: {asig['ids_pickers']}"
        )
        for pid in asig["ids_pickers"]:
            pk = mapa_pickers[pid]
            dist_ini = asig["distancias_picker_a_wave"][pid]
            ruta_pk = asig["rutas_por_picker"][pid]
            print(
                f"    -> Picker {pid} (estaba a {dist_ini:.0f} pasos) realiza {wid} | "
                f"Pedidos: {asig['pedidos_por_picker'][pid]} | "
                f"Carga: {asig['peso_por_picker'][pid]:.2f}/{pk.capacidad_carga_kg:.1f} kg | "
                f"Longitud ruta inicial: {max(0, len(ruta_pk) - 1)} celdas"
            )

    if resultado["waves_sin_picker_disponible"]:
        print(
            f"\n  [!] Waves seleccionadas en espera por falta de Pickers libres "
            f"(no se mezclan Waves en un mismo viaje): {resultado['waves_sin_picker_disponible']}"
        )

    # -------------------------------------------------------------------------
    # PASO 5: SIMULACIÓN PASO A PASO CON EL GESTOR DE COLISIONES DE LEONEL
    # -------------------------------------------------------------------------
    print("\n" + "=" * 95)
    print(
        " PASO 5: SIMULACIÓN CONCURRENTE PASO A PASO (TURN & COLLISION MANAGER - LEONEL)"
    )
    print("=" * 95)

    gestor_colisiones = TurnAndCollisionManager(max_turnos_bloqueo_recalculo=2)
    paso_tiempo = 0
    max_pasos_seguridad = 500

    while paso_tiempo < max_pasos_seguridad:
        en_movimiento = gestor_colisiones.avanzar_un_turno_simulacion(
            pickers=warehouse.pickers,
            paso_actual=paso_tiempo,
            grafo=warehouse.grafo_pasillos,
            gestor_waves=gestor_waves,
            catalogo=warehouse,
        )
        if en_movimiento == 0:
            break
        paso_tiempo += 1

    print(f"  * Turnos totales simulados          : {paso_tiempo} pasos de tiempo")
    print(
        f"  * Pausas/Esperas por prioridad      : {gestor_colisiones.total_esperas_aplicadas}"
    )
    print(
        f"  * Desvíos recalculados con Dijkstra : {gestor_colisiones.total_desvios_recalculados}"
    )
    if gestor_colisiones.eventos_colision:
        print(
            "  * Primeros eventos de evasión registrados por TurnAndCollisionManager:"
        )
        for ev in gestor_colisiones.eventos_colision[:5]:
            print(f"      - {ev}")

    waves_finalizadas = [
        w.id_wave for w in gestor_waves.waves_creadas if w.estado.value == "FINALIZADA"
    ]
    waves_pendientes = [w.id_wave for w in gestor_waves.obtener_waves_disponibles()]
    print(f"  * Waves FINALIZADAS y descargadas   : {waves_finalizadas}")
    print(f"  * Waves aún PENDIENTES para elegir  : {waves_pendientes}")

    ruta_salida = FileParser.guardar_estado_warehouse_json(
        warehouse, ARCHIVO_SALIDA_JSON
    )
    print(f"  * Estado guardado en JSON           : {ruta_salida}")
    print("=" * 95)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Orquestador unificado sin CatalogManager: Laureano (Warehouse/Grafo) + Exequiel (WaveManager) + Leonel (Pathfinding/Colisiones)"
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=ESCENARIO_A_CARGAR,
        help="Escenario JSON a cargar (escenario_basico.json o escenario_grande.json)",
    )
    parser.add_argument(
        "-w",
        "--waves",
        type=str,
        default=None,
        help="IDs de Waves a ejecutar en simultáneo separados por coma (ej: WAVE_01,WAVE_02)",
    )
    args = parser.parse_args()

    if args.waves:
        SELECCIONAR_WAVES_INTERACTIVAMENTE = False
        WAVES_A_EJECUTAR_SIMULTANEAMENTE = [
            w.strip() for w in args.waves.split(",") if w.strip()
        ]

    ejecutar_orquestador(
        archivo_entrada=args.input,
        waves_preseleccionadas=WAVES_A_EJECUTAR_SIMULTANEAMENTE,
    )
