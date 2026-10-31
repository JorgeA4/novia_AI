"""
Lógica de la relación: transiciones de etapa, actualización de métricas
e interés de contacto.

Operaciones:
    - Evaluar si una transición entre etapas es elegible según condiciones de umbral.
    - Determinar el modo de activación (permiso vs. impulso automático).
    - Aplicar el impacto de un evento sobre las métricas de RELACION con cap y
      resistencia en extremos.
    - Aplicar deltas independientes por dimensión (afecto, confianza, familiaridad,
      tension, disposicion) con los mismos mecanismos de control de velocidad.
    - Calcular `interes_actual` en tiempo real a partir de disposicion, estado de
      ánimo presente y tiempo transcurrido desde la última interacción.

Regla: este módulo no importa nada de persistencia, interfaz ni LLM.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime
from typing import NamedTuple, Optional

from dominio.configuracion import cfg
from dominio.modelos import Emocion, Estado, Evento, Relacion, TipoEvento, TransicionEtapa


# ---------------------------------------------------------------------------
# Constantes del sistema
# ---------------------------------------------------------------------------

# Tolerancia para comparaciones de punto flotante.
_EPSILON: float = 1e-9

# Accesos directos a la configuración (para legibilidad del módulo)
_ALPHA_EMA: float = cfg.relacion.ema_alpha
_TAU_HORAS: float = cfg.relacion.tau_horas_interes
UMBRAL_IMPULSO_AUTOMATICO: float = cfg.relacion.umbral_impulso_automatico


# ---------------------------------------------------------------------------
# Deltas independientes por dimensión
# ---------------------------------------------------------------------------

class DeltasRelacion(NamedTuple):
    """
    Variación independiente de cada métrica de RELACION para un turno.

    Todos los valores están en [-1.0, 1.0] antes de aplicar cap y resistencia.
    Permite que un turno suba confianza sin mover familiaridad, etc.
    """
    afecto: float = 0.0
    confianza: float = 0.0
    familiaridad: float = 0.0
    tension: float = 0.0
    disposicion: float = 0.0


# ---------------------------------------------------------------------------
# Mecanismos de control de velocidad de cambio
# ---------------------------------------------------------------------------

def _resistencia(valor: float) -> float:
    """
    Factor de resistencia al cambio según la posición actual de la métrica.

    Fórmula: max(0.05, 4 × valor × (1 − valor))
        — máxima (1.0) en valor=0.5  → cambio más fácil en el centro
        — mínima (0.05) en valor=0 y 1 → cambio muy lento en extremos, pero posible

    El piso de 0.05 evita que métricas en 0.0 (como tensión al inicio) queden
    permanentemente bloqueadas sin poder cambiar.

    El resultado escala el impacto_base: impacto_real = impacto_base × resistencia.
    """
    return max(0.05, 4.0 * valor * (1.0 - valor))


def _aplicar_cambio(valor_actual: float, impacto_base: float, cap: Optional[float] = None) -> tuple[float, float]:
    """
    Aplica un cambio a una métrica con cap opcional y resistencia en extremos.

    Devuelve (nuevo_valor, cambio_real) donde `cambio_real` es el delta
    efectivamente aplicado — se usa para actualizar el campo _delta correspondiente.

    Orden de aplicación (ver logica_interna.md):
        1. Aplicar cap por tipo de evento  → impacto_capped
        2. Aplicar resistencia de extremos → impacto_real
        3. Recortar resultado a [0.0, 1.0]
    """
    impacto_capped = _aplicar_cap(impacto_base, cap)
    impacto_real = impacto_capped * _resistencia(valor_actual)
    nuevo_valor = _recortar(valor_actual + impacto_real)
    cambio_real = nuevo_valor - valor_actual
    return nuevo_valor, cambio_real


def _aplicar_cap(impacto: float, cap: Optional[float]) -> float:
    """Limita el valor absoluto del impacto al cap dado. None = sin límite."""
    if cap is None:
        return impacto
    return max(-cap, min(cap, impacto))


def _actualizar_ema(delta_anterior: float, cambio_real: float) -> float:
    """
    Recalcula el campo _delta como media exponencial ponderada (EMA).

        delta_nuevo = delta_anterior × α + cambio_real × (1 − α)

    El delta no decae solo con el tiempo — solo cambia cuando hay un evento
    que modifica la métrica.

    α se lee de configuracion.json (relacion.ema_alpha).
    """
    alpha = cfg.relacion.ema_alpha
    return delta_anterior * alpha + cambio_real * (1.0 - alpha)


def _recortar(valor: float) -> float:
    """Recorta un valor al rango [0.0, 1.0]."""
    return max(0.0, min(1.0, valor))


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
    """
    if relacion.etapa != condicion.desde_id:
        return None
    if transicion.desde_id != condicion.desde_id or transicion.hasta_id != condicion.hasta_id:
        return None
    if not condicion_cumplida(relacion, condicion):
        return None

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
        if relacion.confianza < condicion.confianza_min + margen - _EPSILON:
            return False
    if condicion.afecto_min is not None:
        if relacion.afecto < condicion.afecto_min + margen - _EPSILON:
            return False
    if condicion.familiaridad_min is not None:
        if relacion.familiaridad < condicion.familiaridad_min + margen - _EPSILON:
            return False
    if condicion.tension_max is not None:
        if relacion.tension > condicion.tension_max - margen + _EPSILON:
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
# Cálculo del delta de disposicion a partir de tendencias
# ---------------------------------------------------------------------------

def calcular_delta_disposicion(relacion: Relacion) -> float:
    """
    Calcula el impulso de cambio para `disposicion` basándose en las tendencias
    recientes de afecto y confianza, modulado por la tensión actual.

    Fuentes del impulso:
        impulso = afecto_delta × 0.55 + confianza_delta × 0.45

    Se usan las tendencias (campos _delta), no los valores absolutos, porque
    el interés interpersonal crece cuando las cosas van bien, no porque
    ya estén bien — un 0.9 estable no genera entusiasmo nuevo.

    Modulación por tensión (solo frena subidas, no amortigua bajadas):
        factor_tension = 1.0 − tension × 0.6
        Si impulso > 0  → delta_disposicion = impulso × factor_tension
        Si impulso <= 0 → delta_disposicion = impulso  (sin modulación)

    La tensión alta dificulta que el interés suba pero no evita que baje —
    perder el interés cuando hay conflicto ocurre igual.
    """
    impulso = relacion.afecto_delta * 0.55 + relacion.confianza_delta * 0.45
    if impulso > 0:
        factor_tension = 1.0 - relacion.tension * 0.6
        return impulso * factor_tension
    return impulso


# ---------------------------------------------------------------------------
# Actualización de métricas tras un evento
# ---------------------------------------------------------------------------

# CAP_EXTRAORDINARIO no tiene valor numérico — es la ausencia de límite (None).
CAP_EXTRAORDINARIO: Optional[float] = None

_CAPS_POR_CATEGORIA: dict[str, Optional[float]] = {
    "cotidiano":      None,   # se rellena en tiempo de ejecución desde cfg
    "significativo":  None,
    "extraordinario": CAP_EXTRAORDINARIO,
}


def cap_para_categoria(tipo_evento: TipoEvento) -> Optional[float]:
    """
    Devuelve el cap de velocidad de cambio correspondiente a la categoría
    de un TipoEvento (leído de configuracion.json).

    Si la categoría no está reconocida, aplica cap_cotidiano como fallback
    seguro para no producir saltos inesperados en las métricas.
    """
    caps = {
        "cotidiano":      cfg.relacion.cap_cotidiano,
        "significativo":  cfg.relacion.cap_significativo,
        "extraordinario": CAP_EXTRAORDINARIO,
    }
    return caps.get(tipo_evento.categoria, cfg.relacion.cap_cotidiano)


def aplicar_impacto_evento(
    relacion: Relacion,
    evento: Evento,
    cap: Optional[float] = None,
) -> Relacion:
    """
    Devuelve una nueva Relacion con las métricas actualizadas según el impacto
    escalar del evento, aplicando cap y resistencia en extremos.

    `cap` debe venir de la categoría del TipoEvento vía `cap_para_categoria`.
    None aquí actúa como cap_significativo (fallback seguro para eventos sin categoría).

    Reglas de distribución del impacto:
        impacto > 0  → sube afecto y confianza, baja tension
        impacto < 0  → baja afecto y confianza, sube tension
        familiaridad → sube siempre con cualquier evento (la interacción acumula)
        disposicion  → sube con impacto positivo, baja con impacto negativo sostenido
    """
    if cap is None:
        cap = cfg.relacion.cap_significativo
    magnitud = abs(evento.impacto)
    signo = 1.0 if evento.impacto >= 0 else -1.0

    nuevo_afecto,       cambio_afecto       = _aplicar_cambio(relacion.afecto,       signo * magnitud * 0.5,  cap)
    nuevo_confianza,    cambio_confianza    = _aplicar_cambio(relacion.confianza,    signo * magnitud * 0.3,  cap)
    nuevo_tension,      cambio_tension      = _aplicar_cambio(relacion.tension,      -signo * magnitud * 0.4, cap)
    nuevo_familiaridad, cambio_familiaridad = _aplicar_cambio(relacion.familiaridad, magnitud * 0.2,          cap)
    nuevo_disposicion,  cambio_disposicion  = _aplicar_cambio(relacion.disposicion,  signo * magnitud * 0.2,  cap)

    return replace(
        relacion,
        afecto=nuevo_afecto,
        afecto_delta=_actualizar_ema(relacion.afecto_delta, cambio_afecto),
        confianza=nuevo_confianza,
        confianza_delta=_actualizar_ema(relacion.confianza_delta, cambio_confianza),
        tension=nuevo_tension,
        familiaridad=nuevo_familiaridad,
        disposicion=nuevo_disposicion,
        disposicion_delta=_actualizar_ema(relacion.disposicion_delta, cambio_disposicion),
    )


def aplicar_deltas_turno(
    relacion: Relacion,
    deltas: DeltasRelacion,
    cap: Optional[float] = None,
) -> Relacion:
    """
    Devuelve una nueva Relacion aplicando variaciones independientes por dimensión,
    con cap y resistencia en extremos.

    `cap` es cap_cotidiano (de configuracion.json) por defecto — los turnos de
    conversación ordinarios son eventos cotidianos. Pasar cap_significativo para
    conversaciones largas o especialmente relevantes.
    """
    if cap is None:
        cap = cfg.relacion.cap_cotidiano
    nuevo_afecto,       cambio_afecto       = _aplicar_cambio(relacion.afecto,       deltas.afecto,       cap)
    nuevo_confianza,    cambio_confianza    = _aplicar_cambio(relacion.confianza,     deltas.confianza,    cap)
    nuevo_familiaridad, _                  = _aplicar_cambio(relacion.familiaridad,  deltas.familiaridad, cap)
    nuevo_tension,      _                  = _aplicar_cambio(relacion.tension,       deltas.tension,      cap)
    nuevo_disposicion,  cambio_disposicion = _aplicar_cambio(relacion.disposicion,   deltas.disposicion,  cap)

    return replace(
        relacion,
        afecto=nuevo_afecto,
        afecto_delta=_actualizar_ema(relacion.afecto_delta, cambio_afecto),
        confianza=nuevo_confianza,
        confianza_delta=_actualizar_ema(relacion.confianza_delta, cambio_confianza),
        familiaridad=nuevo_familiaridad,
        tension=nuevo_tension,
        disposicion=nuevo_disposicion,
        disposicion_delta=_actualizar_ema(relacion.disposicion_delta, cambio_disposicion),
    )


# ---------------------------------------------------------------------------
# Interés de contacto en tiempo real
# ---------------------------------------------------------------------------

def calcular_interes_actual(
    relacion: Relacion,
    estado: Estado,
    catalogo_emociones: dict[str, Emocion],
    ahora: Optional[datetime] = None,
) -> float:
    """
    Calcula el interés del personaje en interactuar ahora mismo.

    No se persiste — se calcula en cada turno que lo necesite.

    Fórmula (ver logica_interna.md):
        factor_tiempo  = 1.0 − e^(−horas_sin_hablar / τ)
        interes_actual = disposicion × 0.50
                       + valencia_estado_animo_norm × 0.35
                       + factor_tiempo × 0.15

    Interpretación del resultado:
        < 0.25   → el personaje evita o ignora el contacto
        0.25–0.50 → responde si le hablan, sin energía
        0.50–0.75 → disposición normal
        > 0.75   → puede tomar iniciativa

    `catalogo_emociones` debe ser un dict {codigo: Emocion} con al menos
    la emoción referenciada por estado.estado_animo_id.
    """
    if ahora is None:
        ahora = datetime.now()

    horas_sin_hablar = (ahora - estado.ultima_interaccion).total_seconds() / 3600.0
    factor_tiempo = 1.0 - math.exp(-horas_sin_hablar / _TAU_HORAS)

    emocion_animo = catalogo_emociones.get(estado.estado_animo_id)
    if emocion_animo is not None:
        valencia_norm = (emocion_animo.valencia + 1.0) / 2.0
    else:
        valencia_norm = 0.5   # neutral si no se encuentra la emoción

    interes = (
        relacion.disposicion * 0.50
        + valencia_norm      * 0.35
        + factor_tiempo      * 0.15
    )
    return _recortar(interes)


# ---------------------------------------------------------------------------
# Familiaridad — recalculo desde perfil/recuerdos y decaimiento temporal
# ---------------------------------------------------------------------------

def recalcular_familiaridad(
    relacion: Relacion,
    perfil_usuario: "list[PerfilUsuario]",
    recuerdos: "list[Recuerdo]",
    n_mensajes: int = 0,
) -> Relacion:
    """
    Recalcula `familiaridad` a partir de las fuentes de conocimiento acumulado,
    ignorando el delta que pueda haber reportado el LLM.

    Fórmula:
        señal_perfil    = sqrt(n_entradas_usuario / escala_perfil)
        señal_recuerdos = sqrt(suma_importancia_recuerdos / escala_recuerdos)
        señal_mensajes  = sqrt(n_mensajes / escala_mensajes)
        familiaridad_base = clip(
            señal_perfil    × peso_perfil
            + señal_recuerdos × peso_recuerdos
            + señal_mensajes  × peso_mensajes,
            0.0, 1.0
        )

    Solo sube — el decaimiento temporal lo aplica `decaer_familiaridad`.
    Solo cuenta entradas de sujeto "usuario" del perfil (lo que sabe de esta persona).
    """
    from dominio.modelos import PerfilUsuario, Recuerdo
    from dominio.confianza import confianza_final_de
    import math as _math

    cfg_r = cfg.relacion

    entradas_usuario = [p for p in perfil_usuario if p.sujeto == "usuario"]
    n_perfil = sum(confianza_final_de(p) for p in entradas_usuario)
    señal_perfil = _math.sqrt(max(0.0, n_perfil) / cfg_r.familiaridad_escala_perfil)

    suma_importancia = sum(r.importancia for r in recuerdos)
    señal_recuerdos = _math.sqrt(max(0.0, suma_importancia) / cfg_r.familiaridad_escala_recuerdos)

    señal_mensajes = _math.sqrt(max(0.0, n_mensajes) / cfg_r.familiaridad_escala_mensajes)

    familiaridad_base = _recortar(
        señal_perfil    * cfg_r.familiaridad_peso_perfil
        + señal_recuerdos * cfg_r.familiaridad_peso_recuerdos
        + señal_mensajes  * cfg_r.familiaridad_peso_mensajes
    )

    # Solo puede subir — si la base calculada es menor que la actual, no tocar
    nueva_familiaridad = max(relacion.familiaridad, familiaridad_base)

    return replace(relacion, familiaridad=nueva_familiaridad)


def decaer_familiaridad(
    relacion: Relacion,
    segundos_transcurridos: float,
) -> Relacion:
    """
    Aplica decaimiento exponencial a `familiaridad` según el tiempo sin interacción.

    La semivida configurada es de 60 días por defecto — muy lenta, pero perceptible
    tras semanas/meses de silencio. No decae por debajo de 0.0.
    """
    import math as _math

    semivida_segundos = cfg.relacion.familiaridad_semivida_dias * 86400.0
    tasa = _math.log(2) / semivida_segundos
    nueva = relacion.familiaridad * _math.exp(-tasa * segundos_transcurridos)
    return replace(relacion, familiaridad=_recortar(nueva))
