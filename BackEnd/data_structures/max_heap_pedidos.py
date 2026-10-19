from typing import List, Optional, TYPE_CHECKING
from BackEnd.data_structures.mypriorityqueue import (
    PriorityQueue,
    enqueue_priority,
    dequeue_priority,
    build_priority_queue_O_N,
    is_empty_priority,
)

if TYPE_CHECKING:
    from BackEnd.models.entities import Order


class MaxHeapPedidos:
    """
    Adaptador orientado a objetos sobre PriorityQueue (mypriorityqueue.py)
    para gestionar pedidos pendientes mediante un Montículo Binario de Máximos.
    """

    def __init__(self):
        self.cola = PriorityQueue()

    def construir_monticulo(self, pedidos: List["Order"]) -> None:
        pares = [(p, p.prioridad) for p in pedidos]
        build_priority_queue_O_N(self.cola, pares)

    def insertar(self, pedido: "Order") -> None:
        enqueue_priority(self.cola, pedido, pedido.prioridad)

    def extraer_maximo(self) -> Optional["Order"]:
        return dequeue_priority(self.cola)

    def esta_vacio(self) -> bool:
        return is_empty_priority(self.cola)
