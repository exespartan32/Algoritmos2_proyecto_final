class PriorityNode:
    def __init__(self, value=None, priority=None, orden_llegada: int = 0):
        self.value = value
        self.nextNode = None
        self.priority = priority
        self.orden_llegada = orden_llegada


class PriorityQueue:
    def __init__(self):
        self.head = None
        self._heap = []
        self._contador = 0


def _es_mayor_prioridad(nodo_a: PriorityNode, nodo_b: PriorityNode) -> bool:
    if nodo_a.priority != nodo_b.priority:
        return nodo_a.priority > nodo_b.priority
    id_a = getattr(nodo_a.value, "id_pedido", None)
    id_b = getattr(nodo_b.value, "id_pedido", None)
    if id_a is not None and id_b is not None and id_a != id_b:
        return id_a < id_b
    return nodo_a.orden_llegada < nodo_b.orden_llegada


def _sift_up(heap: list, idx: int) -> None:
    nodo = heap[idx]
    while idx > 0:
        padre_idx = (idx - 1) >> 1
        padre = heap[padre_idx]
        if _es_mayor_prioridad(nodo, padre):
            heap[idx] = padre
            idx = padre_idx
        else:
            break
    heap[idx] = nodo


def _max_heapify(heap: list, idx: int) -> None:
    n = len(heap)
    nodo = heap[idx]
    mitad = n >> 1

    while idx < mitad:
        izq = (idx << 1) + 1
        der = izq + 1
        mayor = izq

        if der < n and _es_mayor_prioridad(heap[der], heap[izq]):
            mayor = der

        if _es_mayor_prioridad(heap[mayor], nodo):
            heap[idx] = heap[mayor]
            idx = mayor
        else:
            break

    heap[idx] = nodo


def enqueue_priority(Q: PriorityQueue, element, priority: int) -> None:
    """Inserta un elemento según su prioridad en O(log N)."""
    Q._contador += 1
    newNode = PriorityNode(value=element, priority=priority, orden_llegada=Q._contador)
    Q._heap.append(newNode)
    _sift_up(Q._heap, len(Q._heap) - 1)
    Q.head = Q._heap[0]


def dequeue_priority(Q: PriorityQueue):
    """Extrae y retorna el elemento de mayor prioridad en O(log N)."""
    if not Q._heap:
        Q.head = None
        return None

    max_node = Q._heap[0]
    ultimo = Q._heap.pop()

    if Q._heap:
        Q._heap[0] = ultimo
        _max_heapify(Q._heap, 0)
        Q.head = Q._heap[0]
    else:
        Q.head = None

    return max_node.value


def build_priority_queue_O_N(Q: PriorityQueue, pares_elemento_prioridad: list) -> None:
    """Construye el Max-Heap en tiempo lineal O(N) (BUILD-MAX-HEAP)."""
    Q._heap.clear()
    for elem, prio in pares_elemento_prioridad:
        Q._contador += 1
        Q._heap.append(
            PriorityNode(value=elem, priority=prio, orden_llegada=Q._contador)
        )

    n = len(Q._heap)
    for i in range((n // 2) - 1, -1, -1):
        _max_heapify(Q._heap, i)

    Q.head = Q._heap[0] if Q._heap else None


def is_empty_priority(Q: PriorityQueue) -> bool:
    return len(Q._heap) == 0
