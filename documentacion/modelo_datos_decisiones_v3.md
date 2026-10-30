# Modelo de datos — v3 — Decisiones y descartados

---

## Descartados

- **`sesion_id` en MENSAJE** — con `fecha` es suficiente para el MVP. Retomar si se necesita tratar una sesión como unidad coherente de contexto.
- **`procesado` en MENSAJE** — el flujo es síncrono; no se puede interrumpir a mitad. Retomar si el procesamiento se vuelve asíncrono.
- **`confianza` en RECUERDO** — solo se crearán recuerdos explícitos por ahora. Retomar cuando el sistema genere recuerdos candidatos ambiguos.
- **`percepcion_estado_usuario` en ESTADO** — una percepción emocional sobre el usuario es una inferencia puntual que pertenece al contexto dinámico del turno, no a la persistencia. Si el patrón se repite y es relevante, ya existe RECUERDO para eso.
- **`intimidad` en RELACION** — la relación raramente llega a etapas donde sea significativa. Retomar en fase 2 con etapas avanzadas mejor modeladas.
- **`objetivos_activos` en ESTADO** — añaden complejidad sin beneficio claro en el MVP. Retomar en fase 2 junto con autonomía del personaje.
- **`notas_internas` en ESTADO** — sin un uso concreto definido es un cajón de sastre. Retomar con casos específicos.
- **`estado_base` en ESTADO** — un punto fijo de recuperación emocional genera dinámicas antinaturales (un personaje molesto no debería recuperarse solo por el tiempo). El `sentimiento` cubre el concepto útil: capa profunda que da el tono de fondo y solo cambia por eventos reales.
- **Relaciones causales entre EVENTO y CONFLICTO** (`evento_origen_id`, `evento_padre_id`) — sin lógica de inferencia causal, estos campos estarían siempre en NULL. Retomar cuando el sistema pueda inferir causalidad.
- **`defectos` en PERSONAJE** — los defectos ya están cubiertos por MBTI + eneagrama + temperamento con más profundidad y sin riesgo de contradicción. Descartado definitivamente.
- **`objetivos` como constante en PERSONAJE** — los objetivos de vida son más dinámicos que una constante; su expresión depende del contexto y la etapa. Retomar en fase 2 como entidad propia.
- **HISTORIAL_ETAPA como entidad separada** — los EVENTOs de tipo `"cambio_etapa"` con `etapa_desde_id` y `etapa_hasta_id` ya constituyen ese historial.
- **Catálogos para enums internos** (`tipo` en TRANSICION_ETAPA, `estado` en CONFLICTO, etc.) — estos valores son internos de una sola entidad, nunca son FK desde otro sitio. Una tabla para ellos añade joins sin añadir capacidad.
- **`energia_social` en PERSONAJE** — el MBTI ya cubre la dimensión introversión/extroversión. Retomar si el LLM no la interpreta bien a partir del tipo MBTI solo.

---

## Decisiones

- **Rango `0.0–1.0` en métricas de RELACION** — ampliar a `0–100` es matemáticamente equivalente; no resuelve nada y obliga a reescribir todas las fórmulas. La velocidad de cambio se controla con cap por tipo de evento y resistencia en extremos (ver logica_interna.md).

- **`disposicion` es persistente, no calculada** — calculada al vuelo perdería la noción de que hay personajes que por historia de la relación buscan o evitan el contacto independientemente del estado emocional puntual. La solución: `disposicion` persiste como tendencia base lenta (solo la mueven eventos reales) e `interes_actual` se calcula al vuelo combinando `disposicion`, `estado_animo` y tiempo sin hablar.

- **`_delta` solo en `confianza`, `afecto` y `disposicion`** — `familiaridad` en la práctica solo sube; un delta negativo sostenido sería señal de problema de diseño. `tension` tiene carácter direccional implícito en su valor.

- **Delta como EMA, no diferencia con valor anterior** — la diferencia captura solo el último salto. La EMA acumula la dirección reciente con decaimiento natural, produciendo una señal más robusta.

- **Perfil psicológico en lugar de sliders** — parámetros numéricos (`humor: 0.7`) producen personajes planos porque el LLM los interpreta con sus sesgos de entrenamiento. Los marcos MBTI + eneagrama + temperamento tienen miles de matices en el entrenamiento del LLM, y su combinación obliga al modelo a reconciliar características en tensión, produciendo respuestas más ricas.
