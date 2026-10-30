"""
Cliente LLM — abstracción sobre el proveedor de lenguaje.

Responsabilidades:
    - Enviar el contexto estructurado al LLM y recibir la respuesta en texto.
    - Abstraer el proveedor concreto (OpenAI, Ollama, etc.) detrás de un Protocol.
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
# Implementación OpenAI
# ---------------------------------------------------------------------------

class ClienteOpenAI:
    """
    Cliente para la API de OpenAI (o compatible: Ollama, LM Studio, etc.).

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
