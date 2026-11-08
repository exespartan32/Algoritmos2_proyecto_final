from typing import Dict, List, Optional, Set, Tuple

from BackEnd.enums.enums import SentidoCirculacion as Sentido
from BackEnd.models.entities import CeldaRack

Coord = Tuple[int, int]


class NodoGrafo:
    """Celda de pasillo transitable dentro del dígrafo del almacén."""

    def __init__(
        self, x: int, y: int, sentido: Sentido, pasillo_id: Optional[str] = None
    ) -> None:
        self.x = x
        self.y = y
        self.sentido_permitido = sentido
        self.pasillo_id = pasillo_id
        self.racks_adyacentes: List[CeldaRack] = []
        self.zonas_despacho_adyacentes: List[str] = []


class Digrafo:
    """Grafo dirigido mediante lista de adyacencia con soporte de bloqueos por turno."""

    def __init__(self) -> None:
        self.nodos: Dict[Coord, NodoGrafo] = {}
        self.lista_adyacencia: Dict[Coord, List[Coord]] = {}
        self.bloqueos_temporales: Dict[Tuple[int, int, int], str] = {}
        self.nodos_evasion_actual: Set[Coord] = set()

    def agregar_nodo(
        self, x: int, y: int, sentido: Sentido, pasillo_id: Optional[str] = None
    ) -> NodoGrafo:
        coord = (x, y)
        if coord not in self.nodos:
            self.nodos[coord] = NodoGrafo(x, y, sentido, pasillo_id)
            self.lista_adyacencia[coord] = []
        return self.nodos[coord]

    def agregar_arista_dirigida(self, origen: Coord, destino: Coord) -> None:
        if origen in self.lista_adyacencia and destino in self.nodos:
            if destino not in self.lista_adyacencia[origen]:
                self.lista_adyacencia[origen].append(destino)

    def obtener_vecinos(self, coord: Coord) -> List[Coord]:
        return self.lista_adyacencia.get(coord, [])

    def bloquear_celda_temporal(
        self, coord: Coord, paso_tiempo: int, picker_id: str
    ) -> None:
        self.bloqueos_temporales[(coord[0], coord[1], int(paso_tiempo))] = picker_id

    def limpiar_bloqueos_antiguos(self, paso_actual: int) -> None:
        claves_vencidas = [k for k in self.bloqueos_temporales if k[2] < paso_actual]
        for k in claves_vencidas:
            del self.bloqueos_temporales[k]

    def obtener_vecinos_validos(
        self,
        nodo_actual: Coord,
        paso_tiempo: int = 0,
        picker_id_solicitante: Optional[str] = None,
    ) -> List[Coord]:
        vecinos_base = self.lista_adyacencia.get(nodo_actual, [])
        if not self.bloqueos_temporales and not self.nodos_evasion_actual:
            return list(vecinos_base)

        validos: List[Coord] = []
        for v in vecinos_base:
            if v in self.nodos_evasion_actual:
                continue
            if paso_tiempo > 0:
                ocupante = self.bloqueos_temporales.get((v[0], v[1], paso_tiempo))
                if ocupante is not None and ocupante != picker_id_solicitante:
                    continue
            validos.append(v)
        return validos
