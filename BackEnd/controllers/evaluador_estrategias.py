import sys
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from BackEnd.controllers.path_finding import Pathfinding
from BackEnd.controllers.wave_builder import ESTRATEGIAS_ARMADO, WaveBuilder

if TYPE_CHECKING:
    from BackEnd.controllers.simulador import Simulador

Coord = Tuple[int, int]


def _mantener_ventana_activa(paso: int) -> None:
    """Refresca la cola de eventos de Pygame durante simulaciones largas en segundo plano."""
    if paso % 80 == 0 and "pygame" in sys.modules:
        pygame_mod = sys.modules["pygame"]
        if pygame_mod.display.get_init():
            pygame_mod.event.pump()


class EvaluadorEstrategias:
    """Ejecuta comparaciones de ruteo, comparaciones de armado y trazas explicativas."""

    @staticmethod
    def elegir_mejor_estrategia_armado(
        sim: "Simulador",
    ) -> Tuple[str, Dict[str, Dict[str, Any]]]:
        """Compara las tres estrategias de armado y devuelve la mejor y el reporte."""
        comparativa = EvaluadorEstrategias.comparar_armado(sim)
        mejor_clave = min(
            comparativa,
            key=lambda k: (
                comparativa[k]["distancia"],
                comparativa[k]["turnos"],
                comparativa[k]["pasillos_por_wave"],
                comparativa[k]["tiempo_armado_ms"],
            ),
        )
        return mejor_clave, comparativa

    @staticmethod
    def comparar_estrategias(
        sim: "Simulador",
        ids_waves: Optional[List[str]] = None,
        pickers_por_wave: Optional[int] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Simula las mismas waves con Orden de pedidos y con Cercanía sobre copias aisladas."""
        from BackEnd.controllers.simulador import (
            ESTRATEGIAS,
            MAX_PASOS_TANDA,
            NOMBRE_ESTRATEGIA,
            Simulador,
        )

        indice = len(sim.estado.tandas) - 1
        if ids_waves is None:
            tanda = sim.tanda_actual
            if tanda is None or indice not in sim._inicio_tanda:
                raise ValueError("Seleccioná waves (o iniciá una tanda) para comparar.")
            ids_waves = tanda["waves"] + tanda["en_espera"]
            base = sim._inicio_tanda[indice][0]
            pickers_por_wave = tanda.get("pickers_por_wave", 1)
        else:
            base = sim.estado

        resultados: Dict[str, Dict[str, Any]] = {}
        for clave in ESTRATEGIAS:
            clon = Simulador.__new__(Simulador)
            clon.__dict__.update(sim.__dict__)
            clon.estado = sim._copiar(base)
            clon.historial = []
            clon._inicio_tanda = {}
            clon.acciones = []
            clon.estrategia = clave

            inicio = time.perf_counter()
            tanda = clon.iniciar_waves(ids_waves, clave, pickers_por_wave)
            tiempo_plan = (time.perf_counter() - inicio) * 1000
            clon.historial = []

            pasos = 0
            while pasos < MAX_PASOS_TANDA and clon.avanzar(guardar_historial=False):
                pasos += 1
                _mantener_ventana_activa(pasos)

            planes = tanda["planes"]
            resultados[clave] = {
                "nombre": NOMBRE_ESTRATEGIA[clave],
                "waves": tanda["waves"],
                "pickers": len({p["picker"] for p in planes}),
                "viajes": len(planes),
                "distancia": sum(p["distancia"] for p in planes),
                "aristas": sum(p["aristas"] for p in planes),
                "nodos_visitados": sum(p["nodos_visitados"] for p in planes),
                "nodos_explorados": sum(p["nodos_explorados"] for p in planes),
                "expansiones": sum(p["expansiones"] for p in planes),
                "tiempo_ms": round(sum(p["tiempo_ms"] for p in planes), 3),
                "tiempo_total_ms": round(tiempo_plan, 3),
                "turnos": pasos,
                "esperas": (
                    clon.estado.colisiones.total_esperas_aplicadas
                    - base.colisiones.total_esperas_aplicadas
                ),
                "desvios": (
                    clon.estado.colisiones.total_desvios_recalculados
                    - base.colisiones.total_desvios_recalculados
                ),
            }
        return resultados

    @staticmethod
    def comparar_armado(sim: "Simulador") -> Dict[str, Dict[str, Any]]:
        """Arma todas las waves con cada criterio de agrupamiento y simula su preparación completa."""
        from BackEnd.controllers.simulador import MAX_PASOS_TANDA, Simulador

        base = sim._pre_waves if sim._pre_waves is not None else sim.estado
        if base.gestor_waves is not None:
            raise ValueError("No hay un estado previo sin waves para comparar.")

        resultados: Dict[str, Dict[str, Any]] = {}
        for clave, nombre in ESTRATEGIAS_ARMADO.items():
            clon = Simulador.__new__(Simulador)
            clon.__dict__.update(sim.__dict__)
            clon.config = dict(sim.config, estrategia_waves=clave)
            clon.estado = sim._copiar(base)
            clon._pre_waves = None
            clon.historial, clon._inicio_tanda, clon.acciones = [], {}, []

            waves = clon.generar_waves()
            gestor = clon.estado.gestor_waves
            evaluados = sum(
                paso.get("candidatos_evaluados", 0)
                for traza in gestor.traza_armado.values()
                for paso in traza
            )
            pasillos = [
                len(
                    set().union(
                        *(WaveBuilder.pasillos_de(p, clon.warehouse) for p in w.pedidos)
                    )
                )
                for w in waves
            ]
            prioridad_media = [
                sum(p.prioridad for p in w.pedidos) / len(w.pedidos) for w in waves
            ]

            tanda = clon.iniciar_waves([w.id_wave for w in waves], sim.estrategia)
            clon.historial = []
            pasos = 0
            while pasos < MAX_PASOS_TANDA * 4 and clon.avanzar(guardar_historial=False):
                pasos += 1
                _mantener_ventana_activa(pasos)

            planes = tanda["planes"]
            resultados[clave] = {
                "nombre": nombre,
                "waves": len(waves),
                "pedidos_en_waves": sum(len(w.pedidos) for w in waves),
                "pedidos_por_wave": round(
                    sum(len(w.pedidos) for w in waves) / max(1, len(waves)), 2
                ),
                "pasillos_por_wave": round(sum(pasillos) / max(1, len(pasillos)), 2),
                "prioridad_primera_wave": (
                    round(prioridad_media[0], 2) if prioridad_media else 0
                ),
                "tiempo_armado_ms": round(clon.tiempo_waves_ms, 3),
                "candidatos_evaluados": evaluados,
                "distancia": sum(p["distancia"] for p in planes),
                "turnos": pasos,
                "pedidos_preparados": clon.metricas()["pedidos_preparados"],
            }
        return resultados

    @staticmethod
    def explicar_armado(sim: "Simulador", id_wave: str) -> Dict[str, Any]:
        """Reconstruye los pasos de armado de una wave y la ruta resultante para animarlos."""
        from BackEnd.controllers.simulador import NOMBRE_ESTRATEGIA

        gestor = sim.estado.gestor_waves
        if gestor is None or id_wave not in gestor.waves_por_id:
            raise ValueError("Primero generá las waves.")

        wh = sim.warehouse
        grafo = wh.grafo_pasillos
        wave = gestor.waves_por_id[id_wave]
        traza = gestor.traza_armado.get(id_wave, [])
        estrategia_armado = gestor.estrategia_armado

        def celdas_de(id_pedido: str) -> List[Coord]:
            ped = wh.buscar_pedido_O1(id_pedido)
            vistas, salida = set(), []
            for item in ped.items:
                prod = wh.buscar_producto_O1(item.producto_id)
                if prod and prod.coordenadas_xy not in vistas:
                    vistas.add(prod.coordenadas_xy)
                    salida.append(prod.coordenadas_xy)
            return salida

        def acceso(c: Coord) -> Coord:
            return Pathfinding.obtener_celda_acceso_pasillo(c, grafo, wh)

        def describir_ponderado() -> str:
            if estrategia_armado == "CERCANIA":
                return (
                    "Para cada candidato se calcula el costo marginal promedio: por cada producto, "
                    "la distancia en el dígrafo al producto más cercano que ya está en la wave "
                    "(más una penalización por la altura z), y se promedia. Gana el menor."
                )
            if estrategia_armado == "PASILLO":
                return (
                    "Para cada candidato se cuentan los pasillos nuevos que agregaría "
                    "a la wave. Gana el que agrega menos."
                )
            return "No se mira la ubicación: gana el candidato de mayor prioridad."

        pasos: List[Dict[str, Any]] = []
        en_wave: List[Coord] = []
        nombre_zona = wave.id_zona_despacho

        for entrada in traza:
            rol = entrada["rol"]
            if rol == "RAIZ_MAX_HEAP":
                celdas = celdas_de(entrada["id_pedido"])
                pasos.append(
                    {
                        "tipo": "raiz",
                        "pedido": entrada["id_pedido"],
                        "prioridad": entrada["prioridad"],
                        "celdas": celdas,
                        "texto": (
                            f"Del Max-Heap sale {entrada['id_pedido']} (prioridad {entrada['prioridad']}), "
                            f"el pedido pendiente más urgente. Abre la wave y se le asigna {nombre_zona}, "
                            f"la zona de despacho más cercana a sus productos con capacidad disponible."
                        ),
                    }
                )
                en_wave.extend(celdas)
            elif rol == "FIN":
                pasos.append(
                    {
                        "tipo": "fin",
                        "texto": "La wave se cierra. " + (entrada.get("motivo") or ""),
                    }
                )
            else:
                celdas = celdas_de(entrada["id_pedido"])
                ranking = [
                    dict(r, celdas=celdas_de(r["id_pedido"]))
                    for r in entrada.get("ranking", [])
                ]
                pasos.append(
                    {
                        "tipo": "evaluar",
                        "ranking": ranking,
                        "factibles": entrada.get("factibles", len(ranking)),
                        "evaluados": entrada.get("candidatos_evaluados", len(ranking)),
                        "texto": (
                            f"Se revisan los {entrada.get('factibles', len(ranking))} pedidos pendientes que entran "
                            f"en las unidades libres; {entrada.get('candidatos_evaluados', len(ranking))} cumplen "
                            f"stock, zona y pickers. " + describir_ponderado()
                        ),
                    }
                )

                enlaces = []
                if estrategia_armado == "CERCANIA" and en_wave:
                    for c in celdas:
                        if c in en_wave:
                            continue
                        mejor = min(
                            en_wave,
                            key=lambda u: gestor._distancia_enlace_digrafo(
                                c, u, sim.matriz_distancias
                            ),
                        )
                        ida = gestor._obtener_distancia_dirigida(
                            mejor, c, sim.matriz_distancias
                        )
                        vuelta = gestor._obtener_distancia_dirigida(
                            c, mejor, sim.matriz_distancias
                        )
                        origen, destino = (
                            (acceso(mejor), acceso(c))
                            if ida <= vuelta
                            else (acceso(c), acceso(mejor))
                        )
                        camino, _ = Pathfinding.calcular_ruta_dijkstra(
                            origen, destino, grafo
                        )
                        enlaces.append(
                            {
                                "desde": c,
                                "hasta": mejor,
                                "camino": camino,
                                "distancia": max(0, len(camino) - 1),
                            }
                        )

                score = entrada.get("score_marginal", 0.0)
                pasos.append(
                    {
                        "tipo": "elegir",
                        "pedido": entrada["id_pedido"],
                        "prioridad": entrada["prioridad"],
                        "score": score,
                        "celdas": celdas,
                        "enlaces": enlaces,
                        "texto": (
                            f"Gana {entrada['id_pedido']} (prioridad {entrada['prioridad']}) con ponderado "
                            f"{score:.2f}"
                            + (
                                " pasillos nuevos"
                                if estrategia_armado == "PASILLO"
                                else ""
                            )
                            + ". Se suma a la wave."
                            + (
                                " Las líneas muestran el camino en el dígrafo hasta el producto más cercano de la wave."
                                if enlaces
                                else ""
                            )
                        ),
                    }
                )
                en_wave.extend(c for c in celdas if c not in en_wave)

        accesos_zona = wh.obtener_nodos_acceso_zona(wave.id_zona_despacho)
        destinos = list(dict.fromkeys(acceso(c) for c in en_wave))
        ruta = None
        if accesos_zona and destinos:
            despacho = min(
                accesos_zona,
                key=lambda c: (
                    abs(c[0] - destinos[0][0]) + abs(c[1] - destinos[0][1]),
                    c,
                ),
            )
            if sim.estrategia == "ORDEN":
                res = Pathfinding.calcular_estrategia_orden_pedidos(
                    grafo, despacho, destinos, despacho, wh
                )
            else:
                res = Pathfinding.calcular_estrategia_cercania_multidestino(
                    grafo, despacho, destinos, despacho, wh
                )
            orden_visita, pendientes = [], set(destinos)
            for celda in res.camino_completo:
                if celda in pendientes:
                    orden_visita.append(celda)
                    pendientes.discard(celda)
            ruta = {
                "despacho": despacho,
                "camino": list(res.camino_completo),
                "destinos": orden_visita,
                "distancia": res.distancia_total,
                "orden_exploracion": list(res.orden_exploracion),
            }
            pasos.append(
                {
                    "tipo": "ruta",
                    "texto": (
                        f"Recorrido del picker con {NOMBRE_ESTRATEGIA[sim.estrategia]}: sale del despacho, "
                        + (
                            "visita los productos en el orden de los pedidos"
                            if sim.estrategia == "ORDEN"
                            else "va siempre al producto pendiente más cercano (Dijkstra multidestino)"
                        )
                        + f" y vuelve a {nombre_zona}. Total: {res.distancia_total} pasos."
                    ),
                }
            )

        return {
            "wave": id_wave,
            "zona": nombre_zona,
            "estrategia_armado": estrategia_armado,
            "estrategia_ruta": sim.estrategia,
            "pedidos": [p.id_pedido for p in wave.pedidos],
            "pasos": pasos,
            "ruta": ruta,
        }
