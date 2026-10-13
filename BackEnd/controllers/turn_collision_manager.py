from typing import Dict, List, Tuple
from BackEnd.models.entities import Picker
from BackEnd.data_structures.grafo_warehouse import GrafoWarehouse


class TurnAndCollisionManager:
    def __init__(self):
        self.reservas_celdas: Dict[Tuple[int, int, int], str] = {}

    def detectar_cruce_o_colision(self, p1: Picker, p2: Picker) -> bool:
        if not p1.ruta_asignada or not p2.ruta_asignada:
            return False

        sig_p1 = p1.ruta_asignada[0]
        sig_p2 = p2.ruta_asignada[0]

        # Colisión en la misma celda destino
        if sig_p1 == sig_p2:
            return True

        # Cruce frontal de aristas (intercambio de posiciones)
        if sig_p1 == p2.posicion_actual and sig_p2 == p1.posicion_actual:
            return True

        return False

    def resolver_conflicto(
        self, picker: Picker, grafo: GrafoWarehouse, paso_actual: int = 0
    ) -> None:
        if picker.ruta_asignada:
            celda_conflicto = picker.ruta_asignada[0]
            grafo.bloquear_celda_temporal(
                celda_conflicto, paso_actual + 1, picker.id_picker
            )
            # Espera un turno en su posición actual
            picker.ruta_asignada.insert(0, picker.posicion_actual)

    def validar_movimiento_simultaneo(
        self, pickers: List[Picker], paso_actual: int, grafo: GrafoWarehouse
    ) -> None:
        for i in range(len(pickers)):
            for j in range(i + 1, len(pickers)):
                if self.detectar_cruce_o_colision(pickers[i], pickers[j]):
                    self.resolver_conflicto(pickers[j], grafo, paso_actual)

        for p in pickers:
            if p.ruta_asignada:
                nx, ny = p.ruta_asignada[0]
                self.reservas_celdas[(nx, ny, paso_actual + 1)] = p.id_picker
