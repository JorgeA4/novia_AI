# Lógica interna del sistema

Decisiones sobre comportamiento interno del sistema que no pertenecen al modelo de datos pero que son necesarias para diseñar e implementar la lógica de negocio.

---

## Modelo emocional — espacio de Russell vectorial

### Fundamento

Cada emoción del catálogo `EMOCION` ocupa una posición fija en el espacio 2D de Russell, definida por dos coordenadas:

- `valencia` — eje horizontal. Rango `[-1.0, 1.0]`. Negativo = displacer, positivo = placer.
- `activacion` — eje vertical. Rango `[-1.0, 1.0]`. Negativo = baja energía, positivo = alta energía.

Esas coordenadas son la **coordenada canónica** de la emoción — su posición natural en el mapa afectivo.

### Intensidad como escala del vector

En `ESTADO`, cada capa emocional tiene una `intensidad` (`FLOAT 0.0 – 1.0`). La intensidad **escala** el vector canónico sin desplazarlo lateralmente:

```
posicion = (valencia × intensidad, activacion × intensidad)
```

Una emoción con intensidad `0.0` colapsa al origen — estado neutro.
Una emoción con intensidad `1.0` ocupa su posición canónica completa.

### Estado emocional compuesto

El estado emocional real del personaje en un momento dado es la **suma ponderada** de los vectores de las tres capas:

```
estado_compuesto = (
    vector(emocion)      × intensidad_emocion      × 0.50 +
    vector(estado_animo) × intensidad_estado_animo × 0.35 +
    vector(sentimiento)  × intensidad_sentimiento  × 0.15
)
```

Los pesos (0.50 / 0.35 / 0.15) son constantes del sistema. Pueden ajustarse durante el desarrollo pero deben mantenerse constantes en producción para garantizar comportamiento predecible.

### Detección de cambio de emoción — enfoque emergente

El cambio de emoción no se dispara por un umbral arbitrario. El sistema calcula el vector compuesto y busca la emoción del catálogo cuya coordenada canónica esté más cercana por **distancia euclidiana**:

```
emocion_actual = argmin[ distancia(vector_compuesto, coord_canonica[e]) para e en EMOCION ]
```

Si la emoción más cercana cambia respecto a la del turno anterior, el sistema registra el cambio. No hay decisión manual — el cambio es emergente del espacio geométrico.

### Decaimiento y derivación entre capas

La intensidad de la capa `emocion` decae con el tiempo (tasa rápida, horas).
La intensidad de la capa `estado_animo` decae más lento (días).
La capa `sentimiento` apenas decae sola — solo la modifican eventos reales.

**Función de decaimiento: exponencial.**

```
intensidad_nueva = intensidad × e^(−tasa × segundos)
```

La tasa usa semivida como parámetro intuitivo: `tasa = ln(2) / semivida_segundos`.

| capa         | semivida   | tasa (1/s)       |
|--------------|------------|------------------|
| emocion      | 1 hora     | ln(2) / 3600     |
| estado_animo | 1 día      | ln(2) / 86400    |
| sentimiento  | no decae   | —                |

Cuando la intensidad cae por debajo del umbral de corte (`0.01`) se fuerza a `0.0`
y el `emocion_id` se limpia a `"neutro"`. Esto evita el estado inconsistente de
tener un código de emoción activo con intensidad efectivamente nula.

**El decaimiento no colapsa al neutro de golpe.** Cuando la intensidad de `emocion` baja, su contribución al vector compuesto disminuye y el `estado_animo` gana peso relativo. El vector resultante **deriva naturalmente** hacia donde está el estado de ánimo.

Esto produce comportamiento emergente correcto:
- Si el estado de ánimo es positivo, el personaje se recupera de emociones negativas de forma natural.
- Si el estado de ánimo también es negativo, la caída es más profunda y duradera.
- Una emoción que decae no desaparece en el vacío — se funde con el tono de fondo del personaje.

### Comunicación al LLM

El sistema **nunca pasa coordenadas al LLM**. El proceso es:

1. Calcular el vector compuesto `(v, a)`.
2. Buscar la emoción del catálogo más cercana (distancia euclidiana mínima).
3. Pasar al LLM el **nombre** de esa emoción como lenguaje natural.

El LLM recibe: *"el personaje siente frustración"* — no números.

---

## Pendiente de documentar

- Cómo los eventos modifican la intensidad de cada capa (¿fórmula de impacto?)
- Cómo la `importancia` de un RECUERDO decae y se reactiva
- Cómo `confianza`, `afecto`, `familiaridad`, `tension` y `disposicion` en RELACION se actualizan tras un evento

---

## Confianza en PERFIL_USUARIO

La confianza final de un dato en PERFIL_USUARIO se calcula combinando la certeza que el LLM declaró al extraerlo con un factor de penalización por origen:

```
confianza_final = confianza_llm × factor_origen
```

Factores de origen (constantes del sistema):

```
"usuario_explicito" → 1.0   (el usuario lo declaró directamente — sin penalización)
"sistema"           → 1.0   (lo calculó el código — sin penalización)
"llm"               → 0.7   (inferencia del LLM — penalización del 30%)
```

Esto permite distinguir, por ejemplo:
- LLM muy seguro  + origen llm  → 0.9 × 0.7 = 0.63
- LLM inseguro    + origen llm  → 0.4 × 0.7 = 0.28  ← el sistema puede ignorarlo
- Usuario explícito             → 1.0 × 1.0 = 1.00

Cuando el sistema registra un dato con `origen: "sistema"` o `origen: "usuario_explicito"`, `confianza_llm` se fija a `1.0` por defecto ya que no hay inferencia que penalizar.

Si al extraer un dato el LLM detecta que ya existe una entrada con la misma `clave`, el sistema debe resolver el conflicto comparando `confianza_final` de ambos registros y conservando el de mayor confianza, o marcando ambos para revisión si la diferencia es pequeña.


---

## Campos `_delta` en RELACION

### Propósito

Los campos `confianza_delta`, `afecto_delta` y `disposicion_delta` capturan la **tasa de cambio reciente** de su métrica. Un valor de `0.5` en `afecto` significa cosas distintas si lleva tres eventos subiendo o si acaba de caer desde `0.8`. El delta permite al sistema distinguir ambas situaciones y transmitirlas al LLM en lenguaje natural.

### Cálculo

Cada vez que un evento modifica una métrica, su delta se recalcula como **media exponencial ponderada** de los cambios recientes:

```
cambio_nuevo  = valor_nuevo − valor_anterior
delta_nuevo   = delta_anterior × α + cambio_nuevo × (1 − α)
```

`α` es el factor de suavizado (`0.0 – 1.0`). Un `α` alto da más peso al historial; uno bajo reacciona más rápido al cambio inmediato. Valor de referencia: `α = 0.6`. Se ajusta durante implementación.

El delta **no decae solo con el tiempo** — solo cambia cuando hay un evento que modifica la métrica. Si la relación está estancada, el delta refleja el último impulso que tuvo.

### Uso

**Contexto para el LLM.** Antes de generar una respuesta, el sistema convierte los deltas a lenguaje natural:

```
afecto = 0.5,  afecto_delta > +0.10  → "el afecto está en 0.5 y creciendo con fuerza"
afecto = 0.5,  afecto_delta ≈ 0      → "el afecto está en 0.5 y estable"
afecto = 0.5,  afecto_delta < −0.10  → "el afecto está en 0.5 y en declive"
```

Los umbrales de conversión (cuándo es "estable" vs "creciendo") se definen durante implementación.

**Cálculo de `interes_actual`.** Un `afecto_delta` o `disposicion_delta` negativo significativo puede penalizar el interés de contacto aunque los valores base sean aceptables — ver sección `interes_actual`.

---

## `interes_actual`

Valor calculado en tiempo real — **no se persiste**. El sistema lo computa cada vez que necesita decidir si el personaje toma iniciativa o con qué energía responde.

### Fórmula

```
factor_tiempo  = 1.0 − e^(−horas_sin_hablar / τ)     [τ = 24.0 por defecto]

interes_actual = (
    disposicion                    × 0.50 +
    valencia_estado_animo_norm     × 0.35 +
    factor_tiempo                  × 0.15
)
```

`valencia_estado_animo_norm` es la coordenada `valencia` del `estado_animo_id` actual, normalizada a `[0.0, 1.0]` con `(valencia + 1.0) / 2.0`.

`factor_tiempo` usa una curva exponencial que sube rápido en las primeras horas y se satura cerca de `1.0` — pocas horas sin hablar ya generan impulso, pero pasar de 72 h no añade mucho más. `τ` se ajusta durante implementación.

### Interpretación

```
interes_actual < 0.25   → el personaje evita o ignora el contacto
0.25 – 0.50             → responde si el usuario escribe, sin energía
0.50 – 0.75             → disposición normal
> 0.75                  → puede tomar iniciativa
```

Los umbrales exactos se ajustan durante implementación.

### Relación con los `_delta`

Un `disposicion_delta` o `afecto_delta` muy negativo puede aplicar una penalización adicional sobre `interes_actual` aunque los valores base sean razonables. La fórmula exacta de esa penalización se define al implementar — el principio es que la dirección del cambio tiene peso propio.

---

## Velocidad de cambio en métricas de RELACION

### Principio

El rango `0.0 – 1.0` de las métricas de RELACION no implica que sea fácil llegar a los extremos. La velocidad a la que se mueven está controlada por dos mecanismos combinados: un **cap por tipo de evento** que limita el impacto máximo según la naturaleza del evento, y una **resistencia creciente en los extremos** que hace cada vez más difícil acercarse a `0.0` o `1.0`.

### Mecanismo 1 — Cap de impacto por tipo de evento

Cada tipo de evento tiene un impacto máximo que no puede superar, independientemente de lo bien o mal que haya ido:

```
evento cotidiano        → cap ±0.03   (conversación normal, mensaje breve)
evento significativo    → cap ±0.10   (conversación larga y positiva, discusión real)
evento extraordinario   → sin cap     (confesión, promesa importante, traición, ruptura)
```

La clasificación de cada TIPO_EVENTO en una de estas tres categorías se define al poblar el catálogo durante implementación.

### Mecanismo 2 — Resistencia en los extremos

Antes de aplicar un cambio, el sistema lo escala según la posición actual de la métrica. El cambio es más fácil en el centro (`0.5`) y más difícil cerca de `0.0` o `1.0`:

```
resistencia  = 4 × valor × (1 − valor)     ← máxima (1.0) en valor=0.5, mínima (0.0) en extremos
impacto_real = impacto_base × resistencia
```

Ejemplo con `afecto = 0.9` e `impacto_base = +0.10`:

```
resistencia  = 4 × 0.9 × 0.1 = 0.36
impacto_real = 0.10 × 0.36   = 0.036
```

El mismo evento que en `afecto = 0.5` movería `0.10` completo, en `afecto = 0.9` solo mueve `0.036`. Llegar a `1.0` requiere muchos eventos extraordinarios sostenidos.

La resistencia aplica igual para subidas y bajadas — perder el último rastro de afecto también cuesta.

### Orden de aplicación

```
1. Calcular impacto_base del evento
2. Aplicar cap según tipo de evento   → impacto_capped
3. Aplicar resistencia de extremos    → impacto_real
4. Actualizar valor: nuevo = clamp(actual + impacto_real, 0.0, 1.0)
5. Recalcular _delta con el cambio real aplicado
```

### Métricas afectadas

Este mecanismo aplica a `confianza`, `afecto`, `familiaridad`, `tension` y `disposicion`. Los campos `_delta` usan el `impacto_real` (post-resistencia) para su cálculo, no el `impacto_base`.

---

## Transiciones de etapa relacional

El sistema controla todas las transiciones entre etapas. No puede ocurrir una transición que no esté registrada en `TRANSICION_ETAPA`.

### Tipos de transición

- `avance` — la relación progresa hacia mayor cercanía o compromiso
- `retroceso` — la relación se deteriora pero puede recuperarse
- `ruptura` — transición hacia un estado final o difícilmente reversible

### Reglas de transición

Cada transición puede tener asociadas **condiciones de umbral** sobre los campos de RELACION que deben cumplirse para que el sistema la considere elegible:

```
ejemplo: desconocidos → conocidos
  condicion: familiaridad > 0.2 AND interacciones >= 3

ejemplo: amigos_cercanos → interes_romantico
  condicion: afecto > 0.75 AND confianza > 0.70 AND tension < 0.20

ejemplo: pareja → distanciamiento
  condicion: tension > 0.70 OR afecto < 0.25
```

Las condiciones exactas se definirán durante la implementación y podrán ajustarse sin modificar el modelo de datos.

### Impulso vs. permiso

El sistema distingue entre dos modos de activación de una transición:

- **Permiso** — las condiciones se cumplen y la transición *puede* ocurrir, pero requiere un evento significativo que la detone (ej: una confesión, una promesa, una ruptura explícita)
- **Impulso automático** — las condiciones se cumplen de forma tan clara y sostenida que el sistema avanza la etapa sin necesidad de un evento puntual

El diseño exacto de cuándo aplicar uno u otro se define al implementar la máquina de estados relacional.


---

## Valores de enum internos

Campos con conjunto cerrado de valores que se gestionan como enums en el código, sin catálogo en base de datos.

### EMOCION — `capa`

Controla en qué contexto es válido usar cada entrada del catálogo.

```
"emocion"      — emoción inmediata, alta volatilidad (minutos/horas)
"estado_animo" — tono de fondo reciente (horas/días)
"sentimiento"  — capa profunda acumulada (días/semanas)
"cualquiera"   — válida en cualquier capa
```

### RECUERDO — `tipo`

```
"episodico"   — evento concreto con dimensión temporal
"relacional"  — momento importante del vínculo entre personaje y usuario
```

### RECUERDO — `origen`

```
"sistema" — registrado por el código a partir de un EVENTO verificado
"llm"     — inferido por el LLM del texto de conversación
```

### PERFIL_USUARIO — `origen`

```
"sistema"            — calculado directamente por el código
"llm"                — extraído por el LLM de la conversación
"usuario_explicito"  — declarado por el usuario en la interfaz
```

### CONFLICTO — `estado`

```
"activo"   — conflicto en curso, no resuelto
"escalado" — conflicto agravado respecto a su estado inicial
"latente"  — conflicto sin resolución pero sin actividad reciente
"resuelto" — conflicto cerrado; el campo `resolucion` debe estar poblado
```

### TRANSICION_ETAPA — `tipo`

```
"avance"    — la relación progresa hacia mayor cercanía o compromiso
"retroceso" — la relación se deteriora pero puede recuperarse
"ruptura"   — transición hacia un estado final o difícilmente reversible
```

