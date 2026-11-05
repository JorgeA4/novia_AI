"""
Funciones de selección de recuerdos relevantes para el contexto del LLM.

Combina similitud semántica (embedding coseno) con la importancia intrínseca
del recuerdo usando la fórmula:

    score = peso_semantico × similitud_coseno(mensaje, recuerdo)
          + (1 − peso_semantico) × recuerdo.importancia

Los recuerdos sin embedding (embedding=None) contribuyen 0.0 en la parte
semántica — degradación graceful para recuerdos ya guardados antes de
activar esta funcionalidad.
"""

from __future__ import annotations

from dominio.embedding import ServicioEmbedding
from dominio.modelos import Recuerdo


def seleccionar_recuerdos_relevantes(
    mensaje: str,
    recuerdos: list[Recuerdo],
    servicio: ServicioEmbedding,
    k: int,
    peso_semantico: float,
) -> list[Recuerdo]:
    """
    Devuelve los `k` recuerdos con mayor score combinado de relevancia semántica
    al `mensaje` e importancia intrínseca.

    Parámetros:
        mensaje         — texto del mensaje del usuario (se codificará una sola vez)
        recuerdos       — lista completa de recuerdos candidatos
        servicio        — instancia de ServicioEmbedding (carga el modelo lazy)
        k               — número máximo de recuerdos a devolver
        peso_semantico  — fracción del score que proviene de la similitud (0.0–1.0)
    """
    if not recuerdos:
        return []

    embedding_mensaje = servicio.codificar(mensaje)

    puntuados: list[tuple[float, Recuerdo]] = []
    for recuerdo in recuerdos:
        if recuerdo.embedding is not None:
            sim = servicio.similitud_coseno(embedding_mensaje, recuerdo.embedding)
        else:
            sim = 0.0
        score = peso_semantico * sim + (1.0 - peso_semantico) * recuerdo.importancia
        puntuados.append((score, recuerdo))

    puntuados.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in puntuados[:k]]
