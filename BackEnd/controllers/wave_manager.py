from typing import Any, Dict, List, Optional, Set, Tuple

from BackEnd.controllers.wave_assigner import WaveAssigner
from BackEnd.controllers.wave_builder import (
    ESTRATEGIAS_ARMADO,
    OPCIONES_ESTRATEGIA_ARMADO,
    WaveBuilder,
)
from BackEnd.enums.enums import EstadoWave, EstrategiaRuteo
from BackEnd.models.entities import Pedido, Picker, Wave, ZonaDespacho
from BackEnd.models.warehouse import Warehouse

CoordXY = Tuple[int, int]


class WaveManager:
    """Fachada que coordina el armado de waves (WaveBuilder) y su asignación (WaveAssigner)."""

    def __init__(
        self,
        wave_max_pedidos: int,
        wave_max_productos: int,
        prefijo_id_wave: str = "WAVE",
        incluir_altura_z_unica: bool = True,
        max_pickers_por_wave: int = 2,
        proveedor_distancias: Optional[Any] = None,
        estrategia_armado: str = "CERCANIA",
    ) -> None:
        self.builder = WaveBuilder(
            wave_max_pedidos=wave_max_pedidos,
            wave_max_productos=wave_max_productos,
            prefijo_id_wave=prefijo_id_wave,
            incluir_altura_z_unica=incluir_altura_z_unica,
            max_pickers_por_wave=max_pickers_por_wave,
            proveedor_distancias=proveedor_distancias,
            estrategia_armado=estrategia_armado,
        )
        self.assigner = WaveAssigner(max_pickers_por_wave=max_pickers_por_wave)

        self.estrategia_armado = self.builder.estrategia_armado
        self.cola_prioridad = self.builder.cola_prioridad
        self.wave_max_pedidos = self.builder.wave_max_pedidos
        self.wave_max_productos = self.builder.wave_max_productos
        self.prefijo_id_wave = self.builder.prefijo_id_wave
        self.incluir_altura_z_unica = self.builder.incluir_altura_z_unica
        self.max_pickers_por_wave = self.builder.max_pickers_por_wave
        self.proveedor_distancias = self.builder.proveedor_distancias

        self.errores_validacion = self.builder.errores_validacion
        self.pedidos_descartados = self.builder.pedidos_descartados
        self.traza_armado = self.builder.traza_armado

        self.waves_creadas: List[Wave] = []
        self.waves_por_id: Dict[str, Wave] = {}
        self._pickers_pendientes_descarga = self.assigner.pickers_pendientes_descarga

    def _obtener_distancia_dirigida(
        self,
        origen: CoordXY,
        destino: CoordXY,
        proveedor: Optional[Any] = None,
    ) -> float:
        return self.builder.obtener_distancia_dirigida(origen, destino, proveedor)

    def _distancia_enlace_digrafo(
        self,
        p_xy: CoordXY,
        u_xy: CoordXY,
        proveedor: Optional[Any] = None,
    ) -> float:
        return self.builder.distancia_enlace_digrafo(p_xy, u_xy, proveedor)

    @staticmethod
    def _pasillos_de(pedido: Pedido, warehouse: Warehouse) -> Set[str]:
        return WaveBuilder.pasillos_de(pedido, warehouse)

    def obtener_zonas_despacho_salida(self, warehouse: Warehouse) -> List[ZonaDespacho]:
        return self.builder.obtener_zonas_despacho_salida(warehouse)

    def seleccionar_zona_despacho_para_wave(
        self,
        warehouse: Warehouse,
        pedido_semilla: Pedido,
    ) -> Optional[ZonaDespacho]:
        return self.builder.seleccionar_zona_despacho_para_wave(
            warehouse, pedido_semilla
        )

    def validar_pedidos_entrada(
        self,
        pedidos: List[Pedido],
        warehouse: Warehouse,
    ) -> List[Pedido]:
        return self.builder.validar_pedidos_entrada(pedidos, warehouse)

    def calcular_costo_marginal_promedio(
        self,
        wave: Wave,
        pedido_candidato: Pedido,
        warehouse: Warehouse,
        proveedor_distancias: Optional[Any] = None,
    ) -> float:
        return self.builder.calcular_costo_marginal_promedio(
            wave, pedido_candidato, warehouse, proveedor_distancias
        )

    def generar_waves(
        self,
        warehouse: Warehouse,
        proveedor_distancias: Optional[Any] = None,
    ) -> List[Wave]:
        self.waves_creadas, self.waves_por_id = self.builder.generar_waves(
            warehouse=warehouse,
            proveedor_distancias=proveedor_distancias,
        )
        return self.waves_creadas

    def obtener_waves_disponibles(self) -> List[Wave]:
        return [w for w in self.waves_creadas if w.estado == EstadoWave.PENDIENTE]

    def obtener_waves_en_ejecucion(self) -> List[Wave]:
        return [w for w in self.waves_creadas if w.estado == EstadoWave.EN_EJECUCION]

    @staticmethod
    def obtener_pickers_libres(pickers: List[Picker]) -> List[Picker]:
        return WaveAssigner.obtener_pickers_libres(pickers)

    def calcular_distancia_picker_a_wave(
        self,
        picker: Picker,
        wave: Wave,
        warehouse: Warehouse,
    ) -> float:
        return self.assigner.calcular_distancia_picker_a_wave(picker, wave, warehouse)

    def asignar_y_ejecutar_waves_seleccionadas(
        self,
        ids_waves_seleccionadas: List[str],
        warehouse: Warehouse,
        estrategia_ruteo: EstrategiaRuteo = EstrategiaRuteo.CERCANIA_DIJKSTRA_MULTIDESTINO,
        pickers_por_wave: int = 1,
    ) -> Dict[str, Any]:
        return self.assigner.asignar_y_ejecutar(
            ids_waves_seleccionadas=ids_waves_seleccionadas,
            waves_por_id=self.waves_por_id,
            warehouse=warehouse,
            estrategia_ruteo=estrategia_ruteo,
            pickers_por_wave=pickers_por_wave,
        )

    def notificar_picker_descargo_en_despacho(
        self,
        id_wave: str,
        id_picker: str,
        pickers: List[Picker],
        warehouse: Optional[Warehouse] = None,
    ) -> None:
        self.assigner.notificar_picker_descargo_en_despacho(
            id_wave=id_wave,
            id_picker=id_picker,
            waves_por_id=self.waves_por_id,
            warehouse=warehouse,
        )


__all__ = ["WaveManager", "ESTRATEGIAS_ARMADO", "OPCIONES_ESTRATEGIA_ARMADO"]
