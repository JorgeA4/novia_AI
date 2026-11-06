"""
Widget BurbujaDiagnostico — burbuja colapsable que muestra el diagnóstico
de contexto de un turno (estado emocional enviado al LLM, recuerdos inyectados,
conflictos activos y deltas devueltos).

Aparece justo debajo de cada respuesta del personaje cuando el modo tester
está activo. Pulsar sobre el encabezado la expande o colapsa.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.events import Click
from textual.widget import Widget
from textual.widgets import Label, Static

from aplicacion.gestor_turno import DiagnosticoContexto


class BurbujaDiagnostico(Widget):
    """
    Burbuja de diagnóstico colapsable.

    Encabezado siempre visible: "▶ contexto turno #N".
    Cuerpo expandible: secciones de estado emocional, recuerdos, conflictos
    y deltas devueltos por el LLM.
    """

    DEFAULT_CSS = """
    BurbujaDiagnostico {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }

    BurbujaDiagnostico #diag-encabezado {
        color: $text-muted;
        padding: 0 2;
        background: $surface-darken-2;
        border: round $surface-lighten-1;
        width: auto;
        max-width: 40%;
    }

    BurbujaDiagnostico #diag-encabezado:hover {
        color: $accent;
        border: round $accent;
    }

    BurbujaDiagnostico #diag-cuerpo {
        display: none;
        padding: 1 2;
        border: round $surface-lighten-1;
        background: $surface-darken-2;
        color: $text-muted;
        width: 80%;
        margin-top: 0;
    }

    BurbujaDiagnostico #diag-cuerpo.expandido {
        display: block;
    }

    BurbujaDiagnostico .diag-seccion {
        text-style: bold;
        color: $accent;
        margin-top: 1;
    }

    BurbujaDiagnostico .diag-linea {
        color: $text;
    }

    BurbujaDiagnostico .diag-linea-muted {
        color: $text-muted;
    }

    BurbujaDiagnostico .diag-delta-pos {
        color: $success;
    }

    BurbujaDiagnostico .diag-delta-neg {
        color: $error;
    }

    BurbujaDiagnostico .diag-delta-neu {
        color: $text-muted;
    }
    """

    def __init__(self, diagnostico: DiagnosticoContexto) -> None:
        super().__init__()
        self._d = diagnostico
        self._expandido = False

    def compose(self) -> ComposeResult:
        d = self._d
        yield Label(
            f"▶ contexto turno #{d.num_turno}",
            id="diag-encabezado",
        )
        with Static(id="diag-cuerpo"):
            # --- Estado emocional enviado al LLM ---
            yield Label("Estado emocional (enviado al LLM)", classes="diag-seccion")
            yield Label(
                f"  emoción:   {d.emocion_id}  {_barra_corta(d.emocion_intensidad)}",
                classes="diag-linea",
                markup=False,
            )
            yield Label(
                f"  ánimo:     {d.estado_animo_id}  {_barra_corta(d.estado_animo_intensidad)}",
                classes="diag-linea",
                markup=False,
            )
            yield Label(
                f"  sentim.:   {d.sentimiento_id}  {_barra_corta(d.sentimiento_intensidad)}",
                classes="diag-linea",
                markup=False,
            )

            # --- Recuerdos inyectados ---
            yield Label(
                f"Recuerdos inyectados ({len(d.recuerdos_inyectados)})",
                classes="diag-seccion",
            )
            if d.recuerdos_inyectados:
                for contenido, relevancia in zip(d.recuerdos_inyectados, d.relevancia_recuerdos):
                    linea = f"  [{relevancia:.2f}] {contenido}"
                    yield Label(linea, classes="diag-linea", markup=False)
            else:
                yield Label("  —", classes="diag-linea-muted", markup=False)

            # --- Conflictos activos ---
            yield Label(
                f"Conflictos activos ({len(d.conflictos_activos)})",
                classes="diag-seccion",
            )
            if d.conflictos_activos:
                for c in d.conflictos_activos:
                    yield Label(f"  {c}", classes="diag-linea", markup=False)
            else:
                yield Label("  —", classes="diag-linea-muted", markup=False)

            # --- Deltas devueltos por el LLM ---
            yield Label("Deltas devueltos por el LLM", classes="diag-seccion")
            yield Label(
                f"  afecto:    {d.delta_afecto:+.2f}",
                classes=_clase_delta(d.delta_afecto),
                markup=False,
            )
            yield Label(
                f"  confianza: {d.delta_confianza:+.2f}",
                classes=_clase_delta(d.delta_confianza),
                markup=False,
            )
            yield Label(
                f"  tensión:   {d.delta_tension:+.2f}",
                classes=(
                    "diag-delta-neg" if d.delta_tension >= 0.05
                    else "diag-delta-pos" if d.delta_tension <= -0.05
                    else "diag-delta-neu"
                ),
                markup=False,
            )
            yield Label(
                f"  atracción: {d.delta_atraccion:+.2f}",
                classes=_clase_delta(d.delta_atraccion),
                markup=False,
            )

            # --- Métricas pre-turno + interés ---
            yield Label("Métricas (antes de este turno)", classes="diag-seccion")
            yield Label(
                f"  confianza: {d.confianza_pre:.2f}  "
                f"afecto: {d.afecto_pre:.2f}  "
                f"tensión: {d.tension_pre:.2f}  "
                f"familiar.: {d.familiaridad_pre:.2f}",
                classes="diag-linea",
                markup=False,
            )
            yield Label(
                f"  disposición: {d.disposicion_pre:.2f}  "
                f"atracción: {d.atraccion_pre:.2f}",
                classes="diag-linea",
                markup=False,
            )
            yield Label(
                f"  interes_ahora: {d.interes_actual:.2f}  "
                f"{_barra_corta(d.interes_actual)}",
                classes=_clase_delta(d.interes_actual - 0.5),
                markup=False,
            )

    @on(Click, "#diag-encabezado")
    def _al_pulsar_encabezado(self) -> None:
        self._expandido = not self._expandido
        cuerpo = self.query_one("#diag-cuerpo", Static)
        encabezado = self.query_one("#diag-encabezado", Label)
        if self._expandido:
            cuerpo.add_class("expandido")
            encabezado.update(f"▼ contexto turno #{self._d.num_turno}")
        else:
            cuerpo.remove_class("expandido")
            encabezado.update(f"▶ contexto turno #{self._d.num_turno}")


# ---------------------------------------------------------------------------
# Utilidades de formateo
# ---------------------------------------------------------------------------

def _barra_corta(valor: float, ancho: int = 8) -> str:
    """Barra de progreso compacta para el diagnóstico."""
    rellenos = round(valor * ancho)
    return f"{'█' * rellenos}{'░' * (ancho - rellenos)}  {int(valor * 100):3d}%"


def _clase_delta(delta: float) -> str:
    if delta >= 0.05:
        return "diag-delta-pos"
    if delta <= -0.05:
        return "diag-delta-neg"
    return "diag-delta-neu"
