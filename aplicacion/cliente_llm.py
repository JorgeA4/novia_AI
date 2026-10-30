"""
Cliente LLM — abstracción sobre el proveedor de lenguaje.

Responsabilidades:
    - Enviar el contexto estructurado al LLM y recibir la respuesta en texto.
    - Abstraer el proveedor concreto (OpenAI, Gemini, Ollama, etc.) detrás de un Protocol.
    - Extraer datos estructurados del texto de respuesta cuando se solicita
      (recuerdos candidatos, datos de PERFIL_USUARIO).

Regla: este módulo no importa nada de persistencia ni de interfaz.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Protocolo abstracto
# ---------------------------------------------------------------------------

@runtime_checkable
class ClienteLLM(Protocol):
    def completar(self, mensajes: list[dict[str, str]]) -> str:
        """
        Recibe una lista de mensajes en formato {role, content} y devuelve
        el texto de respuesta del asistente.
        """
        ...


# ---------------------------------------------------------------------------
# Implementación OpenAI (y compatibles: Ollama, LM Studio, OpenRouter…)
# ---------------------------------------------------------------------------

class ClienteOpenAI:
    """
    Cliente para la API de OpenAI (o compatible: Ollama, LM Studio, OpenRouter, etc.).

    Parámetros:
        modelo      — nombre del modelo, p.ej. "gpt-4o-mini"
        url_base    — URL base de la API; None usa la de OpenAI por defecto
        api_key     — clave de API; None la lee de OPENAI_API_KEY
        temperatura — controla la aleatoriedad de las respuestas [0.0, 2.0]
    """

    def __init__(
        self,
        modelo: str = "gpt-4o-mini",
        url_base: str | None = None,
        api_key: str | None = None,
        temperatura: float = 0.8,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai no está instalado. Ejecuta: pip install openai"
            )

        self._modelo = modelo
        self._temperatura = temperatura
        self._cliente = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
            base_url=url_base,
        )

    def completar(self, mensajes: list[dict[str, str]]) -> str:
        respuesta = self._cliente.chat.completions.create(
            model=self._modelo,
            messages=mensajes,
            temperature=self._temperatura,
        )
        return respuesta.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Implementación Gemini (Google Generative AI)
# ---------------------------------------------------------------------------

class ClienteGemini:
    """
    Cliente para la API de Google Gemini usando el SDK nativo.

    Parámetros:
        modelo      — nombre del modelo, p.ej. "gemini-1.5-flash" o "gemini-2.0-flash-exp"
        api_key     — clave de API; None la lee de GEMINI_API_KEY
        temperatura — controla la aleatoriedad de las respuestas [0.0, 2.0]

    Convierte el formato {role, content} estándar al formato de Gemini.
    El mensaje de sistema (role="system") se inyecta como instrucción del sistema.
    """

    def __init__(
        self,
        modelo: str = "gemini-1.5-flash",
        api_key: str | None = None,
        temperatura: float = 0.8,
    ) -> None:
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai no está instalado. "
                "Ejecuta: pip install google-generativeai"
            )

        clave = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not clave:
            raise ValueError(
                "Falta la clave de API de Gemini. "
                "Define GEMINI_API_KEY o pásala como api_key."
            )

        genai.configure(api_key=clave)
        self._genai = genai
        self._nombre_modelo = modelo
        self._temperatura = temperatura

    def completar(self, mensajes: list[dict[str, str]]) -> str:
        # Separar el mensaje de sistema del historial de chat
        instruccion_sistema = ""
        historial_chat: list[dict[str, str]] = []

        for msg in mensajes:
            if msg["role"] == "system":
                instruccion_sistema = msg["content"]
            else:
                historial_chat.append(msg)

        modelo = self._genai.GenerativeModel(
            model_name=self._nombre_modelo,
            system_instruction=instruccion_sistema or None,
            generation_config=self._genai.types.GenerationConfig(
                temperature=self._temperatura,
            ),
        )

        # Convertir historial al formato de Gemini
        # Gemini usa "user" / "model" (no "assistant")
        partes_gemini = []
        for msg in historial_chat:
            rol = "model" if msg["role"] == "assistant" else "user"
            partes_gemini.append({"role": rol, "parts": [msg["content"]]})

        if not partes_gemini:
            return ""

        # El último mensaje es el turno actual del usuario
        ultimo = partes_gemini[-1]
        historial_previo = partes_gemini[:-1]

        chat = modelo.start_chat(history=historial_previo)
        respuesta = chat.send_message(ultimo["parts"][0])
        return respuesta.text or ""


# ---------------------------------------------------------------------------
# Implementación stub para desarrollo y tests
# ---------------------------------------------------------------------------

class ClienteStub:
    """
    Cliente ficticio que devuelve respuestas predefinidas.
    Útil para desarrollo sin conexión y para tests.
    """

    def __init__(self, respuesta_fija: str = "...") -> None:
        self._respuesta = respuesta_fija

    def completar(self, mensajes: list[dict[str, str]]) -> str:
        return self._respuesta


# ---------------------------------------------------------------------------
# Extracción estructurada de la respuesta del LLM
# ---------------------------------------------------------------------------

def extraer_json_de_respuesta(texto: str) -> Any | None:
    """
    Intenta extraer un objeto JSON del texto de respuesta del LLM.

    El LLM puede incluir el JSON entre ```json ... ``` o directamente.
    Devuelve None si no se encuentra JSON válido.
    """
    # Intentar con bloque de código markdown
    if "```json" in texto:
        inicio = texto.find("```json") + 7
        fin = texto.find("```", inicio)
        if fin > inicio:
            fragmento = texto[inicio:fin].strip()
            try:
                return json.loads(fragmento)
            except json.JSONDecodeError:
                pass

    # Intentar con bloque de código genérico
    if "```" in texto:
        inicio = texto.find("```") + 3
        fin = texto.find("```", inicio)
        if fin > inicio:
            fragmento = texto[inicio:fin].strip()
            try:
                return json.loads(fragmento)
            except json.JSONDecodeError:
                pass

    # Intentar parsear todo el texto directamente
    try:
        return json.loads(texto.strip())
    except json.JSONDecodeError:
        return None
