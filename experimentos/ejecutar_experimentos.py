"""Suite de experimentos para evaluar tiempos y calidad de rutas del sistema.

Genera escenarios con el generador determinista variando un parámetro por vez
y mide cada etapa. Escribe:

- docs/experimentos/resultados.xlsx  (libro Excel con tablas formateadas y gráficos nativos)
- docs/experimentos/resultados.csv   (una fila por escenario y estrategia)
- docs/experimentos/resultados.md    (tablas en Markdown para el informe)
- docs/experimentos/*.png            (gráficos, si está instalado matplotlib)

Uso:  python experimentos/ejecutar_experimentos.py [--rapido]
"""

import argparse
import csv
from pathlib import Path
import statistics
import sys
import time

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from BackEnd.controllers.simulador import Simulador  # noqa: E402
from BackEnd.utils.graph_builder import GraphBuilder  # noqa: E402
from BackEnd.utils.scenario_generator import ScenarioGenerator  # noqa: E402

SALIDA = RAIZ / "docs" / "experimentos"

BASE = dict(
    cantidad_estantes=24,
    cantidad_pasillos=7,
    cantidad_productos=200,
    localizacion="DISTRIBUIDA",
    cantidad_pedidos=40,
    max_productos_por_pedido=5,
    wave_max_pedidos=4,
    wave_max_productos=20,
    cantidad_pickers=4,
)

SERIES = {
    "tamano": (
        "Tamaño del warehouse (estantes)",
        "cantidad_estantes",
        [6, 12, 24, 48, 96, 160],
        lambda v: {"cantidad_pasillos": max(3, round((v * 1.2) ** 0.5) + 1)},
    ),
    "pedidos": (
        "Cantidad de pedidos",
        "cantidad_pedidos",
        [10, 20, 40, 80, 160, 320],
        lambda v: {},
    ),
    "productos": (
        "Cantidad de productos",
        "cantidad_productos",
        [25, 50, 100, 200, 400, 800],
        lambda v: {},
    ),
    "localizacion": (
        "Localización de los productos",
        "localizacion",
        ["CERCA_DESPACHO", "POR_RACK", "DISTRIBUIDA"],
        lambda v: {},
    ),
    "pasillos": (
        "Cantidad de pasillos",
        "cantidad_pasillos",
        [3, 5, 7, 9, 13, 17],
        lambda v: {},
    ),
}

ARMADO = [
    ("pedidos", 20),
    ("pedidos", 40),
    ("pedidos", 80),
    ("pedidos", 160),
    ("localizacion", "CERCA_DESPACHO"),
    ("localizacion", "POR_RACK"),
]


def medir(params, repeticiones=5):
    datos = ScenarioGenerator.generar_escenario_dict(**params)
    tiempos, tiempos_kos = [], []
    for _ in range(repeticiones):
        t = time.perf_counter()
        wh = GraphBuilder.construir_warehouse_desde_dict(datos)
        tiempos.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter()
        GraphBuilder.componentes_fuertemente_conexas(wh)
        tiempos_kos.append((time.perf_counter() - t) * 1000)

    sim = Simulador(datos)
    t = time.perf_counter()
    waves = sim.generar_waves()
    t_waves = (time.perf_counter() - t) * 1000
    evaluados = sum(
        paso.get("candidatos_evaluados", 0)
        for traza in sim.estado.gestor_waves.traza_armado.values()
        for paso in traza
    )
    comp = sim.comparar_estrategias([w.id_wave for w in waves])
    fila_base = {
        "ancho": wh.ancho_x,
        "alto": wh.largo_y,
        "celdas": wh.ancho_x * wh.largo_y,
        "nodos": len(wh.grafo_pasillos.nodos),
        "aristas": sum(len(v) for v in wh.grafo_pasillos.lista_adyacencia.values()),
        "racks": len(wh.racks),
        "productos": len(wh.catalogo_productos),
        "pedidos": len(wh.pedidos),
        "t_grafo_ms": round(statistics.median(tiempos), 3),
        "t_kosaraju_ms": round(statistics.median(tiempos_kos), 3),
        "t_matriz_ms": round(sim.tiempo_matriz_ms, 3),
        "pares_matriz": len(sim.matriz_distancias),
        "waves": len(waves),
        "t_waves_ms": round(t_waves, 3),
        "candidatos_evaluados": evaluados,
    }
    filas = []
    for clave, r in comp.items():
        fila = dict(fila_base)
        fila.update(
            estrategia=clave,
            distancia=r["distancia"],
            nodos_visitados=r["nodos_visitados"],
            aristas_recorridas=r["aristas"],
            nodos_explorados=r["nodos_explorados"],
            expansiones=r["expansiones"],
            t_rutas_ms=r["tiempo_ms"],
            turnos=r["turnos"],
            esperas=r["esperas"],
            desvios=r["desvios"],
            viajes=r["viajes"],
        )
        filas.append(fila)
    return filas


def graficar(filas):
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib no está instalado: se omiten los gráficos PNG.")
        return []

    hechos = []
    colores = {"ORDEN": "#c4581e", "CERCANIA": "#2563a6"}
    nombres = {"ORDEN": "Orden de pedidos", "CERCANIA": "Cercanía"}

    for serie, (titulo, clave, valores, _) in SERIES.items():
        if serie == "localizacion":
            continue
        sub = [f for f in filas if f["serie"] == serie]
        fig, ejes = plt.subplots(1, 3, figsize=(15, 4.2))
        for est in ("ORDEN", "CERCANIA"):
            xs = [f["valor"] for f in sub if f["estrategia"] == est]
            ejes[0].plot(
                xs,
                [f["distancia"] for f in sub if f["estrategia"] == est],
                "o-",
                color=colores[est],
                label=nombres[est],
            )
            ejes[1].plot(
                xs,
                [f["expansiones"] for f in sub if f["estrategia"] == est],
                "o-",
                color=colores[est],
                label=nombres[est],
            )
            ejes[2].plot(
                xs,
                [f["t_rutas_ms"] for f in sub if f["estrategia"] == est],
                "o-",
                color=colores[est],
                label=nombres[est],
            )
        for eje, etiqueta in zip(
            ejes,
            [
                "Distancia total (pasos)",
                "Nodos expandidos por Dijkstra (suma)",
                "Tiempo de cálculo de rutas (ms)",
            ],
        ):
            eje.set_xlabel(titulo)
            eje.set_ylabel(etiqueta)
            eje.grid(alpha=0.3)
            eje.legend()
        fig.suptitle(f"Estrategias de recorrido según {titulo.lower()}")
        fig.tight_layout()
        ruta = SALIDA / f"estrategias_{serie}.png"
        fig.savefig(ruta, dpi=110)
        plt.close(fig)
        hechos.append(ruta)

    tam = [f for f in filas if f["serie"] == "tamano" and f["estrategia"] == "CERCANIA"]
    ped = [
        f for f in filas if f["serie"] == "pedidos" and f["estrategia"] == "CERCANIA"
    ]
    pro = [
        f for f in filas if f["serie"] == "productos" and f["estrategia"] == "CERCANIA"
    ]
    fig, ejes = plt.subplots(1, 3, figsize=(15, 4.2))
    ejes[0].plot(
        [f["celdas"] for f in tam],
        [f["t_grafo_ms"] for f in tam],
        "o-",
        label="Construir dígrafo",
    )
    ejes[0].plot(
        [f["celdas"] for f in tam],
        [f["t_kosaraju_ms"] for f in tam],
        "s-",
        label="Kosaraju",
    )
    ejes[0].set_xlabel("Celdas del almacén (ancho × largo)")
    ejes[0].set_ylabel("ms")
    ejes[0].set_title("Lineal en el área: O(W·H)")

    ejes[1].plot(
        [f["pedidos"] for f in ped],
        [f["t_waves_ms"] for f in ped],
        "o-",
        label="Armar waves",
    )
    ejes[1].set_xlabel("Pedidos")
    ejes[1].set_ylabel("ms")
    ejes[1].set_title("Armado de waves")
    eje2 = ejes[1].twinx()
    eje2.plot(
        [f["pedidos"] for f in ped],
        [f["candidatos_evaluados"] for f in ped],
        "s--",
        color="gray",
        label="Candidatos evaluados",
    )
    eje2.set_ylabel("candidatos evaluados")

    ejes[2].plot(
        [f["productos"] for f in pro],
        [f["t_matriz_ms"] for f in pro],
        "o-",
        label="Matriz de distancias",
    )
    ejes[2].set_xlabel("Productos")
    ejes[2].set_ylabel("ms")
    ejes[2].set_title("Matriz de distancias (un Dijkstra por acceso)")

    for eje in ejes:
        eje.grid(alpha=0.3)
        eje.legend(loc="upper left")
    fig.tight_layout()
    ruta = SALIDA / "escalabilidad.png"
    fig.savefig(ruta, dpi=110)
    plt.close(fig)
    hechos.append(ruta)
    return hechos


def tabla_md(filas, serie, titulo):
    sub = [f for f in filas if f["serie"] == serie]
    lineas = [
        f"### {titulo}",
        "",
        "| Valor | Celdas | Nodos | Productos | Pedidos | Waves | Estrategia | Distancia | Nodos visitados | Nodos explorados | Nodos expandidos | Rutas (ms) | Turnos | Esperas |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for f in sub:
        lineas.append(
            f"| {f['valor']} | {f['celdas']} | {f['nodos']} | {f['productos']} | {f['pedidos']} | {f['waves']} | "
            f"{'Orden' if f['estrategia'] == 'ORDEN' else 'Cercanía'} | {f['distancia']} | {f['nodos_visitados']} | "
            f"{f['nodos_explorados']} | {f['expansiones']} | {f['t_rutas_ms']:.2f} | {f['turnos']} | {f['esperas']} |"
        )
    lineas.append("")
    return lineas


def tabla_etapas(filas):
    lineas = [
        "### Tiempo de cada etapa (estrategia Cercanía)",
        "",
        "| Serie | Valor | Celdas | Nodos | Aristas | Dígrafo (ms) | Kosaraju (ms) | Matriz (ms) | Pares matriz | Waves (ms) | Candidatos evaluados |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for f in filas:
        if f["estrategia"] != "CERCANIA":
            continue
        lineas.append(
            f"| {f['serie']} | {f['valor']} | {f['celdas']} | {f['nodos']} | {f['aristas']} | {f['t_grafo_ms']:.2f} | "
            f"{f['t_kosaraju_ms']:.2f} | {f['t_matriz_ms']:.1f} | {f['pares_matriz']} | {f['t_waves_ms']:.2f} | {f['candidatos_evaluados']} |"
        )
    lineas.append("")
    return lineas


def medir_armado():
    filas = []
    for clave, valor in ARMADO:
        params = dict(BASE)
        params["cantidad_" + clave if clave == "pedidos" else clave] = valor
        sim = Simulador(ScenarioGenerator.generar_escenario_dict(**params))
        for estrategia, r in sim.comparar_armado().items():
            filas.append(
                dict(
                    variable=clave,
                    valor=valor,
                    armado=estrategia,
                    **{k: v for k, v in r.items() if k != "nombre"},
                )
            )
        print(f"armado {clave:12s} {str(valor):15s} listo")
    return filas


def escribir_armado(filas):
    with open(SALIDA / "armado.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)

    nombres = {
        "CERCANIA": "Cercanía",
        "PASILLO": "Por pasillo",
        "PRIORIDAD": "Solo prioridad",
    }
    lineas = [
        "### Estrategias de armado de waves (recorrido con Cercanía)",
        "",
        "| Escenario | Armado | Waves | Pedidos/wave | Pasillos/wave | Prioridad 1.ª wave | Distancia | Turnos | Armado (ms) | Candidatos |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for f in filas:
        lineas.append(
            f"| {f['variable']}={f['valor']} | {nombres[f['armado']]} | {f['waves']} | {f['pedidos_por_wave']} | "
            f"{f['pasillos_por_wave']} | {f['prioridad_primera_wave']} | {f['distancia']} | {f['turnos']} | "
            f"{f['tiempo_armado_ms']:.2f} | {f['candidatos_evaluados']} |"
        )
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return lineas + [""]

    sub = [f for f in filas if f["variable"] == "pedidos"]
    fig, ejes = plt.subplots(1, 3, figsize=(15, 4.2))
    colores = {"CERCANIA": "#2563a6", "PASILLO": "#1f8062", "PRIORIDAD": "#c4581e"}
    for est in nombres:
        xs = [f["valor"] for f in sub if f["armado"] == est]
        for eje, campo in zip(
            ejes, ("distancia", "pasillos_por_wave", "tiempo_armado_ms")
        ):
            eje.plot(
                xs,
                [f[campo] for f in sub if f["armado"] == est],
                "o-",
                color=colores[est],
                label=nombres[est],
            )
    for eje, etiqueta in zip(
        ejes,
        (
            "Distancia total (pasos)",
            "Pasillos distintos por wave",
            "Tiempo de armado (ms)",
        ),
    ):
        eje.set_xlabel("Cantidad de pedidos")
        eje.set_ylabel(etiqueta)
        eje.grid(alpha=0.3)
        eje.legend()
    fig.suptitle("Estrategias de armado de waves")
    fig.tight_layout()
    fig.savefig(SALIDA / "armado.png", dpi=110)
    plt.close(fig)
    return lineas + ["", "![Armado de waves](armado.png)", ""]


def exportar_excel(filas, filas_armado):
    """Exporta todas las tablas de experimentos y gráficos interactivos a un archivo Excel (.xlsx)."""
    try:
        import openpyxl
        from openpyxl.chart import BarChart, LineChart, Reference
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        print(
            "Aviso: 'openpyxl' no está instalado (pip install openpyxl). "
            "Se omite la generación de resultados.xlsx."
        )
        return None

    wb = openpyxl.Workbook()
    # Quitamos la hoja por defecto para crear una por cada serie
    wb.remove(wb.active)

    fill_header = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    fill_zebra = PatternFill(start_color="F4F7FA", end_color="F4F7FA", fill_type="solid")
    fill_green = PatternFill(start_color="E6F4EA", end_color="E6F4EA", fill_type="solid")

    font_title = Font(name="Calibri", size=14, bold=True, color="1E3A5F")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_green = Font(name="Calibri", size=11, bold=True, color="137333")
    borde_fino = Side(border_style="thin", color="D0D7DE")
    borde = Border(left=borde_fino, right=borde_fino, top=borde_fino, bottom=borde_fino)

    # 1. Crear una pestaña comparativa (Orden vs Cercanía) con gráficos por cada serie de SERIES
    for serie, (titulo, _clave, _valores, _) in SERIES.items():
        ws = wb.create_sheet(title=f"Serie_{serie}"[:31])
        ws["A1"] = f"Experimento: {titulo}"
        ws["A1"].font = font_title

        encabezados = [
            titulo,
            "Celdas (W×H)",
            "Nodos Dígrafo",
            "Productos",
            "Pedidos",
            "Waves",
            "Distancia Orden",
            "Distancia Cercanía",
            "Ahorro Distancia (%)",
            "Expandidos Orden",
            "Expandidos Cercanía",
            "Tiempo Orden (ms)",
            "Tiempo Cercanía (ms)",
            "Turnos Orden",
            "Turnos Cercanía",
            "Esperas Orden",
            "Esperas Cercanía",
        ]
        ws.append([])
        ws.append(encabezados)
        for col_i in range(1, len(encabezados) + 1):
            c = ws.cell(row=3, column=col_i)
            c.fill = fill_header
            c.font = font_header
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[3].height = 28

        sub_orden = {f["valor"]: f for f in filas if f["serie"] == serie and f["estrategia"] == "ORDEN"}
        sub_cerc = {f["valor"]: f for f in filas if f["serie"] == serie and f["estrategia"] == "CERCANIA"}
        valores_ordenados = [f["valor"] for f in filas if f["serie"] == serie and f["estrategia"] == "ORDEN"]

        for idx_fila, val in enumerate(valores_ordenados, start=4):
            fo = sub_orden.get(val, {})
            fc = sub_cerc.get(val, {})
            datos_fila = [
                val,
                fo.get("celdas", 0),
                fo.get("nodos", 0),
                fo.get("productos", 0),
                fo.get("pedidos", 0),
                fo.get("waves", 0),
                fo.get("distancia", 0),
                fc.get("distancia", 0),
                f"=(G{idx_fila}-H{idx_fila})/G{idx_fila}" if fo.get("distancia", 0) else 0.0,
                fo.get("expansiones", 0),
                fc.get("expansiones", 0),
                fo.get("t_rutas_ms", 0.0),
                fc.get("t_rutas_ms", 0.0),
                fo.get("turnos", 0),
                fc.get("turnos", 0),
                fo.get("esperas", 0),
                fc.get("esperas", 0),
            ]
            ws.append(datos_fila)
            for col_i in range(1, len(datos_fila) + 1):
                celda = ws.cell(row=idx_fila, column=col_i)
                celda.border = borde
                if idx_fila % 2 == 1:
                    celda.fill = fill_zebra
                if col_i == 9:
                    celda.number_format = "0.0%"
                    celda.fill = fill_green
                    celda.font = font_green
                elif col_i in (12, 13):
                    celda.number_format = "0.00"
                elif col_i > 1:
                    celda.number_format = "#,##0"

        max_row = 3 + len(valores_ordenados)
        if max_row >= 4:
            # Gráfico 1: Distancia Orden vs Cercanía
            ch_dist = BarChart() if serie == "localizacion" else LineChart()
            ch_dist.title = f"Distancia Total según {titulo}"
            ch_dist.y_axis.title = "Pasos"
            ch_dist.x_axis.title = titulo
            ch_dist.add_data(Reference(ws, min_col=7, min_row=3, max_col=8, max_row=max_row), titles_from_data=True)
            ch_dist.set_categories(Reference(ws, min_col=1, min_row=4, max_row=max_row))
            ch_dist.width = 15
            ch_dist.height = 10
            ws.add_chart(ch_dist, f"B{max_row + 3}")

            # Gráfico 2: Nodos Expandidos por Dijkstra
            ch_exp = BarChart() if serie == "localizacion" else LineChart()
            ch_exp.title = f"Nodos Expandidos según {titulo}"
            ch_exp.y_axis.title = "Nodos Expandidos"
            ch_exp.x_axis.title = titulo
            ch_exp.add_data(Reference(ws, min_col=10, min_row=3, max_col=11, max_row=max_row), titles_from_data=True)
            ch_exp.set_categories(Reference(ws, min_col=1, min_row=4, max_row=max_row))
            ch_exp.width = 15
            ch_exp.height = 10
            ws.add_chart(ch_exp, f"I{max_row + 3}")

            # Gráfico 3: Tiempo de cálculo de rutas (ms)
            ch_ms = BarChart() if serie == "localizacion" else LineChart()
            ch_ms.title = f"Tiempo de Ruteo (ms) según {titulo}"
            ch_ms.y_axis.title = "Tiempo (ms)"
            ch_ms.x_axis.title = titulo
            ch_ms.add_data(Reference(ws, min_col=12, min_row=3, max_col=13, max_row=max_row), titles_from_data=True)
            ch_ms.set_categories(Reference(ws, min_col=1, min_row=4, max_row=max_row))
            ch_ms.width = 15
            ch_ms.height = 10
            ws.add_chart(ch_ms, f"P{max_row + 3}")

    # 2. Pestaña de Tiempos por Etapa (Dígrafo, Kosaraju, Matriz, Waves)
    ws_etapas = wb.create_sheet(title="Tiempos_Etapas")
    ws_etapas["A1"] = "Tiempos de Ejecución por Etapa del Sistema (ms)"
    ws_etapas["A1"].font = font_title
    ws_etapas.append([])
    cols_etapas = [
        "Serie", "Valor", "Celdas", "Nodos", "Aristas",
        "Dígrafo (ms)", "Kosaraju (ms)", "Matriz Distancias (ms)",
        "Pares Matriz", "Armado Waves (ms)", "Candidatos Evaluados"
    ]
    ws_etapas.append(cols_etapas)
    for col_i in range(1, len(cols_etapas) + 1):
        c = ws_etapas.cell(row=3, column=col_i)
        c.fill = fill_header
        c.font = font_header
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    fila_idx = 4
    for f in filas:
        if f["estrategia"] != "CERCANIA":
            continue
        ws_etapas.append([
            f["serie"], f["valor"], f["celdas"], f["nodos"], f["aristas"],
            f["t_grafo_ms"], f["t_kosaraju_ms"], f["t_matriz_ms"],
            f["pares_matriz"], f["t_waves_ms"], f["candidatos_evaluados"]
        ])
        for col_i in range(1, len(cols_etapas) + 1):
            ws_etapas.cell(row=fila_idx, column=col_i).border = borde
        fila_idx += 1

    # 3. Pestaña de Comparación de Armado de Waves
    if filas_armado:
        ws_arm = wb.create_sheet(title="Comparativa_Armado_Waves")
        ws_arm["A1"] = "Comparación de Estrategias de Armado de Waves (Cercanía vs Pasillo vs Prioridad)"
        ws_arm["A1"].font = font_title
        ws_arm.append([])
        cols_arm = list(filas_armado[0].keys())
        ws_arm.append(cols_arm)
        for col_i in range(1, len(cols_arm) + 1):
            c = ws_arm.cell(row=3, column=col_i)
            c.fill = fill_header
            c.font = font_header
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for idx_a, fa in enumerate(filas_armado, start=4):
            ws_arm.append([fa[k] for k in cols_arm])
            for col_i in range(1, len(cols_arm) + 1):
                ws_arm.cell(row=idx_a, column=col_i).border = borde

    # Ajustar ancho de columnas en todas las hojas
    for sheet in wb.worksheets:
        sheet.freeze_panes = "A4"
        for col in sheet.columns:
            letra = get_column_letter(col[0].column)
            largo = max(len(str(celda.value or "")) for celda in col[:25])
            sheet.column_dimensions[letra].width = max(14, min(32, largo + 4))

    ruta_xlsx = SALIDA / "resultados.xlsx"
    wb.save(ruta_xlsx)
    return ruta_xlsx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rapido",
        action="store_true",
        help="Ejecuta solo los 3 primeros valores de cada serie",
    )
    args = parser.parse_args()
    SALIDA.mkdir(parents=True, exist_ok=True)
    filas = []

    for serie, (titulo, clave, valores, extra) in SERIES.items():
        for valor in valores[:3] if args.rapido else valores:
            params = dict(BASE)
            params[clave] = valor
            params.update(extra(valor))
            if params["cantidad_productos"] < params["max_productos_por_pedido"]:
                params["max_productos_por_pedido"] = params["cantidad_productos"]
            inicio = time.perf_counter()
            for fila in medir(params):
                fila.update(serie=serie, valor=valor)
                filas.append(fila)
            print(
                f"{serie:12s} {str(valor):15s} listo en {time.perf_counter() - inicio:.1f} s"
            )

    columnas = ["serie", "valor", "estrategia"] + [
        k for k in filas[0] if k not in ("serie", "valor", "estrategia")
    ]
    with open(SALIDA / "resultados.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)

    filas_armado = medir_armado()

    md = [
        "# Resultados experimentales",
        "",
        "Generado por `experimentos/ejecutar_experimentos.py`.",
        "",
        f"Escenario base: {BASE}",
        "",
    ]
    for serie, (titulo, *_rest) in SERIES.items():
        md += tabla_md(filas, serie, titulo)
    md += tabla_etapas(filas)
    md += escribir_armado(filas_armado)
    (SALIDA / "resultados.md").write_text("\n".join(md), encoding="utf-8")

    for ruta in graficar(filas):
        print("Gráfico:", ruta.relative_to(RAIZ))

    ruta_excel = exportar_excel(filas, filas_armado)
    if ruta_excel is not None:
        print("Excel generado en:", ruta_excel.relative_to(RAIZ))

    print("Resultados en", (SALIDA / "resultados.csv").relative_to(RAIZ))


if __name__ == "__main__":
    main()