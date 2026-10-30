"""
PantallaChat — pantalla principal de conversación.

Layout:
    ┌─────────────────────────┬──────────────────┐
    │  Historial de mensajes  │  Panel de estado │
    │  (scrollable)           │  (IndicadorEstado)│
    ├─────────────────────────┴──────────────────┤
    │  Input del usuario                [Enviar] │
    └────────────────────────────────────────────┘

El procesamiento del turno se ejecuta en un worker de Textual para no
bloquear el hilo principal mientras el LLM responde.
"""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label

from aplicacion.gestor_turno import GestorTurno, ResultadoTurno
from dominio.emociones import calcular_emocion_actual
from interfaz.widgets.burbuja import BurbujaMensaje
from interfaz.widgets.indicador import IndicadorEstado


class PantallaChat(Screen):
    """
    Pantalla principal. Recibe el gestor_turno y relacion_id como parámetros
    para mantenerse desacoplada de cómo se construyeron.
    """

    BINDINGS = [
        ("ctrl+q", "app.quit", "Salir"),
        ("ctrl+e", "toggle_estado", "Panel estado"),
    ]

    DEFAULT_CSS = """
    PantallaChat {
        layout: vertical;
    }

    #contenedor-principal {
        height: 1fr;
    }

    #historial {
        width: 3fr;
        height: 100%;
        padding: 1;
        border-right: solid $surface-lighten-1;
    }

    #panel-estado {
        width: 1fr;
        height: 100%;
        padding: 1;
    }

    #panel-estado.oculto {
        display: none;
    }

    #barra-input {
        height: 3;
        padding: 0 1;
        align: left middle;
        background: $surface-darken-1;
        border-top: solid $surface-lighten-1;
    }

    #campo-input {
        width: 1fr;
        margin-right: 1;
    }

    #boton-enviar {
        width: auto;
    }

    #etiqueta-pensando {
        display: none;
        color: $text-muted;
        padding: 0 1;
    }

    #etiqueta-pensando.visible {
        display: block;
    }
    """

    def __init__(self, gestor: GestorTurno, relacion_id: int) -> None:
        super().__init__()
        self._gestor = gestor
        self._relacion_id = relacion_id
        self._procesando = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="contenedor-principal"):
            with ScrollableContainer(id="historial"):
                pass
            with Vertical(id="panel-estado"):
                yield IndicadorEstado()
        with Horizontal(id="barra-input"):
            yield Input(placeholder="Escribe un mensaje…", id="campo-input")
            yield Label("pensando…", id="etiqueta-pensando")
            yield Button("Enviar", variant="primary", id="boton-enviar")
        yield Footer()

    def on_mount(self) -> None:
        """Al montar, cargar historial existente y actualizar el panel de estado."""
        self._cargar_historial_inicial()
        self._actualizar_panel_estado()
        self.query_one("#campo-input", Input).focus()

    def _cargar_historial_inicial(self) -> None:
        repos = self._gestor._repos
        mensajes = repos.mensaje.listar_por_relacion(self._relacion_id)
        historial = self.query_one("#historial", ScrollableContainer)
        for mensaje in mensajes:
            historial.mount(BurbujaMensaje(mensaje.rol, mensaje.contenido))
        historial.scroll_end(animate=False)

    def _actualizar_panel_estado(self) -> None:
        repos = self._gestor._repos
        relacion = repos.relacion.obtener(self._relacion_id)
        estado = repos.estado.obtener(self._relacion_id)
        catalogo = repos.catalogos.obtener_emociones()
        etapas = {e.codigo: e for e in repos.catalogos.obtener_etapas_relacion()}

        emocion_actual = calcular_emocion_actual(estado, catalogo)
        etapa_nombre = etapas.get(relacion.etapa, None)
        etapa_str = etapa_nombre.nombre if etapa_nombre else relacion.etapa

        self.query_one(IndicadorEstado).actualizar(
            etapa=etapa_str,
            emocion=emocion_actual.nombre,
            confianza=relacion.confianza,
            afecto=relacion.afecto,
            familiaridad=relacion.familiaridad,
            tension=relacion.tension,
        )

    @on(Button.Pressed, "#boton-enviar")
    def _al_pulsar_enviar(self) -> None:
        self._enviar_mensaje()

    @on(Input.Submitted, "#campo-input")
    def _al_pulsar_enter(self) -> None:
        self._enviar_mensaje()

    def _enviar_mensaje(self) -> None:
        if self._procesando:
            return
        campo = self.query_one("#campo-input", Input)
        texto = campo.value.strip()
        if not texto:
            return
        campo.value = ""
        self._procesando = True
        self._mostrar_pensando(True)

        # Añadir burbuja del usuario al instante
        historial = self.query_one("#historial", ScrollableContainer)
        historial.mount(BurbujaMensaje("usuario", texto))
        historial.scroll_end(animate=True)

        # Procesar en worker para no bloquear la UI
        self._procesar_turno(texto)

    @work(thread=True)
    def _procesar_turno(self, texto: str) -> None:
        resultado = self._gestor.procesar(self._relacion_id, texto)
        self.app.call_from_thread(self._on_turno_completado, resultado)

    def _on_turno_completado(self, resultado: ResultadoTurno) -> None:
        historial = self.query_one("#historial", ScrollableContainer)
        historial.mount(BurbujaMensaje("personaje", resultado.respuesta))
        historial.scroll_end(animate=True)

        if resultado.transicion_aplicada:
            aviso = (
                f"✨ La relación ha avanzado: "
                f"{resultado.etapa_anterior} → {resultado.etapa_nueva}"
            )
            historial.mount(BurbujaMensaje("sistema", aviso))
            historial.scroll_end(animate=True)

        self._actualizar_panel_estado()
        self._mostrar_pensando(False)
        self._procesando = False
        self.query_one("#campo-input", Input).focus()

    def _mostrar_pensando(self, visible: bool) -> None:
        etiqueta = self.query_one("#etiqueta-pensando", Label)
        boton = self.query_one("#boton-enviar", Button)
        if visible:
            etiqueta.add_class("visible")
            boton.disabled = True
        else:
            etiqueta.remove_class("visible")
            boton.disabled = False

    def action_toggle_estado(self) -> None:
        """Ctrl+E: mostrar/ocultar el panel lateral de estado."""
        panel = self.query_one("#panel-estado", Vertical)
        panel.toggle_class("oculto")
