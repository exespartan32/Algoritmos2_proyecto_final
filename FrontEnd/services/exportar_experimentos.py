"""Exportación de la misma muestra que se presenta en Pygame."""

import csv
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from BackEnd.controllers.simulador import NOMBRE_ESTRATEGIA
from BackEnd.controllers.wave_manager import ESTRATEGIAS_ARMADO


def nombre_estrategia(clave, modo):
    nombres = NOMBRE_ESTRATEGIA if modo == "recorrido" else ESTRATEGIAS_ARMADO
    return nombres[clave]


def exportar_muestra(filas, modo, campo, etiqueta, eje, carpeta):
    import xlsxwriter

    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = f"{modo}_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}"
    ruta_csv, ruta_excel = (carpeta / f"{nombre}.{ext}" for ext in ("csv", "xlsx"))
    columnas = list(filas[0])
    valores = list(dict.fromkeys(fila["valor"] for fila in filas))
    estrategias = list(dict.fromkeys(fila["estrategia"] for fila in filas))
    resultados = {(fila["valor"], fila["estrategia"]): fila[campo] for fila in filas}

    with xlsxwriter.Workbook(str(ruta_excel)) as libro:
        resumen = libro.add_worksheet("Comparación")
        detalle = libro.add_worksheet("Datos")
        cabecera = libro.add_format({"bold": True, "bg_color": "#DCE9F7"})
        resumen.write_row(
            0, 0, [eje] + [nombre_estrategia(e, modo) for e in estrategias], cabecera
        )
        detalle.write_row(0, 0, columnas, cabecera)
        for i, fila in enumerate(filas, 1):
            detalle.write_row(i, 0, [fila[c] for c in columnas])
        detalle.freeze_panes(1, 3)
        detalle.autofilter(0, 0, len(filas), len(columnas) - 1)
        for j, columna in enumerate(columnas):
            detalle.set_column(j, j, max(15, len(columna) + 2))
        for i, valor in enumerate(valores, 1):
            resumen.write_row(
                i, 0, [valor] + [resultados[valor, e] for e in estrategias]
            )
        resumen.set_column(0, len(estrategias), 28)
        grafico = libro.add_chart({"type": "column"})
        for j, _ in enumerate(estrategias, 1):
            grafico.add_series(
                {
                    "name": [resumen.name, 0, j],
                    "categories": [resumen.name, 1, 0, len(valores), 0],
                    "values": [resumen.name, 1, j, len(valores), j],
                }
            )
        grafico.set_title({"name": etiqueta})
        grafico.set_x_axis({"name": eje})
        grafico.set_y_axis({"name": etiqueta, "min": 0})
        resumen.insert_chart("A7", grafico)

    with ruta_csv.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)
    return ruta_excel, ruta_csv
