"""Dibujo de una celda del almacén. Solo dibuja: no decide por dónde se camina."""

import pygame

COLORES = {
    "PASILLO": (251, 252, 253),
    "RACK": (170, 179, 189),
    "RACK_CON_PRODUCTOS": (120, 131, 143),
    "ZONA_DESPACHO": (172, 214, 184),
    "PUERTA": (242, 205, 140),
}
EXPLORADO = (219, 234, 250)
INTERSECCION = (241, 244, 248)
FLECHA = (110, 120, 132)
RESALTE = (214, 140, 22)


def dibujar_celda(superficie, rect, tipo, sentido, fuente, explorado=False,
                  interseccion=False, productos=0, resaltada=False):
    if tipo == "RACK" and productos:
        color = COLORES["RACK_CON_PRODUCTOS"]
    elif tipo == "PASILLO" and explorado:
        color = EXPLORADO
    elif tipo == "PASILLO" and interseccion:
        color = INTERSECCION
    else:
        color = COLORES.get(tipo, (255, 255, 255))
    pygame.draw.rect(superficie, color, rect)
    pygame.draw.rect(superficie, (200, 207, 216), rect, 1)

    if tipo == "PASILLO" and sentido not in ("AMBOS", "NINGUNO"):
        # El eje y del almacén crece hacia arriba; en pantalla, hacia abajo.
        dx, dy = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "O": (-1, 0)}[sentido]
        cx, cy = rect.center
        largo = max(2, rect.width * 0.22)
        fin = (cx + dx * largo, cy + dy * largo)
        pygame.draw.line(superficie, FLECHA, (cx - dx * largo, cy - dy * largo), fin)
        for lado in (-1, 1):
            pygame.draw.line(
                superficie, FLECHA, fin,
                (fin[0] - dx * largo * 0.8 + dy * largo * 0.8 * lado,
                 fin[1] - dy * largo * 0.8 - dx * largo * 0.8 * lado),
            )
    elif tipo == "PASILLO" and interseccion and rect.width >= 8:
        pygame.draw.circle(superficie, (190, 198, 208), rect.center, max(1, rect.width // 9))
    elif tipo == "RACK" and productos and rect.width >= 14:
        imagen = fuente(max(10, int(rect.width * 0.42)), True).render(str(productos), True, (255, 255, 255))
        superficie.blit(imagen, imagen.get_rect(center=rect.center))
    elif tipo == "PUERTA" and rect.width >= 14:
        imagen = fuente(max(10, int(rect.width * 0.45)), True).render("P", True, (120, 80, 20))
        superficie.blit(imagen, imagen.get_rect(center=rect.center))

    if resaltada:
        pygame.draw.rect(superficie, RESALTE, rect, max(2, rect.width // 7))
