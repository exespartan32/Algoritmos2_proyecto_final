"""
from modelos.entidades import Producto
from modelos.inventario import InventarioManager

# 1. Instanciamos el inventario
inventario = InventarioManager()

# 2. Creamos un producto
p1 = Producto(id_producto="P-001", nombre="Caja de Tornillos", peso=1.5)
inventario.registrar_producto(p1)

# 3. Simulamos la dispersión: Guardamos el mismo producto en racks muy alejados
inventario.agregar_stock("P-001", id_nodo="2,2,1", cantidad=5)  # Rack cercano
inventario.agregar_stock("P-001", id_nodo="18,15,3", cantidad=20)  # Rack lejano

# 4. Consulta de O(1) cuando llega un pedido
ubicaciones_disponibles = inventario.buscar_ubicaciones("P-001")
print(f"Ubicaciones con stock de P-001: {ubicaciones_disponibles}")
"""

from modelos.grafo import GrafoWarehouse
from modelos.entidades import Picker, Producto
from algoritmos.pathfinding import PathfindingService

# 1. PRIMERO: Crear la instancia del almacén (Esto define la variable 'almacen')
almacen = GrafoWarehouse()

# (Aquí deberías cargar tu matriz o generar la cuadrícula base del almacén)
# almacen.generar_cuadricula_base(20, 20)
# almacen.conectar_pasillos()

# 2. SEGUNDO: Crear el operario
operario = Picker(id_picker="Picker-01", id_nodo_inicial="0,0,0", capacidad_max=50.0)

# 3. TERCERO: Crear el enrutador pasándole la variable 'almacen' que ya existe
# Forma posicional (recomendada):
enrutador = PathfindingService(almacen)

# O especificando el nombre correcto del argumento:
enrutador = PathfindingService(grafo_warehouse=almacen)
