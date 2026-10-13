from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from BackEnd.enums.enums import TipoCelda, SentidoCirculacion, TipoPuerta
from BackEnd.data_structures.grafo_warehouse import GrafoWarehouse


@dataclass
class WarehouseCell:
    x: int
    y: int
    tipo: TipoCelda
    sentido: SentidoCirculacion = SentidoCirculacion.AMBOS
    id_elemento_asociado: str = ""


@dataclass
class Rack:
    id_rack: str
    ubicacion_x: int
    ubicacion_y: int
    ancho: int
    alto: int

    def es_valido_lado_dos(self) -> bool:
        return self.ancho == 2 or self.alto == 2

    def obtener_celdas_ocupadas(self) -> List[Tuple[int, int]]:
        return [
            (x, y)
            for x in range(self.ubicacion_x, self.ubicacion_x + self.ancho)
            for y in range(self.ubicacion_y, self.ubicacion_y + self.alto)
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id_rack,
            "ubicacion": {"x": self.ubicacion_x, "y": self.ubicacion_y},
            "ancho": self.ancho,
            "alto": self.alto,
        }


@dataclass
class Pasillo:
    id_pasillo: str
    ubicacion_x: int
    ubicacion_y: int
    ancho: int
    alto: int
    sentido: SentidoCirculacion

    def obtener_celdas_ocupadas(self) -> List[Tuple[int, int]]:
        return [
            (x, y)
            for x in range(self.ubicacion_x, self.ubicacion_x + self.ancho)
            for y in range(self.ubicacion_y, self.ubicacion_y + self.alto)
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id_pasillo,
            "ubicacion": {"x": self.ubicacion_x, "y": self.ubicacion_y},
            "ancho": self.ancho,
            "alto": self.alto,
            "sentido": self.sentido.value,
        }


@dataclass
class Puerta:
    id_puerta: str
    tipo: TipoPuerta
    ubicacion_x: int
    ubicacion_y: int

    def permite_despacho_salida(self) -> bool:
        return self.tipo in (TipoPuerta.OUTBOUND, TipoPuerta.AMBOS)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id_puerta,
            "tipo": self.tipo.value,
            "ubicacion": {"x": self.ubicacion_x, "y": self.ubicacion_y},
        }


@dataclass
class ZonaDespacho:
    id_zona: str
    puerta_id: str
    ubicacion_x: int
    ubicacion_y: int
    ancho: int
    alto: int
    peso_max_kg: float
    peso_actual_kg: float = 0.0

    def puede_recibir_carga(self, peso: float) -> bool:
        return (self.peso_actual_kg + peso) <= self.peso_max_kg

    def registrar_carga(self, peso: float) -> bool:
        if self.puede_recibir_carga(peso):
            self.peso_actual_kg = round(self.peso_actual_kg + peso, 4)
            return True
        return False

    def obtener_celdas_ocupadas(self) -> List[Tuple[int, int]]:
        return [
            (x, y)
            for x in range(self.ubicacion_x, self.ubicacion_x + self.ancho)
            for y in range(self.ubicacion_y, self.ubicacion_y + self.alto)
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id_zona,
            "puerta_id": self.puerta_id,
            "ubicacion": {"x": self.ubicacion_x, "y": self.ubicacion_y},
            "ancho": self.ancho,
            "alto": self.alto,
            "peso_max_kg": self.peso_max_kg,
        }


@dataclass
class Warehouse:
    ancho_x: int
    largo_y: int
    grilla_hash: Dict[Tuple[int, int], WarehouseCell] = field(default_factory=dict)
    racks: Dict[str, Rack] = field(default_factory=dict)
    puertas: Dict[str, Puerta] = field(default_factory=dict)
    zonas_despacho: Dict[str, ZonaDespacho] = field(default_factory=dict)
    pasillos: Dict[str, Pasillo] = field(default_factory=dict)
    grafo: GrafoWarehouse = field(default_factory=GrafoWarehouse)

    def poblar_grilla_y_grafo(self) -> None:
        self.grilla_hash.clear()

        for pas in self.pasillos.values():
            for x, y in pas.obtener_celdas_ocupadas():
                self.grilla_hash[(x, y)] = WarehouseCell(
                    x=x,
                    y=y,
                    tipo=TipoCelda.PASILLO,
                    sentido=pas.sentido,
                    id_elemento_asociado=pas.id_pasillo,
                )

        for zona in self.zonas_despacho.values():
            for x, y in zona.obtener_celdas_ocupadas():
                self.grilla_hash[(x, y)] = WarehouseCell(
                    x=x,
                    y=y,
                    tipo=TipoCelda.ZONA_DESPACHO,
                    id_elemento_asociado=zona.id_zona,
                )

        for rack in self.racks.values():
            for x, y in rack.obtener_celdas_ocupadas():
                self.grilla_hash[(x, y)] = WarehouseCell(
                    x=x, y=y, tipo=TipoCelda.RACK, id_elemento_asociado=rack.id_rack
                )

        for pta in self.puertas.values():
            self.grilla_hash[(pta.ubicacion_x, pta.ubicacion_y)] = WarehouseCell(
                x=pta.ubicacion_x,
                y=pta.ubicacion_y,
                tipo=TipoCelda.PUERTA,
                id_elemento_asociado=pta.id_puerta,
            )

        self.grafo.construir_desde_grilla(self)

    def validar_sin_solapamientos(self) -> bool:
        ocupadas = set()
        for coleccion in (self.racks.values(), self.zonas_despacho.values()):
            for elem in coleccion:
                for celda in elem.obtener_celdas_ocupadas():
                    if celda in ocupadas:
                        return False
                    ocupadas.add(celda)
        return True

    def obtener_celda_acceso_pasillo(
        self, x_rack: int, y_rack: int
    ) -> Optional[Tuple[int, int]]:
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            vecino = (x_rack + dx, y_rack + dy)
            celda = self.grilla_hash.get(vecino)
            if celda and celda.tipo == TipoCelda.PASILLO:
                return vecino
        return None

    def obtener_celda_acceso_despacho(self, id_zona: str) -> Optional[Tuple[int, int]]:
        zona = self.zonas_despacho.get(id_zona)
        if not zona:
            return None

        for x, y in zona.obtener_celdas_ocupadas():
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                vecino = (x + dx, y + dy)
                celda = self.grilla_hash.get(vecino)
                if celda and celda.tipo == TipoCelda.PASILLO:
                    return vecino
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimensiones": {"ancho_x": self.ancho_x, "largo_y": self.largo_y},
            "puertas": [p.to_dict() for p in self.puertas.values()],
            "zonas_despacho": [z.to_dict() for z in self.zonas_despacho.values()],
            "racks": [r.to_dict() for r in self.racks.values()],
            "pasillos": [pas.to_dict() for pas in self.pasillos.values()],
        }
