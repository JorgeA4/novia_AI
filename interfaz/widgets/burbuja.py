"""
Widget BurbujaMensaje — muestra un mensaje individual del historial de conversación.

Rol "usuario"   → alineado a la derecha, fondo azul oscuro.
Rol "personaje" → alineado a la izquierda, fondo gris oscuro.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label
from textual.css.query import NoMatches


class BurbujaMensaje(Widget):
    """
    Widget estático que representa un mensaje en el historial.

    Se construye con rol y contenido; no tiene estado dinámico.
    """

    DEFAULT_CSS = """
    BurbujaMensaje {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }

    BurbujaMensaje.usuario {
        align: right middle;
    }

    BurbujaMensaje.personaje {
        align: left middle;
    }

    BurbujaMensaje .burbuja-texto {
        max-width: 70%;
        padding: 1 2;
        border: round $surface-lighten-1;
    }

    BurbujaMensaje.usuario .burbuja-texto {
        background: $primary-darken-2;
        color: $text;
        border: round $primary;
    }

    BurbujaMensaje.personaje .burbuja-texto {
        background: $surface-darken-1;
        color: $text;
        border: round $surface-lighten-2;
    }
    """

    def __init__(self, rol: str, contenido: str) -> None:
        super().__init__(classes=rol)
        self._rol = rol
        self._contenido = contenido

    def compose(self) -> ComposeResult:
        yield Label(self._contenido, classes="burbuja-texto")
