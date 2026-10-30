"""
Lógica del espacio emocional de Russell.

Operaciones:
    - Calcular el vector de posición de una capa (valencia × intensidad, activacion × intensidad).
    - Calcular el estado_compuesto: suma ponderada de las tres capas (0.50 / 0.35 / 0.15).
    - Detectar la emoción más cercana al vector compuesto por distancia euclidiana.
    - Aplicar decaimiento de intensidad a una capa.

Regla: este módulo no importa nada de persistencia, interfaz ni LLM.
"""

from __future__ import annotations

import math
from typing import NamedTuple

from dominio.modelos import Emocion, Estado


# ---------------------------------------------------------------------------
# Pesos fijos de las capas — constantes del sistema, no parámetros
# ---------------------------------------------------------------------------

PESO_EMOCION: float = 0.50
PESO_ESTADO_ANIMO: float = 0.35
PESO_SENTIMIENTO: float = 0.15


# ---------------------------------------------------------------------------
# Tipos auxiliares
# ---------------------------------------------------------------------------

class Vector2D(NamedTuple):
    valencia: float
    activacion: float


# ---------------------------------------------------------------------------
# Operaciones sobre vectores
# ---------------------------------------------------------------------------

def calcular_vector_capa(emocion: Emocion, intensidad: float) -> Vector2D:
    """
    Escala el vector canónico de una emoción por su intensidad.

    intensidad 0.0 → origen (estado neutro)
    intensidad 1.0 → posición canónica completa
    """
    return Vector2D(
        valencia=emocion.valencia * intensidad,
        activacion=emocion.activacion * intensidad,
    )


def calcular_estado_compuesto(
    vector_emocion: Vector2D,
    vector_estado_animo: Vector2D,
    vector_sentimiento: Vector2D,
) -> Vector2D:
    """
    Suma ponderada de los tres vectores de capa.

    Pesos fijos: emocion × 0.50 + estado_animo × 0.35 + sentimiento × 0.15
    """
    valencia = (
        vector_emocion.valencia * PESO_EMOCION
        + vector_estado_animo.valencia * PESO_ESTADO_ANIMO
        + vector_sentimiento.valencia * PESO_SENTIMIENTO
    )
    activacion = (
        vector_emocion.activacion * PESO_EMOCION
        + vector_estado_animo.activacion * PESO_ESTADO_ANIMO
        + vector_sentimiento.activacion * PESO_SENTIMIENTO
    )
    return Vector2D(valencia=valencia, activacion=activacion)


def distancia_euclidiana(a: Vector2D, b: Vector2D) -> float:
    return math.sqrt((a.valencia - b.valencia) ** 2 + (a.activacion - b.activacion) ** 2)


def detectar_emocion_cercana(
    vector_compuesto: Vector2D,
    catalogo: list[Emocion],
    capa: str,
) -> Emocion:
    """
    Devuelve la emoción del catálogo cuya coordenada canónica está más cerca
    del vector_compuesto por distancia euclidiana.

    Solo considera entradas cuyo campo `capa` sea igual al argumento `capa`
    o sea "cualquiera".

    Nunca aplica umbrales ni reglas if/else — el cambio es emergente del espacio geométrico.
    """
    candidatas = [e for e in catalogo if e.capa in (capa, "cualquiera")]
    if not candidatas:
        raise ValueError(f"El catálogo no contiene emociones válidas para la capa '{capa}'")

    return min(
        candidatas,
        key=lambda e: distancia_euclidiana(
            vector_compuesto,
            Vector2D(e.valencia, e.activacion),
        ),
    )


# ---------------------------------------------------------------------------
# Estado compuesto completo desde un Estado y un catálogo
# ---------------------------------------------------------------------------

def calcular_emocion_actual(estado: Estado, catalogo: list[Emocion]) -> Emocion:
    """
    A partir del Estado persistido y el catálogo completo de emociones,
    calcula el vector compuesto y devuelve la emoción más cercana.

    Esta es la función que usa la capa de aplicación antes de construir
    el contexto para el LLM.
    """
    emocion_catalogo = _buscar_en_catalogo(catalogo, estado.emocion_id)
    estado_animo_catalogo = _buscar_en_catalogo(catalogo, estado.estado_animo_id)
    sentimiento_catalogo = _buscar_en_catalogo(catalogo, estado.sentimiento_id)

    vector_emocion = calcular_vector_capa(emocion_catalogo, estado.emocion_intensidad)
    vector_estado_animo = calcular_vector_capa(estado_animo_catalogo, estado.estado_animo_intensidad)
    vector_sentimiento = calcular_vector_capa(sentimiento_catalogo, estado.sentimiento_intensidad)

    compuesto = calcular_estado_compuesto(vector_emocion, vector_estado_animo, vector_sentimiento)

    # La emoción resultante puede ser de cualquier capa — buscamos en todo el catálogo
    return detectar_emocion_cercana(compuesto, catalogo, capa="cualquiera")


# ---------------------------------------------------------------------------
# Decaimiento de intensidad
# ---------------------------------------------------------------------------

def aplicar_decaimiento(intensidad_actual: float, tasa: float, segundos: float) -> float:
    """
    Aplica decaimiento lineal a la intensidad de una capa.

    `tasa` es la fracción de intensidad que se pierde por segundo.
    El resultado nunca cae por debajo de 0.0.

    Nota: la elección entre decaimiento lineal y exponencial está pendiente
    de decisión de diseño (ver logica_interna.md). Esta implementación usa
    lineal como punto de partida; se puede sustituir sin cambiar la interfaz.
    """
    nueva_intensidad = intensidad_actual - (tasa * segundos)
    return max(0.0, nueva_intensidad)


def decaer_estado(estado: Estado, segundos_transcurridos: float) -> Estado:
    """
    Devuelve un nuevo Estado con las intensidades de emocion y estado_animo
    reducidas por decaimiento. El sentimiento no decae aquí — solo lo modifican
    eventos reales.

    Las tasas son placeholders hasta que el diseño las defina:
        emocion      → 1/3600  (decae en ~1 hora si intensidad = 1.0)
        estado_animo → 1/86400 (decae en ~1 día  si intensidad = 1.0)

    TODO: reemplazar tasas cuando se decida lineal vs. exponencial.
    """
    TASA_EMOCION: float = 1 / 3600
    TASA_ESTADO_ANIMO: float = 1 / 86400

    nueva_emocion_intensidad = aplicar_decaimiento(
        estado.emocion_intensidad, TASA_EMOCION, segundos_transcurridos
    )
    nuevo_estado_animo_intensidad = aplicar_decaimiento(
        estado.estado_animo_intensidad, TASA_ESTADO_ANIMO, segundos_transcurridos
    )

    return Estado(
        relacion_id=estado.relacion_id,
        emocion_id=estado.emocion_id,
        emocion_intensidad=nueva_emocion_intensidad,
        estado_animo_id=estado.estado_animo_id,
        estado_animo_intensidad=nuevo_estado_animo_intensidad,
        sentimiento_id=estado.sentimiento_id,
        sentimiento_intensidad=estado.sentimiento_intensidad,
        ultima_interaccion=estado.ultima_interaccion,
    )


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def _buscar_en_catalogo(catalogo: list[Emocion], codigo: str) -> Emocion:
    for emocion in catalogo:
        if emocion.codigo == codigo:
            return emocion
    raise ValueError(f"Emoción '{codigo}' no encontrada en el catálogo")
