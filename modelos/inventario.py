class InventarioManager:
    def __init__(self):
        # Tabla Hash principal
        # Estructura esperada: { id_producto: { id_nodo: cantidad, id_nodo2: cantidad } }
        self.stock_ubicacion = {}
        # Tabla Hash secundaria para guardar los metadatos del producto (nombre, peso, etc.)
        self.productos_info = {}

    def registrar_producto(self, producto):
        """Guarda la información base del producto en O(1)."""
        self.productos_info[producto.id_producto] = producto
        # Inicializamos su entrada en la tabla de stock si no existe
        if producto.id_producto not in self.stock_ubicacion:
            self.stock_ubicacion[producto.id_producto] = {}

    def agregar_stock(self, id_producto, id_nodo, cantidad):
        """
        Añade stock de un producto en un nodo específico (Rack).
        Si el producto ya existía en ese nodo, suma la cantidad.
        """
        if id_producto not in self.stock_ubicacion:
            self.stock_ubicacion[id_producto] = {}

        ubicaciones = self.stock_ubicacion[id_producto]

        if id_nodo in ubicaciones:
            ubicaciones[id_nodo] += cantidad
        else:
            ubicaciones[id_nodo] = cantidad

    def buscar_ubicaciones(self, id_producto):
        """
        Retorna un diccionario con todos los nodos donde hay stock disponible.
        Tiempo de ejecución: O(1) promedio gracias a la Tabla Hash.
        """
        ubicaciones = self.stock_ubicacion.get(id_producto, {})
        # Filtramos para devolver solo los nodos que tengan stock > 0
        return {nodo: cant for nodo, cant in ubicaciones.items() if cant > 0}

    def extraer_stock(self, id_producto, id_nodo, cantidad_requerida):
        """
        Simula la acción del picker tomando el producto del estante.
        Retorna True si pudo extraerlo, False si no hay stock suficiente en ese nodo.
        """
        ubicaciones = self.stock_ubicacion.get(id_producto, {})

        if id_nodo in ubicaciones and ubicaciones[id_nodo] >= cantidad_requerida:
            ubicaciones[id_nodo] -= cantidad_requerida
            return True

        return False
