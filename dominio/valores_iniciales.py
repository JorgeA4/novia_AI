"""
Valores por defecto para la creación de nuevas entidades de relación.

Este módulo es la única fuente de verdad para los valores iniciales que se
usan al crear un nuevo chat (Relacion + Estado) y al resetear uno existente.

No importa nada de persistencia, interfaz ni LLM.
"""

from __future__ import annotations

from datetime import datetime

from dominio.modelos import Estado, Relacion


# ---------------------------------------------------------------------------
# Valores iniciales de Relacion
# ---------------------------------------------------------------------------

ETAPA_INICIAL: str = "desconocidos"

RELACION_VALORES_INICIALES: dict = dict(
    etapa=ETAPA_INICIAL,
    confianza=0.05,
    confianza_delta=0.0,
    afecto=0.05,
    afecto_delta=0.0,
    familiaridad=0.0,
    tension=0.0,
    disposicion=0.40,
    disposicion_delta=0.0,
    instrucciones_llm=(
        "Comunícate como una persona real hablando por WhatsApp: mensajes cortos, lenguaje natural "
        "y coloquial, sin describir acciones ni emociones entre asteriscos ni paréntesis. No hagas "
        "roleplay, no narres lo que haces ni lo que sientes; solo escribe lo que dirías de verdad. "
        "Usa frases sueltas, abreviaciones ocasionales y el tono que corresponde a cómo te sientes "
        "ahora. Está bien mandar dos frases o incluso una sola. No empieces siempre de la misma "
        "forma. Nunca rompas el personaje ni menciones que eres una IA."
    ),
)

# ---------------------------------------------------------------------------
# Valores iniciales de Estado
# ---------------------------------------------------------------------------

ESTADO_VALORES_INICIALES: dict = dict(
    emocion_id="neutro",
    emocion_intensidad=0.3,
    estado_animo_id="neutro",
    estado_animo_intensidad=0.2,
    sentimiento_id="neutro",
    sentimiento_intensidad=0.1,
)


# ---------------------------------------------------------------------------
# Funciones de construcción
# ---------------------------------------------------------------------------

def nueva_relacion(num: int, personaje_id: int, usuario_id: int) -> Relacion:
    """
    Construye una Relacion nueva con los valores iniciales por defecto.

    Es el único lugar donde se instancia una Relacion desde cero; cualquier
    cambio en los defaults solo requiere editar este módulo.
    """
    return Relacion(
        num=num,
        personaje_id=personaje_id,
        usuario_id=usuario_id,
        **RELACION_VALORES_INICIALES,
    )


def nuevo_estado(relacion_id: int, ahora: datetime | None = None) -> Estado:
    """
    Construye un Estado inicial para una relación recién creada.

    `ahora` puede pasarse explícitamente en tests; si es None se usa
    datetime.now() en el momento de la llamada.
    """
    return Estado(
        relacion_id=relacion_id,
        ultima_interaccion=ahora or datetime.now(),
        **ESTADO_VALORES_INICIALES,
    )
