"""Traduce teclado, mouse y archivos arrastrados en acciones de la interfaz."""

import pygame


def handle_event(self, event):
    if event.type == pygame.QUIT:
        self.running = False
    elif event.type == pygame.DROPFILE:
        try:
            self.import_file(event.file)
        except Exception as exc:
            self.message = "JSON inválido: " + str(exc)
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        for rect, action, enabled in reversed(self.buttons):
            if enabled and rect.collidepoint(event.pos):
                self.action(action)
                break
    elif event.type == pygame.TEXTINPUT and self.dialog == "generator":
        self.fields[self.focus] = (
            self.fields[self.focus] + "".join(c for c in event.text if c.isdigit())
        )[:3]
    elif event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
            self.dialog = None
            pygame.key.stop_text_input()
        elif self.dialog == "generator":
            if event.key == pygame.K_BACKSPACE:
                self.fields[self.focus] = self.fields[self.focus][:-1]
            elif event.key == pygame.K_TAB:
                self.focus = (self.focus + 1) % 3
        elif not self.dialog and self.page == "sim":
            if event.key == pygame.K_RIGHT:
                self.action("forward")
            elif event.key == pygame.K_LEFT:
                self.action("back")
            elif event.key == pygame.K_SPACE:
                self.action("pause" if self.playing else "continue")
