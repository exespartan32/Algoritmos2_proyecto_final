from typing import Any, Dict, List, Optional, Set, Tuple

from BackEnd.controllers.path_finding import Pathfinding
from BackEnd.models.entities import ListaDeInmutables, Picker

CoordXY = Tuple[int, int]


class TurnAndCollisionManager:
    """Gestor de avance por turnos y evasión de colisiones para múltiples pickers en el dígrafo."""

    def __init__(
        self,
        max_turnos_bloqueo_recalculo: int = 2,
        turnos_estela: int = 2,
        turnos_recogida: int = 4,
        turnos_descarga: int = 3,
    ) -> None:
        self.reservas_celdas: Dict[Tuple[int, int, int], str] = {}
        self.pathfinding = Pathfinding()
        self.max_turnos_bloqueo_recalculo = max_turnos_bloqueo_recalculo
        self.turnos_para_ceder = max_turnos_bloqueo_recalculo + 1
        # Estela: bloquea temporalmente la celda recién abandonada para mantener distancia entre pickers.
        self.turnos_estela = max(0, int(turnos_estela))
        self.estela: Dict[CoordXY, Tuple[str, int]] = {}
        # Turnos que demora recoger un producto en estantería y descargar en despacho.
        self.turnos_recogida = max(0, int(turnos_recogida))
        self.turnos_descarga = max(0, int(turnos_descarga))
        self.eventos_colision: List[str] = ListaDeInmutables()
        self.total_esperas_aplicadas: int = 0
        self.total_desvios_recalculados: int = 0

    @staticmethod
    def _esta_fijo_en_celda(picker: Picker) -> bool:
        """Indica si el picker está detenido recogiendo mercadería, buscando ruta o descargando."""
        if picker.turnos_pausa > 0 or picker.turnos_busqueda > 0:
            return True
        if not picker.ruta_asignada:
            return True
        return False

    def detectar_cruce_o_colision(self, p1: Picker, p2: Picker) -> bool:
        sig_p1 = p1.ruta_asignada[0] if p1.ruta_asignada else p1.posicion_actual
        sig_p2 = p2.ruta_asignada[0] if p2.ruta_asignada else p2.posicion_actual

        # Si ambos están quietos en sus propias celdas (distintas), no hay colisión
        if sig_p1 == p1.posicion_actual and sig_p2 == p2.posicion_actual:
            return sig_p1 == sig_p2

        # Misma celda de destino en el siguiente turno
        if sig_p1 == sig_p2:
            return True

        # Cruce frontal intercambiando posiciones (u <-> v)
        if sig_p1 == p2.posicion_actual and sig_p2 == p1.posicion_actual:
            return True

        return False

    def _buscar_mejor_desvio_lateral(
        self,
        picker: Picker,
        celdas_prohibidas: Set[CoordXY],
        grafo: Any,
    ) -> Optional[List[CoordXY]]:
        """Evalúa todas las celdas adyacentes libres y devuelve la ruta desviada más corta."""
        if self._esta_fijo_en_celda(picker):
            return None

        vecinos = Pathfinding._obtener_vecinos(
            grafo, picker.posicion_actual, paso_tiempo=0, picker_id=picker.id_picker
        )
        mejor_ruta: Optional[List[CoordXY]] = None
        for v in vecinos:
            if v in celdas_prohibidas:
                continue
            ruta_candidata = Pathfinding.desviar_por(picker, v, grafo)
            if ruta_candidata and (
                mejor_ruta is None or len(ruta_candidata) < len(mejor_ruta)
            ):
                mejor_ruta = ruta_candidata
        return mejor_ruta

    def resolver_conflicto(
        self,
        picker_prioritario: Picker,
        picker_cedente: Picker,
        grafo: Any,
        paso_actual: int = 0,
        ocupadas_actuales: Optional[Set[CoordXY]] = None,
    ) -> None:
        if not picker_cedente.ruta_asignada and not picker_prioritario.ruta_asignada:
            return

        # Si el cedente está fijo cargando/buscando y el prioritario no, invertimos roles
        if self._esta_fijo_en_celda(picker_cedente) and not self._esta_fijo_en_celda(
            picker_prioritario
        ):
            picker_prioritario, picker_cedente = picker_cedente, picker_prioritario

        if self._esta_fijo_en_celda(picker_cedente):
            return

        sig_prio = (
            picker_prioritario.ruta_asignada[0]
            if picker_prioritario.ruta_asignada
            else picker_prioritario.posicion_actual
        )
        sig_ced = (
            picker_cedente.ruta_asignada[0]
            if picker_cedente.ruta_asignada
            else picker_cedente.posicion_actual
        )
        es_cruce_frontal = (
            sig_prio == picker_cedente.posicion_actual
            and sig_ced == picker_prioritario.posicion_actual
            and sig_prio != sig_ced
        )

        prohibidas = set(ocupadas_actuales or set())
        prohibidas.add(sig_prio)
        prohibidas.add(picker_prioritario.posicion_actual)

        if hasattr(grafo, "bloquear_celda_temporal"):
            grafo.bloquear_celda_temporal(
                sig_prio, paso_actual + 1, picker_prioritario.id_picker
            )
            grafo.bloquear_celda_temporal(
                picker_prioritario.posicion_actual,
                paso_actual + 1,
                picker_prioritario.id_picker,
            )

        if es_cruce_frontal:
            nueva_ruta = self._buscar_mejor_desvio_lateral(
                picker_cedente, prohibidas, grafo
            )
            if nueva_ruta:
                celda_escape = nueva_ruta[0]
                picker_cedente.ruta_asignada = nueva_ruta
                self.total_desvios_recalculados += 1
                self.eventos_colision.append(
                    f"[Turno {paso_actual}] Cruce frontal resuelto: {picker_cedente.id_picker} "
                    f"se aparta hacia {celda_escape} para dar paso a {picker_prioritario.id_picker}."
                )
                return

            if not self._esta_fijo_en_celda(picker_prioritario):
                prohibidas_prio = (ocupadas_actuales or set()) | {
                    sig_ced,
                    picker_cedente.posicion_actual,
                }
                nueva_ruta_prio = self._buscar_mejor_desvio_lateral(
                    picker_prioritario, prohibidas_prio, grafo
                )
                if nueva_ruta_prio:
                    picker_prioritario.ruta_asignada = nueva_ruta_prio
                    self.total_desvios_recalculados += 1
                    return

        if picker_cedente.turnos_bloqueado >= self.max_turnos_bloqueo_recalculo:
            nueva_ruta = self.pathfinding.recalcular_evitando_obstaculo(
                grafo,
                picker_cedente,
                paso_actual,
                celdas_bloqueadas=prohibidas,
            )
            picker_cedente.ruta_asignada = nueva_ruta
            self.total_desvios_recalculados += 1
            self.eventos_colision.append(
                f"[Turno {paso_actual}] {picker_cedente.id_picker} recalcula su camino "
                f"tras {picker_cedente.turnos_bloqueado} turnos de espera."
            )
        else:
            if (
                not picker_cedente.ruta_asignada
                or picker_cedente.ruta_asignada[0] != picker_cedente.posicion_actual
            ):
                picker_cedente.ruta_asignada.insert(0, picker_cedente.posicion_actual)
                self.total_esperas_aplicadas += 1
                self.eventos_colision.append(
                    f"[Turno {paso_actual}] {picker_cedente.id_picker} espera en "
                    f"{picker_cedente.posicion_actual} cediendo el paso a {picker_prioritario.id_picker} en {sig_prio}."
                )

    def validar_movimiento_simultaneo(
        self, pickers: List[Picker], paso_actual: int, grafo: Any
    ) -> None:
        if hasattr(grafo, "limpiar_bloqueos_antiguos"):
            grafo.limpiar_bloqueos_antiguos(paso_actual)

        self.reservas_celdas = {
            k: v for k, v in self.reservas_celdas.items() if k[2] > paso_actual
        }
        self.estela = {c: v for c, v in self.estela.items() if v[1] > paso_actual}
        estela_de = {c: pid for c, (pid, _) in self.estela.items()}

        pickers_activos = [
            p for p in pickers if p.id_wave_actual is not None or p.ruta_asignada
        ]
        ids_activos = {id(p) for p in pickers_activos}
        estacionados = {
            p.posicion_actual: p for p in pickers if id(p) not in ids_activos
        }
        if not pickers_activos:
            return

        # Si un picker ya recogió todo, está demorado y ya se encuentra adyacente a su zona de despacho, descarga ahí.
        nodos = getattr(grafo, "nodos", {})
        for p in pickers_activos:
            if (
                p.ruta_asignada
                and p.turnos_bloqueado >= 2
                and not p.objetivos_pendientes
                and p.id_wave_actual is not None
                and any(
                    q is not p and q.posicion_actual in p.ruta_asignada
                    for q in pickers_activos
                )
            ):
                aca = nodos.get(p.posicion_actual)
                destino = nodos.get(p.ruta_asignada[-1])
                if (
                    aca is not None
                    and destino is not None
                    and set(aca.zonas_despacho_adyacentes)
                    & set(destino.zonas_despacho_adyacentes)
                ):
                    p.ruta_asignada = []
                    p.destino_despacho_actual = p.posicion_actual
                    p.turnos_bloqueado = 0
                    self.eventos_colision.append(
                        f"[Turno {paso_actual}] {p.id_picker} descarga en {p.posicion_actual} "
                        f"junto a la zona de despacho porque el paso estaba obstruido."
                    )

        # Si un picker libre obstruye a uno activo durante 2 turnos, se desplaza a una celda vecina libre.
        for p in pickers_activos:
            if not p.ruta_asignada or p.turnos_bloqueado < 2:
                continue
            proxima = next((c for c in p.ruta_asignada if c != p.posicion_actual), None)
            libre = estacionados.get(proxima)
            if libre is None:
                continue
            ocupadas = {q.posicion_actual for q in pickers} | {
                q.ruta_asignada[0] for q in pickers_activos if q.ruta_asignada
            }
            for vecino in Pathfinding._obtener_vecinos(grafo, libre.posicion_actual, 0):
                if vecino not in ocupadas and vecino not in estela_de:
                    libre.ruta_asignada = [vecino]
                    del estacionados[libre.posicion_actual]
                    self.eventos_colision.append(
                        f"[Turno {paso_actual}] {libre.id_picker} (libre) se corre a {vecino} "
                        f"para dejar pasar a {p.id_picker}."
                    )
                    break
            else:
                faltan = [c for c in p.ruta_asignada if c != p.posicion_actual]
                aca = nodos.get(p.posicion_actual)
                destino = nodos.get(proxima)
                if (
                    faltan == [proxima]
                    and aca is not None
                    and destino is not None
                    and set(aca.zonas_despacho_adyacentes)
                    & set(destino.zonas_despacho_adyacentes)
                ):
                    p.ruta_asignada = []
                    p.destino_despacho_actual = p.posicion_actual
                    p.turnos_bloqueado = 0
                    self.eventos_colision.append(
                        f"[Turno {paso_actual}] {p.id_picker} descarga en {p.posicion_actual} porque "
                        f"{libre.id_picker} está estacionado en {proxima}."
                    )

        pickers_activos = [
            p for p in pickers if p.id_wave_actual is not None or p.ruta_asignada
        ]
        ids_en_marcha = {id(p) for p in pickers_activos}

        # Orden de prioridad:
        # 1. Pickers detenidos cargando en rack o inicializando búsqueda (no pueden moverse de su celda).
        # 2. Pickers que llevan más turnos esperando bloqueados.
        # 3. Pickers que están más cerca de terminar su recorrido.
        pickers_ordenados = sorted(
            pickers_activos,
            key=lambda p: (
                -(1 if self._esta_fijo_en_celda(p) else 0),
                -p.turnos_bloqueado,
                len(p.ruta_asignada),
                p.id_picker,
            ),
        )

        ocupadas_base = {p.posicion_actual for p in pickers_activos} | set(estacionados)

        # Primera pasada: resolución de cruces y colisiones entre pares
        for i in range(len(pickers_ordenados)):
            for j in range(i + 1, len(pickers_ordenados)):
                p_prio = pickers_ordenados[i]
                p_ced = pickers_ordenados[j]
                if self.detectar_cruce_o_colision(p_prio, p_ced):
                    estela_ajena = {
                        c
                        for c, pid in estela_de.items()
                        if pid != p_ced.id_picker
                    }
                    self.resolver_conflicto(
                        p_prio,
                        p_ced,
                        grafo,
                        paso_actual,
                        ocupadas_base | estela_ajena,
                    )

        por_id = {p.id_picker: p for p in pickers}

        # Segunda pasada: si un picker frena, los que vienen detrás también esperan su turno
        cambio = True
        iteraciones = 0
        while cambio and iteraciones < len(pickers_ordenados) + 2:
            cambio = False
            iteraciones += 1
            celdas_reservadas_turno: Dict[CoordXY, Picker] = {}

            for p in pickers_ordenados:
                sig = p.ruta_asignada[0] if p.ruta_asignada else p.posicion_actual
                if sig == p.posicion_actual:
                    celdas_reservadas_turno[sig] = p

            for p in pickers_ordenados:
                if p.posicion_actual not in celdas_reservadas_turno:
                    celdas_reservadas_turno[p.posicion_actual] = p
            for celda, p in estacionados.items():
                celdas_reservadas_turno.setdefault(celda, p)
            for celda, pid in estela_de.items():
                if celda not in celdas_reservadas_turno and pid in por_id:
                    celdas_reservadas_turno[celda] = por_id[pid]

            for p in pickers_ordenados:
                if not p.ruta_asignada:
                    continue
                sig = p.ruta_asignada[0]
                if sig == p.posicion_actual:
                    continue

                ocupante = celdas_reservadas_turno.get(sig)
                if (
                    ocupante is not None
                    and ocupante is not p
                    and id(ocupante) not in ids_en_marcha
                    and p.turnos_bloqueado >= self.turnos_para_ceder
                ):
                    celdas_reservadas_turno[sig] = p
                elif ocupante is not None and ocupante is not p:
                    p.ruta_asignada.insert(0, p.posicion_actual)
                    celdas_reservadas_turno[p.posicion_actual] = p
                    self.total_esperas_aplicadas += 1
                    cambio = True
                else:
                    celdas_reservadas_turno[sig] = p

        # Tercera pasada: si un picker sigue trabado tras varios turnos, cede el lugar hacia una celda vecina libre
        reservadas = {
            (p.ruta_asignada[0] if p.ruta_asignada else p.posicion_actual)
            for p in pickers_ordenados
        }
        for p in pickers_ordenados:
            if (
                self._esta_fijo_en_celda(p)
                or p.ruta_asignada[0] != p.posicion_actual
                or p.turnos_bloqueado < self.turnos_para_ceder
            ):
                continue
            estela_ajena = {
                c for c, pid in estela_de.items() if pid != p.id_picker
            }
            mejor = self._buscar_mejor_desvio_lateral(
                p, reservadas | ocupadas_base | estela_ajena, grafo
            )
            if mejor is not None:
                reservadas.discard(p.posicion_actual)
                reservadas.add(mejor[0])
                p.ruta_asignada = mejor
                self.total_desvios_recalculados += 1
                self.eventos_colision.append(
                    f"[Turno {paso_actual}] {p.id_picker} cede el paso hacia {mejor[0]} "
                    f"tras {p.turnos_bloqueado} turnos detenido."
                )

        for p in pickers_ordenados:
            sig = p.ruta_asignada[0] if p.ruta_asignada else p.posicion_actual
            self.reservas_celdas[(sig[0], sig[1], paso_actual + 1)] = p.id_picker

    def avanzar_un_turno_simulacion(
        self,
        pickers: List[Picker],
        paso_actual: int,
        grafo: Any,
        gestor_waves: Any = None,
        catalogo: Any = None,
    ) -> int:
        """Avanza un turno completo para todos los pickers y devuelve cuántos siguen activos."""
        for p in pickers:
            if p.id_wave_actual is None and p.cola_waves_asignadas:
                p.iniciar_siguiente_tarea_en_cola()
                # Si el primer producto ya está exactamente en su celda inicial:
                if (
                    p.objetivos_pendientes
                    and p.posicion_actual in p.objetivos_pendientes
                ):
                    p.objetivos_pendientes.remove(p.posicion_actual)
                    if self.turnos_recogida:
                        p.ruta_asignada[0:0] = [
                            p.posicion_actual
                        ] * self.turnos_recogida
                        p.turnos_pausa = self.turnos_recogida

        self.validar_movimiento_simultaneo(pickers, paso_actual, grafo)

        pickers_en_movimiento = 0

        for p in pickers:
            if not p.ruta_asignada:
                if p.id_wave_actual is not None:
                    pickers_en_movimiento += 1
                    p.turnos_descargando += 1
                    if p.turnos_descargando >= self.turnos_descarga:
                        p.turnos_descargando = 0
                        wave_terminada = p.id_wave_actual
                        p.peso_actual_kg = 0.0
                        p.id_wave_actual = None
                        if gestor_waves is not None:
                            gestor_waves.notificar_picker_descargo_en_despacho(
                                wave_terminada, p.id_picker, pickers, catalogo
                            )
                continue

            pickers_en_movimiento += 1
            siguiente_celda = p.ruta_asignada.pop(0)

            if siguiente_celda == p.posicion_actual:
                if p.turnos_busqueda > 0:
                    p.turnos_busqueda -= 1
                elif p.turnos_pausa > 0:
                    p.turnos_pausa -= 1
                else:
                    p.turnos_bloqueado += 1
            else:
                if self.turnos_estela and p.id_wave_actual is not None:
                    self.estela[p.posicion_actual] = (
                        p.id_picker,
                        paso_actual + 1 + self.turnos_estela,
                    )
                p.posicion_actual = siguiente_celda
                p.turnos_bloqueado = 0
                if (
                    p.objetivos_pendientes
                    and p.posicion_actual in p.objetivos_pendientes
                ):
                    p.objetivos_pendientes.remove(p.posicion_actual)
                    if self.turnos_recogida:
                        p.ruta_asignada[0:0] = [
                            p.posicion_actual
                        ] * self.turnos_recogida
                        p.turnos_pausa = self.turnos_recogida

            p.historial_recorrido.append(p.posicion_actual)

            if (
                self.turnos_descarga == 0
                and not p.ruta_asignada
                and p.id_wave_actual is not None
            ):
                wave_terminada = p.id_wave_actual
                p.peso_actual_kg = 0.0
                p.id_wave_actual = None
                if gestor_waves is not None:
                    gestor_waves.notificar_picker_descargo_en_despacho(
                        wave_terminada, p.id_picker, pickers, catalogo
                    )

        return pickers_en_movimiento