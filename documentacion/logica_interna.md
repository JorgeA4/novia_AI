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

**El decaimiento no cae al neutro.** Cuando la intensidad de `emocion` baja, su contribución al vector compuesto disminuye y el `estado_animo` gana peso relativo. El vector resultante **deriva naturalmente** hacia donde está el estado de ánimo.

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

- Tasas de decaimiento concretas por capa (¿función lineal? ¿exponencial?)
- Cómo los eventos modifican la intensidad de cada capa (¿fórmula de impacto?)
- Cómo la `importancia` de un RECUERDO decae y se reactiva
- Cómo `confianza`, `afecto`, `familiaridad` y `tension` en RELACION se actualizan tras un evento

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

