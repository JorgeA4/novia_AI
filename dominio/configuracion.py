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


@dataclass(frozen=True)
class ConfigRecuerdos:
    vigencia_dias: int


@dataclass(frozen=True)
class ConfigTransicionEtapa:
    impacto_evento: float
    delta_sentimiento_al_avanzar: float


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
    )


cfg: Configuracion = _cargar_configuracion()
