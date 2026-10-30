"""
App principal — punto de entrada de la interfaz Textual.

Responsabilidades:
    - Leer configuración de entorno (ruta de datos, proveedor LLM, clave API).
    - Construir los repositorios y el gestor de turno.
    - Garantizar que existan datos mínimos (personaje y usuario por defecto).
    - Lanzar la PantallaChat.

Uso:
    python -m interfaz.app

Variables de entorno:
    NOVIA_DATOS       — ruta al directorio de datos (por defecto: ./data)
    OPENAI_API_KEY    — clave de API de OpenAI
    NOVIA_MODELO      — modelo a usar (por defecto: gpt-4o-mini)
    NOVIA_URL_BASE    — URL base alternativa (Ollama, LM Studio, etc.)
    NOVIA_STUB        — si está definida, usa el ClienteStub en lugar del real
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult

from aplicacion.cliente_llm import ClienteOpenAI, ClienteStub
from aplicacion.gestor_turno import GestorTurno
from dominio.modelos import Estado, Personaje, Relacion, Usuario
from interfaz.pantallas.chat import PantallaChat
from repositorios.json.factoria import Repositorios, crear_repositorios


# ---------------------------------------------------------------------------
# Datos por defecto para la primera ejecución
# ---------------------------------------------------------------------------

PERSONAJE_DEFECTO = Personaje(
    num=1,
    nombre="Luna",
    descripcion=(
        "Chica inteligente y algo reservada. Observadora, con humor sutil "
        "y mucha profundidad emocional. Le cuesta abrirse, pero cuando lo hace "
        "es completamente sincera."
    ),
    historia=(
        "Creció en un pueblo pequeño. Estudió literatura. Vive sola en la ciudad "
        "desde hace tres años y todavía le cuesta encontrar personas con quienes "
        "conectar de verdad."
    ),
    valores=["honestidad", "lealtad", "profundidad"],
    gustos=["leer", "música indie", "el silencio cómodo", "el café solo"],
    aversiones=["falsedad", "superficialidad", "el ruido innecesario"],
    mbti_id="INFJ",
    eneagrama_id="4w5",
    temperamento_id="melancolico",
)

USUARIO_DEFECTO = Usuario(num=1, nombre="tú")

RELACION_DEFECTO = Relacion(
    num=1,
    personaje_id=1,
    usuario_id=1,
    etapa="desconocidos",
    confianza=0.05,
    afecto=0.05,
    familiaridad=0.0,
    tension=0.0,
)

ESTADO_DEFECTO = Estado(
    relacion_id=1,
    emocion_id="neutro",
    emocion_intensidad=0.3,
    estado_animo_id="neutro",
    estado_animo_intensidad=0.2,
    sentimiento_id="neutro",
    sentimiento_intensidad=0.1,
    ultima_interaccion=datetime.now(),
)


# ---------------------------------------------------------------------------
# Inicialización de datos mínimos
# ---------------------------------------------------------------------------

def _asegurar_datos_iniciales(repos: Repositorios) -> None:
    """
    Si no existe ningún personaje o relación, crea los datos por defecto.
    Esto permite arrancar sin configuración manual en la primera ejecución.
    """
    try:
        repos.personaje.obtener(1)
    except KeyError:
        repos.personaje.guardar(PERSONAJE_DEFECTO)

    try:
        repos.usuario.obtener(1)
    except KeyError:
        repos.usuario.guardar(USUARIO_DEFECTO)

    try:
        repos.relacion.obtener(1)
    except KeyError:
        repos.relacion.guardar(RELACION_DEFECTO)

    try:
        repos.estado.obtener(1)
    except KeyError:
        repos.estado.guardar(ESTADO_DEFECTO)


# ---------------------------------------------------------------------------
# App Textual
# ---------------------------------------------------------------------------

class NoviApp(App):
    """Aplicación principal."""

    TITLE = "novia_AI"
    SUB_TITLE = "conversación"

    CSS = """
    Screen {
        background: $surface;
    }
    """

    def __init__(self) -> None:
        super().__init__()

        # Directorio de datos
        ruta_datos = Path(os.environ.get("NOVIA_DATOS", "data"))

        # Repositorios
        self._repos = crear_repositorios(ruta_datos)
        _asegurar_datos_iniciales(self._repos)

        # Cliente LLM
        if os.environ.get("NOVIA_STUB"):
            cliente = ClienteStub("… (modo stub sin LLM)")
        else:
            cliente = ClienteOpenAI(
                modelo=os.environ.get("NOVIA_MODELO", "gpt-4o-mini"),
                url_base=os.environ.get("NOVIA_URL_BASE") or None,
                api_key=os.environ.get("OPENAI_API_KEY"),
            )

        self._gestor = GestorTurno(self._repos, cliente)

    def on_mount(self) -> None:
        self.push_screen(PantallaChat(self._gestor, relacion_id=1))


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    NoviApp().run()


if __name__ == "__main__":
    main()
