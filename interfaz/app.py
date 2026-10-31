"""
App principal — punto de entrada de la interfaz Textual.

Responsabilidades:
    - Leer configuración de entorno (ruta de datos, proveedor LLM, clave API).
    - Construir los repositorios y el gestor de turno.
    - Garantizar que existan datos mínimos (personaje y usuario por defecto).
    - Lanzar la PantallaChat.

Uso:
    python main.py          ← forma recomendada (lee .env automáticamente)
    python -m interfaz      ← alternativa sin carga de .env

Variables de entorno (configurar en .env — ver .env.ejemplo):
    PROVEEDOR         — "gemini" | "openai" | "stub"
                        Si no se define: gemini si hay GEMINI_API_KEY, si no openai.
    NOVIA_DATOS       — ruta al directorio de datos (por defecto: ./data)
    NOVIA_STUB        — alternativa a PROVEEDOR=stub (retrocompatibilidad)

    Proveedor gemini:
    GEMINI_API_KEY    — clave de API de Google Gemini
    NOVIA_MODELO      — modelo (por defecto: gemini-1.5-flash)

    Proveedor openai (también Ollama, LM Studio, OpenRouter, etc.):
    OPENAI_API_KEY    — clave de API
    NOVIA_MODELO      — modelo (por defecto: gpt-4o-mini)
    NOVIA_URL_BASE    — URL base alternativa para servidores compatibles
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult

from aplicacion.cliente_llm import ClienteGemini, ClienteOpenAI, ClienteStub
from aplicacion.gestor_turno import GestorTurno
from dominio.modelos import Estado, Personaje, Relacion, Usuario
from interfaz.pantallas.menu_principal import MenuPrincipal
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
    confianza_delta=0.0,
    afecto=0.05,
    afecto_delta=0.0,
    familiaridad=0.0,
    tension=0.0,
    disposicion=0.5,
    disposicion_delta=0.0,
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

        # Cliente LLM — se elige el proveedor según PROVEEDOR (o heurística por clave)
        cliente = _crear_cliente_llm()

        self._gestor = GestorTurno(self._repos, cliente)

    def on_mount(self) -> None:
        """Al montar, ajustar subtítulo con el proveedor activo."""
        self.SUB_TITLE = _nombre_proveedor_activo()
        self.call_after_refresh(self.push_screen, MenuPrincipal(self._repos, self._gestor))


# ---------------------------------------------------------------------------
# Selección de proveedor LLM
# ---------------------------------------------------------------------------

def _crear_cliente_llm():
    """
    Elige e instancia el cliente LLM según las variables de entorno.

    Orden de prioridad:
        1. NOVIA_STUB o PROVEEDOR=stub  → ClienteStub (sin LLM real)
        2. PROVEEDOR=gemini             → ClienteGemini
        3. PROVEEDOR=openai             → ClienteOpenAI
        4. Sin PROVEEDOR + GEMINI_API_KEY → ClienteGemini  (retrocompatibilidad)
        5. Sin PROVEEDOR                → ClienteOpenAI   (fallback)
    """
    proveedor = os.environ.get("PROVEEDOR", "").lower().strip()

    if os.environ.get("NOVIA_STUB") or proveedor == "stub":
        return ClienteStub("… (modo stub sin LLM)")

    if proveedor == "gemini" or (not proveedor and os.environ.get("GEMINI_API_KEY")):
        return ClienteGemini(
            modelo=os.environ.get("NOVIA_MODELO", "gemini-1.5-flash"),
            api_key=os.environ.get("GEMINI_API_KEY"),
        )

    # openai explícito o fallback
    return ClienteOpenAI(
        modelo=os.environ.get("NOVIA_MODELO", "gpt-4o-mini"),
        url_base=os.environ.get("NOVIA_URL_BASE") or None,
        api_key=os.environ.get("OPENAI_API_KEY"),
    )


def _nombre_proveedor_activo() -> str:
    """Devuelve una cadena legible con el proveedor y modelo activos."""
    proveedor = os.environ.get("PROVEEDOR", "").lower().strip()

    if os.environ.get("NOVIA_STUB") or proveedor == "stub":
        return "stub (sin LLM)"

    if proveedor == "gemini" or (not proveedor and os.environ.get("GEMINI_API_KEY")):
        modelo = os.environ.get("NOVIA_MODELO", "gemini-1.5-flash")
        return f"gemini · {modelo}"

    modelo = os.environ.get("NOVIA_MODELO", "gpt-4o-mini")
    url = os.environ.get("NOVIA_URL_BASE")
    if url:
        return f"openai-compat · {modelo} · {url}"
    return f"openai · {modelo}"


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    NoviApp().run()


if __name__ == "__main__":
    main()
