"""
Lógica del espacio emocional de Russell.

Operaciones:
    - Calcular el vector de posición de una capa (valencia × intensidad, activacion × intensidad).
    - Calcular el estado_compuesto: suma ponderada de las tres capas (pesos en configuracion.json).
    - Detectar la emoción más cercana al vector compuesto por distancia euclidiana.
    - Aplicar decaimiento de intensidad a una capa.
    - Aplicar presión acumulativa de la emoción sobre el estado_animo (Brecha 1 + 2).
    - Aplicar deriva del sentimiento sobre el estado_animo en reposo (Brecha 3).

Regla: este módulo no importa nada de persistencia, interfaz ni LLM.
"""

from __future__ import annotations

import math
from typing import NamedTuple

from dominio.configuracion import cfg
from dominio.modelos import Emocion, Estado


# ---------------------------------------------------------------------------
# Pesos de las capas — leídos de configuración, no hardcodeados
# ---------------------------------------------------------------------------

PESO_EMOCION: float = cfg.capas.peso_emocion
PESO_ESTADO_ANIMO: float = cfg.capas.peso_estado_animo
PESO_SENTIMIENTO: float = cfg.capas.peso_sentimiento


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

    Pesos: emocion × 0.50 + estado_animo × 0.35 + sentimiento × 0.15
    (valores leídos de configuracion.json)
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

    El vector compuesto integra las tres capas ponderadas,
    por lo que el resultado puede ser cualquier emoción del catálogo
    independientemente de su capa. Se compara contra todo el catálogo.

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

    # Buscar en todo el catálogo sin filtrar por capa: el vector compuesto
    # ya representa la síntesis de las tres capas y puede aterrizar en cualquiera.
    return min(
        catalogo,
        key=lambda e: distancia_euclidiana(
            compuesto,
            Vector2D(e.valencia, e.activacion),
        ),
    )


# ---------------------------------------------------------------------------
# Brecha 1 + 2: presión acumulativa de la emoción sobre el estado_animo
# ---------------------------------------------------------------------------

def calcular_factor_moderacion(
    vector_emocion: Vector2D,
    vector_sentimiento: Vector2D,
) -> float:
    """
    Calcula el factor de moderación basado en la similitud coseno entre
    el vector de la emoción actual y el vector del sentimiento.

    Fórmula:
        similitud = coseno(vector_emocion, vector_sentimiento) ∈ [-1, 1]
        factor    = centroide + similitud × amplitud            ∈ [0.30, 1.00]

    Con amor (valencia positiva) y emociones positivas → factor ≈ 1.0
    Con amor y emociones negativas → factor ≈ 0.30

    Si alguno de los vectores es el origen (intensidad = 0), devuelve el centroide
    (moderación neutra) para evitar división por cero.
    """
    norma_e = math.sqrt(vector_emocion.valencia ** 2 + vector_emocion.activacion ** 2)
    norma_s = math.sqrt(vector_sentimiento.valencia ** 2 + vector_sentimiento.activacion ** 2)

    c = cfg.presion_turno.centroide_moderacion
    a = cfg.presion_turno.amplitud_moderacion

    if norma_e < 1e-9 or norma_s < 1e-9:
        return c  # sin vector definido → moderación neutra

    similitud = (
        vector_emocion.valencia * vector_sentimiento.valencia
        + vector_emocion.activacion * vector_sentimiento.activacion
    ) / (norma_e * norma_s)

    return c + similitud * a


def aplicar_presion_emocion_sobre_animo(
    estado: Estado,
    nueva_emocion_id: str,
    nueva_emocion_intensidad: float,
    catalogo: list[Emocion],
) -> tuple[str, float]:
    """
    Brecha 1 + 2: calcula la presión que ejerce la emoción del turno actual
    sobre el estado_animo, moderada por el sentimiento vigente.

    Flujo:
        1. Calcular presion_turno = valencia_emocion × intensidad × factor_presion_base
        2. Calcular factor_moderacion mediante similitud coseno(emocion, sentimiento)
        3. presion_real = presion_turno × factor_moderacion
        4. Mover el vector del estado_animo actual en la dirección del vector de la emoción
           la distancia presion_real (interpolación lineal en el espacio de Russell).
        5. Devolver el código de estado_animo más cercano al vector resultante
           y la intensidad interpolada.

    Este mecanismo cumple los tres requisitos del diseño:
        - Acumulación: se llama en cada turno; muchos turnos suman presión.
        - Resistencia: factor_presion_base = 0.015 → un turno mueve ~1.5%.
        - Freno del sentimiento: emociones contrarias al sentimiento se amortiguan a ~30%.
    """
    emocion_obj = _buscar_en_catalogo(catalogo, nueva_emocion_id)
    estado_animo_obj = _buscar_en_catalogo(catalogo, estado.estado_animo_id)
    sentimiento_obj = _buscar_en_catalogo(catalogo, estado.sentimiento_id)

    vector_emocion = calcular_vector_capa(emocion_obj, nueva_emocion_intensidad)
    vector_animo = calcular_vector_capa(estado_animo_obj, estado.estado_animo_intensidad)
    vector_sentimiento = calcular_vector_capa(sentimiento_obj, estado.sentimiento_intensidad)

    # Presión bruta del turno (Brecha 1)
    presion_bruta = (
        emocion_obj.valencia * nueva_emocion_intensidad
        * cfg.presion_turno.factor_presion_base
    )

    # Factor de moderación por sentimiento (Brecha 2)
    factor_moderacion = calcular_factor_moderacion(vector_emocion, vector_sentimiento)

    presion_real = abs(presion_bruta) * factor_moderacion

    # Mover el vector del estado_animo en dirección al vector de la emoción
    # La presión es una fracción del camino desde la posición actual hacia la emoción
    nuevo_valencia = vector_animo.valencia + (
        (vector_emocion.valencia - vector_animo.valencia) * presion_real
    )
    nuevo_activacion = vector_animo.activacion + (
        (vector_emocion.activacion - vector_animo.activacion) * presion_real
    )
    vector_nuevo_animo = Vector2D(nuevo_valencia, nuevo_activacion)

    # Intensidad: interpolar levemente hacia la intensidad de la emoción
    nueva_intensidad = (
        estado.estado_animo_intensidad
        + (nueva_emocion_intensidad - estado.estado_animo_intensidad) * presion_real
    )

    candidatas = [e for e in catalogo if e.capa in ("estado_animo", "cualquiera")]
    animo_resultante = min(
        candidatas,
        key=lambda e: distancia_euclidiana(vector_nuevo_animo, Vector2D(e.valencia, e.activacion)),
    )

    return animo_resultante.codigo, max(0.0, min(1.0, nueva_intensidad))


# ---------------------------------------------------------------------------
# Inercia emocional — se mantiene para usos que la llamen explícitamente
# ---------------------------------------------------------------------------

def aplicar_inercia_estado_animo(
    estado: Estado,
    nuevo_animo_id: str,
    nueva_intensidad: float,
    catalogo: list[Emocion],
) -> tuple[str, float]:
    """
    Calcula el nuevo estado_animo aplicando inercia: en lugar de reemplazar
    directamente, interpola en el espacio de Russell hacia el nuevo valor.

    La interpolación ocurre en dos dimensiones:
      1. Posición vectorial: mezcla el vector actual con el nuevo por INERCIA.
      2. Intensidad: mezcla la intensidad actual con la nueva por INERCIA.
      3. El código resultante es la emoción de capa estado_animo más cercana
         al vector interpolado.

    Devuelve (animo_id_resultante, intensidad_resultante).
    """
    inercia = cfg.inercia_estado_animo.factor

    actual = _buscar_en_catalogo(catalogo, estado.estado_animo_id)
    nuevo = _buscar_en_catalogo(catalogo, nuevo_animo_id)

    valencia_interpolada = (
        actual.valencia * (1 - inercia)
        + nuevo.valencia * inercia
    )
    activacion_interpolada = (
        actual.activacion * (1 - inercia)
        + nuevo.activacion * inercia
    )
    vector_interpolado = Vector2D(valencia_interpolada, activacion_interpolada)

    candidatas = [e for e in catalogo if e.capa in ("estado_animo", "cualquiera")]
    animo_resultante = min(
        candidatas,
        key=lambda e: distancia_euclidiana(vector_interpolado, Vector2D(e.valencia, e.activacion)),
    )

    intensidad_resultante = (
        estado.estado_animo_intensidad * (1 - inercia)
        + nueva_intensidad * inercia
    )

    return animo_resultante.codigo, max(0.0, min(1.0, intensidad_resultante))


# ---------------------------------------------------------------------------
# Decaimiento de intensidad
# ---------------------------------------------------------------------------

def aplicar_decaimiento(intensidad_actual: float, tasa: float, segundos: float) -> float:
    """
    Aplica decaimiento exponencial a la intensidad de una capa.

    Fórmula: intensidad × e^(−tasa × segundos)

    La intensidad decae más rápido cuando es alta y más lento cuando es baja,
    lo que produce una transición natural hacia el estado_animo de fondo.
    Cuando el resultado cae por debajo del umbral configurado se fuerza a 0.0 para
    que el emocion_id se limpie a "neutro" (ver decaer_estado).

    `tasa` es la constante de decaimiento en unidades de 1/segundo:
        tasa = ln(2) / semivida_en_segundos
    """
    nueva_intensidad = intensidad_actual * math.exp(-tasa * segundos)
    umbral = cfg.decaimiento.umbral_corte
    return 0.0 if nueva_intensidad < umbral else nueva_intensidad


def decaer_estado(
    estado: Estado,
    segundos_transcurridos: float,
    catalogo: list[Emocion] | None = None,
) -> Estado:
    """
    Devuelve un nuevo Estado con las intensidades de emocion y estado_animo
    reducidas por decaimiento exponencial, y con la deriva del sentimiento
    sobre el estado_animo aplicada (Brecha 3).

    El sentimiento no decae — solo lo modifican eventos reales.

    Si `catalogo` es None, la Brecha 3 se omite (retrocompatibilidad).

    Tasas (leídas de configuracion.json):
        emocion      → semivida de 1 hora  (ln(2)/3600)
        estado_animo → semivida de 1 día   (ln(2)/86400)
    """
    tasa_emocion = cfg.decaimiento.tasa_emocion
    tasa_estado_animo = cfg.decaimiento.tasa_estado_animo

    nueva_emocion_intensidad = aplicar_decaimiento(
        estado.emocion_intensidad, tasa_emocion, segundos_transcurridos
    )
    nuevo_estado_animo_intensidad = aplicar_decaimiento(
        estado.estado_animo_intensidad, tasa_estado_animo, segundos_transcurridos
    )

    # Si la emoción decayó por completo, limpiar el ID a neutro.
    # Una intensidad 0.0 con un código activo es un estado inconsistente.
    emocion_id_final = (
        "neutro" if nueva_emocion_intensidad == 0.0 else estado.emocion_id
    )

    # --- Brecha 3: deriva del sentimiento sobre el estado_animo en reposo ---
    animo_id_final = estado.estado_animo_id
    if catalogo is not None:
        animo_id_final, nuevo_estado_animo_intensidad = _aplicar_deriva_sentimiento(
            estado=estado,
            nuevo_estado_animo_intensidad=nuevo_estado_animo_intensidad,
            segundos=segundos_transcurridos,
            catalogo=catalogo,
        )

    return Estado(
        relacion_id=estado.relacion_id,
        emocion_id=emocion_id_final,
        emocion_intensidad=nueva_emocion_intensidad,
        estado_animo_id=animo_id_final,
        estado_animo_intensidad=nuevo_estado_animo_intensidad,
        sentimiento_id=estado.sentimiento_id,
        sentimiento_intensidad=estado.sentimiento_intensidad,
        ultima_interaccion=estado.ultima_interaccion,
    )


# ---------------------------------------------------------------------------
# Brecha 3: deriva del sentimiento sobre el estado_animo en reposo
# ---------------------------------------------------------------------------

def _aplicar_deriva_sentimiento(
    estado: Estado,
    nuevo_estado_animo_intensidad: float,
    segundos: float,
    catalogo: list[Emocion],
) -> tuple[str, float]:
    """
    Desplaza levemente el estado_animo hacia la dirección del sentimiento
    durante períodos de reposo (sin interacción).

    Fórmula:
        horas = segundos / 3600
        presion = (vector_sentimiento − vector_estado_animo) × factor_deriva × intensidad_sentimiento × horas
        vector_nuevo_animo = vector_animo + presion

    factor_deriva es muy pequeño (≈ 0.002/hora): con amor a máxima intensidad y
    24h de ausencia, el estado_animo se mueve apenas un 4–5% hacia el territorio del amor.
    """
    horas = segundos / 3600.0

    sentimiento_obj = _buscar_en_catalogo(catalogo, estado.sentimiento_id)
    animo_obj = _buscar_en_catalogo(catalogo, estado.estado_animo_id)

    vector_sentimiento = calcular_vector_capa(sentimiento_obj, estado.sentimiento_intensidad)
    vector_animo = calcular_vector_capa(animo_obj, nuevo_estado_animo_intensidad)

    factor = cfg.deriva_sentimiento.factor_deriva_por_hora * horas * estado.sentimiento_intensidad

    nuevo_valencia = vector_animo.valencia + (vector_sentimiento.valencia - vector_animo.valencia) * factor
    nuevo_activacion = vector_animo.activacion + (vector_sentimiento.activacion - vector_animo.activacion) * factor

    vector_nuevo = Vector2D(nuevo_valencia, nuevo_activacion)

    candidatas = [e for e in catalogo if e.capa in ("estado_animo", "cualquiera")]
    animo_resultante = min(
        candidatas,
        key=lambda e: distancia_euclidiana(vector_nuevo, Vector2D(e.valencia, e.activacion)),
    )

    # La intensidad del estado_animo también deriva levemente hacia la del sentimiento
    nueva_intensidad = nuevo_estado_animo_intensidad + (
        estado.sentimiento_intensidad - nuevo_estado_animo_intensidad
    ) * factor

    return animo_resultante.codigo, max(0.0, min(1.0, nueva_intensidad))


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def _buscar_en_catalogo(catalogo: list[Emocion], codigo: str) -> Emocion:
    for emocion in catalogo:
        if emocion.codigo == codigo:
            return emocion
    raise ValueError(f"Emoción '{codigo}' no encontrada en el catálogo")
