"""
PantallaOpcionesChat — modal de opciones para una conversación.

Muestra las acciones disponibles para una relación concreta:
  - Borrar conversación (con confirmación).
  - Editar instrucciones LLM del campo instrucciones_llm en RELACION.

Se abre encima del MenuPrincipal y se cierra con Escape o tras ejecutar la acción.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, TextArea

from dominio.modelos import Estado, Relacion
from dominio.valores_iniciales import RELACION_VALORES_INICIALES, ESTADO_VALORES_INICIALES
from repositorios.json.factoria import Repositorios


class PantallaOpcionesChat(ModalScreen):
    """
    Modal con opciones de gestión para una conversación.

    Flujo de borrado:
        1. Se muestra la lista de opciones.
        2. Al pulsar "Borrar conversación", se pide confirmación.
        3. Al confirmar, se eliminan mensajes, eventos, recuerdos,
           perfil y conflictos de la relación, y se resetean
           relación y estado a valores iniciales.
        4. El modal se cierra y el menú principal se refresca.
    """

    DEFAULT_CSS = """
    PantallaOpcionesChat {
        align: center middle;
    }

    #dialogo {
        width: 60;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 2 3;
    }

    #titulo {
        text-style: bold;
        margin-bottom: 1;
    }

    #descripcion {
        color: $text-muted;
        margin-bottom: 1;
    }

    #aviso-confirmacion {
        color: $warning;
        margin-bottom: 1;
    }

    .boton-opcion {
        width: 100%;
        margin-bottom: 1;
    }

    #btn-confirmar-borrar {
        width: 100%;
        margin-bottom: 1;
    }

    #btn-cancelar {
        width: 100%;
    }

    #area-instrucciones {
        width: 100%;
        height: 10;
        margin-bottom: 1;
    }

    #btn-guardar-instrucciones {
        width: 100%;
        margin-bottom: 1;
    }

    #btn-cancelar-instrucciones {
        width: 100%;
    }
    """

    BINDINGS = [("escape", "dismiss", "Cerrar")]

    def __init__(
        self,
        repos: Repositorios,
        relacion_id: int,
        nombre_personaje: str,
    ) -> None:
        super().__init__()
        self._repos = repos
        self._relacion_id = relacion_id
        self._nombre_personaje = nombre_personaje
        self._confirmar_borrado = False

    def compose(self) -> ComposeResult:
        with Vertical(id="dialogo"):
            yield Label(f"Opciones · {self._nombre_personaje}", id="titulo")
            yield Button(
                "✏️  Instrucciones LLM",
                id="btn-instrucciones",
                variant="primary",
                classes="boton-opcion",
            )
            yield Button(
                "🗑  Borrar conversación",
                id="btn-borrar",
                variant="error",
                classes="boton-opcion",
            )
            yield Button("Cerrar", id="btn-cerrar", variant="default", classes="boton-opcion")

    def on_button_pressed(self, evento: Button.Pressed) -> None:
        if evento.button.id == "btn-instrucciones":
            self._mostrar_editor_instrucciones()
        elif evento.button.id == "btn-borrar":
            self._mostrar_confirmacion()
        elif evento.button.id == "btn-confirmar-borrar":
            self._ejecutar_borrado()
        elif evento.button.id == "btn-guardar-instrucciones":
            self._guardar_instrucciones()
        elif evento.button.id in ("btn-cerrar", "btn-cancelar", "btn-cancelar-confirm", "btn-cancelar-instrucciones"):
            self.dismiss()

    # ---------------------------------------------------------------------------
    # Flujo de confirmación
    # ---------------------------------------------------------------------------

    def _mostrar_confirmacion(self) -> None:
        """Reemplaza los botones por la vista de confirmación."""
        dialogo = self.query_one("#dialogo", Vertical)
        dialogo.remove_children()
        # IDs distintos a los de la vista inicial para evitar DuplicateIds
        # (remove_children es asíncrono; los IDs antiguos siguen registrados)
        dialogo.mount(Label(f"¿Borrar chat con {self._nombre_personaje}?", id="titulo-confirm"))
        dialogo.mount(Label(
            "Se borrarán todos los mensajes, recuerdos y el progreso\n"
            "de la relación. Esta acción no se puede deshacer.",
            id="aviso-confirm",
        ))
        dialogo.mount(Button(
            "Sí, borrar todo",
            id="btn-confirmar-borrar",
            variant="error",
        ))
        dialogo.mount(Button("Cancelar", id="btn-cancelar-confirm", variant="default"))

    # ---------------------------------------------------------------------------
    # Flujo de edición de instrucciones LLM
    # ---------------------------------------------------------------------------

    def _mostrar_editor_instrucciones(self) -> None:
        """Reemplaza los botones por el editor de instrucciones_llm."""
        relacion = self._repos.relacion.obtener(self._relacion_id)
        texto_actual = relacion.instrucciones_llm or ""

        dialogo = self.query_one("#dialogo", Vertical)
        dialogo.remove_children()
        dialogo.mount(Label("Instrucciones LLM", id="titulo-instrucciones"))
        dialogo.mount(Label(
            "Texto libre que se incluirá en el prompt del LLM para este personaje.\n"
            "Deja vacío para desactivar.",
            id="desc-instrucciones",
        ))
        dialogo.mount(TextArea(texto_actual, id="area-instrucciones"))
        dialogo.mount(Button(
            "Guardar",
            id="btn-guardar-instrucciones",
            variant="success",
        ))
        dialogo.mount(Button("Cancelar", id="btn-cancelar-instrucciones", variant="default"))

    def _guardar_instrucciones(self) -> None:
        """Persiste el valor editado de instrucciones_llm en la relación."""
        area = self.query_one("#area-instrucciones", TextArea)
        texto = area.text.strip()
        relacion = self._repos.relacion.obtener(self._relacion_id)
        instrucciones = texto if texto else None
        relacion_actualizada = replace(relacion, instrucciones_llm=instrucciones)
        self._repos.relacion.guardar(relacion_actualizada)
        self.dismiss()

    # ---------------------------------------------------------------------------
    # Flujo de borrado
    # ---------------------------------------------------------------------------

    def _ejecutar_borrado(self) -> None:
        """
        Elimina todos los datos de la conversación y resetea la relación
        y el estado emocional a sus valores iniciales.
        """
        rid = self._relacion_id
        repos = self._repos

        # Borrar datos de conversación
        repos.mensaje.eliminar_por_relacion(rid)
        repos.recuerdo.eliminar_por_relacion(rid)
        repos.perfil_usuario.eliminar_por_relacion(rid)
        repos.conflicto.eliminar_por_relacion(rid)
        repos.evento.eliminar_por_relacion(rid)

        # Resetear relación a valores iniciales
        relacion = repos.relacion.obtener(rid)
        relacion_reseteada = replace(relacion, **RELACION_VALORES_INICIALES)
        repos.relacion.guardar(relacion_reseteada)

        # Resetear estado emocional
        estado = repos.estado.obtener(rid)
        estado_reseteado = replace(estado, **ESTADO_VALORES_INICIALES, ultima_interaccion=datetime.now())
        repos.estado.guardar(estado_reseteado)

        self.dismiss()
