from dataclasses import dataclass
from typing import Dict
from BackEnd.enums.enums import EstrategiaRuteo


@dataclass
class MetricaWave:
    id_wave: str
    estrategia: EstrategiaRuteo
    distancia_total: int
    nodos_visitados: int
    aristas_recorridas: int
    tiempo_ms: float


class MetricsManager:
    def __init__(self):
        self._historial: Dict[str, Dict[EstrategiaRuteo, MetricaWave]] = {}

    def registrar_metrica(
        self,
        id_wave: str,
        estrategia: EstrategiaRuteo,
        dist_total: int,
        nodos_visitados: int,
        aristas_recorridas: int,
        tiempo_ms: float,
    ) -> None:
        if id_wave not in self._historial:
            self._historial[id_wave] = {}

        self._historial[id_wave][estrategia] = MetricaWave(
            id_wave=id_wave,
            estrategia=estrategia,
            distancia_total=dist_total,
            nodos_visitados=nodos_visitados,
            aristas_recorridas=aristas_recorridas,
            tiempo_ms=tiempo_ms,
        )

    def comparar_estrategias(self, id_wave: str) -> Dict[EstrategiaRuteo, MetricaWave]:
        return self._historial.get(id_wave, {})
