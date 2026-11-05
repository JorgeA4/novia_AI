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

    # Cargar .env antes de importar los módulos (que leen os.environ al importar)
    _cargar_dotenv(raiz / ".env")

    # Importar aquí para que sys.path ya esté configurado
    from dominio.configuracion import cfg  # noqa: PLC0415
    from dominio.embedding import ServicioEmbedding  # noqa: PLC0415
    from aplicacion.gestor_turno import GestorTurno  # noqa: PLC0415
    from interfaz.app import (  # noqa: PLC0415
        NoviApp,
        _asegurar_datos_iniciales,
        _crear_cliente_llm,
    )
    from repositorios.json.factoria import crear_repositorios  # noqa: PLC0415

    ruta_datos = Path(os.environ.get("NOVIA_DATOS", "data"))
    repos = crear_repositorios(ruta_datos)
    _asegurar_datos_iniciales(repos)
    cliente = _crear_cliente_llm()
    servicio_embedding = ServicioEmbedding(cfg.embedding.modelo)
    gestor = GestorTurno(repos, cliente, servicio_embedding)
    NoviApp(repos=repos, gestor=gestor).run()


if __name__ == "__main__":
    main()
