"""
PantallaSeleccionPersonaje — modal para iniciar un nuevo chat.

Lista los personajes disponibles en /data y permite elegir con cuál
crear una nueva relación. Si ya existe una relación activa con ese
personaje, la opción aparece deshabilitada.

Al confirmar, crea Relacion y Estado iniciales y abre PantallaChat.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from aplicacion.gestor_turno import GestorTurno
from dominio.modelos import Personaje
from dominio.valores_iniciales import nueva_relacion, nuevo_estado
from repositorios.json._utilidades import siguiente_id, leer_json
from repositorios.json.factoria import Repositorios


class PantallaSeleccionPersonaje(ModalScreen):
    """
    Modal que lista todos los personajes disponibles para iniciar un chat.

    Para cada personaje muestra nombre, MBTI y eneagrama.
    Si ya existe una relación activa, el botón queda deshabilitado.
    """

    DEFAULT_CSS = """
    PantallaSeleccionPersonaje {
        align: center middle;
    }

    #dialogo {
        width: 55;
        height: auto;
        max-height: 80%;
        border: solid $accent;
        background: $surface;
        padding: 2 3;
    }

    #titulo {
        text-style: bold;
        margin-bottom: 1;
    }

    #lista-personajes {
        height: auto;
        max-height: 30;
    }

    .tarjeta-personaje {
        height: auto;
        border: solid $surface-lighten-2;
        margin-bottom: 1;
        padding: 1;
        background: $surface-darken-1;
    }

    .nombre-personaje {
        text-style: bold;
    }

    .meta-personaje {
        color: $text-muted;
        margin-bottom: 1;
    }

    .btn-iniciar {
        width: 100%;
    }

    #btn-cancelar {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "dismiss", "Cancelar")]

    def __init__(self, repos: Repositorios, gestor: GestorTurno) -> None:
        super().__init__()
        self._repos = repos
        self._gestor = gestor

    def compose(self) -> ComposeResult:
        personajes = self._repos.personaje.listar()
        relaciones_existentes = {
            r.personaje_id
            for r in self._repos.relacion.listar_por_usuario(usuario_id=1)
        }

        with Vertical(id="dialogo"):
            yield Label("Nuevo chat — elige un personaje", id="titulo")
            with ScrollableContainer(id="lista-personajes"):
                if not personajes:
                    yield Label("No hay personajes disponibles.", classes="meta-personaje")
                for personaje in personajes:
                    ya_existe = personaje.num in relaciones_existentes
                    with Vertical(classes="tarjeta-personaje"):
                        yield Label(personaje.nombre, classes="nombre-personaje")
                        yield Label(
                            f"{personaje.mbti_id} · {personaje.eneagrama_id} · {personaje.temperamento_id}",
                            classes="meta-personaje",
                        )
                        yield Label(personaje.descripcion[:80] + "…" if len(personaje.descripcion) > 80 else personaje.descripcion, classes="meta-personaje")
                        yield Button(
                            "Continuar conversación" if ya_existe else "Iniciar chat",
                            id=f"btn-iniciar-{personaje.num}",
                            variant="primary",
                            classes="btn-iniciar",
                        )
            yield Button("Cancelar", id="btn-cancelar", variant="default")

    def on_button_pressed(self, evento: Button.Pressed) -> None:
        bid = evento.button.id or ""
        if bid == "btn-cancelar":
            self.dismiss()
            return
        if bid.startswith("btn-iniciar-"):
            personaje_id = int(bid.removeprefix("btn-iniciar-"))
            self._crear_relacion_y_abrir(personaje_id)

    def _crear_relacion_y_abrir(self, personaje_id: int) -> None:
        """Abre la relación existente o crea una nueva si no existe."""
        repos = self._repos

        # Si ya existe una relación con este personaje, reutilizarla
        existentes = repos.relacion.listar_por_usuario(usuario_id=1)
        for rel in existentes:
            if rel.personaje_id == personaje_id:
                def _abrir_existente(rid=rel.num) -> None:
                    from interfaz.pantallas.chat import PantallaChat
                    self.app.push_screen(PantallaChat(self._gestor, relacion_id=rid))
                self.dismiss(_abrir_existente)
                return

        # No existe — crear relación y estado iniciales
        todas_relaciones = leer_json(repos.relacion._ruta)
        nuevo_num = siguiente_id(todas_relaciones)

        repos.relacion.guardar(nueva_relacion(nuevo_num, personaje_id, usuario_id=1))
        repos.estado.guardar(nuevo_estado(nuevo_num))

        def _abrir_nueva(rid=nuevo_num) -> None:
            from interfaz.pantallas.chat import PantallaChat
            self.app.push_screen(PantallaChat(self._gestor, relacion_id=rid))

        self.dismiss(_abrir_nueva)
