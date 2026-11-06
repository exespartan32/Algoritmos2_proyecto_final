"""Gestión de la biblioteca local de escenarios y sesiones guardadas."""

from datetime import datetime
import json
from pathlib import Path
import re
from typing import List

from BackEnd.controllers.simulador import Simulador
from BackEnd.utils.scenario_generator import ScenarioGenerator
from BackEnd.utils.validator_escenario import validar_escenario

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "BackEnd" / "data"


def _nombre_seguro(texto: str) -> str:
    texto = re.sub(r"[^A-Za-z0-9_\-]+", "_", texto).strip("_")
    return (texto or "escenario")[:50]


class Biblioteca:
    def __init__(self, carpeta=None) -> None:
        self.carpeta = Path(carpeta or RAIZ / "biblioteca")
        self.carpeta.mkdir(parents=True, exist_ok=True)
        marca = self.carpeta / ".inicializada"
        if not marca.exists():
            for ruta in sorted(DATOS.glob("escenario_*.json")):
                destino = self.carpeta / ruta.name
                if not destino.exists():
                    destino.write_bytes(ruta.read_bytes())
            marca.touch()

    def archivos(self) -> List[Path]:
        return sorted(self.carpeta.glob("*.json"), key=lambda p: p.name.lower())

    def _ruta_libre(self, base: str) -> Path:
        ruta = self.carpeta / f"{base}.json"
        n = 2
        while ruta.exists():
            ruta = self.carpeta / f"{base}_{n}.json"
            n += 1
        return ruta

    @staticmethod
    def leer(ruta) -> dict:
        return json.loads(Path(ruta).read_text(encoding="utf-8-sig"))

    @staticmethod
    def es_sesion(ruta) -> bool:
        try:
            return "_sesion" in Biblioteca.leer(ruta)
        except Exception:
            return False

    @staticmethod
    def abrir(ruta) -> Simulador:
        datos = Biblioteca.leer(ruta)
        validar_escenario({k: v for k, v in datos.items() if not k.startswith("_")})
        return Simulador(datos)

    def importar(self, ruta) -> Path:
        datos = self.leer(ruta)
        validar_escenario({k: v for k, v in datos.items() if not k.startswith("_")})
        sim = Simulador(datos)
        if sim.advertencias:
            raise ValueError(
                "El mapa presenta advertencias: " + "; ".join(sim.advertencias[:3])
            )
        destino = self._ruta_libre(_nombre_seguro(Path(ruta).stem))
        destino.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return destino

    def generar(self, **parametros) -> Path:
        datos = ScenarioGenerator.generar_escenario_dict(**parametros)
        p = datos["_generador"]
        base = (
            f"generado_{p['cantidad_estantes']}r_{p['cantidad_pasillos']}p_"
            f"{p['cantidad_productos']}prod_{p['cantidad_pedidos']}ped_{p['localizacion'].lower()}"
        )
        destino = self._ruta_libre(base)
        destino.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return destino

    def guardar_sesion(self, sim: Simulador, nombre: str) -> Path:
        base = f"sesion_{_nombre_seguro(nombre)}_{datetime.now():%Y%m%d_%H%M%S}"
        return sim.guardar(self._ruta_libre(base))

    def eliminar(self, ruta) -> None:
        ruta = Path(ruta).resolve()
        if ruta.parent != self.carpeta.resolve() or ruta.suffix != ".json":
            raise ValueError("Solo se pueden borrar archivos de la biblioteca.")
        ruta.unlink()
