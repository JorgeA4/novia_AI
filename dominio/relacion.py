"""
Lógica de la relación: transiciones de etapa y actualización de métricas.

Operaciones:
    - Evaluar si una transición entre etapas es elegible según condiciones de umbral.
    - Determinar el modo de activación (permiso vs. impulso automático).
    - Aplicar el impacto de un evento sobre las métricas de RELACION.

Regla: este módulo no importa nada de persistencia, interfaz ni LLM.

NOTA: Las fórmulas concretas de actualización de métricas (confianza, afecto,
familiaridad, tension) y los umbrales exactos de cada transición están pendientes
de decisión de diseño (ver logica_interna.md). Este módulo define la estructura
y los contratos; los valores placeholder se marcan con TODO.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from dominio.modelos import Evento, Relacion, TransicionEtapa


# ---------------------------------------------------------------------------
# Condiciones de transición
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CondicionTransicion:
    """
    Umbral mínimo que deben cumplir los campos de RELACION para que
    una transición sea elegible.

    Todos los campos son opcionales — None significa "sin restricción".
    """
    desde_id: str
    hasta_id: str
    confianza_min: Optional[float] = None
    afecto_min: Optional[float] = None
    familiaridad_min: Optional[float] = None
    tension_max: Optional[float] = None
    # TODO: añadir condición sobre número mínimo de interacciones cuando
    # el modelo registre ese contador.


def condicion_cumplida(relacion: Relacion, condicion: CondicionTransicion) -> bool:
    """
    Comprueba si los campos de una Relacion satisfacen todos los umbrales
    de una CondicionTransicion.
    """
    if condicion.confianza_min is not None and relacion.confianza < condicion.confianza_min:
        return False
    if condicion.afecto_min is not None and relacion.afecto < condicion.afecto_min:
        return False
    if condicion.familiaridad_min is not None and relacion.familiaridad < condicion.familiaridad_min:
        return False
    if condicion.tension_max is not None and relacion.tension > condicion.tension_max:
        return False
    return True


# ---------------------------------------------------------------------------
# Evaluación de transiciones elegibles
# ---------------------------------------------------------------------------

# Umbral a partir del cual una transición elegible se activa por impulso
# automático sin necesidad de evento significativo.
# TODO: afinar este valor durante la implementación.
UMBRAL_IMPULSO_AUTOMATICO: float = 0.15
"""
Si todos los campos de la relación superan sus umbrales por este margen,
la transición se activa por impulso automático.
"""


def evaluar_transicion(
    relacion: Relacion,
    transicion: TransicionEtapa,
    condicion: CondicionTransicion,
) -> Optional[str]:
    """
    Evalúa si una transición es elegible para la relación dada.

    Devuelve:
        "impulso"  — las condiciones se cumplen con margen suficiente para avance automático
        "permiso"  — las condiciones se cumplen pero se necesita un evento significativo
        None       — las condiciones no se cumplen

    Solo evalúa transiciones cuyo par (desde_id, hasta_id) coincida con la
    etapa actual de la relación. Si no coincide, devuelve None.
    """
    if relacion.etapa != condicion.desde_id:
        return None
    if transicion.desde_id != condicion.desde_id or transicion.hasta_id != condicion.hasta_id:
        return None
    if not condicion_cumplida(relacion, condicion):
        return None

    # Determinar si hay margen suficiente para impulso automático
    if _cumple_con_margen(relacion, condicion, UMBRAL_IMPULSO_AUTOMATICO):
        return "impulso"
    return "permiso"


def _cumple_con_margen(
    relacion: Relacion,
    condicion: CondicionTransicion,
    margen: float,
) -> bool:
    """
    Comprueba si todos los campos superan sus umbrales por al menos `margen`.
    """
    if condicion.confianza_min is not None:
        if relacion.confianza < condicion.confianza_min + margen:
            return False
    if condicion.afecto_min is not None:
        if relacion.afecto < condicion.afecto_min + margen:
            return False
    if condicion.familiaridad_min is not None:
        if relacion.familiaridad < condicion.familiaridad_min + margen:
            return False
    if condicion.tension_max is not None:
        if relacion.tension > condicion.tension_max - margen:
            return False
    return True


def buscar_transicion_elegible(
    relacion: Relacion,
    transiciones: list[TransicionEtapa],
    condiciones: list[CondicionTransicion],
) -> Optional[tuple[TransicionEtapa, str]]:
    """
    Busca la primera transición elegible para la etapa actual de la relación.

    Devuelve (TransicionEtapa, modo) donde modo es "impulso" o "permiso",
    o None si ninguna transición es elegible.

    El orden de `transiciones` determina la prioridad si varias son elegibles.
    """
    indice_condiciones = {(c.desde_id, c.hasta_id): c for c in condiciones}

    for transicion in transiciones:
        if transicion.desde_id != relacion.etapa:
            continue
        clave = (transicion.desde_id, transicion.hasta_id)
        condicion = indice_condiciones.get(clave)
        if condicion is None:
            continue
        modo = evaluar_transicion(relacion, transicion, condicion)
        if modo is not None:
            return transicion, modo

    return None


# ---------------------------------------------------------------------------
# Actualización de métricas tras un evento
# ---------------------------------------------------------------------------

def aplicar_impacto_evento(relacion: Relacion, evento: Evento) -> Relacion:
    """
    Devuelve una nueva Relacion con las métricas actualizadas según el impacto
    del evento.

    Reglas actuales (TODO: reemplazar por fórmulas definitivas cuando el
    diseño las especifique — ver logica_interna.md):

        impacto > 0  → sube afecto y confianza, baja tension
        impacto < 0  → baja afecto y confianza, sube tension
        familiaridad → sube siempre con cualquier evento (la interacción acumula)

    El impacto se escala al 50% antes de aplicarse para evitar cambios
    demasiado bruscos en una sola interacción. Todos los campos se recortan
    al rango [0.0, 1.0].
    """
    magnitud = abs(evento.impacto)
    signo = 1.0 if evento.impacto >= 0 else -1.0

    # TODO: reemplazar estas fórmulas por las definitivas
    delta_afecto = signo * magnitud * 0.5
    delta_confianza = signo * magnitud * 0.3
    delta_tension = -signo * magnitud * 0.4
    delta_familiaridad = magnitud * 0.2   # siempre positivo

    return replace(
        relacion,
        afecto=_recortar(relacion.afecto + delta_afecto),
        confianza=_recortar(relacion.confianza + delta_confianza),
        tension=_recortar(relacion.tension + delta_tension),
        familiaridad=_recortar(relacion.familiaridad + delta_familiaridad),
    )


def _recortar(valor: float) -> float:
    """Recorta un valor al rango [0.0, 1.0]."""
    return max(0.0, min(1.0, valor))
