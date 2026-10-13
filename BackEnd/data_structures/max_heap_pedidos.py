from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from BackEnd.models.entities import Order


class MaxHeapPedidos:
    def __init__(self):
        self._heap: List["Order"] = []

    def _parent(self, i: int) -> int:
        return (i - 1) // 2

    def _left(self, i: int) -> int:
        return 2 * i + 1

    def _right(self, i: int) -> int:
        return 2 * i + 2

    def esta_vacio(self) -> bool:
        return len(self._heap) == 0

    def insertar(self, pedido: "Order") -> None:
        self._heap.append(pedido)
        i = len(self._heap) - 1
        while i > 0 and self._heap[self._parent(i)].prioridad < self._heap[i].prioridad:
            padre = self._parent(i)
            self._heap[i], self._heap[padre] = self._heap[padre], self._heap[i]
            i = padre

    def extraer_maximo(self) -> Optional["Order"]:
        if self.esta_vacio():
            return None
        if len(self._heap) == 1:
            return self._heap.pop()

        maximo = self._heap[0]
        self._heap[0] = self._heap.pop()
        self._max_heapify(0)
        return maximo

    def _max_heapify(self, i: int) -> None:
        l = self._left(i)
        r = self._right(i)
        n = len(self._heap)
        largest = i

        if l < n and self._heap[l].prioridad > self._heap[largest].prioridad:
            largest = l
        if r < n and self._heap[r].prioridad > self._heap[largest].prioridad:
            largest = r

        if largest != i:
            self._heap[i], self._heap[largest] = self._heap[largest], self._heap[i]
            self._max_heapify(largest)
