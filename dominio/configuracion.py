"""
Configuración del sistema — carga los parámetros de diseño desde data/configuracion.json.

Todas las constantes del comportamiento emocional y relacional se leen de ese archivo.
Ningún módulo debe usar literales numéricos de diseño; debe importar desde aquí.

Uso:
    from dominio.configuracion import cfg

    cfg.presion_turno.factor_presion_base      # float
    cfg.decaimiento.semivida_emocion_segundos  # float
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Ruta al archivo de configuración — relativa a la raíz del proyecto
# ---------------------------------------------------------------------------

_RUTA_CONFIG = Path(__file__).parent.parent / "data" / "configuracion.json"


# ---------------------------------------------------------------------------
# Dataclasses que mapean la estructura del JSON
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfigCapas:
    peso_emocion: float
    peso_estado_animo: float
    peso_sentimiento: float


@dataclass(frozen=True)
class ConfigPresionTurno:
    factor_presion_base: float
    centroide_moderacion: float
    amplitud_moderacion: float


@dataclass(frozen=True)
class ConfigDerivaSentimiento:
    factor_deriva_por_hora: float


@dataclass(frozen=True)
class ConfigDecaimiento:
    semivida_emocion_segundos: float
    semivida_estado_animo_segundos: float
    umbral_corte: float

    @property
    def tasa_emocion(self) -> float:
        """Constante de decaimiento 1/segundo para la emoción."""
        return math.log(2) / self.semivida_emocion_segundos

    @property
    def tasa_estado_animo(self) -> float:
        """Constante de decaimiento 1/segundo para el estado_animo."""
        return math.log(2) / self.semivida_estado_animo_segundos


@dataclass(frozen=True)
class ConfigInerciaEstadoAnimo:
    factor: float


@dataclass(frozen=True)
class ConfigConfianzaLlm:
    penalizacion_inferencia: float


@dataclass(frozen=True)
class ConfigRelacion:
    ema_alpha: float
    tau_horas_interes: float
    umbral_impulso_automatico: float
    cap_cotidiano: float
    cap_significativo: float
    impulso_disposicion_base: float
    familiaridad_peso_perfil: float
    familiaridad_peso_recuerdos: float
    familiaridad_peso_mensajes: float
    familiaridad_escala_perfil: float       # nº de entradas de perfil que equivale a familiaridad=1.0 (antes de raíz)
    familiaridad_escala_recuerdos: float    # nº de recuerdos que equivale a familiaridad=1.0 (antes de raíz)
    familiaridad_escala_mensajes: float     # nº de mensajes que equivale a familiaridad=1.0 (antes de raíz)
    familiaridad_semivida_dias: float       # días para que la familiaridad sin interacción baje a la mitad
    tension_semivida_horas: float           # horas para que la tensión sin fricción baje a la mitad
    tension_reduccion_por_afecto: float     # fracción del afecto positivo que reduce tensión en cada turno


@dataclass(frozen=True)
class ConfigRecuerdos:
    vigencia_dias_hecho_puntual: int    # días de vigencia para "hecho_puntual"
    vigencia_dias_estado_temporal: int  # días de vigencia para "estado_temporal"
    umbral_permanencia: float           # importancia o emocion_intensidad >= este valor → vigencia None
    relevancia_boost_emocion: float     # fracción de emocion_intensidad que se suma a relevancia_activa inicial
    relevancia_boost_recuperacion: float  # boost aplicado a relevancia_activa al ser recuperado
    relevancia_semivida_dias: float     # días para que relevancia_activa baje a la mitad sin uso


@dataclass(frozen=True)
class ConfigTransicionEtapa:
    impacto_evento: float
    delta_sentimiento_al_avanzar: float


@dataclass(frozen=True)
class ConfigConflictos:
    umbral_tension_crear: float    # tension_delta >= este valor → crear conflicto nuevo
    umbral_tension_escalar: float  # tension_delta >= este valor + conflicto activo → escalar


@dataclass(frozen=True)
class ConfigContextoLlm:
    limite_historial: int
    limite_recuerdos: int
    confianza_minima_perfil: float
    limite_conflictos_activos: int


@dataclass(frozen=True)
class ConfigEmbedding:
    modelo: str
    top_k_semantico: int
    umbral_similitud_minima: float      # similitud coseno mínima para que un recuerdo sea candidato
    peso_importancia: float             # peso de importancia en el ranking de candidatos
    peso_relevancia: float              # peso de relevancia_activa en el ranking de candidatos
    peso_emocion_recuperacion: float    # peso de emocion_asociada_intensidad en el ranking


@dataclass(frozen=True)
class Configuracion:
    capas: ConfigCapas
    presion_turno: ConfigPresionTurno
    deriva_sentimiento: ConfigDerivaSentimiento
    decaimiento: ConfigDecaimiento
    inercia_estado_animo: ConfigInerciaEstadoAnimo
    confianza_llm: ConfigConfianzaLlm
    relacion: ConfigRelacion
    recuerdos: ConfigRecuerdos
    transicion_etapa: ConfigTransicionEtapa
    conflictos: ConfigConflictos
    contexto_llm: ConfigContextoLlm
    embedding: ConfigEmbedding


# ---------------------------------------------------------------------------
# Carga — singleton perezoso
# ---------------------------------------------------------------------------

def _cargar_configuracion() -> Configuracion:
    with open(_RUTA_CONFIG, encoding="utf-8") as f:
        d = json.load(f)

    return Configuracion(
        capas=ConfigCapas(**d["capas"]),
        presion_turno=ConfigPresionTurno(**d["presion_turno"]),
        deriva_sentimiento=ConfigDerivaSentimiento(**d["deriva_sentimiento"]),
        decaimiento=ConfigDecaimiento(**d["decaimiento"]),
        inercia_estado_animo=ConfigInerciaEstadoAnimo(**d["inercia_estado_animo"]),
        confianza_llm=ConfigConfianzaLlm(**d["confianza_llm"]),
        relacion=ConfigRelacion(**d["relacion"]),
        recuerdos=ConfigRecuerdos(**d["recuerdos"]),
        transicion_etapa=ConfigTransicionEtapa(**d["transicion_etapa"]),
        conflictos=ConfigConflictos(**d["conflictos"]),
        contexto_llm=ConfigContextoLlm(**d["contexto_llm"]),
        embedding=ConfigEmbedding(**d["embedding"]),
    )


cfg: Configuracion = _cargar_configuracion()
