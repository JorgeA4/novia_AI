# Lógica interna del sistema

Decisiones de comportamiento interno no deducibles directamente del código o del modelo de datos.

Todos los parámetros numéricos se leen de `data/configuracion.json` vía `dominio/configuracion.py`.

---

## Modelo emocional — espacio de Russell vectorial

Cada emoción del catálogo `EMOCION` ocupa una posición fija en el espacio 2D de Russell:
- `valencia` — eje horizontal `[-1.0, 1.0]`. Negativo = displacer, positivo = placer.
- `activacion` — eje vertical `[-1.0, 1.0]`. Negativo = baja energía, positivo = alta energía.

### Intensidad como escala del vector

```
posicion = (valencia × intensidad, activacion × intensidad)
```

Intensidad `0.0` colapsa al origen. Intensidad `1.0` es la posición canónica.

### Estado emocional compuesto

```
estado_compuesto = (
    vector(emocion)      × intensidad_emocion      × 0.50 +
    vector(estado_animo) × intensidad_estado_animo × 0.35 +
    vector(sentimiento)  × intensidad_sentimiento  × 0.15
)
```

### Detección de emoción resultante

```
emocion_actual = argmin[ distancia_euclidiana(vector_compuesto, coord_canonica[e]) ]
```

No hay umbrales ni if/else — el cambio es emergente del espacio geométrico.

### Comunicación al LLM

El sistema calcula el vector compuesto y pasa al LLM únicamente el **nombre** de la emoción más cercana. Nunca pasa coordenadas.

---

## Decaimiento de capas emocionales

Exponencial. Fórmula: `intensidad × e^(−tasa × segundos)`, donde `tasa = ln(2) / semivida_segundos`.

| capa         | semivida         |
|--------------|------------------|
| emocion      | 1 hora (config)  |
| estado_animo | 1 día (config)   |
| sentimiento  | no decae sola    |

Cuando la intensidad cae bajo el umbral de corte (config) se fuerza a `0.0` y el `emocion_id` se limpia a `"neutro"`. El `sentimiento` solo lo modifican eventos reales.

**Derivación natural entre capas:** cuando la `emocion` decae, su contribución al vector compuesto disminuye y el `estado_animo` gana peso relativo. La emoción no desaparece en el vacío — se funde con el tono de fondo.

---

## Brechas 1, 2 y 3 — interacción entre capas

Las tres brechas son los mecanismos por los que las capas se influyen mutuamente.

### Brecha 1 — Presión de la emoción sobre el estado_animo (por turno)

En cada turno, la emoción inferida ejerce una presión acumulativa sobre el `estado_animo`. El estado_animo no cambia de golpe — se desplaza lentamente en el espacio de Russell hacia la dirección de la emoción:

```
presion_bruta = valencia_emocion × intensidad_emocion × factor_presion_base
vector_nuevo_animo = vector_animo + (vector_emocion − vector_animo) × presion_real
```

`factor_presion_base` es pequeño (≈ 0.015): un turno mueve el estado_animo ~1.5%.

### Brecha 2 — Modulación del sentimiento sobre la presión

El sentimiento vigente modera la presión de la Brecha 1. Si la emoción va en la misma dirección que el sentimiento, la presión es plena (~1.0). Si va en dirección opuesta (p.ej. emoción de rabia con sentimiento de amor), la presión se reduce (~0.30):

```
similitud = coseno(vector_emocion, vector_sentimiento) ∈ [-1, 1]
factor_moderacion = centroide + similitud × amplitud     ∈ [0.30, 1.00]
presion_real = presion_bruta × factor_moderacion
```

`centroide` y `amplitud` están en config.

### Brecha 3 — Deriva del sentimiento sobre el estado_animo en reposo

Durante períodos sin interacción, el `estado_animo` deriva lentamente hacia la dirección del `sentimiento`:

```
factor = factor_deriva_por_hora × horas × intensidad_sentimiento
vector_nuevo_animo = vector_animo + (vector_sentimiento − vector_animo) × factor
```

`factor_deriva_por_hora` es muy pequeño (≈ 0.002): con amor a máxima intensidad y 24h de ausencia, el estado_animo se mueve apenas ~4–5%.

---

## Confianza en PERFIL_USUARIO

```
confianza_final = confianza_llm × factor_origen
```

Factores de origen (el valor del LLM se lee de `configuracion.json`):
```
"usuario_explicito" → × 1.0
"sistema"           → × 1.0
"llm"               → × penalizacion_inferencia  (0.7 por defecto)
```

Al resolver duplicados (misma `sujeto` + `clave`): gana el de mayor `confianza_final`. Si la diferencia es pequeña (< umbral), se conserva el existente y se marca para revisión.

El campo `sujeto` identifica de quién es el dato. Valores válidos:
```
"usuario"          — el usuario de la relación
"personaje"        — el propio personaje
"tercero:<nombre>" — tercera persona mencionada (ej. "tercero:mama")
```
La clave única de un dato de perfil es la tripleta `(relacion_id, sujeto, clave)`.

---

## Campos `_delta` en RELACION

`confianza_delta`, `afecto_delta` y `disposicion_delta` capturan la tasa de cambio reciente como EMA:

```
delta_nuevo = delta_anterior × α + cambio_real × (1 − α)
```

`α` se lee de config (`relacion.ema_alpha`). El delta no decae con el tiempo — solo cambia cuando hay un evento que modifica la métrica.

`familiaridad` y `tension` no tienen `_delta`: `familiaridad` en la práctica solo sube, y `tension` ya tiene carácter direccional implícito en su valor.

---

## `interes_actual`

Calculado en tiempo real, no persistido:

```
factor_tiempo  = 1.0 − e^(−horas_sin_hablar / τ)          [τ en config]
interes_actual = disposicion                    × 0.50
               + valencia_estado_animo_norm     × 0.35
               + factor_tiempo                  × 0.15
```

`valencia_estado_animo_norm = (valencia + 1.0) / 2.0`

| rango        | interpretación                              |
|--------------|---------------------------------------------|
| < 0.25       | el personaje evita o ignora el contacto     |
| 0.25 – 0.50  | responde si le hablan, sin energía          |
| 0.50 – 0.75  | disposición normal                          |
| > 0.75       | puede tomar iniciativa                      |

---

## Velocidad de cambio en métricas de RELACION

Dos mecanismos combinados:

**Cap por categoría de evento:**
```
cotidiano       → cap ±cfg.relacion.cap_cotidiano    (≈ 0.03)
significativo   → cap ±cfg.relacion.cap_significativo (≈ 0.10)
extraordinario  → sin cap
```

**Resistencia en extremos:**
```
resistencia  = 4 × valor × (1 − valor)    [máx 1.0 en valor=0.5, min 0.0 en extremos]
impacto_real = impacto_capped × resistencia
```

**Orden de aplicación:**
1. Cap por categoría → `impacto_capped`
2. Resistencia → `impacto_real`
3. `nuevo = clamp(actual + impacto_real, 0.0, 1.0)`
4. Recalcular `_delta` con `impacto_real`

---

## Transiciones de etapa relacional

El sistema consulta `TRANSICION_ETAPA` antes de cualquier cambio. Si el par `(desde, hasta)` no existe, la transición no está permitida.

Tipos:
- `avance` — progresa hacia mayor cercanía
- `retroceso` — deterioro recuperable
- `ruptura` — irreversible

Las condiciones de umbral se evalúan sobre los campos de `RELACION`. El modo de activación:
- **Impulso automático** — condiciones superadas con margen suficiente (`umbral_impulso_automatico` en config)
- **Permiso** — condiciones cumplidas pero se necesita un momento decisivo (el sistema hace una llamada auxiliar al LLM para verificarlo)

Al avanzar de etapa, el sentimiento se actualiza: el sistema asigna el sentimiento correspondiente a la nueva etapa y suma `delta_sentimiento_al_avanzar` (config) a la intensidad vigente.

---

## RECUERDO — categoría y vigencia

El campo `categoria` clasifica cada recuerdo para aplicar lógica de vigencia y priorización:

| categoria         | descripción                                               | vigencia por defecto |
|-------------------|-----------------------------------------------------------|----------------------|
| `hecho_puntual`   | algo que ocurrió una vez, ligado a un momento concreto    | 30 días              |
| `rasgo`           | característica estable de una persona, cosa o lugar       | permanente           |
| `hito`            | evento que marcó la relación; irrepetible en este estado  | permanente           |
| `estado_temporal` | cómo estaba alguien o algo durante un periodo             | 14 días              |

La vigencia la calcula el sistema (`calcular_vigencia()` en `dominio/modelos.py`), **nunca el LLM**:

```
si importancia >= umbral_permanencia (0.85)  →  vigencia = None (permanente)
si emocion_intensidad >= umbral_permanencia  →  vigencia = None (permanente)
si categoria en ("rasgo", "hito")            →  vigencia = None (permanente)
si categoria == "hecho_puntual"              →  vigencia = ahora + 30 días
si categoria == "estado_temporal"            →  vigencia = ahora + 14 días
```

Los umbrales y días se leen de `configuracion.json` (`recuerdos.*`). `vigencia = None` significa permanente; el recuerdo nunca caduca salvo que se borre explícitamente.

`emocion_asociada_id` e `emocion_asociada_intensidad` son **obligatorios**. Usar `"neutro"` / `0.0` cuando no hay carga emocional. Todos los códigos del catálogo de emociones son válidos (incluyendo `"neutro"` con `capa: "cualquiera"`).

**Regla de formato del contenido:** oración completa con sujeto explícito + verbo en pasado. Si el sujeto es el propio personaje, se usa primera persona (`"Admití que..."`, `"Sentí que..."`). Si es otra persona o cosa, se nombra (`"Jorge dijo que..."`, `"El clima estaba..."`). Los fragmentos nominales o frases sin verbo no son válidos.

## Deduplicación de RECUERDO

El LLM tiende a generar recuerdos duplicados cuando el usuario vuelve a mencionar un hecho ya registrado. Se aplican dos capas de protección:

**Capa B — instrucción al LLM:** el system prompt incluye explícitamente los recuerdos existentes como lista de verificación. La instrucción exige comprobar que ningún recuerdo existente ya cubre el mismo hecho antes de añadir uno nuevo.

**Capa A — filtro en código (Jaccard):** antes de persistir, se calcula la similitud de Jaccard entre los tokens del candidato y cada recuerdo existente:
```
similitud = |tokens(nuevo) ∩ tokens(existente)| / |tokens(nuevo) ∪ tokens(existente)|
```
Tokens = palabras en minúsculas de longitud ≥ 3. Umbral: `0.45`. Si la similitud supera el umbral, el recuerdo se descarta silenciosamente. La lista local se actualiza en cada iteración del turno para evitar también duplicados dentro del mismo turno.

La capa B captura paráfrasis semánticas (vocabulario diferente, mismo significado). La capa A captura variantes verbosas del mismo texto.

---

## Valores de enum internos

Campos con conjunto cerrado de valores modelados como enums en el código, sin catálogo en base de datos.

**EMOCION — `capa`:** `"emocion"` · `"estado_animo"` · `"sentimiento"` · `"cualquiera"`

**RECUERDO — `tipo`:** `"episodico"` · `"relacional"`

**RECUERDO / PERFIL_USUARIO — `origen`:** `"sistema"` · `"llm"` · `"usuario_explicito"`

**CONFLICTO — `estado`:** `"activo"` · `"escalado"` · `"latente"` · `"resuelto"`

**TRANSICION_ETAPA — `tipo`:** `"avance"` · `"retroceso"` · `"ruptura"`

---

## Pendiente de definir

- Fórmulas de actualización del `sentimiento` por eventos que no sean cambio de etapa.
- Decaimiento y reactivación de `importancia` en RECUERDO.
