import os
import sqlite3


def conectar_bd(nombre_archivo="database.sqlite"):
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    ruta_data = os.path.join(os.path.dirname(directorio_actual), "data")
    os.makedirs(ruta_data, exist_ok=True)
    ruta_db = os.path.join(ruta_data, nombre_archivo)

    conexion = sqlite3.connect(ruta_db)
    conexion.execute("PRAGMA foreign_keys = ON;")
    return conexion


def inicializar_tablas(conexion):
    cursor = conexion.cursor()

    # 1. Nodos del Almacén (id_nodo servirá como clave primaria y coordenada)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS WarehouseNode (
        id_nodo TEXT PRIMARY KEY,
        tipo TEXT NOT NULL CHECK(tipo IN ('CALLE', 'RACK', 'PUERTA', 'DESPACHO', 'PARED', 'OFICINA'))
    )
    """)

    # 2. Productos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Producto (
        id_producto TEXT PRIMARY KEY,
        nombre TEXT NOT NULL,
        peso REAL NOT NULL
    )
    """)

    # 3. Stock Disperso
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS StockUbicacion (
        id_stock TEXT PRIMARY KEY,
        id_producto TEXT NOT NULL,
        id_nodo TEXT NOT NULL,
        cantidad_disponible INTEGER NOT NULL,
        FOREIGN KEY (id_producto) REFERENCES Producto(id_producto),
        FOREIGN KEY (id_nodo) REFERENCES WarehouseNode(id_nodo)
    )
    """)

    # 4. Pedidos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Pedido (
        id_pedido TEXT PRIMARY KEY,
        fecha TEXT NOT NULL,
        prioridad INTEGER NOT NULL CHECK(prioridad BETWEEN 1 AND 5),
        estado TEXT NOT NULL CHECK(estado IN ('PENDIENTE', 'EN_WAVE', 'EN_PREPARACION', 'PREPARADO'))
    )
    """)

    # 5. Detalles de los Pedidos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS DetallePedido (
        id_detalle TEXT PRIMARY KEY,
        id_pedido TEXT NOT NULL,
        id_producto TEXT NOT NULL,
        cantidad_solicitada INTEGER NOT NULL,
        FOREIGN KEY (id_pedido) REFERENCES Pedido(id_pedido),
        FOREIGN KEY (id_producto) REFERENCES Producto(id_producto)
    )
    """)

    # 6. Recolector (Picker)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Picker (
        id_picker TEXT PRIMARY KEY,
        id_nodo_actual TEXT NOT NULL,
        capacidad_max_peso REAL NOT NULL,
        peso_actual REAL NOT NULL DEFAULT 0.0,
        FOREIGN KEY (id_nodo_actual) REFERENCES WarehouseNode(id_nodo)
    )
    """)

    # 7. Inventario en el carro del Picker
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS PickerProducto (
        id_picker_producto TEXT PRIMARY KEY,
        id_picker TEXT NOT NULL,
        id_producto TEXT NOT NULL,
        cantidad_cargada INTEGER NOT NULL,
        FOREIGN KEY (id_picker) REFERENCES Picker(id_picker),
        FOREIGN KEY (id_producto) REFERENCES Producto(id_producto)
    )
    """)

    # 8. Waves
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Wave (
        id_wave TEXT PRIMARY KEY,
        id_picker TEXT,
        estado TEXT NOT NULL CHECK(estado IN ('PENDIENTE', 'EN_EJECUCION', 'FINALIZADA', 'CANCELADA')),
        capacidad_max_pedidos INTEGER NOT NULL,
        capacidad_max_productos INTEGER NOT NULL,
        capacidad_max_peso REAL NOT NULL,
        FOREIGN KEY (id_picker) REFERENCES Picker(id_picker)
    )
    """)

    # 9. Pedidos asignados a una Wave
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS WavePedido (
        id_wave_pedido TEXT PRIMARY KEY,
        id_wave TEXT NOT NULL,
        id_pedido TEXT NOT NULL,
        FOREIGN KEY (id_wave) REFERENCES Wave(id_wave),
        FOREIGN KEY (id_pedido) REFERENCES Pedido(id_pedido)
    )
    """)

    # 10. Estado de la Simulación
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Simulacion (
        id_simulacion INTEGER PRIMARY KEY AUTOINCREMENT,
        estado TEXT NOT NULL CHECK(estado IN ('DETENIDO', 'EJECUTANDO', 'PAUSADO', 'FINALIZADO')),
        estrategia_activa TEXT NOT NULL DEFAULT 'ORDEN_PEDIDO',
        velocidad REAL NOT NULL DEFAULT 1.0
    )
    """)

    # 11. Métricas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS MetricaSimulacion (
        id_metrica INTEGER PRIMARY KEY AUTOINCREMENT,
        id_wave TEXT NOT NULL,
        estrategia TEXT NOT NULL,
        distancia_total REAL NOT NULL,
        nodos_visitados INTEGER NOT NULL,
        tiempo_ejecucion_ms REAL NOT NULL,
        FOREIGN KEY (id_wave) REFERENCES Wave(id_wave)
    )
    """)

    conexion.commit()
    print("Base de datos inicializada correctamente.")


if __name__ == "__main__":
    conn = conectar_bd()
    inicializar_tablas(conn)
    conn.close()
