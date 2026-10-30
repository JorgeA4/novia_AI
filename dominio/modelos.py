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
    codigo: str
    nombre: str
    descripcion: str


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


@dataclass
class Usuario:
    num: int
    nombre: str


@dataclass
class Relacion:
    num: int
    personaje_id: int
    usuario_id: int
    etapa: str            # FK -> EtapaRelacion.codigo
    confianza: float      # [0.0, 1.0]
    afecto: float         # [0.0, 1.0]
    familiaridad: float   # [0.0, 1.0]
    tension: float        # [0.0, 1.0]


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
    Dato factual que el personaje ha aprendido sobre el usuario.

    confianza_final = confianza_llm × factor_origen
        "usuario_explicito" → × 1.0
        "sistema"           → × 1.0
        "llm"               → × 0.7
    """
    num: int
    relacion_id: int
    clave: str
    valor: str
    origen: str           # "sistema" | "llm" | "usuario_explicito"
    confianza_llm: float  # [0.0, 1.0]


@dataclass
class Recuerdo:
    """
    Memoria narrativa del personaje sobre la relación.

    `embedding` se deja None en el MVP; se popula en fase 2 para búsqueda semántica.
    `importancia` decae con el tiempo; cuando cae bajo umbral deja de recuperarse.
    `vigencia` marca la fecha tras la cual puede borrarse físicamente si no se reactivó.
    """
    num: int
    relacion_id: int
    tipo: str                                       # "episodico" | "relacional"
    contenido: str
    origen: str                                     # "sistema" | "llm"
    importancia: float                              # [0.0, 1.0]
    fecha_creacion: datetime
    ultima_relevancia: datetime
    vigencia: datetime
    evento_id: Optional[int] = None                 # FK -> Evento.num
    emocion_asociada_id: Optional[str] = None       # FK -> Emocion.codigo
    emocion_asociada_intensidad: Optional[float] = None
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
