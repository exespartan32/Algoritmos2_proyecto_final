from typing import Dict, Hashable, Any


class DisjointNode:
    """Nodo para representar un elemento en un árbol de conjuntos disjuntos."""

    def __init__(self, value: Any):
        self.value = value
        self.parent: "DisjointNode" = self
        self.rank: int = 0


def make_set(x: Any) -> DisjointNode:
    """MAKE-SET(x): Crea un nuevo conjunto cuyo único miembro es x en O(1)."""
    return DisjointNode(x)


def find_set(x: DisjointNode) -> DisjointNode:
    """FIND-SET(x) con Compresión de Caminos (Path Compression)."""
    if x != x.parent:
        x.parent = find_set(x.parent)
    return x.parent


def link(x: DisjointNode, y: DisjointNode) -> bool:
    """LINK(x, y) aplicando Unión por Rango (Union by Rank)."""
    if x == y:
        return False
    if x.rank > y.rank:
        y.parent = x
    else:
        x.parent = y
        if x.rank == y.rank:
            y.rank += 1
    return True


def union(x: DisjointNode, y: DisjointNode) -> bool:
    """UNION(x, y): Une los conjuntos dinámicos que contienen a x e y."""
    return link(find_set(x), find_set(y))


class DisjointSet:
    """
    Estructura de Conjuntos Disjuntos indexada para el algoritmo de Kruskal.
    Opera en tiempo casi constante O(alfa(V)) por operación.
    """

    def __init__(self, n: int = 0):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.nodos_genericos: Dict[Hashable, DisjointNode] = {}

    def crear_conjunto(self, clave: Hashable) -> DisjointNode:
        nodo = make_set(clave)
        self.nodos_genericos[clave] = nodo
        return nodo

    def buscar_representante(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def unir(self, i: int, j: int) -> bool:
        raiz_i = self.buscar_representante(i)
        raiz_j = self.buscar_representante(j)

        if raiz_i == raiz_j:
            return False

        if self.rank[raiz_i] < self.rank[raiz_j]:
            self.parent[raiz_i] = raiz_j
        elif self.rank[raiz_i] > self.rank[raiz_j]:
            self.parent[raiz_j] = raiz_i
        else:
            self.parent[raiz_j] = raiz_i
            self.rank[raiz_i] += 1

        return True
