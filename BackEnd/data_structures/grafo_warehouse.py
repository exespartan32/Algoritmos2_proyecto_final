from typing import Dict, List, Tuple, TYPE_CHECKING
from BackEnd.enums.enums import TipoCelda, SentidoCirculacion

if TYPE_CHECKING:
    from BackEnd.models.warehouse_models import Warehouse


class GrafoWarehouse:
    def __init__(self):
        self.lista_adyacencia: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        self.aristas_bloqueadas: Dict[Tuple[Tuple[int, int], int], str] = {}

    def construir_desde_grilla(self, warehouse: "Warehouse") -> None:
        self.lista_adyacencia.clear()

        # En el sistema de coordenadas del JSON (PAS_H_INF en y=3, PAS_H_SUP en y=11):
        # Norte incrementa Y, Sur decrementa Y, Este incrementa X, Oeste decrementa X.
        desplazamientos = {
            SentidoCirculacion.N: [(0, 1), (1, 0), (-1, 0)],
            SentidoCirculacion.S: [(0, -1), (1, 0), (-1, 0)],
            SentidoCirculacion.E: [(1, 0), (0, 1), (0, -1)],
            SentidoCirculacion.O: [(-1, 0), (0, 1), (0, -1)],
            SentidoCirculacion.AMBOS: [(0, 1), (0, -1), (1, 0), (-1, 0)],
        }

        for coord, celda in warehouse.grilla_hash.items():
            if celda.tipo != TipoCelda.PASILLO:
                continue

            self.lista_adyacencia[coord] = []
            dirs_permitidas = desplazamientos.get(
                celda.sentido, desplazamientos[SentidoCirculacion.AMBOS]
            )

            for dx, dy in dirs_permitidas:
                vecino_coord = (coord[0] + dx, coord[1] + dy)
                celda_vecina = warehouse.grilla_hash.get(vecino_coord)

                if celda_vecina and celda_vecina.tipo == TipoCelda.PASILLO:
                    # Evitar entrar en contramano a un pasillo unidireccional
                    if dy == 1 and celda_vecina.sentido == SentidoCirculacion.S:
                        continue
                    if dy == -1 and celda_vecina.sentido == SentidoCirculacion.N:
                        continue
                    if dx == 1 and celda_vecina.sentido == SentidoCirculacion.O:
                        continue
                    if dx == -1 and celda_vecina.sentido == SentidoCirculacion.E:
                        continue

                    self.lista_adyacencia[coord].append(vecino_coord)

    def obtener_vecinos_validos(
        self, coord: Tuple[int, int], paso_tiempo: int = -1
    ) -> List[Tuple[int, int]]:
        vecinos = self.lista_adyacencia.get(coord, [])
        if paso_tiempo < 0:
            return list(vecinos)
        return [v for v in vecinos if (v, paso_tiempo) not in self.aristas_bloqueadas]

    def bloquear_celda_temporal(
        self, coord: Tuple[int, int], paso: int, id_picker: str
    ) -> None:
        self.aristas_bloqueadas[(coord, paso)] = id_picker

    def limpiar_bloqueos(self) -> None:
        self.aristas_bloqueadas.clear()
