"""
Widget IndicadorEstado — muestra las métricas de la relación y el estado emocional.

Se actualiza después de cada turno con los valores más recientes.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static


class IndicadorEstado(Widget):
    """
    Panel lateral que muestra:
        - Etapa actual de la relación
        - Emoción actual del personaje
        - Barras de confianza, afecto, familiaridad, tensión
    """

    DEFAULT_CSS = """
    IndicadorEstado {
        width: 100%;
        height: auto;
        padding: 1 2;
        border: round $surface-lighten-1;
        background: $surface-darken-1;
    }

    IndicadorEstado .indicador-titulo {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    IndicadorEstado .indicador-etiqueta {
        color: $text-muted;
    }

    IndicadorEstado .indicador-valor {
        color: $text;
        text-style: bold;
    }

    IndicadorEstado .indicador-barra {
        color: $success;
    }

    IndicadorEstado .indicador-barra-tension {
        color: $error;
    }

    IndicadorEstado .indicador-separador {
        margin-top: 1;
        margin-bottom: 1;
        color: $surface-lighten-2;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._etapa = "—"
        self._emocion = "—"
        self._confianza = 0.0
        self._afecto = 0.0
        self._familiaridad = 0.0
        self._tension = 0.0

    def compose(self) -> ComposeResult:
        yield Label("Estado de la relación", classes="indicador-titulo")
        yield Label("Etapa:", classes="indicador-etiqueta")
        yield Label(self._etapa, id="ind-etapa", classes="indicador-valor")
        yield Static("─" * 24, classes="indicador-separador")
        yield Label("Emoción actual:", classes="indicador-etiqueta")
        yield Label(self._emocion, id="ind-emocion", classes="indicador-valor")
        yield Static("─" * 24, classes="indicador-separador")
        yield Label("Confianza:", classes="indicador-etiqueta")
        yield Label(self._barra(self._confianza), id="ind-confianza", classes="indicador-barra")
        yield Label("Afecto:", classes="indicador-etiqueta")
        yield Label(self._barra(self._afecto), id="ind-afecto", classes="indicador-barra")
        yield Label("Familiaridad:", classes="indicador-etiqueta")
        yield Label(self._barra(self._familiaridad), id="ind-familiaridad", classes="indicador-barra")
        yield Label("Tensión:", classes="indicador-etiqueta")
        yield Label(self._barra(self._tension), id="ind-tension", classes="indicador-barra-tension")

    def actualizar(
        self,
        etapa: str,
        emocion: str,
        confianza: float,
        afecto: float,
        familiaridad: float,
        tension: float,
    ) -> None:
        """Actualiza todos los valores del panel y refresca los labels."""
        self._etapa = etapa
        self._emocion = emocion
        self._confianza = confianza
        self._afecto = afecto
        self._familiaridad = familiaridad
        self._tension = tension

        self.query_one("#ind-etapa", Label).update(etapa)
        self.query_one("#ind-emocion", Label).update(emocion)
        self.query_one("#ind-confianza", Label).update(self._barra(confianza))
        self.query_one("#ind-afecto", Label).update(self._barra(afecto))
        self.query_one("#ind-familiaridad", Label).update(self._barra(familiaridad))
        self.query_one("#ind-tension", Label).update(self._barra(tension))

    @staticmethod
    def _barra(valor: float, ancho: int = 20) -> str:
        """Genera una barra de progreso ASCII proporcional al valor [0.0, 1.0]."""
        rellenos = round(valor * ancho)
        porcentaje = int(valor * 100)
        return f"[{'█' * rellenos}{'░' * (ancho - rellenos)}] {porcentaje:3d}%"
