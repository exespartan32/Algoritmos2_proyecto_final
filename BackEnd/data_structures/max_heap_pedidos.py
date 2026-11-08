from typing import List, Optional

from BackEnd.models.entities import Pedido


class MaxHeapPedidos:
    """Cola de prioridad sobre un montículo binario de máximos (Max-Heap).

    Construye el montículo en O(N) y extrae el pedido de mayor prioridad en O(log N).
    """

    def __init__(self) -> None:
        self._heap: List[Pedido] = []

    def _parent(self, i: int) -> int:
        return (i - 1) >> 1

    def _left(self, i: int) -> int:
        return (i << 1) + 1

    def _right(self, i: int) -> int:
        return (i << 1) + 2

    def esta_vacio(self) -> bool:
        return len(self._heap) == 0

    def tamano(self) -> int:
        return len(self._heap)

    def _tiene_mayor_prioridad(self, a: Pedido, b: Pedido) -> bool:
        """Prioriza mayor número (5 a 1) y desempata por menor ID de pedido."""
        if a.prioridad != b.prioridad:
            return a.prioridad > b.prioridad
        return a.id_pedido < b.id_pedido

    def construir_monticulo(self, pedidos: List[Pedido]) -> None:
        self._heap = list(pedidos)
        n = len(self._heap)
        for i in range((n // 2) - 1, -1, -1):
            self._max_heapify(i)

    def insertar(self, pedido: Pedido) -> None:
        self._heap.append(pedido)
        i = len(self._heap) - 1
        while i > 0 and self._tiene_mayor_prioridad(
            self._heap[i], self._heap[self._parent(i)]
        ):
            padre = self._parent(i)
            self._heap[i], self._heap[padre] = self._heap[padre], self._heap[i]
            i = padre

    def extraer_maximo(self) -> Optional[Pedido]:
        if self.esta_vacio():
            return None
        if len(self._heap) == 1:
            return self._heap.pop()

        maximo = self._heap[0]
        self._heap[0] = self._heap.pop()
        self._max_heapify(0)
        return maximo

    def eliminar_pedido(self, id_pedido: str) -> bool:
        """Quita un pedido específico del montículo y restaura la propiedad de orden."""
        idx = -1
        for i, p in enumerate(self._heap):
            if p.id_pedido == id_pedido:
                idx = i
                break

        if idx == -1:
            return False

        ultimo = self._heap.pop()
        if idx < len(self._heap):
            self._heap[idx] = ultimo
            padre = self._parent(idx)
            if idx > 0 and self._tiene_mayor_prioridad(
                self._heap[idx], self._heap[padre]
            ):
                while idx > 0 and self._tiene_mayor_prioridad(
                    self._heap[idx], self._heap[self._parent(idx)]
                ):
                    p_idx = self._parent(idx)
                    self._heap[idx], self._heap[p_idx] = (
                        self._heap[p_idx],
                        self._heap[idx],
                    )
                    idx = p_idx
            else:
                self._max_heapify(idx)
        return True

    def obtener_candidatos_factibles(self, capacidad_restante: int) -> List[Pedido]:
        """Devuelve los pedidos en espera cuyas unidades entran en el cupo restante de la wave."""
        return [
            p
            for p in self._heap
            if p.obtener_cantidad_productos() <= capacidad_restante
        ]

    def _max_heapify(self, i: int) -> None:
        l = self._left(i)
        r = self._right(i)
        n = len(self._heap)
        largest = i

        if l < n and self._tiene_mayor_prioridad(self._heap[l], self._heap[largest]):
            largest = l
        if r < n and self._tiene_mayor_prioridad(self._heap[r], self._heap[largest]):
            largest = r

        if largest != i:
            self._heap[i], self._heap[largest] = self._heap[largest], self._heap[i]
            self._max_heapify(largest)
