import random
from typing import List, Tuple
from BackEnd.models.entity import StockUbicacion


class InventoryManager:
    def __init__(self, tamano_tabla: int = 1009):
        """
        Implementa Tabla Hash con Encadenamiento (Chaining) y Función Universal.
        Permite que la cantidad de productos (n) supere libremente al tamaño de la tabla (m).
        """
        self.m = tamano_tabla

        # p debe ser un número primo estrictamente mayor que m (p > m) y
        # mayor que el tamaño del universo de claves posibles. Usamos un primo grande.
        self.p = 999983

        # Hashing Universal: a pertenece a {1, ..., p-1} y b pertenece a {0, ..., p-1}
        self.a = random.randint(1, self.p - 1)
        self.b = random.randint(0, self.p - 1)

        # Tabla implementada como un Array de Listas (Chaining)
        # Cada celda almacena una tupla: (id_producto, [lista_de_ubicaciones])
        self.tabla_hash: List[List[Tuple[str, List[StockUbicacion]]]] = [
            [] for _ in range(self.m)
        ]

    def _convertir_string_a_int(self, key: str) -> int:
        """
        Convierte la cadena de texto (ID del producto) a un número entero
        utilizando sus valores ASCII posicionales (Base 128).
        """
        hash_val = 0
        for i, char in enumerate(reversed(key)):
            hash_val += (128**i) * ord(char)
        return hash_val

    def _hash_universal(self, k_string: str) -> int:
        """
        Aplica la familia de funciones de hash universal:
        h_ab(k) = ((a * k + b) mod p) mod m
        """
        k = self._convertir_string_a_int(k_string)
        return ((self.a * k + self.b) % self.p) % self.m

    def cargar_stock_desde_bd(self, lista_stock_total: List[StockUbicacion]):
        """
        Itera sobre todos los registros extraídos de la Base de Datos y los agrupa.
        Si el producto ya existe en la lista enlazada, añade la nueva ubicación.
        """
        # Limpiamos la tabla en caso de recargar datos dinámicamente
        self.tabla_hash = [[] for _ in range(self.m)]

        for stock in lista_stock_total:
            posicion = self._hash_universal(stock.id_producto)
            cadena = self.tabla_hash[posicion]

            encontrado = False

            # Recorremos la lista enlazada de ese índice particular
            for i, (prod_id, ubicaciones) in enumerate(cadena):
                if prod_id == stock.id_producto:
                    # El producto ya fue registrado, anexamos el stock disperso
                    ubicaciones.append(stock)
                    encontrado = True
                    break

            if not encontrado:
                # Si el producto no estaba en la cadena, lo insertamos al final
                cadena.append((stock.id_producto, [stock]))

    def buscar_producto_O1(self, id_producto: str) -> List[StockUbicacion]:
        """
        Busca todas las ubicaciones de un producto en tiempo Theta(1 + alfa).
        Retorna la lista de coordenadas donde hay stock disponible para armar las Waves.
        """
        posicion = self._hash_universal(id_producto)
        cadena = self.tabla_hash[posicion]

        # Búsqueda lineal dentro de la pequeña lista de colisiones
        for prod_id, ubicaciones in cadena:
            if prod_id == id_producto:
                return ubicaciones

        # Si el producto no está en el almacén, retorna lista vacía
        return []
