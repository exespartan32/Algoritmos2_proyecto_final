from typing import Dict, List, Tuple
from BackEnd.models.entities import Picker
from BackEnd.data_structures.grafo_warehouse import GrafoWarehouse
from BackEnd.controllers.pathfinding import Pathfinding


class TurnAndCollisionManager:
    def __init__(self):
        self.reservas_celdas: Dict[Tuple[int, int, int], str] = {}
        self.pathfinding = Pathfinding()

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
        self, picker_prioritario: Picker, picker_cedente: Picker, grafo: GrafoWarehouse, paso_actual: int = 0
    ) -> None:
        if not picker_cedente.ruta_asignada or not picker_prioritario.ruta_asignada:
            return

        sig_prio = picker_prioritario.ruta_asignada[0]
        sig_ced = picker_cedente.ruta_asignada[0]
        es_cruce_frontal = (
            sig_prio == picker_cedente.posicion_actual
            and sig_ced == picker_prioritario.posicion_actual
        )

        # Bloqueamos la celda a la que va el prioritario y su celda actual en el próximo paso
        grafo.bloquear_celda_temporal(sig_prio, paso_actual + 1, picker_prioritario.id_picker)
        grafo.bloquear_celda_temporal(picker_prioritario.posicion_actual, paso_actual + 1, picker_prioritario.id_picker)

        if es_cruce_frontal:
            # En un cruce frontal, el cedente no puede quedarse quieto en sig_prio; debe desviarse
            picker_cedente.ruta_asignada = self.pathfinding.recalcular_evitando_obstaculo(
                grafo, picker_cedente, paso_actual
            )
            # Si aun así no pudo moverse de esa celda, el prioritario espera 1 turno
            if picker_cedente.ruta_asignada and picker_cedente.ruta_asignada[0] == picker_cedente.posicion_actual:
                picker_prioritario.ruta_asignada.insert(0, picker_prioritario.posicion_actual)
        else:
            # Colisión normal hacia la misma celda: intenta rodear; si no puede, espera 1 turno
            nueva_ruta = self.pathfinding.recalcular_evitando_obstaculo(
                grafo, picker_cedente, paso_actual
            )
            picker_cedente.ruta_asignada = nueva_ruta

    def validar_movimiento_simultaneo(
        self, pickers: List[Picker], paso_actual: int, grafo: GrafoWarehouse
    ) -> None:
        for i in range(len(pickers)):
            for j in range(i + 1, len(pickers)):
                if self.detectar_cruce_o_colision(pickers[i], pickers[j]):
                    self.resolver_conflicto(pickers[i], pickers[j], grafo, paso_actual)

        for p in pickers:
            if p.ruta_asignada:
                nx, ny = p.ruta_asignada[0]
                self.reservas_celdas[(nx, ny, paso_actual + 1)] = p.id_picker