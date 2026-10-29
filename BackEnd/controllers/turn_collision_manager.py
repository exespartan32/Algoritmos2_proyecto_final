from typing import Dict, List, Tuple, Set, Optional, Any
from BackEnd.models.entities import ListaDeInmutables, Picker
from BackEnd.controllers.path_finding import Pathfinding

CoordXY = Tuple[int, int]


class TurnAndCollisionManager:
    """
    Gestor de Turnos y Evasión de Colisiones Multi-Picker sobre el Dígrafo.
    Previene:
    1. Colisiones de vértice (misma celda destino en t + 1).
    2. Head-on Deadlocks (intercambio de aristas u <-> v en t + 1).
    3. Colisiones en cadena (alcance trasero cuando un picker frena).
    4. Livelocks / Bloqueos cíclicos (recálculo con Dijkstra tras X turnos bloqueado).
    """

    def __init__(
        self,
        max_turnos_bloqueo_recalculo: int = 2,
        turnos_estela: int = 2,
        turnos_recogida: int = 2,
        turnos_descarga: int = 2,
    ) -> None:
        self.reservas_celdas: Dict[Tuple[int, int, int], str] = {}
        self.pathfinding = Pathfinding()
        self.max_turnos_bloqueo_recalculo = max_turnos_bloqueo_recalculo
        self.turnos_para_ceder = max_turnos_bloqueo_recalculo + 1
        # Estela: la celda que un picker acaba de dejar queda bloqueada para
        # los demás durante ``turnos_estela`` turnos. Así nadie camina pegado
        # detrás de otro: entre dos pickers siempre queda espacio.
        self.turnos_estela = max(0, int(turnos_estela))
        self.estela: Dict[CoordXY, Tuple[str, int]] = {}
        # Tiempo que el picker se queda quieto al recoger y al descargar.
        self.turnos_recogida = max(0, int(turnos_recogida))
        self.turnos_descarga = max(0, int(turnos_descarga))
        self.eventos_colision: List[str] = ListaDeInmutables()
        self.total_esperas_aplicadas: int = 0
        self.total_desvios_recalculados: int = 0

    def detectar_cruce_o_colision(self, p1: Picker, p2: Picker) -> bool:
        sig_p1 = p1.ruta_asignada[0] if p1.ruta_asignada else p1.posicion_actual
        sig_p2 = p2.ruta_asignada[0] if p2.ruta_asignada else p2.posicion_actual

        # 1. Colisión en la misma celda destino
        if sig_p1 == sig_p2:
            return True

        # 2. Cruce frontal de aristas (intercambio de posiciones A <-> B)
        if sig_p1 == p2.posicion_actual and sig_p2 == p1.posicion_actual:
            return True

        return False

    def _buscar_celda_evasion_lateral(
        self,
        picker: Picker,
        celdas_prohibidas: Set[CoordXY],
        grafo: Any,
    ) -> Optional[CoordXY]:
        """
        Busca una celda vecina válida en el dígrafo que no esté ocupada ni prohibida
        para destrabar un cruce frontal (Head-on Deadlock).
        """
        vecinos = Pathfinding._obtener_vecinos(
            grafo, picker.posicion_actual, paso_tiempo=0, picker_id=picker.id_picker
        )
        for v in vecinos:
            if v not in celdas_prohibidas:
                return v
        return None

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
            # Caso 1: Head-on Deadlock. Intentar que el cedente esquive a una celda lateral
            celda_escape = self._buscar_celda_evasion_lateral(
                picker_cedente, prohibidas, grafo
            )
            if celda_escape is not None:
                nueva_ruta = Pathfinding.desviar_por(picker_cedente, celda_escape, grafo)
                if nueva_ruta:
                    picker_cedente.ruta_asignada = nueva_ruta
                    self.total_desvios_recalculados += 1
                    self.eventos_colision.append(
                        f"[Turno {paso_actual}] Head-on Deadlock evitado: {picker_cedente.id_picker} "
                        f"cede paso lateralmente hacia {celda_escape} ante {picker_prioritario.id_picker}."
                    )
                    return

            # Si el cedente está encajonado, probar si el prioritario puede correrse a un costado
            prohibidas_prio = (ocupadas_actuales or set()) | {
                sig_ced,
                picker_cedente.posicion_actual,
            }
            escape_prio = self._buscar_celda_evasion_lateral(
                picker_prioritario, prohibidas_prio, grafo
            )
            if escape_prio is not None and picker_prioritario.ruta_asignada:
                nueva_ruta = Pathfinding.desviar_por(picker_prioritario, escape_prio, grafo)
                if nueva_ruta:
                    picker_prioritario.ruta_asignada = nueva_ruta
                    self.total_desvios_recalculados += 1
                    return

        # Caso 2: Colisión hacia la misma celda o bloqueo prolongado (> X turnos)
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
                f"[Turno {paso_actual}] Recálculo anti-livelock en {picker_cedente.id_picker} "
                f"tras {picker_cedente.turnos_bloqueado} turnos bloqueado."
            )
        else:
            # Pausa coordinada de 1 turno (Wait-Step) en su posición actual
            if (
                not picker_cedente.ruta_asignada
                or picker_cedente.ruta_asignada[0] != picker_cedente.posicion_actual
            ):
                picker_cedente.ruta_asignada.insert(0, picker_cedente.posicion_actual)
                self.total_esperas_aplicadas += 1
                self.eventos_colision.append(
                    f"[Turno {paso_actual}] {picker_cedente.id_picker} espera en "
                    f"{picker_cedente.posicion_actual} cediendo paso a {picker_prioritario.id_picker} en {sig_prio}."
                )

    def validar_movimiento_simultaneo(
        self, pickers: List[Picker], paso_actual: int, grafo: Any
    ) -> None:
        """
        Orquesta las intenciones de movimiento de todos los pickers activos en el turno:
        - Ordena por prioridad dinámica (los pickers que llevan más turnos esperando tienen prioridad
          para evitar inanición/livelock).
        - Resuelve colisiones directas, cruces frontales y colisiones en cadena (efecto dominó).
        """
        if hasattr(grafo, "limpiar_bloqueos_antiguos"):
            grafo.limpiar_bloqueos_antiguos(paso_actual)
        # Las reservas de turnos que ya pasaron no se usan más.
        self.reservas_celdas = {
            k: v for k, v in self.reservas_celdas.items() if k[2] > paso_actual
        }
        self.estela = {c: v for c, v in self.estela.items() if v[1] > paso_actual}
        estela_de = {c: pid for c, (pid, _) in self.estela.items()}

        pickers_activos = [
            p for p in pickers if p.id_wave_actual is not None or p.ruta_asignada
        ]
        # Los pickers libres quedan estacionados: son obstáculos para los demás.
        ids_activos = {id(p) for p in pickers_activos}
        estacionados = {
            p.posicion_actual: p for p in pickers if id(p) not in ids_activos
        }
        if not pickers_activos:
            return
        # Si un picker libre estorba a otro que lleva 2 turnos esperando, se
        # corre a una celda vecina libre para dejarlo pasar.
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
                # El libre no tiene adónde correrse. Si lo que le falta al otro
                # es solo llegar a su celda de descarga y ya está pegado a la
                # misma zona de despacho, descarga desde donde está.
                faltan = [c for c in p.ruta_asignada if c != p.posicion_actual]
                nodos = getattr(grafo, "nodos", {})
                aca = nodos.get(p.posicion_actual)
                destino = nodos.get(proxima)
                if (
                    faltan == [proxima]
                    and aca is not None
                    and destino is not None
                    and set(aca.zonas_despacho_adyacentes) & set(destino.zonas_despacho_adyacentes)
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

        # Ordenar por prioridad anti-starvation: mayor turnos_bloqueado primero, luego menor ruta restante
        pickers_ordenados = sorted(
            pickers_activos,
            key=lambda p: (-p.turnos_bloqueado, len(p.ruta_asignada), p.id_picker),
        )

        ocupadas_actuales = {p.posicion_actual for p in pickers_activos} | set(estacionados)
        # Para los desvíos, la estela de cada picker también cuenta como ocupada.
        ocupadas_actuales |= set(estela_de)

        # Pasada 1: Resolver conflictos entre pares usando resolver_conflicto
        for i in range(len(pickers_ordenados)):
            for j in range(i + 1, len(pickers_ordenados)):
                p_prio = pickers_ordenados[i]
                p_ced = pickers_ordenados[j]
                if self.detectar_cruce_o_colision(p_prio, p_ced):
                    self.resolver_conflicto(
                        p_prio, p_ced, grafo, paso_actual, ocupadas_actuales
                    )

        por_id = {p.id_picker: p for p in pickers}

        # Pasada 2 (Punto Fijo anti-Efecto Dominó):
        # Si un picker frenó en su celda actual, ningún otro picker puede entrar a esa celda en este turno
        cambio = True
        iteraciones = 0
        while cambio and iteraciones < len(pickers_ordenados) + 2:
            cambio = False
            iteraciones += 1
            celdas_reservadas_turno: Dict[CoordXY, Picker] = {}

            # Primero fijar a los que están quietos (sin ruta o esperando en su lugar)
            for p in pickers_ordenados:
                sig = p.ruta_asignada[0] if p.ruta_asignada else p.posicion_actual
                if sig == p.posicion_actual:
                    celdas_reservadas_turno[sig] = p
            # Nadie entra a una celda ocupada, aunque el que está ahí se vaya en
            # este mismo turno: así no se camina "pegado" detrás de otro.
            for p in pickers_ordenados:
                if p.posicion_actual not in celdas_reservadas_turno:
                    celdas_reservadas_turno[p.posicion_actual] = p
            for celda, p in estacionados.items():
                celdas_reservadas_turno.setdefault(celda, p)
            # Las celdas de la estela quedan reservadas para su dueño.
            for celda, pid in estela_de.items():
                if celda not in celdas_reservadas_turno and pid in por_id:
                    celdas_reservadas_turno[celda] = por_id[pid]

            # Luego validar a los que intentan avanzar
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
                    # Último recurso: un picker libre que no pudo correrse no
                    # puede trabar la simulación; se lo atraviesa.
                    celdas_reservadas_turno[sig] = p
                elif ocupante is not None and ocupante is not p:
                    # La celda está ocupada por alguien con mayor prioridad o que frenó adelante
                    p.ruta_asignada.insert(0, p.posicion_actual)
                    celdas_reservadas_turno[p.posicion_actual] = p
                    self.total_esperas_aplicadas += 1
                    cambio = True
                else:
                    celdas_reservadas_turno[sig] = p

        # Pasada 3 (anti-atasco): si un picker lleva varios turnos sin poder
        # avanzar y ni siquiera el recálculo encontró desvío (por ejemplo, una
        # fila de pickers trabada en un pasillo), cede el lugar: se corre a una
        # celda vecina libre y desde ahí retoma la ruta hacia su próximo
        # producto. Así se rompen los ciclos de espera (deadlocks).
        reservadas = {
            (p.ruta_asignada[0] if p.ruta_asignada else p.posicion_actual)
            for p in pickers_ordenados
        }
        for p in pickers_ordenados:
            if (
                not p.ruta_asignada
                or p.ruta_asignada[0] != p.posicion_actual
                or p.turnos_bloqueado < self.turnos_para_ceder
            ):
                continue
            mejor: Optional[List[CoordXY]] = None
            for vecino in Pathfinding._obtener_vecinos(grafo, p.posicion_actual, 0):
                if vecino in reservadas or vecino in ocupadas_actuales:
                    continue
                ruta = Pathfinding.desviar_por(p, vecino, grafo)
                if ruta and (mejor is None or len(ruta) < len(mejor)):
                    mejor = ruta
            if mejor is not None:
                reservadas.discard(p.posicion_actual)
                reservadas.add(mejor[0])
                p.ruta_asignada = mejor
                self.total_desvios_recalculados += 1
                self.eventos_colision.append(
                    f"[Turno {paso_actual}] {p.id_picker} cede el lugar hacia {mejor[0]} "
                    f"para destrabar un atasco ({p.turnos_bloqueado} turnos sin avanzar)."
                )

        # Registrar reservas definitivas del turno t + 1
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
        """
        Ejecuta 1 tick completo de la simulación paso a paso:
        1. Activa la siguiente Wave de la cola para los Pickers que estén en Despacho con 0 kg.
        2. Valida colisiones y cruces simultáneos.
        3. Mueve cada Picker 1 celda a lo largo de su ruta_asignada.
        4. Al terminar su recorrido en la Zona de Despacho, descarga el peso a 0 kg y cierra su tarea.
        Retorna la cantidad de Pickers que siguen en movimiento.
        """
        # 1. Asignar siguiente tarea de la cola a pickers libres (Prohibición de mezcla de Waves)
        for p in pickers:
            if p.id_wave_actual is None and p.cola_waves_asignadas:
                p.iniciar_siguiente_tarea_en_cola()

        # 2. Resolver colisiones antes de dar el paso
        self.validar_movimiento_simultaneo(pickers, paso_actual, grafo)

        pickers_en_movimiento = 0

        # 3. Efectuar el movimiento físico de 1 celda
        for p in pickers:
            if not p.ruta_asignada:
                if p.id_wave_actual is not None:
                    # En la Zona de Despacho: descarga durante turnos_descarga turnos.
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
                if p.turnos_pausa > 0:
                    p.turnos_pausa -= 1  # está recogiendo, no bloqueado
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
                    # Se frena a recoger: espera en su celda unos turnos.
                    if self.turnos_recogida:
                        p.ruta_asignada[0:0] = [p.posicion_actual] * self.turnos_recogida
                        p.turnos_pausa = self.turnos_recogida

            p.historial_recorrido.append(p.posicion_actual)

            # Sin tiempo de descarga, descarga en el mismo turno en que llega.
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
