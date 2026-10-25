from enum import Enum


class EstadoSimulacion(Enum):
    DETENIDO = "DETENIDO"
    EJECUTANDO = "EJECUTANDO"
    PAUSADO = "PAUSADO"
    PASO_A_PASO = "PASO_A_PASO"
    FINALIZADO = "FINALIZADO"


class EstrategiaRuteo(Enum):
    ORDEN_PEDIDOS_DIJKSTRA = "ORDEN_PEDIDOS_DIJKSTRA"
    CERCANIA_DIJKSTRA_MULTIDESTINO = "CERCANIA_DIJKSTRA_MULTIDESTINO"


class TipoCelda(Enum):
    PASILLO = "PASILLO"
    RACK = "RACK"
    PUERTA = "PUERTA"
    ZONA_DESPACHO = "ZONA_DESPACHO"


class SentidoCirculacion(Enum):
    N = "N"
    S = "S"
    E = "E"
    O = "O"
    AMBOS = "AMBOS"
    NINGUNO = "NINGUNO"


class TipoPuerta(Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"
    AMBOS = "AMBOS"


class EstadoPedido(Enum):
    PENDIENTE = "PENDIENTE"
    EN_WAVE = "EN_WAVE"
    EN_PREPARACION = "EN_PREPARACION"
    PREPARADO = "PREPARADO"
    IRREALIZABLE = "IRREALIZABLE"


class EstadoWave(Enum):
    PENDIENTE = "PENDIENTE"
    EN_EJECUCION = "EN_EJECUCION"
    FINALIZADA = "FINALIZADA"
    CANCELADA = "CANCELADA"
