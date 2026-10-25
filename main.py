import time
import argparse
from typing import Optional, List, Dict

from BackEnd.models.catalog_manager import CatalogManager
from BackEnd.models.entities import Wave
from BackEnd.controllers.wave_manager import WaveManager
from BackEnd.controllers.path_finding import Pathfinding

# =============================================================================
# PARÁMETROS DE EJECUCIÓN (DEFINIDOS UNA ÚNICA VEZ AQUÍ)
# =============================================================================
# 1. Escenario que quieres cargar ("escenario_basico.json" o "escenario_grande.json"):
ESCENARIO_A_CARGAR: str = "escenario_grande.json"
ARCHIVO_SALIDA_JSON: str = "estado_guardado.json"

# 2. Selección de Waves a ejecutar al mismo tiempo:
#    - Si SELECCIONAR_WAVES_INTERACTIVAMENTE = True, luego de ver las Waves disponibles
#      podrás elegir por teclado cuáles quieres ejecutar en simultáneo (ej: 1, 3).
#    - Si es False, ejecutará directamente la lista WAVES_A_EJECUTAR_SIMULTANEAMENTE.
SELECCIONAR_WAVES_INTERACTIVAMENTE: bool = True
WAVES_A_EJECUTAR_SIMULTANEAMENTE: List[str] = ["WAVE_01", "WAVE_02"]

# 3. Si quieres que los pickers libres que sobren se sumen a colaborar en las Waves elegidas:
REPARTIR_PICKERS_SOBRANTES_EN_LAS_WAVES_ELEGIDAS: bool = False
MAX_PICKERS_POR_WAVE: int = 2

# 4. Límites de capacidad por Wave (None = usa los del JSON cargado)
WAVE_MAX_PEDIDOS: Optional[int] = None
WAVE_MAX_PRODUCTOS: Optional[int] = None

# 5. Configuración de la Tabla Hash Universal
TAMANO_TABLA_HASH: int = 1009
PRIMO_P_HASH: int = 999983
SEMILLA_HASH: int = 42


def mostrar_waves_disponibles_y_pickers(
    gestor_waves: WaveManager, catalogo: CatalogManager
) -> List[Wave]:
    waves_disponibles = gestor_waves.obtener_waves_disponibles()
    pickers_libres = gestor_waves.obtener_pickers_libres(catalogo.pickers)

    print("\n" + "=" * 92)
    print(
        f" PASO 2: WAVES DISPONIBLES PARA SELECCIONAR ({len(waves_disponibles)} Waves en estado PENDIENTE)"
    )
    print("=" * 92)
    for idx, w in enumerate(waves_disponibles, start=1):
        ids_ped = [f"{p.id_pedido}(P:{p.prioridad})" for p in w.pedidos]
        print(
            f"  [{idx:2d}] {w.id_wave} | Estado: {w.estado.value:9s} | "
            f"Pedidos ({len(w.pedidos)}/{w.wave_max_pedidos}): {ids_ped} | "
            f"Unidades: {w.unidades_totales:2d}/{w.wave_max_productos} | "
            f"Peso: {w.peso_total_kg:6.2f} kg | Zona: {w.id_zona_despacho}"
        )

    print("-" * 92)
    print(
        f" PICKERS LIBRES ACTUALMENTE ({len(pickers_libres)}/{len(catalogo.pickers)}):"
    )
    for pk in pickers_libres:
        print(
            f"  * {pk.id_picker} -> Posición actual: {pk.posicion_actual} | "
            f"Capacidad máxima: {pk.capacidad_carga_kg:.1f} kg | Wave actual: {pk.id_wave_actual}"
        )
    print("=" * 92)
    return waves_disponibles


def solicitar_seleccion_waves_usuario(
    waves_disponibles: List[Wave], seleccion_por_defecto: List[str]
) -> List[str]:
    if not waves_disponibles:
        return []

    if not SELECCIONAR_WAVES_INTERACTIVAMENTE:
        return seleccion_por_defecto

    print("\n" + "=" * 92)
    print(" PASO 3: SELECCIÓN DE LAS WAVES QUE QUIERES EJECUTAR AL MISMO TIEMPO")
    print("=" * 92)
    print(
        "  Puedes ingresar los números de índice (ej: 1, 3) o los IDs (ej: WAVE_01, WAVE_03)."
    )
    try:
        entrada = input(
            f"  Ingrese las Waves a ejecutar en simultáneo "
            f"(Enter para usar por defecto {seleccion_por_defecto}): "
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
            # Permite escribir "WAVE_01" o "1"
            if not token.startswith("WAVE_"):
                Posible_num = token.replace("WAVE", "").strip("_")
                if Posible_num.isdigit():
                    token = f"WAVE_{int(Posible_num):02d}"
            ids_elegidos.append(token)

    return ids_elegidos if ids_elegidos else seleccion_por_defecto


def ejecutar_flujo_completo(
    archivo_entrada: str,
    waves_preseleccionadas: List[str],
    repartir_sobrantes: bool = False,
) -> None:
    # -------------------------------------------------------------------------
    # CARGA DEL ESCENARIO E INDEXACIÓN EN TABLAS HASH O(1)
    # -------------------------------------------------------------------------
    catalogo = CatalogManager(
        tamano_tabla=TAMANO_TABLA_HASH,
        primo_p=PRIMO_P_HASH,
        semilla_hash=SEMILLA_HASH,
    )

    t0 = time.perf_counter()
    ruta_cargada = catalogo.cargar_escenario_json(archivo_entrada)
    t_carga_ms = (time.perf_counter() - t0) * 1000.0

    stock_inicial: Dict[str, int] = {
        p.id_producto: p.cantidad_disponible
        for p in catalogo.obtener_todos_los_productos()
    }

    max_pedidos = (
        WAVE_MAX_PEDIDOS if WAVE_MAX_PEDIDOS is not None else catalogo.wave_max_pedidos
    )
    max_productos = (
        WAVE_MAX_PRODUCTOS
        if WAVE_MAX_PRODUCTOS is not None
        else catalogo.wave_max_productos
    )

    # Precalcular matriz de distancias dirigidas usando el Pathfinding de Leonel
    t_pre = time.perf_counter()
    coords_productos = {
        p.coordenadas_xy for p in catalogo.obtener_todos_los_productos()
    }
    matriz_distancias = Pathfinding.construir_matriz_distancias_productos(
        coordenadas_productos_xy=coords_productos,
        grafo=catalogo.digrafo,
    )
    t_pre_ms = (time.perf_counter() - t_pre) * 1000.0

    # -------------------------------------------------------------------------
    # PASO 1: ARMAR TODAS LAS WAVES (QUEDAN EN ESTADO PENDIENTE, SIN EJECUTAR)
    # -------------------------------------------------------------------------
    t_wave = time.perf_counter()
    gestor_waves = WaveManager(
        wave_max_pedidos=max_pedidos,
        wave_max_productos=max_productos,
        max_pickers_por_wave=MAX_PICKERS_POR_WAVE,
        proveedor_distancias=matriz_distancias,
    )

    waves_armadas = gestor_waves.generar_waves(
        catalogo=catalogo,
        proveedor_distancias=matriz_distancias,
    )
    t_wave_ms = (time.perf_counter() - t_wave) * 1000.0

    print("=" * 92)
    print(" PASO 1: ARMADO DE WAVES (MAX-HEAP + CERCANÍA EN DÍGRAFO)")
    print("=" * 92)
    print(f"  * Escenario cargado           : {ruta_cargada} ({t_carga_ms:.2f} ms)")
    print(
        f"  * Matriz Dígrafo (Leonel)     : {len(matriz_distancias)} pares en {t_pre_ms:.2f} ms"
    )
    print(
        f"  * Total de Waves armadas      : {len(waves_armadas)} Waves creadas en {t_wave_ms:.3f} ms"
    )
    print(
        "  * Nota: Todas las Waves fueron armadas en estado PENDIENTE y el stock permanece intacto."
    )

    # -------------------------------------------------------------------------
    # PASO 2: VER LAS WAVES DISPONIBLES Y LOS PICKERS LIBRES
    # -------------------------------------------------------------------------
    waves_disponibles = mostrar_waves_disponibles_y_pickers(gestor_waves, catalogo)

    # -------------------------------------------------------------------------
    # PASO 3: SELECCIONAR QUÉ WAVES EJECUTAR AL MISMO TIEMPO
    # -------------------------------------------------------------------------
    ids_seleccionados = solicitar_seleccion_waves_usuario(
        waves_disponibles, waves_preseleccionadas
    )
    print(
        f"\n  -> Waves seleccionadas para ejecutar en simultáneo: {ids_seleccionados}"
    )

    # -------------------------------------------------------------------------
    # PASO 4: ASIGNAR LAS WAVES SELECCIONADAS A LOS PICKERS MÁS CERCANOS
    # -------------------------------------------------------------------------
    resultado_ejecucion = gestor_waves.asignar_y_ejecutar_waves_seleccionadas(
        ids_waves_seleccionadas=ids_seleccionados,
        pickers=catalogo.pickers,
        catalogo=catalogo,
        grafo=catalogo.digrafo,
        repartir_pickers_sobrantes=repartir_sobrantes,
    )

    print("\n" + "=" * 92)
    print(" PASO 4: ASIGNACIÓN A LOS PICKERS MÁS CERCANOS Y EJECUCIÓN SIMULTÁNEA")
    print("=" * 92)

    mapa_pickers = {p.id_picker: p for p in catalogo.pickers}

    for asig in resultado_ejecucion["asignaciones"]:
        id_wave = asig["id_wave"]
        wave_obj = gestor_waves.waves_por_id[id_wave]
        ids_pickers = asig["ids_pickers"]
        distancias = asig["distancias_picker_a_wave"]

        print(
            f"\n  [EJECUTANDO] {id_wave} (Estado: {wave_obj.estado.value}) "
            f"| Asignada a Picker(s) más cercano(s): {ids_pickers} "
            f"| Peso: {wave_obj.peso_total_kg:.2f} kg | Zona: {wave_obj.id_zona_despacho}"
        )

        for pid in ids_pickers:
            pk = mapa_pickers[pid]
            dist_entrada = distancias[pid]
            pedidos_pk = asig["pedidos_por_picker"].get(pid, [])
            destinos_pk = asig["destinos_xy_por_picker"].get(pid, [])

            res_ruta = Pathfinding.calcular_estrategia_cercania_multidestino(
                catalogo.digrafo, pk.posicion_actual, destinos_pk
            )
            print(
                f"    -> Picker {pid} (estaba en {pk.posicion_actual}, a {dist_entrada:.0f} pasos de la Wave) "
                f"está realizando {id_wave}:"
            )
            print(f"       * Pedidos que prepara : {pedidos_pk}")
            print(
                f"       * Ubicaciones a visitar: {destinos_pk} "
                f"| Ruta Greedy de Leonel = {res_ruta.distancia_total} celdas"
            )

    if resultado_ejecucion["waves_sin_picker_disponible"]:
        print(
            f"\n  [!] Waves seleccionadas que quedaron en espera por falta de Pickers libres: "
            f"{resultado_ejecucion['waves_sin_picker_disponible']}"
        )

    # Resumen de cómo quedó el estado general para Pygame
    waves_en_curso = [w.id_wave for w in gestor_waves.obtener_waves_en_ejecucion()]
    waves_aun_pendientes = [w.id_wave for w in gestor_waves.obtener_waves_disponibles()]
    pickers_ocupados = [
        (p.id_picker, f"realizando {p.id_wave_actual}")
        for p in catalogo.pickers
        if p.id_wave_actual is not None
    ]
    pickers_aun_libres = [
        p.id_picker for p in gestor_waves.obtener_pickers_libres(catalogo.pickers)
    ]

    print("\n" + "-" * 92)
    print(" RESUMEN DE ESTADO PARA EL MOTOR GRÁFICO (PYGAME):")
    print(f"  * Waves EN_EJECUCION ahora ({len(waves_en_curso)}) : {waves_en_curso}")
    print(
        f"  * Pickers activos ahora    ({len(pickers_ocupados)}) : {pickers_ocupados}"
    )
    print(
        f"  * Pickers aún libres       ({len(pickers_aun_libres)}) : {pickers_aun_libres}"
    )
    print(
        f"  * Waves aún PENDIENTES     ({len(waves_aun_pendientes)}) : {waves_aun_pendientes}"
    )

    # Comprobar invariancia de stock
    alterados = sum(
        1
        for p in catalogo.obtener_todos_los_productos()
        if p.cantidad_disponible != stock_inicial[p.id_producto]
    )
    print(
        f"  * Verificación de Stock        : {alterados} productos modificados (el stock se descuenta recién al recoger)."
    )
    print("=" * 92)

    catalogo.guardar_estado_simulacion_json(ARCHIVO_SALIDA_JSON)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Flujo de 4 pasos: 1) Armar Waves, 2) Ver disponibles, 3) Seleccionar cuáles ejecutar, 4) Asignar a Pickers más cercanos"
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
        help="Waves a ejecutar simultáneamente separadas por coma (ej: WAVE_01,WAVE_03)",
    )
    args = parser.parse_args()

    if args.waves:
        SELECCIONAR_WAVES_INTERACTIVAMENTE = False
        WAVES_A_EJECUTAR_SIMULTANEAMENTE = [
            w.strip() for w in args.waves.split(",") if w.strip()
        ]

    ejecutar_flujo_completo(
        archivo_entrada=args.input,
        waves_preseleccionadas=WAVES_A_EJECUTAR_SIMULTANEAMENTE,
        repartir_sobrantes=REPARTIR_PICKERS_SOBRANTES_EN_LAS_WAVES_ELEGIDAS,
    )
