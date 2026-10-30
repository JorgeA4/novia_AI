# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Estado actual del repositorio

Este repositorio está en **fase de diseño/arquitectura pura**. No existe código implementado, ni lenguaje/framework decidido, ni herramientas de build/test. Toda la lógica está definida en `/documentacion/`.

## Documentación crítica (leer antes de cualquier cambio)

| Archivo | Contenido |
|---------|-----------|
| [`documentacion/modelo_datos_v3.md`](documentacion/modelo_datos_v3.md) | Esquema de datos canónico (entidades, campos, tipos, restricciones) |
| [`documentacion/modelo_datos_decisiones_v3.md`](documentacion/modelo_datos_decisiones_v3.md) | Justificación de cada decisión de diseño — **consultar antes de proponer cambios estructurales** |
| [`documentacion/logica_interna.md`](documentacion/logica_interna.md) | Lógica del sistema (emociones, transiciones, confianza) |

## Convenciones del modelo de datos

- **Español obligatorio** para todos los nombres de entidades, campos, documentación y comentarios.
- Las emociones usan el **modelo de Russell** (valencia × activación en `[-1.0, 1.0]²`); las emociones resultantes son emergentes — el sistema elige la más cercana por distancia euclidiana, nunca por umbrales manuales.
- **3 capas emocionales** con pesos fijos: `emocion × 0.50 + estado_animo × 0.35 + sentimiento × 0.15`; los coeficientes son parte del diseño, no parámetros configurables.
- Los campos marcados como `NULL` en el MVP (p.ej. `embedding` en RECUERDO, `intimidad` en RELACION) están reservados para fase 2 — no eliminarlos del esquema.
- Los enums internos (`tipo`, `estado`, `capa`) **no tienen tabla catálogo** deliberadamente; modelar como CHECK constraint o enum del lenguaje, nunca como FK.

## Patrones de confianza

```
confianza_final = confianza_llm × factor_origen
  "usuario_explicito" → × 1.0
  "sistema"           → × 1.0
  "llm"               → × 0.7  (penalización por inferencia)
```

Al resolver duplicados en PERFIL_USUARIO, se conserva el registro de mayor `confianza_final`.

## Arquitectura LLM

El LLM **nunca recibe** vectores numéricos ni estados crudos. Solo recibe lenguaje natural + nombre de emoción inferido. Los frameworks psicológicos (MBTI + Eneagrama + Temperamento) se usan juntos para forzar tensión y profundidad en el personaje, no por separado.

## Áreas pendientes (no inventar sin consenso)

- Fórmulas de decaimiento de capas emocionales (lineal vs exponencial — aún no decidido).
- Fórmulas de actualización de `confianza`, `afecto`, `familiaridad`, `tension` en RELACION tras eventos.
- Decaimiento y reactivación de `importancia` en RECUERDO.
- Estrategia de prompting para extracción de recuerdos e inferencia de PERFIL_USUARIO.
