class LinkedList:
    def __init__(self):
        self.head = None
        self.size = 0


class Node:
    def __init__(self, value=None, nextNode=None):
        self.value = value
        self.nextNode = nextNode


def add(L: LinkedList, element):
    """Inserta un nuevo nodo al comienzo (head) de la lista en O(1)."""
    newNode = Node(value=element, nextNode=L.head)
    L.head = newNode
    L.size += 1


def search(L: LinkedList, element):
    """Busca un elemento y devuelve su posición o None."""
    i = L.head
    position = 0
    while i is not None:
        if i.value == element:
            return position
        i = i.nextNode
        position += 1
    return None


def insert(L: LinkedList, element, position: int):
    """Inserta un elemento en una posición específica en O(position)."""
    if position < 0 or position > L.size:
        return None
    if position == 0:
        add(L, element)
        return 0

    positionList = 0
    current = L.head
    while current is not None and positionList < position - 1:
        current = current.nextNode
        positionList += 1

    if current is None:
        return None

    newNode = Node(value=element, nextNode=current.nextNode)
    current.nextNode = newNode
    L.size += 1
    return position


def delete(L: LinkedList, element):
    """Elimina la primera aparición del elemento en O(N)."""
    if element is None or L.head is None:
        return None

    i = L.head
    prev = None
    pos = 0
    while i is not None:
        if i.value == element:
            if prev is None:
                L.head = i.nextNode
            else:
                prev.nextNode = i.nextNode
            L.size -= 1
            return pos
        prev = i
        i = i.nextNode
        pos += 1
    return None


def length(L: LinkedList) -> int:
    """Devuelve la cantidad de elementos en O(1)."""
    return L.size


def access(L: LinkedList, position: int):
    """Accede al elemento en la posición indicada con corte temprano."""
    if position < 0 or position >= L.size:
        return None
    positionList = 0
    i = L.head
    while i is not None:
        if positionList == position:
            return i.value
        positionList += 1
        i = i.nextNode
    return None


def update(L: LinkedList, element, position: int):
    """Actualiza el elemento en la posición indicada."""
    if position < 0 or position >= L.size:
        return None
    i = L.head
    positionList = 0
    while i is not None:
        if positionList == position:
            i.value = element
            return position
        positionList += 1
        i = i.nextNode
    return None
