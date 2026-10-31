"""
PantallaMenuPrincipal — pantalla de inicio de la aplicación.

Layout:
    ┌──────────────────────────────────────────┐
    │  novia_AI                    [q] Salir   │
    ├──────────────────────────────────────────┤
    │                                          │
    │   ┌──────────────────────────────────┐   │
    │   │  Luna  INFJ · 4w5               │   │
    │   │  conocidos  ·  hace 5 min  [⋮]  │   │
    │   └──────────────────────────────────┘   │
    │                                          │
    ├──────────────────────────────────────────┤
    │  [c] Configuración                       │
    └──────────────────────────────────────────┘

Cada tarjeta de chat tiene un botón [⋮] que abre PantallaOpcionesChat.
"""

from __future__ import annotations

from datetime import datetime, timezone

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Static

from aplicacion.gestor_turno import GestorTurno
from dominio.modelos import Personaje, Relacion
from repositorios.json.factoria import Repositorios


class TarjetaChat(Static):
    """
    Widget que representa una conversación en el menú principal.

    Muestra nombre del personaje, MBTI, eneagrama, etapa y tiempo
    desde la última interacción. Incluye botón [⋮] para opciones.
    """

    DEFAULT_CSS = """
    TarjetaChat {
        height: auto;
        border: solid $surface-lighten-2;
        margin: 0 2 1 2;
        padding: 1 2;
        background: $surface;
    }

    TarjetaChat:focus-within {
        border: solid $accent;
    }

    TarjetaChat #fila-principal {
        layout: horizontal;
        height: auto;
    }

    TarjetaChat #info-chat {
        width: 1fr;
        height: auto;
    }

    TarjetaChat #nombre-personaje {
        text-style: bold;
    }

    TarjetaChat #meta-personaje {
        color: $text-muted;
    }

    TarjetaChat #btn-abrir {
        width: 1fr;
        margin: 0 1 0 0;
    }

    TarjetaChat #btn-opciones {
        width: 5;
        min-width: 5;
    }
    """

    def __init__(
        self,
        relacion: Relacion,
        personaje: Personaje,
        ultima_interaccion: datetime,
    ) -> None:
        super().__init__()
        self._relacion = relacion
        self._personaje = personaje
        self._ultima_interaccion = ultima_interaccion

    def compose(self) -> ComposeResult:
        tiempo = _tiempo_relativo(self._ultima_interaccion)
        meta = f"{self._personaje.mbti_id} · {self._personaje.eneagrama_id}  ·  {self._relacion.etapa}  ·  {tiempo}"

        with Vertical(id="fila-principal"):
            yield Label(self._personaje.nombre, id="nombre-personaje")
            yield Label(meta, id="meta-personaje")
            yield Button(
                "Continuar conversación",
                id="btn-abrir",
                variant="primary",
            )
            yield Button("⋮", id="btn-opciones", variant="default")

    def on_button_pressed(self, evento: Button.Pressed) -> None:
        if evento.button.id == "btn-abrir":
            self.post_message(MenuPrincipal.AbrirChat(self._relacion.num))
        elif evento.button.id == "btn-opciones":
            self.post_message(MenuPrincipal.AbrirOpciones(self._relacion.num, self._personaje.nombre))


class MenuPrincipal(Screen):
    """
    Pantalla de inicio. Muestra la lista de conversaciones activas
    y accesos a configuración.
    """

    # ---------------------------------------------------------------------------
    # Mensajes
    # ---------------------------------------------------------------------------

    class AbrirChat(Message):
        """Solicita abrir la pantalla de chat para una relación."""
        def __init__(self, relacion_id: int) -> None:
            super().__init__()
            self.relacion_id = relacion_id

    class AbrirOpciones(Message):
        """Solicita abrir el modal de opciones para una relación."""
        def __init__(self, relacion_id: int, nombre_personaje: str) -> None:
            super().__init__()
            self.relacion_id = relacion_id
            self.nombre_personaje = nombre_personaje

    # ---------------------------------------------------------------------------
    # Bindings y CSS
    # ---------------------------------------------------------------------------

    BINDINGS = [
        ("ctrl+q", "app.quit", "Salir"),
    ]

    DEFAULT_CSS = """
    MenuPrincipal {
        layout: vertical;
    }

    #contenedor-chats {
        height: 1fr;
        padding: 1 0;
    }

    #sin-chats {
        margin: 2 4;
        color: $text-muted;
    }

    #pie-menu {
        height: auto;
        padding: 1 2;
        border-top: solid $surface-lighten-1;
        layout: horizontal;
        align: left middle;
    }

    #pie-menu Button {
        margin-right: 1;
    }
    """

    def __init__(self, repos: Repositorios, gestor: GestorTurno) -> None:
        super().__init__()
        self._repos = repos
        self._gestor = gestor

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer(id="contenedor-chats"):
            relaciones = self._repos.relacion.listar_por_usuario(usuario_id=1)
            if not relaciones:
                yield Label("No hay conversaciones activas.", id="sin-chats")
            else:
                for relacion in relaciones:
                    try:
                        personaje = self._repos.personaje.obtener(relacion.personaje_id)
                        estado = self._repos.estado.obtener(relacion.num)
                        yield TarjetaChat(relacion, personaje, estado.ultima_interaccion)
                    except KeyError:
                        pass
        with Horizontal(id="pie-menu"):
            yield Button("＋ Nuevo chat", id="btn-nuevo-chat", variant="success")
            yield Button("Salir", id="btn-salir", variant="error")
        yield Footer()

    def on_button_pressed(self, evento: Button.Pressed) -> None:
        if evento.button.id == "btn-nuevo-chat":
            from interfaz.pantallas.seleccion_personaje import PantallaSeleccionPersonaje
            self.app.push_screen(
                PantallaSeleccionPersonaje(self._repos, self._gestor),
                callback=self._tras_seleccion_personaje,
            )
        elif evento.button.id == "btn-salir":
            self.app.exit()

    def _tras_seleccion_personaje(self, abrir_chat) -> None:
        """Callback del modal de selección: si devolvió una función, ejecutarla."""
        if callable(abrir_chat):
            abrir_chat()

    def on_menu_principal_abrir_chat(self, mensaje: AbrirChat) -> None:
        from interfaz.pantallas.chat import PantallaChat
        self.app.push_screen(PantallaChat(self._gestor, relacion_id=mensaje.relacion_id))

    def on_menu_principal_abrir_opciones(self, mensaje: AbrirOpciones) -> None:
        from interfaz.pantallas.opciones_chat import PantallaOpcionesChat
        self.app.push_screen(
            PantallaOpcionesChat(
                repos=self._repos,
                relacion_id=mensaje.relacion_id,
                nombre_personaje=mensaje.nombre_personaje,
            )
        )

    def on_screen_resume(self) -> None:
        """Al volver al menú desde otra pantalla, refrescar la lista de chats."""
        self.refresh(recompose=True)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _tiempo_relativo(ultima: datetime) -> str:
    """Devuelve una cadena legible del tiempo transcurrido desde `ultima`."""
    ahora = datetime.now()
    # Normalizar timezone: si ultima tiene tz y ahora no, quitar tz
    if ultima.tzinfo is not None:
        ultima = ultima.replace(tzinfo=None)
    segundos = max(0, (ahora - ultima).total_seconds())

    if segundos < 60:
        return "ahora mismo"
    if segundos < 3600:
        m = int(segundos // 60)
        return f"hace {m} min"
    if segundos < 86400:
        h = int(segundos // 3600)
        return f"hace {h} h"
    d = int(segundos // 86400)
    return f"hace {d} días"
