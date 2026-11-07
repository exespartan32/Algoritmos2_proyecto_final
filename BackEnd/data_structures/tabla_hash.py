"""Tabla hash propia con hashing universal y encadenamiento.

Reemplaza a los diccionarios de Python en el dígrafo del almacén
(``Digrafo.nodos``, ``Digrafo.lista_adyacencia``) y en
``Warehouse.obstaculos``.

Cómo funciona, en tres pasos:

1. La clave se pasa a un número entero ``k``.
   - Una coordenada ``(x, y)`` da ``k = x * BASE + y``. Como ``BASE`` es mucho
     más grande que cualquier ``y`` posible, dos coordenadas distintas nunca dan
     el mismo ``k``.
   - Un texto se convierte con un polinomio sobre sus caracteres.
2. Hashing universal (Carter y Wegman):
       h(k) = ((a * k + b) mod p) mod m
   - ``p`` es un primo más grande que cualquier ``k`` (el primo de Mersenne 2^61 - 1).
   - ``a`` (entre 1 y p-1) y ``b`` (entre 0 y p-1) se eligen al azar UNA vez,
     con una semilla fija, así el programa es determinista.
   - ``m`` es la cantidad de casillas, siempre un número primo.
   Con la familia universal, la probabilidad de que dos claves distintas
   choquen es como mucho 1/m.
3. Colisiones por ENCADENAMIENTO: cada casilla guarda una lista enlazada de
   nodos. Dos claves que caen en la misma casilla quedan en la misma lista.
   Buscar es: calcular h(k), ir a esa casilla y recorrer su lista.

El factor de carga es alfa = n / m. Cuando supera 0,75 la tabla crece al
primo siguiente a 2m y se reinsertan todas las claves (rehashing). Así las
listas quedan cortas y buscar, insertar y borrar cuestan O(1 + alfa) = O(1)
en promedio. El peor caso, si todo cayera en la misma casilla, es O(n).

Además se guarda el ORDEN DE INSERCIÓN en un arreglo aparte (``_entradas``),
como hace el diccionario de Python. Recorrer la tabla (``for clave in tabla``)
siempre da las claves en el orden en que se insertaron, y eso mantiene la
simulación determinista.
"""

import random
from typing import Any, Iterator, List, Optional, Tuple

P_MERSENNE = (1 << 61) - 1  # 2^61 - 1, primo
BASE_COORDENADA = 1_000_003  # primo; mayor que cualquier coordenada posible
_FACTOR_CARGA_MAXIMO = 0.75
_SEMILLA = 318  # fija: el programa es determinista; reparte bien las coordenadas de los escenarios
_VACIO = object()


def es_primo(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def siguiente_primo(n: int) -> int:
    while not es_primo(n):
        n += 1
    return n


class NodoCadena:
    """Un eslabón de la lista enlazada de una casilla."""

    __slots__ = ("clave", "indice", "siguiente")

    def __init__(self, clave: Any, indice: int, siguiente: Optional["NodoCadena"]) -> None:
        self.clave = clave  # la clave original, para comparar
        self.indice = indice  # posición de la entrada en _entradas
        self.siguiente = siguiente  # próximo eslabón o None


class TablaHashUniversal:
    """Tabla hash con hashing universal, encadenamiento y rehashing.

    Se usa igual que un diccionario: ``t[clave] = valor``, ``t[clave]``,
    ``clave in t``, ``t.get(clave)``, ``t.items()``, ``len(t)``.
    """

    def __init__(self, capacidad_inicial: int = 17, semilla: int = _SEMILLA) -> None:
        generador = random.Random(semilla)
        self._a = generador.randrange(1, P_MERSENNE)
        self._b = generador.randrange(0, P_MERSENNE)
        self._m = siguiente_primo(max(7, int(capacidad_inicial)))
        self._casillas: List[Optional[NodoCadena]] = [None] * self._m
        # Entradas en orden de inserción: [clave, valor] o None si se borró.
        self._entradas: List[Optional[list]] = []
        self._n = 0
        self.cantidad_rehash = 0

    # ------------------------------------------------------------------
    # Función hash
    # ------------------------------------------------------------------
    @staticmethod
    def clave_a_entero(clave: Any) -> int:
        """Paso 1: la clave se convierte en un entero k."""
        if type(clave) is tuple and len(clave) == 2 and type(clave[0]) is int and type(clave[1]) is int:
            x, y = clave  # caso más común: una coordenada
            return (x * BASE_COORDENADA + y) % P_MERSENNE
        if isinstance(clave, int):
            return clave % P_MERSENNE
        if isinstance(clave, str):
            k = 0
            for caracter in clave:
                k = (k * 131 + ord(caracter)) % P_MERSENNE
            return k
        if isinstance(clave, tuple):
            k = 0
            for parte in clave:
                k = (k * BASE_COORDENADA + TablaHashUniversal.clave_a_entero(parte)) % P_MERSENNE
            return k
        raise TypeError(f"Tipo de clave no soportado: {type(clave).__name__}")

    def _hash(self, clave: Any) -> int:
        """Paso 2: hashing universal h(k) = ((a·k + b) mod p) mod m."""
        k = self.clave_a_entero(clave)
        return ((self._a * k + self._b) % P_MERSENNE) % self._m

    # ------------------------------------------------------------------
    # Operaciones básicas
    # ------------------------------------------------------------------
    def _buscar(self, clave: Any) -> Optional[NodoCadena]:
        nodo = self._casillas[self._hash(clave)]
        while nodo is not None:
            if nodo.clave == clave:
                return nodo
            nodo = nodo.siguiente
        return None

    def __setitem__(self, clave: Any, valor: Any) -> None:
        nodo = self._buscar(clave)
        if nodo is not None:  # ya estaba: se actualiza el valor
            self._entradas[nodo.indice][1] = valor
            return
        indice = len(self._entradas)
        self._entradas.append([clave, valor])
        i = self._hash(clave)
        # Paso 3: se agrega al principio de la lista enlazada de su casilla.
        self._casillas[i] = NodoCadena(clave, indice, self._casillas[i])
        self._n += 1
        if self._n > _FACTOR_CARGA_MAXIMO * self._m:
            self._rehash(siguiente_primo(2 * self._m))

    def __getitem__(self, clave: Any) -> Any:
        nodo = self._buscar(clave)
        if nodo is None:
            raise KeyError(clave)
        return self._entradas[nodo.indice][1]

    def __delitem__(self, clave: Any) -> None:
        i = self._hash(clave)
        anterior = None
        nodo = self._casillas[i]
        while nodo is not None and nodo.clave != clave:
            anterior, nodo = nodo, nodo.siguiente
        if nodo is None:
            raise KeyError(clave)
        if anterior is None:
            self._casillas[i] = nodo.siguiente
        else:
            anterior.siguiente = nodo.siguiente
        self._entradas[nodo.indice] = None
        self._n -= 1
        if len(self._entradas) > 2 * self._n + 16:  # muchas entradas borradas
            self._rehash(self._m)

    def _rehash(self, nuevo_m: int) -> None:
        """Crea casillas nuevas y vuelve a insertar todo, en el mismo orden."""
        vivas = [e for e in self._entradas if e is not None]
        self._m = nuevo_m
        self._casillas = [None] * self._m
        self._entradas = vivas
        for indice, (clave, _) in enumerate(vivas):
            i = self._hash(clave)
            self._casillas[i] = NodoCadena(clave, indice, self._casillas[i])
        self.cantidad_rehash += 1

    # ------------------------------------------------------------------
    # Interfaz de diccionario (para no cambiar el resto del proyecto)
    # ------------------------------------------------------------------
    def __contains__(self, clave: Any) -> bool:
        return self._buscar(clave) is not None

    def __len__(self) -> int:
        return self._n

    def __iter__(self) -> Iterator[Any]:
        for e in list(self._entradas):
            if e is not None:
                yield e[0]

    def keys(self) -> Iterator[Any]:
        return iter(self)

    def values(self) -> Iterator[Any]:
        for e in list(self._entradas):
            if e is not None:
                yield e[1]

    def items(self) -> Iterator[Tuple[Any, Any]]:
        for e in list(self._entradas):
            if e is not None:
                yield e[0], e[1]

    def get(self, clave: Any, por_defecto: Any = None) -> Any:
        nodo = self._buscar(clave)
        return por_defecto if nodo is None else self._entradas[nodo.indice][1]

    def setdefault(self, clave: Any, por_defecto: Any = None) -> Any:
        nodo = self._buscar(clave)
        if nodo is not None:
            return self._entradas[nodo.indice][1]
        self[clave] = por_defecto
        return por_defecto

    def pop(self, clave: Any, por_defecto: Any = _VACIO) -> Any:
        nodo = self._buscar(clave)
        if nodo is None:
            if por_defecto is _VACIO:
                raise KeyError(clave)
            return por_defecto
        valor = self._entradas[nodo.indice][1]
        del self[clave]
        return valor

    def clear(self) -> None:
        self._casillas = [None] * self._m
        self._entradas = []
        self._n = 0

    def __repr__(self) -> str:
        return f"TablaHashUniversal(n={self._n}, m={self._m}, alfa={self.factor_de_carga():.2f})"

    # ------------------------------------------------------------------
    # Datos para explicar y medir
    # ------------------------------------------------------------------
    def cantidad_casillas(self) -> int:
        return self._m

    def factor_de_carga(self) -> float:
        return self._n / self._m

    def longitudes_de_cadena(self) -> List[int]:
        largos = []
        for nodo in self._casillas:
            largo = 0
            while nodo is not None:
                largo += 1
                nodo = nodo.siguiente
            largos.append(largo)
        return largos
