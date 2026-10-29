"""Traduce mouse, teclado y archivos arrastrados en acciones de la interfaz."""

import pygame

# Campos que se eligen con clic (no se escriben).
OPCIONES = {"localizacion", "estrategia_waves"}


def _campo_actual(app):
    f = app.formulario
    return f["campos"][f["foco"]] if f else None


def manejar_evento(app, evento):
    if evento.type == pygame.QUIT:
        app.corriendo = False
    elif evento.type == pygame.DROPFILE:
        try:
            app.importar(evento.file)
        except Exception as exc:
            app.mensaje = "JSON inválido: " + str(exc)
    elif evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
        pos = app.a_lienzo(evento.pos)
        app.ultimo_clic = pos
        for rect, accion, habilitado in reversed(app.botones):
            if rect.collidepoint(pos):
                if accion == ("mapa",):
                    # Puede ser un clic (info de la celda) o el comienzo de un arrastre.
                    app.arrastre = {"inicio": pos, "ultimo": pos, "movio": False}
                elif habilitado:
                    app.accion(accion)
                break
    elif evento.type == pygame.MOUSEMOTION and app.arrastre:
        pos = app.a_lienzo(evento.pos)
        inicio, ultimo = app.arrastre["inicio"], app.arrastre["ultimo"]
        if abs(pos[0] - inicio[0]) + abs(pos[1] - inicio[1]) > 4:
            app.arrastre["movio"] = True
        if app.arrastre["movio"]:
            app.mapa.mover(pos[0] - ultimo[0], pos[1] - ultimo[1])
            app.arrastre["ultimo"] = pos
    elif evento.type == pygame.MOUSEBUTTONUP and evento.button == 1:
        if app.arrastre and not app.arrastre["movio"]:
            app.ultimo_clic = app.arrastre["inicio"]
            app.accion(("mapa",))
        app.arrastre = None
    elif evento.type == pygame.MOUSEWHEEL and app.pagina == "sim" and not app.dialogo:
        pos = app.a_lienzo(pygame.mouse.get_pos())
        if app.sim is not None and app.mapa.area.collidepoint(pos):
            app.mapa.zoom_en(pos, 1.2 ** evento.y)
        else:
            app.accion(("pagina", "pag_tabla", -evento.y, 10 ** 6, 1))
    elif evento.type == pygame.TEXTINPUT and app.formulario:
        campo = _campo_actual(app)
        if campo[0] not in OPCIONES:
            permitido = "items" == campo[0]
            texto = evento.text if permitido else "".join(c for c in evento.text if c.isdigit())
            campo[2] = (campo[2] + texto)[: 80 if permitido else 4]
    elif evento.type == pygame.KEYDOWN:
        if evento.key == pygame.K_ESCAPE:
            app.cerrar_dialogo()
        elif app.formulario:
            campo = _campo_actual(app)
            if evento.key == pygame.K_BACKSPACE and campo[0] not in OPCIONES:
                campo[2] = campo[2][:-1]
            elif evento.key in (pygame.K_TAB, pygame.K_DOWN):
                app.formulario["foco"] = (app.formulario["foco"] + 1) % len(app.formulario["campos"])
            elif evento.key == pygame.K_UP:
                app.formulario["foco"] = (app.formulario["foco"] - 1) % len(app.formulario["campos"])
            elif evento.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                app.accion("enviar")
        elif not app.dialogo and app.pagina == "sim":
            if evento.key == pygame.K_RIGHT:
                app.accion("adelante")
            elif evento.key == pygame.K_LEFT:
                app.accion("atras")
            elif evento.key == pygame.K_SPACE:
                app.accion("pausar" if app.reproduciendo else "iniciar")
            elif evento.key == pygame.K_r:
                app.accion("reiniciar")
