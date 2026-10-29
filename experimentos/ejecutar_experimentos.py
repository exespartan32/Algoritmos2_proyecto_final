"""Experimentos del informe (secciones 20 y 21 del enunciado).

Genera escenarios con el generador determinista variando un parámetro por vez
y mide cada etapa del sistema. Escribe:

- docs/experimentos/resultados.csv   (una fila por escenario y estrategia)
- docs/experimentos/resultados.md    (tablas listas para el informe)
- docs/experimentos/*.png            (gráficos, si está instalado matplotlib)

Uso:  python experimentos/ejecutar_experimentos.py [--rapido]
"""

import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

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
    "tamano": ("Tamaño del warehouse (estantes)", "cantidad_estantes", [6, 12, 24, 48, 96, 160],
               lambda v: {"cantidad_pasillos": max(3, round((v * 1.2) ** 0.5) + 1)}),
    "pedidos": ("Cantidad de pedidos", "cantidad_pedidos", [10, 20, 40, 80, 160, 320], lambda v: {}),
    "productos": ("Cantidad de productos", "cantidad_productos", [25, 50, 100, 200, 400, 800], lambda v: {}),
    "localizacion": ("Localización de los productos", "localizacion", ["CERCA_DESPACHO", "POR_RACK", "DISTRIBUIDA"], lambda v: {}),
    "pasillos": ("Cantidad de pasillos", "cantidad_pasillos", [3, 5, 7, 9, 13, 17], lambda v: {}),
}


def medir(params, repeticiones=5):
    datos = ScenarioGenerator.generar_escenario_dict(**params)
    # Construcción del dígrafo + Kosaraju (mediana de varias corridas).
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
        paso["candidatos_evaluados"] for traza in sim.estado.gestor_waves.traza_armado.values() for paso in traza
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
        print("matplotlib no está instalado: se omiten los gráficos.")
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
            ejes[0].plot(xs, [f["distancia"] for f in sub if f["estrategia"] == est], "o-", color=colores[est], label=nombres[est])
            ejes[1].plot(xs, [f["expansiones"] for f in sub if f["estrategia"] == est], "o-", color=colores[est], label=nombres[est])
            ejes[2].plot(xs, [f["t_rutas_ms"] for f in sub if f["estrategia"] == est], "o-", color=colores[est], label=nombres[est])
        for eje, etiqueta in zip(ejes, ["Distancia total (pasos)", "Nodos expandidos por Dijkstra (suma)", "Tiempo de cálculo de rutas (ms)"]):
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

    # Escalabilidad de las etapas frente al tamaño de entrada.
    tam = [f for f in filas if f["serie"] == "tamano" and f["estrategia"] == "CERCANIA"]
    ped = [f for f in filas if f["serie"] == "pedidos" and f["estrategia"] == "CERCANIA"]
    pro = [f for f in filas if f["serie"] == "productos" and f["estrategia"] == "CERCANIA"]
    fig, ejes = plt.subplots(1, 3, figsize=(15, 4.2))
    ejes[0].plot([f["celdas"] for f in tam], [f["t_grafo_ms"] for f in tam], "o-", label="Construir dígrafo")
    ejes[0].plot([f["celdas"] for f in tam], [f["t_kosaraju_ms"] for f in tam], "s-", label="Kosaraju")
    ejes[0].set_xlabel("Celdas del almacén (ancho × largo)")
    ejes[0].set_ylabel("ms")
    ejes[0].set_title("Lineal en el área: O(W·H)")
    ejes[1].plot([f["pedidos"] for f in ped], [f["t_waves_ms"] for f in ped], "o-", label="Armar waves")
    ejes[1].set_xlabel("Pedidos")
    ejes[1].set_ylabel("ms")
    ejes[1].set_title("Armado de waves")
    eje2 = ejes[1].twinx()
    eje2.plot([f["pedidos"] for f in ped], [f["candidatos_evaluados"] for f in ped], "s--", color="gray", label="Candidatos evaluados")
    eje2.set_ylabel("candidatos evaluados")
    ejes[2].plot([f["productos"] for f in pro], [f["t_matriz_ms"] for f in pro], "o-", label="Matriz de distancias")
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


ARMADO = [("pedidos", 20), ("pedidos", 40), ("pedidos", 80), ("pedidos", 160),
          ("localizacion", "CERCA_DESPACHO"), ("localizacion", "POR_RACK")]


def medir_armado():
    """Compara las tres estrategias de armado de waves (recorrido: Cercanía)."""
    filas = []
    for clave, valor in ARMADO:
        params = dict(BASE)
        params["cantidad_" + clave if clave == "pedidos" else clave] = valor
        sim = Simulador(ScenarioGenerator.generar_escenario_dict(**params))
        for estrategia, r in sim.comparar_armado().items():
            filas.append(dict(variable=clave, valor=valor, armado=estrategia,
                              **{k: v for k, v in r.items() if k != "nombre"}))
        print(f"armado {clave:12s} {str(valor):15s} listo")
    return filas


def escribir_armado(filas):
    with open(SALIDA / "armado.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)
    nombres = {"CERCANIA": "Cercanía", "PASILLO": "Por pasillo", "PRIORIDAD": "Solo prioridad"}
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
        for eje, campo in zip(ejes, ("distancia", "pasillos_por_wave", "tiempo_armado_ms")):
            eje.plot(xs, [f[campo] for f in sub if f["armado"] == est], "o-", color=colores[est], label=nombres[est])
    for eje, etiqueta in zip(ejes, ("Distancia total (pasos)", "Pasillos distintos por wave", "Tiempo de armado (ms)")):
        eje.set_xlabel("Cantidad de pedidos")
        eje.set_ylabel(etiqueta)
        eje.grid(alpha=0.3)
        eje.legend()
    fig.suptitle("Estrategias de armado de waves")
    fig.tight_layout()
    fig.savefig(SALIDA / "armado.png", dpi=110)
    plt.close(fig)
    return lineas + ["", "![Armado de waves](armado.png)", ""]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rapido", action="store_true", help="Solo los 3 primeros valores de cada serie")
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
            print(f"{serie:12s} {str(valor):15s} listo en {time.perf_counter() - inicio:.1f} s")

    columnas = ["serie", "valor", "estrategia"] + [k for k in filas[0] if k not in ("serie", "valor", "estrategia")]
    with open(SALIDA / "resultados.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)

    md = ["# Resultados experimentales", "", "Generado por `experimentos/ejecutar_experimentos.py`.", ""]
    md += [f"Escenario base: {BASE}", ""]
    for serie, (titulo, *_rest) in SERIES.items():
        md += tabla_md(filas, serie, titulo)
    md += tabla_etapas(filas)
    md += escribir_armado(medir_armado())
    (SALIDA / "resultados.md").write_text("\n".join(md), encoding="utf-8")
    for ruta in graficar(filas):
        print("Gráfico:", ruta.relative_to(RAIZ))
    print("Resultados en", (SALIDA / "resultados.csv").relative_to(RAIZ))


if __name__ == "__main__":
    main()
