# main.py
from BackEnd.config.db_config import conectar_bd, inicializar_tablas


def main():
    print("Iniciando Sistema de Wave Picking...")

    # 1. Preparar Base de Datos
    conexion = conectar_bd()
    inicializar_tablas(conexion)

    # Aquí irá el resto de tu lógica para inicializar Pygame, el Grafo, etc.

    # Cerrar conexión al finalizar (por ahora lo ponemos aquí)
    conexion.close()


if __name__ == "__main__":
    main()
