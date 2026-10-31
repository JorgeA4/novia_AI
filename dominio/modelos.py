"""
Modelos de dominio — dataclasses que representan las entidades del modelo de datos v3.

Regla: este módulo no importa nada de persistencia, interfaz ni LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------

@dataclass
class Mbti:
    codigo: str
    siglas: str
    descripcion: str


@dataclass
class Eneagrama:
    codigo: str
    siglas: str
    descripcion: str


@dataclass
class Temperamento:
    codigo: str
    nombre: str
    descripcion: str


@dataclass
class Emocion:
    """
    Entrada del catálogo de emociones en el espacio de Russell.

    `capa` controla en qué contexto es válida:
        "emocion"      — respuesta inmediata (minutos/horas)
        "estado_animo" — tono de fondo (horas/días)
        "sentimiento"  — capa profunda (días/semanas)
        "cualquiera"   — válida en cualquier capa
    """
    codigo: str
    nombre: str
    valencia: float       # [-1.0, 1.0]
    activacion: float     # [-1.0, 1.0]
    capa: str             # "emocion" | "estado_animo" | "sentimiento" | "cualquiera"
    descripcion: str


@dataclass
class EtapaRelacion:
    codigo: str
    nombre: str
    descripcion: str


@dataclass
class TransicionEtapa:
    """
    Arista del grafo de transiciones válidas entre etapas.

    `tipo`:
        "avance"    — la relación progresa
        "retroceso" — deterioro recuperable
        "ruptura"   — transición irreversible
    """
    desde_id: str
    hasta_id: str
    tipo: str             # "avance" | "retroceso" | "ruptura"


@dataclass
class TipoEvento:
    """
    Entrada del catálogo de tipos de evento.

    `categoria` determina el cap de velocidad de cambio aplicado cuando el
    evento actualiza las métricas de RELACION (ver logica_interna.md):
        "cotidiano"     → cap ±0.03  (conversación normal, mensaje breve)
        "significativo" → cap ±0.10  (conversación larga, discusión real)
        "extraordinario"→ sin cap    (confesión, traición, ruptura)
    """
    codigo: str
    nombre: str
    descripcion: str
    categoria: str  # "cotidiano" | "significativo" | "extraordinario"


# ---------------------------------------------------------------------------
# Entidades principales
# ---------------------------------------------------------------------------

@dataclass
class Personaje:
    num: int
    nombre: str
    descripcion: str
    historia: str
    valores: list[str]
    gustos: list[str]
    aversiones: list[str]
    mbti_id: str
    eneagrama_id: str
    temperamento_id: str
    temperamento_secundario_id: Optional[str] = None


@dataclass
class Usuario:
    num: int
    nombre: str


@dataclass
class Relacion:
    num: int
    personaje_id: int
    usuario_id: int
    etapa: str              # FK -> EtapaRelacion.codigo
    confianza: float        # [0.0, 1.0]
    confianza_delta: float  # [-1.0, 1.0] — tasa de cambio reciente (EMA)
    afecto: float           # [0.0, 1.0]
    afecto_delta: float     # [-1.0, 1.0] — tasa de cambio reciente (EMA)
    familiaridad: float     # [0.0, 1.0]
    tension: float          # [0.0, 1.0]
    disposicion: float      # [0.0, 1.0] — tendencia base a buscar contacto
    disposicion_delta: float  # [-1.0, 1.0] — tasa de cambio reciente (EMA)
    instrucciones_llm: Optional[str] = None  # instrucciones de estilo/comportamiento para el LLM


@dataclass
class Estado:
    """
    Estado emocional del personaje en el contexto de una relación concreta.

    Las tres capas tienen distinta volatilidad temporal:
        emocion      — respuesta inmediata, decae en minutos/horas
        estado_animo — tono de fondo, decae en horas/días
        sentimiento  — capa profunda, solo cambia por eventos reales
    """
    relacion_id: int
    emocion_id: str                 # FK -> Emocion.codigo, capa "emocion"
    emocion_intensidad: float       # [0.0, 1.0]
    estado_animo_id: str            # FK -> Emocion.codigo, capa "estado_animo"
    estado_animo_intensidad: float  # [0.0, 1.0]
    sentimiento_id: str             # FK -> Emocion.codigo, capa "sentimiento"
    sentimiento_intensidad: float   # [0.0, 1.0]
    ultima_interaccion: datetime


@dataclass
class PerfilUsuario:
    """
    Dato factual que el personaje ha aprendido sobre cualquier persona relevante.

    `sujeto` identifica de quién es el dato:
        "usuario"           — el usuario de la relación (ej. Jorge)
        "personaje"         — el propio personaje (ej. Luna)
        "tercero:<nombre>"  — cualquier tercera persona mencionada (ej. "tercero:mama")

    confianza_final = confianza_llm × factor_origen
        "usuario_explicito" → × 1.0
        "sistema"           → × 1.0
        "llm"               → × 0.7
    """
    num: int
    relacion_id: int
    sujeto: str           # "usuario" | "personaje" | "tercero:<nombre>"
    clave: str
    valor: str
    origen: str           # "sistema" | "llm" | "usuario_explicito"
    confianza_llm: float  # [0.0, 1.0]


@dataclass
class Recuerdo:
    """
    Memoria narrativa del personaje sobre la relación.

    `categoria` clasifica el recuerdo para aplicar lógica de vigencia y priorización:
        "hecho_puntual"   — algo que ocurrió una vez, ligado a un momento concreto
        "rasgo"           — característica estable de una persona, cosa o lugar
        "hito"            — evento que marcó la relación; irrepetible en este estado
        "estado_temporal" — cómo estaba alguien/algo durante un periodo

    `vigencia` es None para recuerdos permanentes (calculada por el sistema, no el LLM).
    `emocion_asociada_id` e `emocion_asociada_intensidad` son obligatorios; usar "neutro"/0.0
    cuando no hay carga emocional.
    `embedding` se deja None en el MVP; se popula en fase 2 para búsqueda semántica.
    """
    num: int
    relacion_id: int
    tipo: str                                       # "episodico" | "relacional"
    categoria: str                                  # "hecho_puntual" | "rasgo" | "hito" | "estado_temporal"
    contenido: str
    origen: str                                     # "sistema" | "llm"
    importancia: float                              # [0.0, 1.0]
    fecha_creacion: datetime
    ultima_relevancia: datetime
    emocion_asociada_id: str                        # FK -> Emocion.codigo; "neutro" si sin carga
    emocion_asociada_intensidad: float              # [0.0, 1.0]; 0.0 si neutro
    vigencia: Optional[datetime] = None             # None = permanente; fecha = caduca
    evento_id: Optional[int] = None                 # FK -> Evento.num
    embedding: Optional[list[float]] = None         # NULL en MVP — fase 2


@dataclass
class Mensaje:
    num: int
    relacion_id: int
    rol: str              # "usuario" | "personaje"
    contenido: str
    fecha: datetime


@dataclass
class Evento:
    """
    Hecho objetivo ocurrido en la relación con impacto medible.

    `etapa_desde_id` y `etapa_hasta_id` solo se usan cuando tipo == "cambio_etapa".
    """
    num: int
    relacion_id: int
    tipo: str             # FK -> TipoEvento.codigo
    descripcion: str
    fecha: datetime
    impacto: float        # [-1.0, 1.0]
    resuelto: bool
    etapa_desde_id: Optional[str] = None   # FK -> EtapaRelacion.codigo
    etapa_hasta_id: Optional[str] = None   # FK -> EtapaRelacion.codigo


@dataclass
class Conflicto:
    """
    Especialización de un evento con naturaleza conflictiva.

    `estado`:
        "activo"   — en curso, no resuelto
        "escalado" — agravado respecto al estado inicial
        "latente"  — sin actividad reciente pero sin resolución
        "resuelto" — cerrado; `resolucion` debe estar poblado
    """
    num: int
    evento_id: int        # FK -> Evento.num
    causa: str
    estado: str           # "activo" | "escalado" | "latente" | "resuelto"
    resolucion: Optional[str] = None


# ---------------------------------------------------------------------------
# Lógica de vigencia para Recuerdo
# ---------------------------------------------------------------------------

def calcular_vigencia(
    categoria: str,
    importancia: float,
    emocion_intensidad: float,
    fecha_creacion: datetime,
) -> Optional[datetime]:
    """
    Calcula la vigencia de un recuerdo de forma determinista.

    Reglas (en orden de precedencia):
      1. Si `importancia` >= umbral_permanencia → None (permanente).
      2. Si `emocion_intensidad` >= umbral_permanencia → None (permanente).
      3. Si `categoria` es "rasgo" o "hito" → None (permanente por diseño).
      4. Si `categoria` es "hecho_puntual" → fecha_creacion + vigencia_dias_hecho_puntual.
      5. Si `categoria` es "estado_temporal" → fecha_creacion + vigencia_dias_estado_temporal.
    """
    from dominio.configuracion import cfg
    from datetime import timedelta

    if (
        importancia >= cfg.recuerdos.umbral_permanencia
        or emocion_intensidad >= cfg.recuerdos.umbral_permanencia
    ):
        return None

    if categoria in ("rasgo", "hito"):
        return None

    if categoria == "hecho_puntual":
        return fecha_creacion + timedelta(days=cfg.recuerdos.vigencia_dias_hecho_puntual)

    if categoria == "estado_temporal":
        return fecha_creacion + timedelta(days=cfg.recuerdos.vigencia_dias_estado_temporal)

    # Categoría desconocida: tratar como hecho_puntual por seguridad
    return fecha_creacion + timedelta(days=cfg.recuerdos.vigencia_dias_hecho_puntual)
