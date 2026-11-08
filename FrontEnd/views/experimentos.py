"""Pantalla de experimentos. La medición corre fuera del bucle de dibujo."""

from queue import Empty, Queue
from threading import Thread

import pygame

from experimentos.ejecutar_experimentos import BASE, RAIZ, SERIES, muestra_visual
from FrontEnd.services.exportar_experimentos import exportar_muestra, nombre_estrategia
from FrontEnd.views.ui_elements import AZUL, GRIS, ROJO

METRICAS = {
    "recorrido": {
        "distancia": "Distancia (pasos)",
        "turnos": "Turnos",
        "t_rutas_ms": "Cálculo de rutas (ms)",
        "nodos_explorados": "Nodos explorados",
    },
    "armado": {
        "distancia": "Distancia (pasos)",
        "turnos": "Turnos",
        "tiempo_armado_ms": "Armado (ms)",
        "pedidos_preparados": "Pedidos preparados",
    },
}
COLORES = ((37, 99, 166), (181, 80, 30), (42, 128, 79))


class ExperimentosVista:
    def _a_experimentos(self):
        self.reproduciendo = False
        self.dialogo = "experimentos"

    def _a_experimento_config(self, variable, valor):
        if self.experimento_pendiente is not None:
            return
        setattr(self, variable, valor)
        self.experimento_filas = []
        self.experimento_metrica = "distancia"
        self.experimento_mensaje = ""

    def _a_experimento_metrica(self, campo):
        self.experimento_metrica = campo

    def _a_ejecutar_experimento(self):
        if self.experimento_pendiente is not None:
            return
        serie, modo = self.experimento_serie, self.experimento_modo
        salida = Queue()
        self.experimento_pendiente = salida
        self.experimento_filas = []
        self.experimento_mensaje = "Ejecutando los tres casos…"

        def medir():
            try:
                salida.put((muestra_visual(serie, modo), None))
            except Exception as exc:
                salida.put(([], str(exc)))

        Thread(target=medir, daemon=True).start()

    def revisar_experimento(self):
        if self.experimento_pendiente is None:
            return
        try:
            filas, error = self.experimento_pendiente.get_nowait()
        except Empty:
            return
        self.experimento_pendiente = None
        self.experimento_filas = filas
        self.experimento_mensaje = (
            f"Error: {error}" if error else "Experimento terminado. Elegí una métrica."
        )

    def _a_exportar_experimento(self):
        campo = self.experimento_metrica
        try:
            excel, csv = exportar_muestra(
                self.experimento_filas,
                self.experimento_modo,
                campo,
                METRICAS[self.experimento_modo][campo],
                SERIES[self.experimento_serie][0],
                RAIZ / "experimentos" / "salidas",
            )
        except (OSError, ImportError) as exc:
            self.experimento_mensaje = f"Error al exportar: {exc}"
            return
        self.experimento_mensaje = (
            f"Guardados en experimentos/salidas: {excel.name} y {csv.name}"
        )

    def dialogo_experimentos(self, x, y, w):
        self.texto("Experimentos", x, y, 26, negrita=True)
        disponible = self.experimento_pendiente is None
        for i, (modo, etiqueta) in enumerate(
            (("recorrido", "Comparar recorridos"), ("armado", "Comparar armado"))
        ):
            self.boton(
                etiqueta,
                x + i * 216,
                y + 48,
                208,
                ("experimento_config", "experimento_modo", modo),
                disponible,
                marcado=self.experimento_modo == modo,
            )
        opciones = zip(
            SERIES, ("Estantes", "Pedidos", "Productos", "Localización", "Pasillos")
        )
        for i, (serie, etiqueta) in enumerate(opciones):
            self.boton(
                etiqueta,
                x + i * 126,
                y + 95,
                118,
                ("experimento_config", "experimento_serie", serie),
                disponible,
                marcado=self.experimento_serie == serie,
            )
        titulo, clave, valores, _ = SERIES[self.experimento_serie]
        self.texto(
            f"{titulo}: {', '.join(map(str, valores[:3]))}",
            x,
            y + 140,
            17,
            negrita=True,
        )
        self.parrafo(
            "Escenario base: "
            + ", ".join(
                f"{v} {k.removeprefix('cantidad_')}"
                for k, v in BASE.items()
                if k.startswith("cantidad_") and k != clave
            )
            + ". En la serie Estantes se ajustan los pasillos para acomodar el depósito.",
            x,
            y + 164,
            w,
            15,
            limite=2,
        )
        self.boton(
            "Ejecutar muestra",
            x,
            y + 212,
            208,
            "ejecutar_experimento",
            disponible,
            marcado=disponible,
        )
        self.boton(
            "Exportar Excel y CSV",
            x + 216,
            y + 212,
            226,
            "exportar_experimento",
            bool(self.experimento_filas),
        )
        error = self.experimento_mensaje.startswith("Error")
        self.parrafo(
            self.experimento_mensaje,
            x,
            y + 256,
            w,
            15,
            ROJO if error else AZUL,
            limite=2,
        )
        if self.experimento_filas:
            for i, (campo, etiqueta) in enumerate(
                METRICAS[self.experimento_modo].items()
            ):
                self.boton(
                    etiqueta,
                    x + i * 211,
                    y + 303,
                    206,
                    ("experimento_metrica", campo),
                    marcado=campo == self.experimento_metrica,
                )
            self._graficar_experimento(x, y + 355, w)

    def _graficar_experimento(self, x, y, w):
        filas = self.experimento_filas
        campo = self.experimento_metrica
        valores = list(dict.fromkeys(f["valor"] for f in filas))
        estrategias = list(dict.fromkeys(f["estrategia"] for f in filas))
        resultados = {(f["valor"], f["estrategia"]): f[campo] for f in filas}
        maximo = max(resultados.values()) or 1
        base, alto = y + 200, 155
        inicio, ancho = x + 60, w - 78
        for i in range(5):
            yy = round(base - i * alto / 4)
            self.texto(
                f"{maximo * i / 4:,.2f}".rstrip("0").rstrip("."), x, yy - 8, 13, GRIS
            )
            pygame.draw.line(self.lienzo, (214, 220, 225), (inicio, yy), (x + w, yy))
        grupo = ancho / len(valores)
        for i, valor in enumerate(valores):
            centro = inicio + (i + 0.5) * grupo
            for j, estrategia in enumerate(estrategias):
                dato = resultados[valor, estrategia]
                xx = round(centro + (j - (len(estrategias) - 1) / 2) * 62)
                altura = round(dato / maximo * alto)
                color = COLORES[j]
                pygame.draw.rect(
                    self.lienzo, color, (xx - 24, base - altura, 48, altura)
                )
                numero = f"{dato:,.2f}".rstrip("0").rstrip(".")
                self.texto(
                    numero,
                    xx - self.fuente(14).size(numero)[0] / 2,
                    base - altura - 18,
                    14,
                )
            texto = str(valor)
            self.texto(texto, centro - self.fuente(15).size(texto)[0] / 2, base + 7, 15)
        for j, estrategia in enumerate(estrategias):
            self.texto(
                nombre_estrategia(estrategia, self.experimento_modo),
                x + j * 200,
                base + 38,
                16,
                COLORES[j],
                True,
            )
