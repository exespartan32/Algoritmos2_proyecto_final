from enum import Enum


class TipoNodo(Enum):
    CALLE = 0
    RACK = 1
    PUERTA = 2
    DESPACHO = 3
    PARED = 4
    OFICINA = 5


class WarehouseNode:
    def __init__(self, x, y, z, tipo):
        self.id_nodo = f"{x},{y},{z}"
        self.x = x
        self.y = y
        self.z = z
        self.tipo = tipo
        self.vecinos = []

    def agregar_vecino(self, nodo):
        self.vecinos.append(nodo)

    def es_transitable(self):
        return self.tipo in [TipoNodo.CALLE, TipoNodo.DESPACHO, TipoNodo.PUERTA]


class Producto:
    def __init__(self, id_producto, nombre, peso):
        self.id_producto = id_producto
        self.nombre = nombre
        self.peso = peso


class Picker:
    def __init__(self, id_picker, id_nodo_inicial, capacidad_max):
        self.id_picker = id_picker
        self.id_nodo_actual = id_nodo_inicial  # Ubicación X,Y,Z actual del operario
        self.capacidad_max = capacidad_max
        self.peso_actual = 0.0
        self.productos_cargados = (
            {}
        )  # Equivalente a la tabla PickerProducto {id_producto: cantidad}

    def evaluar_carga(self, peso_item, cantidad):
        """Devuelve True si el picker puede soportar el peso adicional."""
        peso_futuro = self.peso_actual + (peso_item * cantidad)
        return peso_futuro <= self.capacidad_max

    def recoger_producto(self, producto, cantidad):
        """Suma el peso y guarda el producto en el carro si hay capacidad."""
        if self.evaluar_carga(producto.peso, cantidad):
            self.peso_actual += producto.peso * cantidad
            # Acumulamos la cantidad si ya tenía este producto, o lo creamos
            if producto.id_producto in self.productos_cargados:
                self.productos_cargados[producto.id_producto] += cantidad
            else:
                self.productos_cargados[producto.id_producto] = cantidad
            return True
        return False

    def actualizar_ubicacion(self, id_nuevo_nodo):
        self.id_nodo_actual = id_nuevo_nodo
