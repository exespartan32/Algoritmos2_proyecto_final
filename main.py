import os
import time
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict

from BackEnd.models.catalog_manager import CatalogManager
from BackEnd.controllers.wave_manager import WaveManager
from BackEnd.controllers.path_finding import Pathfinding


# =============================================================================
# PANEL CENTRAL DE PARÁMETROS DE EJECUCIÓN
# =============================================================================
@dataclass
class ConfiguracionSimulacion:
    # 1. Selección del archivo JSON de entrada en BackEnd/data/:
    #    - Si 'preguntar_archivo_en_consola = True', te deja elegir entre
    #      escenario_basico.json y escenario_grande.json al ejecutar.
    #    - Si es False, usa directamente 'archivo_entrada'.
    preguntar_archivo_en_consola: bool = True
    archivo_entrada: str = (
        "escenario_basico.json"  # "escenario_basico.json" o "escenario_grande.json"
    )
    archivo_salida: str = "estado_guardado.json"

    # 2. Parámetros de Capacidad de las Waves (None = usa los del bloque "configuracion" del JSON)
    wave_max_pedidos: Optional[int] = None
    wave_max_productos: Optional[int] = None
    prefijo_id_wave: str = "WAVE"
    incluir_altura_z_unica: bool = True

    # 3. Orientación del eje Y para el Dígrafo (en ambos JSON del profe: Norte es y + 1 -> True)
    norte_aumenta_y: bool = True

    # 4. Parámetros de la Tabla Hash Universal en CatalogManager
    tamano_tabla_hash: int = 1009
    primo_p_hash: int = 999983
    semilla_hash: Optional[int] = 42
    directorio_datos: Optional[str] = None

    # 5. Visualización de trazas y pruebas de ruteo con el módulo de Leonel
    mostrar_traza_cercania: bool = True
    mostrar_comparativa_rutas_leonel: bool = True
    verificar_invariancia_stock: bool = True


PARAMETROS_EJECUCION = ConfiguracionSimulacion(
    preguntar_archivo_en_consola=True,
    archivo_entrada="escenario_basico.json",
    archivo_salida="estado_guardado.json",
    wave_max_pedidos=None,
    wave_max_productos=None,
    prefijo_id_wave="WAVE",
    incluir_altura_z_unica=True,
    norte_aumenta_y=True,
    tamano_tabla_hash=1009,
    primo_p_hash=999983,
    semilla_hash=42,
    mostrar_traza_cercania=True,
    mostrar_comparativa_rutas_leonel=True,
    verificar_invariancia_stock=True,
)


def elegir_escenario_interactivo(
    catalogo: CatalogManager, archivo_por_defecto: str
) -> str:
    escenarios_base = ["escenario_basico.json", "escenario_grande.json"]
    disponibles: List[str] = []

    for nombre in escenarios_base:
        ruta = catalogo.resolver_ruta_archivo(nombre)
        if os.path.isfile(ruta):
            disponibles.append(nombre)

    if os.path.isdir(catalogo.ruta_data):
        for arch in sorted(os.listdir(catalogo.ruta_data)):
            if arch.lower().endswith(".json") and arch not in disponibles:
                disponibles.append(arch)

    if not disponibles:
        return archivo_por_defecto

    print("=" * 85)
    print(" SELECCIÓN DE ESCENARIO BASE DEL WAREHOUSE (BackEnd/data/)")
    print("=" * 85)
    for idx, nombre in enumerate(disponibles, start=1):
        marca = " (por defecto)" if nombre == archivo_por_defecto else ""
        print(f"  [{idx}] {nombre}{marca}")
    print("-" * 85)

    try:
        respuesta = input(
            f"Elija el número de escenario [1-{len(disponibles)}] "
            f"o presione Enter para '{archivo_por_defecto}': "
        ).strip()
    except EOFError:
        return archivo_por_defecto

    if not respuesta:
        return archivo_por_defecto
    if respuesta.isdigit() and 1 <= int(respuesta) <= len(disponibles):
        return disponibles[int(respuesta) - 1]
    return respuesta


def ejecutar_prueba_armado_waves(config: ConfiguracionSimulacion) -> None:
    Pathfinding.NORTE_AUMENTA_Y = config.norte_aumenta_y

    # 1. Inicializar CatalogManager y cargar el JSON elegido
    catalogo = CatalogManager(
        tamano_tabla=config.tamano_tabla_hash,
        primo_p=config.primo_p_hash,
        semilla_hash=config.semilla_hash,
        directorio_datos=config.directorio_datos,
    )

    archivo_a_cargar = (
        elegir_escenario_interactivo(catalogo, config.archivo_entrada)
        if config.preguntar_archivo_en_consola
        else config.archivo_entrada
    )

    t0 = time.perf_counter()
    ruta_cargada = catalogo.cargar_escenario_json(
        archivo_a_cargar, norte_aumenta_y=config.norte_aumenta_y
    )
    t_carga_ms = (time.perf_counter() - t0) * 1000.0

    # Tomar snapshot del stock inicial ANTES de armar las Waves
    stock_inicial: Dict[str, int] = {
        p.id_producto: p.cantidad_disponible
        for p in catalogo.obtener_todos_los_productos()
    }

    max_pedidos = (
        config.wave_max_pedidos
        if config.wave_max_pedidos is not None
        else catalogo.wave_max_pedidos
    )
    max_productos = (
        config.wave_max_productos
        if config.wave_max_productos is not None
        else catalogo.wave_max_productos
    )

    print("\n" + "=" * 85)
    print(" 1. RESUMEN DEL ESCENARIO CARGADO EN TABLAS HASH O(1) Y DÍGRAFO")
    print("=" * 85)
    print(f"  * Archivo de Entrada          : {ruta_cargada} ({t_carga_ms:.2f} ms)")
    print(
        f"  * Dimensiones del Warehouse   : {catalogo.digrafo.ancho_x} x {catalogo.digrafo.largo_y}"
    )
    print(
        f"  * Nodos de Pasillo (Dígrafo)  : {len(catalogo.digrafo.lista_adyacencia)} celdas transitables"
    )
    print(
        f"  * Celdas de Rack (Obstáculos) : {len(catalogo.digrafo.racks_ocupados)} celdas"
    )
    print(
        f"  * Zonas de Despacho           : {list(catalogo.digrafo.zonas_despacho.keys())}"
    )
    print(
        f"  * Pickers Disponibles         : "
        f"{[(p.id_picker, p.posicion_actual, f'{p.capacidad_carga_kg}kg') for p in catalogo.pickers]}"
    )
    print(
        f"  * Productos en Tabla Hash     : {catalogo.productos_hash.cantidad_elementos}"
    )
    print(
        f"  * Pedidos en Tabla Hash       : {catalogo.pedidos_hash.cantidad_elementos}"
    )
    print(
        f"  * Límites por Wave aplicados  : máx {max_pedidos} pedidos | máx {max_productos} unidades"
    )

    # 2. Precalcular matriz de distancias dirigidas usando el Pathfinding de Leonel
    t_pre = time.perf_counter()
    coords_productos = {
        p.coordenadas_xy for p in catalogo.obtener_todos_los_productos()
    }
    matriz_distancias = Pathfinding.construir_matriz_distancias_productos(
        coordenadas_productos_xy=coords_productos,
        grafo=catalogo.digrafo,
    )
    t_pre_ms = (time.perf_counter() - t_pre) * 1000.0
    print(
        f"  * Matriz Dígrafo (Leonel)     : {len(matriz_distancias)} pares precalculados en {t_pre_ms:.2f} ms"
    )

    # 3. Ejecutar WaveManager (SIN modificar el stock de los productos)
    t_wave = time.perf_counter()
    gestor_waves = WaveManager(
        wave_max_pedidos=max_pedidos,
        wave_max_productos=max_productos,
        prefijo_id_wave=config.prefijo_id_wave,
        incluir_altura_z_unica=config.incluir_altura_z_unica,
        proveedor_distancias=matriz_distancias,
    )

    waves = gestor_waves.generar_waves(
        catalogo=catalogo,
        proveedor_distancias=matriz_distancias,
    )
    t_wave_ms = (time.perf_counter() - t_wave) * 1000.0

    print("\n" + "=" * 85)
    print(
        f" 2. DESARROLLO PASO A PASO DE LA ESTRATEGIA DE WAVES "
        f"({len(waves)} olas en {t_wave_ms:.3f} ms)"
    )
    print("=" * 85)

    origen_picker = catalogo.pickers[0].posicion_actual if catalogo.pickers else (1, 3)

    for w in waves:
        print(
            f"\n-> {w.id_wave} | Estado: {w.estado.value} | "
            f"Pedidos: {len(w.pedidos)}/{w.wave_max_pedidos} | "
            f"Unidades: {w.unidades_totales}/{w.wave_max_productos} | "
            f"Peso: {w.peso_total_kg:.2f} kg | "
            f"Costo Marginal Total: {w.costo_mst_total:.4f}"
        )

        if config.mostrar_traza_cercania:
            pasos_wave = gestor_waves.traza_armado.get(w.id_wave, [])
            for idx_paso, info in enumerate(pasos_wave, start=1):
                ped_obj = catalogo.buscar_pedido_O1(info["id_pedido"])
                ubics = (
                    sorted(ped_obj.obtener_ubicaciones_xyz(catalogo)) if ped_obj else []
                )
                accesos_pasillo = [
                    Pathfinding.obtener_celda_acceso_pasillo((x, y), catalogo.digrafo)
                    for (x, y, _) in ubics
                ]
                if info["rol"] == "RAIZ_MAX_HEAP":
                    print(
                        f"   Paso {idx_paso} [Semilla Max-Heap] : {info['id_pedido']} "
                        f"(Prioridad={info['prioridad']}, Unidades={info['unidades']}) "
                        f"-> Racks(x,y,z)={ubics} | Acceso Pasillo={accesos_pasillo}"
                    )
                else:
                    print(
                        f"   Paso {idx_paso} [Average Linkage]  : {info['id_pedido']} "
                        f"(Prioridad={info['prioridad']}, Unidades={info['unidades']}, "
                        f"Score Marginal={info['score_marginal']:.4f}, "
                        f"Candidatos factibles evaluados={info['candidatos_evaluados']}) "
                        f"-> Racks(x,y,z)={ubics} | Acceso Pasillo={accesos_pasillo}"
                    )

        if config.mostrar_comparativa_rutas_leonel:
            # En Estrategia A respetamos el orden de los pedidos de la Wave
            destinos_orden_pedidos = []
            for ped in w.pedidos:
                for it in ped.items:
                    prod = catalogo.buscar_producto_O1(it.producto_id)
                    if prod is not None:
                        destinos_orden_pedidos.append(prod.coordenadas_xy)

            res_a = Pathfinding.calcular_estrategia_orden_pedidos(
                catalogo.digrafo, origen_picker, destinos_orden_pedidos
            )
            res_b = Pathfinding.calcular_estrategia_cercania_multidestino(
                catalogo.digrafo, origen_picker, list(w.ubicaciones_xy)
            )
            print(
                f"   [Ruteo de Leonel desde Picker en {origen_picker}]: "
                f"Estrategia A (Orden Pedidos) = {res_a.distancia_total} pasos ({res_a.tiempo_ejecucion_ms:.3f} ms) | "
                f"Estrategia B (Greedy Multidestino) = {res_b.distancia_total} pasos ({res_b.tiempo_ejecucion_ms:.3f} ms)"
            )

    if gestor_waves.errores_validacion:
        print("\n  [Avisos / Pedidos Descartados en Validación]:")
        for err in gestor_waves.errores_validacion:
            print(f"    ! {err}")

    # 4. Verificar que el stock NO fue modificado durante el armado de las Waves
    if config.verificar_invariancia_stock:
        print("\n" + "=" * 85)
        print(
            " 3. VERIFICACIÓN DE INVARIANCIA DE STOCK (EL ARMADO DE WAVES NO DESCUENTA STOCK)"
        )
        print("=" * 85)
        cambios_detectados = 0
        for p in catalogo.obtener_todos_los_productos():
            if p.cantidad_disponible != stock_inicial[p.id_producto]:
                cambios_detectados += 1
                print(
                    f"  [!] Diferencia en {p.id_producto}: "
                    f"antes={stock_inicial[p.id_producto]}, ahora={p.cantidad_disponible}"
                )

        if cambios_detectados == 0:
            print(
                f"  [OK] Stock 100% intacto en los {len(stock_inicial)} productos de la Tabla Hash."
            )
            print(
                "       Ninguna unidad fue descontada durante el armado de las Waves (solo se actualizaron"
            )
            print("       los estados de los pedidos de PENDIENTE -> EN_WAVE).")

    # 5. Guardar el estado actual (pedidos en EN_WAVE y stock intacto) en estado_guardado.json
    ruta_salida = catalogo.guardar_estado_simulacion_json(config.archivo_salida)
    print(f"\n  * Estado exportado en: {ruta_salida}")


def parsear_cli() -> None:
    parser = argparse.ArgumentParser(
        description="Prueba de la estrategia de armado de Waves con escenario_basico.json y escenario_grande.json"
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=None,
        help="Archivo JSON en BackEnd/data/ (ej. escenario_basico.json o escenario_grande.json)",
    )
    parser.add_argument(
        "--max-pedidos",
        type=int,
        default=None,
        help="Sobrescribir wave_max_pedidos del JSON",
    )
    parser.add_argument(
        "--max-productos",
        type=int,
        default=None,
        help="Sobrescribir wave_max_productos del JSON",
    )
    args = parser.parse_args()

    if args.input is not None:
        PARAMETROS_EJECUCION.archivo_entrada = args.input
        PARAMETROS_EJECUCION.preguntar_archivo_en_consola = False
    if args.max_pedidos is not None:
        PARAMETROS_EJECUCION.wave_max_pedidos = args.max_pedidos
    if args.max_productos is not None:
        PARAMETROS_EJECUCION.wave_max_productos = args.max_productos


if __name__ == "__main__":
    parsear_cli()
    ejecutar_prueba_armado_waves(PARAMETROS_EJECUCION)
