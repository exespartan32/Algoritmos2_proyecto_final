import time
import argparse
from dataclasses import dataclass
from typing import Optional, List

from BackEnd.models.catalog_manager import CatalogManager
from BackEnd.controllers.wave_manager import WaveManager
from BackEnd.enums.enums import EstadoPedido, EstadoWave
from BackEnd.utils.scenario_generator import ScenarioGenerator
from BackEnd.controllers.bfs import BuscadorBFS


@dataclass
class ConfiguracionSimulacion:
    directorio_datos: Optional[str] = None
    archivo_entrada: str = "escenario_basico.json"
    archivo_salida: str = "estado_guardado.json"
    metodo_mst: str = "KRUSKAL"
    prefijo_id_wave: str = "WAVE"
    prioridad_minima_pedidos: int = 1
    wave_max_pedidos: Optional[int] = None
    wave_max_productos: Optional[int] = None
    capacidad_carga_picker_kg: Optional[float] = None
    peso_max_zona_despacho_kg: Optional[float] = None
    ids_pickers_activos: Optional[List[str]] = None
    ids_zonas_activas: Optional[List[str]] = None
    tamano_tabla_hash: int = 1009
    primo_p_hash: int = 999983
    semilla_hash: Optional[int] = 42
    descontar_stock_al_crear_wave: bool = False
    modo_ejecucion_waves: str = "SOLO_PRIMERA"
    cantidad_waves_a_ejecutar: Optional[int] = None
    mostrar_detalle_productos_stock: bool = True


PARAMETROS_EJECUCION = ConfiguracionSimulacion(
    archivo_entrada="escenario_basico.json",
    archivo_salida="estado_guardado.json",
    metodo_mst="KRUSKAL",
    prefijo_id_wave="WAVE",
    prioridad_minima_pedidos=1,
    modo_ejecucion_waves="SOLO_PRIMERA",
    mostrar_detalle_productos_stock=True,
)


def ejecutar_simulacion(config: ConfiguracionSimulacion) -> None:
    t_inicio_total = time.perf_counter()

    # Opcional: Generar un escenario automático previo si se desea probar la Sección 16
    print("=== 0. GENERANDO ESCENARIO AUTOMÁTICO DE PRUEBA (SECCIÓN 16) ===")
    wh_auto, valido = ScenarioGenerator.generar_y_validar_warehouse(
        ruta_guardado_json="BackEnd/data/escenario_generado.json",
        cantidad_estantes=5,
        cantidad_pasillos=8,
        cantidad_productos=20,
        modo_localizacion="ALEATORIO",
        cantidad_pedidos=8,
        max_productos_por_pedido=3,
        wave_max_pedidos=3
    )
    print(f"¿Escenario automático válido y conexo?: {valido} (Dimensiones: {wh_auto.ancho_x}x{wh_auto.largo_y})")

    # Inicializar CatalogManager
    catalogo = CatalogManager(
        tamano_tabla=config.tamano_tabla_hash,
        primo_p=config.primo_p_hash,
        semilla_hash=config.semilla_hash,
        directorio_datos=config.directorio_datos,
    )
    ruta_entrada = catalogo.cargar_escenario_json(config.archivo_entrada)

    print("=" * 75)
    print("1. CONFIGURACIÓN ACTIVA Y CARGA EN TABLAS HASH O(1)")
    print("=" * 75)
    print(f"  * Archivo de Entrada          : {ruta_entrada}")
    print(f"  * Archivo de Salida           : {config.archivo_salida}")
    print(f"  * Método Gestor de Waves (MST): {config.metodo_mst.upper()}")

    # Ejecutar Gestor de Waves
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
    )

    print("\n" + "=" * 75)
    print(f"2. RESULTADO DEL ARMADO DE WAVES ({len(waves)} olas)")
    print("=" * 75)
    for w in waves:
        pedidos_info = [f"{p.id_pedido}(P:{p.prioridad})" for p in w.pedidos]
        print(f"  -> {w.id_wave} | Picker: {w.id_id_picker_asignado if hasattr(w, 'id_id_picker_asignado') else w.id_picker_asignado} | Pedidos: {pedidos_info}")

    # Persistencia final
    ruta_salida = catalogo.guardar_estado_simulacion_json(nombre_archivo_salida=config.archivo_salida)
    t_total_ms = (time.perf_counter() - t_inicio_total) * 1000.0

    print("\n" + "=" * 75)
    print("4. PERSISTENCIA Y DECODIFICACIÓN DE TABLA HASH A JSON")
    print("=" * 75)
    print(f"  * Estado guardado en : {ruta_salida}")
    print(f"  * Tiempo total       : {t_total_ms:.3f} ms")
    print("=" * 75)


if __name__ == "__main__":
    ejecutar_simulacion(PARAMETROS_EJECUCION)