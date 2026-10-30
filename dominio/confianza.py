"""
Lógica de confianza en PERFIL_USUARIO.

Operaciones:
    - Calcular confianza_final a partir de confianza_llm y origen.
    - Resolver conflictos entre entradas duplicadas (misma clave).

Regla: este módulo no importa nada de persistencia, interfaz ni LLM.
"""

from __future__ import annotations

from dominio.configuracion import cfg
from dominio.modelos import PerfilUsuario


# ---------------------------------------------------------------------------
# Factores de origen — construidos desde configuración
# ---------------------------------------------------------------------------

def _factores_origen() -> dict[str, float]:
    return {
        "usuario_explicito": 1.0,
        "sistema": 1.0,
        "llm": cfg.confianza_llm.penalizacion_inferencia,
    }


# ---------------------------------------------------------------------------
# Cálculo de confianza
# ---------------------------------------------------------------------------

def calcular_confianza_final(confianza_llm: float, origen: str) -> float:
    """
    confianza_final = confianza_llm × factor_origen

    Factores (leídos de configuracion.json):
        "usuario_explicito" → × 1.0  (sin penalización)
        "sistema"           → × 1.0  (sin penalización)
        "llm"               → × cfg.confianza_llm.penalizacion_inferencia
    """
    factores = _factores_origen()
    factor = factores.get(origen)
    if factor is None:
        raise ValueError(f"Origen desconocido: '{origen}'. Valores válidos: {list(factores)}")
    return confianza_llm * factor


def confianza_final_de(entrada: PerfilUsuario) -> float:
    """Atajo para calcular la confianza_final de una entrada de PERFIL_USUARIO."""
    return calcular_confianza_final(entrada.confianza_llm, entrada.origen)


# ---------------------------------------------------------------------------
# Resolución de duplicados
# ---------------------------------------------------------------------------

# El umbral de diferencia mínima no está en configuracion.json porque es
# una constante operativa de resolución de conflictos, no un parámetro de diseño.
# Se define aquí para que sea visible y modificable localmente si se necesita.
UMBRAL_DIFERENCIA_MINIMA: float = 0.1


def resolver_duplicado(
    existente: PerfilUsuario,
    nueva: PerfilUsuario,
) -> tuple[PerfilUsuario, bool]:
    """
    Compara dos entradas de PERFIL_USUARIO con la misma clave y decide cuál conservar.

    Devuelve (entrada_ganadora, requiere_revision).

    - Si la diferencia de confianza_final es >= UMBRAL_DIFERENCIA_MINIMA,
      gana la de mayor confianza y no requiere revisión.
    - Si la diferencia es < UMBRAL_DIFERENCIA_MINIMA (empate técnico),
      se conserva la existente por estabilidad y se marca para revisión.
    """
    confianza_existente = confianza_final_de(existente)
    confianza_nueva = confianza_final_de(nueva)
    diferencia = abs(confianza_existente - confianza_nueva)

    if diferencia < UMBRAL_DIFERENCIA_MINIMA:
        return existente, True  # empate — conservar existente, marcar revisión

    ganadora = nueva if confianza_nueva > confianza_existente else existente
    return ganadora, False


def consolidar_perfil(
    entradas: list[PerfilUsuario],
) -> tuple[list[PerfilUsuario], list[tuple[PerfilUsuario, PerfilUsuario]]]:
    """
    Dado un listado de entradas de PERFIL_USUARIO (posiblemente con claves duplicadas),
    devuelve:
        - lista consolidada: una sola entrada por clave (la de mayor confianza_final)
        - lista de pares en conflicto que requieren revisión manual

    El orden de procesamiento es el del listado recibido.
    """
    consolidado: dict[str, PerfilUsuario] = {}
    para_revision: list[tuple[PerfilUsuario, PerfilUsuario]] = []

    for entrada in entradas:
        clave = entrada.clave
        if clave not in consolidado:
            consolidado[clave] = entrada
            continue

        ganadora, requiere_revision = resolver_duplicado(consolidado[clave], entrada)
        if requiere_revision:
            para_revision.append((consolidado[clave], entrada))
        consolidado[clave] = ganadora

    return list(consolidado.values()), para_revision
