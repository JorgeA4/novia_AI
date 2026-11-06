"""
Funciones de selección y mantenimiento de recuerdos.

Estrategia de recuperación en dos fases (opción B):

  1. FILTRO SEMÁNTICO — descarta recuerdos con similitud coseno por debajo de
     `umbral_similitud_minima`. Garantiza pertinencia con la conversación actual.
     Los recuerdos sin embedding (fase 1) pasan con similitud 0.0 y compiten
     solo por la segunda fase.

  2. RANKING — ordena los candidatos que pasaron el filtro por una ponderación
     de tres señales intrínsecas:
         score_ranking = w_imp × importancia
                       + w_rel × relevancia_activa
                       + w_emo × emocion_asociada_intensidad
     Se devuelven los `k` mejores.

`relevancia_activa` es un valor dinámico por recuerdo: se inicializa al crear
el recuerdo, decae exponencialmente con el tiempo sin uso, y recibe un boost
cada vez que el recuerdo es seleccionado en una conversación.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from dominio.configuracion import cfg
from dominio.embedding import ServicioEmbedding, dividir_en_fragmentos
from dominio.modelos import Mensaje, Recuerdo


# ---------------------------------------------------------------------------
# Filtro de vigencia
# ---------------------------------------------------------------------------

def filtrar_vigentes(recuerdos: list[Recuerdo]) -> list[Recuerdo]:
    """
    Descarta recuerdos cuya `vigencia` ya ha expirado.

    Un recuerdo se considera válido si:
      - `vigencia` es None (permanente), o
      - `vigencia` es una fecha futura respecto a ahora (UTC).
    """
    ahora = datetime.now(timezone.utc)
    resultado: list[Recuerdo] = []
    for recuerdo in recuerdos:
        if recuerdo.vigencia is None:
            resultado.append(recuerdo)
            continue
        # Normalizar a UTC si la fecha almacenada no tiene zona horaria
        vigencia = recuerdo.vigencia
        if vigencia.tzinfo is None:
            vigencia = vigencia.replace(tzinfo=timezone.utc)
        if vigencia > ahora:
            resultado.append(recuerdo)
    return resultado


def filtrar_representados_en_historial(
    recuerdos: list[Recuerdo],
    mensajes_historial: list[Mensaje],
) -> list[Recuerdo]:
    """Descarta recuerdos cuyo mensaje de origen ya está en el historial del LLM."""
    numeros_mensajes = {mensaje.num for mensaje in mensajes_historial}
    return [
        recuerdo
        for recuerdo in recuerdos
        if recuerdo.mensaje_origen_id is None
        or recuerdo.mensaje_origen_id not in numeros_mensajes
    ]


# ---------------------------------------------------------------------------
# Relevancia activa — inicialización y decaimiento
# ---------------------------------------------------------------------------

def inicializar_relevancia(recuerdo: Recuerdo) -> float:
    """
    Calcula el valor inicial de `relevancia_activa` para un recuerdo recién creado.

    La importancia es el techo natural. La intensidad emocional añade un pequeño
    boost inicial que refleja que los momentos impactantes quedan más "frescos".
    """
    boost_emo = cfg.recuerdos.relevancia_boost_emocion * recuerdo.emocion_asociada_intensidad
    return min(recuerdo.importancia + boost_emo, 1.0)


def decaer_relevancia(recuerdo: Recuerdo, ahora: datetime) -> Recuerdo:
    """
    Aplica decaimiento exponencial a `relevancia_activa` según el tiempo transcurrido
    desde `ult_recuperacion` (o `fecha_creacion` si nunca fue recuperado).

    La semivida se lee de `cfg.recuerdos.relevancia_semivida_dias`.
    No modifica ningún otro campo del recuerdo.
    """
    referencia = recuerdo.ult_recuperacion or recuerdo.fecha_creacion
    # Normalizar zona horaria
    if referencia.tzinfo is None:
        referencia = referencia.replace(tzinfo=timezone.utc)
    ahora_utc = ahora if ahora.tzinfo is not None else ahora.replace(tzinfo=timezone.utc)

    dias_transcurridos = max(0.0, (ahora_utc - referencia).total_seconds() / 86400.0)
    tasa = math.log(2) / cfg.recuerdos.relevancia_semivida_dias
    nueva_relevancia = recuerdo.relevancia_activa * math.exp(-tasa * dias_transcurridos)

    # Clonar solo con el campo modificado (dataclass frozen=False, asignación directa)
    from dataclasses import replace as dc_replace
    return dc_replace(recuerdo, relevancia_activa=nueva_relevancia)


def aplicar_boost_recuperacion(recuerdo: Recuerdo, ahora: datetime) -> Recuerdo:
    """
    Incrementa `relevancia_activa` tras ser seleccionado en una conversación.

    El techo es siempre `importancia` — el recuerdo no puede volverse más relevante
    de lo que fue importante en su momento.
    Actualiza también `ult_recuperacion` al momento actual.
    """
    from dataclasses import replace as dc_replace
    nueva_relevancia = min(
        recuerdo.relevancia_activa + cfg.recuerdos.relevancia_boost_recuperacion,
        recuerdo.importancia,
    )
    return dc_replace(recuerdo, relevancia_activa=nueva_relevancia, ult_recuperacion=ahora)


# ---------------------------------------------------------------------------
# Selección de recuerdos relevantes — opción B (dos fases)
# ---------------------------------------------------------------------------

def seleccionar_recuerdos_relevantes(
    mensaje: str,
    recuerdos: list[Recuerdo],
    servicio: ServicioEmbedding,
    k: int,
) -> list[Recuerdo]:
    """
    Devuelve los `k` recuerdos más adecuados para el contexto del LLM.

    Fase 1 — filtro semántico:
        El mensaje se divide en fragmentos y cada recuerdo usa la mayor similitud
        coseno obtenida con cualquiera de ellos. Solo pasan los recuerdos con
        similitud >= umbral_similitud_minima.
        Los recuerdos sin embedding (embedding=None) se tratan con similitud 0.0
        y solo pasan si el umbral es 0.0 (degradación graceful).

    Fase 2 — ranking por señales intrínsecas:
        Los candidatos se ordenan por:
            w_imp × importancia + w_rel × relevancia_activa + w_emo × emocion_intensidad
        Se devuelven los `k` primeros.
    """
    if not recuerdos:
        return []

    fragmentos = dividir_en_fragmentos(mensaje)
    if not fragmentos:
        return []
    embeddings_fragmentos = servicio.codificar_multiples(fragmentos)
    umbral = cfg.embedding.umbral_similitud_minima

    # --- Fase 1: filtro semántico ---
    candidatos: list[Recuerdo] = []
    for recuerdo in recuerdos:
        if recuerdo.embedding is not None:
            sim = max(
                servicio.similitud_coseno(embedding, recuerdo.embedding)
                for embedding in embeddings_fragmentos
            )
        else:
            sim = 0.0
        if sim >= umbral:
            candidatos.append(recuerdo)

    if not candidatos:
        return []

    # --- Fase 2: ranking por importancia, relevancia activa e impacto emocional ---
    w_imp = cfg.embedding.peso_importancia
    w_rel = cfg.embedding.peso_relevancia
    w_emo = cfg.embedding.peso_emocion_recuperacion

    def _score_ranking(r: Recuerdo) -> float:
        return (
            w_imp * r.importancia
            + w_rel * r.relevancia_activa
            + w_emo * r.emocion_asociada_intensidad
        )

    candidatos.sort(key=_score_ranking, reverse=True)
    return candidatos[:k]
