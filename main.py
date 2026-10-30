"""
Punto de entrada principal — ejecuta la aplicación desde la raíz del proyecto.

Uso:
    python main.py

Configuración:
    Crea un archivo .env en la raíz (copia .env.ejemplo y rellena tus valores).
    Las variables de entorno del shell tienen prioridad sobre el .env.

Variables disponibles (ver .env.ejemplo para ejemplos completos):
    PROVEEDOR         — "gemini" | "openai" | "stub"  (por defecto: gemini si hay GEMINI_API_KEY, si no openai)
    GEMINI_API_KEY    — clave de API de Google Gemini
    OPENAI_API_KEY    — clave de API de OpenAI (o cualquier compatible)
    NOVIA_URL_BASE    — URL base alternativa para servidores OpenAI-compatibles (Ollama, etc.)
    NOVIA_MODELO      — nombre del modelo a usar
    NOVIA_DATOS       — ruta al directorio de datos  (por defecto: ./data)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _cargar_dotenv(ruta_env: Path) -> None:
    """
    Carga las variables de un archivo .env sin dependencias externas.
    Solo establece variables que no estén ya definidas en el entorno.
    Ignora líneas vacías y comentarios (#).
    """
    if not ruta_env.exists():
        return
    for linea in ruta_env.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave and clave not in os.environ:
            os.environ[clave] = valor


def main() -> None:
    # Añadir la raíz del proyecto al path para que los imports funcionen
    # independientemente de desde dónde se ejecute el script.
    raiz = Path(__file__).parent.resolve()
    if str(raiz) not in sys.path:
        sys.path.insert(0, str(raiz))

    # Cargar .env antes de importar la app (que lee os.environ en __init__)
    _cargar_dotenv(raiz / ".env")

    # Importar aquí para que sys.path ya esté configurado
    from interfaz.app import NoviApp  # noqa: PLC0415

    NoviApp().run()


if __name__ == "__main__":
    main()
