# Modelo de datos — v3

------------------------------------------------------

## PERSONAJE

Atributos constantes de identidad, historia y psicología del personaje.

### Campos

num                         → INT (PK)
nombre                      → STR
descripcion                 → STR
historia                    → STR
valores                     → LIST[STR]
gustos                      → LIST[STR]
aversiones                  → LIST[STR]
mbti_id                     → STR (FK -> MBTI.codigo)
eneagrama_id                → STR (FK -> ENEAGRAMA.codigo)
temperamento_id             → STR (FK -> TEMPERAMENTO.codigo)
temperamento_secundario_id  → STR (FK -> TEMPERAMENTO.codigo, opcional)
tipo_atraccion_id           → STR (FK -> TIPO_ATRACCION.codigo, opcional — None si no definido)
estilo_apego_id             → STR (FK -> ESTILO_APEGO.codigo, opcional — None si no definido)
matiz_atraccion             → STR (opcional — texto libre, 1-2 frases que matizan el perfil)

------------------------------------------------------

## MBTI

Catálogo de los 16 tipos MBTI. `descripcion` es solo informativa para UI.

### Campos

codigo      → STR (PK)
siglas      → STR
descripcion → STR

------------------------------------------------------

## ENEAGRAMA

Catálogo de los 18 tipos del eneagrama (9 tipos × 2 alas). `descripcion` es solo informativa para UI.

### Campos

codigo      → STR (PK)
siglas      → STR
descripcion → STR

------------------------------------------------------

## TEMPERAMENTO

Catálogo de los 4 temperamentos clásicos. `descripcion` es solo informativa para UI.

### Campos

codigo      → STR (PK)
nombre      → STR
descripcion → STR

------------------------------------------------------

## TIPO_ATRACCION

Catálogo de los tipos de atracción del personaje. Define qué dimensión del comportamiento del usuario resonará con este personaje y activará `delta_atraccion` positivo. `descripcion` es solo informativa para UI y para el LLM.

### Campos

codigo      → STR (PK)
nombre      → STR
descripcion → STR

### Entradas

| codigo        | nombre      | descripcion                                                                         |
|---------------|-------------|--------------------------------------------------------------------------------------|
| `intelectual` | Intelectual | Atracción por la mente, el debate, la curiosidad y la profundidad de ideas           |
| `emocional`   | Emocional   | Atracción por la vulnerabilidad compartida, la empatía y la conexión genuina         |
| `vital`       | Vital       | Atracción por la energía, el humor, la espontaneidad y la aventura                   |
| `valoral`     | Valoral     | Atracción por los principios, la coherencia ética y la autenticidad                  |
| `sensorial`   | Sensorial   | Atracción por la presencia, el cuidado físico y los gestos concretos                 |

------------------------------------------------------

## ESTILO_APEGO

Catálogo de los cuatro estilos de apego (Bowlby/Ainsworth). Define cómo la dinámica de la relación modula el desarrollo de la atracción. `descripcion` es solo informativa para UI y para el LLM.

### Campos

codigo      → STR (PK)
nombre      → STR
descripcion → STR

### Entradas

| codigo          | nombre        | descripcion                                                                                          |
|-----------------|---------------|-------------------------------------------------------------------------------------------------------|
| `seguro`        | Seguro        | Florece por conexión genuina sin condiciones especiales; cómodo con cercanía e independencia          |
| `ansioso`       | Ansioso       | Necesita atención sostenida y consistencia; la ambigüedad activa el alejamiento                       |
| `evitativo`     | Evitativo     | La atracción crece cuando se respeta el espacio; la presión o urgencia la bloquea                     |
| `desorganizado` | Desorganizado | Respuestas contradictorias; mezcla de atracción e incomodidad ante la cercanía                        |

------------------------------------------------------

## EMOCION

Catálogo de emociones, estados de ánimo y sentimientos. Compartido por ESTADO y RECUERDO. `descripcion` es solo informativa para UI.

`valencia` y `activacion` son coordenadas en el espacio de Russell — las usa el sistema para lógica interna. El LLM recibe únicamente `nombre`.

`capa` controla en qué contexto es válido usar cada entrada, evitando asignar emociones de corta duración como sentimientos profundos.

### Campos

codigo      → STR (PK)
nombre      → STR
valencia    → FLOAT (-1.0 – 1.0)
activacion  → FLOAT (-1.0 – 1.0)
capa        → STR ("emocion" | "estado_animo" | "sentimiento" | "cualquiera")
descripcion → STR

------------------------------------------------------

## USUARIO

Identidad técnica mínima del usuario. Todo lo que el personaje aprende sobre él pertenece a PERFIL_USUARIO y RECUERDO.

### Campos

num    → INT (PK)
nombre → STR

------------------------------------------------------

## ESTADO

Estado interno del personaje en el contexto de una relación concreta. Es por relación — el mismo personaje puede tener estados distintos en relaciones distintas.

Tres capas emocionales con distinta volatilidad temporal:
- `emocion`: respuesta inmediata a un estímulo. Desaparece en minutos u horas.
- `estado_animo`: tono de fondo reciente. Cambia en horas o días.
- `sentimiento`: capa profunda acumulada. Solo cambia por eventos reales.

### Campos

relacion_id             → INT (FK -> RELACION.num)
emocion_id              → STR (FK -> EMOCION.codigo, capa "emocion")
emocion_intensidad      → FLOAT (0.0 – 1.0)
estado_animo_id         → STR (FK -> EMOCION.codigo, capa "estado_animo")
estado_animo_intensidad → FLOAT (0.0 – 1.0)
sentimiento_id          → STR (FK -> EMOCION.codigo, capa "sentimiento")
sentimiento_intensidad  → FLOAT (0.0 – 1.0)

------------------------------------------------------

## RELACION

Vínculo entre un personaje y un usuario. Evoluciona con el tiempo y con los eventos.

Los campos `_delta` capturan la tasa de cambio reciente de su métrica asociada — calculada como media exponencial de los últimos cambios. Un delta positivo indica crecimiento sostenido; negativo, declive. Permiten distinguir un valor de 0.5 que va en subida de uno que va en bajada, lo que afecta tanto al tono de respuesta del personaje como al cálculo de `interes_actual`.

`disposicion` representa la tendencia base del personaje a buscar o recibir contacto con este usuario. No es aprecio (`afecto`) ni conocimiento (`familiaridad`), sino la tracción hacia el encuentro. `satisfaccion_contacto` representa cuánto contacto reciente ha recibido el personaje y reduce temporalmente la presión de seguir interactuando. `interes_actual` se calcula a partir de `disposicion`, el estado emocional presente, el tiempo sin hablar y `satisfaccion_contacto` — ver lógica interna.

### Campos

num                 → INT (PK)
personaje_id        → INT (FK -> PERSONAJE.num)
usuario_id          → INT (FK -> USUARIO.num)
etapa_id            → STR (FK -> ETAPA_RELACION.codigo)
confianza           → FLOAT (0.0 – 1.0)
confianza_delta     → FLOAT (-1.0 – 1.0)
afecto              → FLOAT (0.0 – 1.0)
afecto_delta        → FLOAT (-1.0 – 1.0)
familiaridad        → FLOAT (0.0 – 1.0)
tension             → FLOAT (0.0 – 1.0)
disposicion         → FLOAT (0.0 – 1.0)
disposicion_delta   → FLOAT (-1.0 – 1.0)
atraccion           → FLOAT (0.0 – 1.0)   — interés romántico del personaje hacia este usuario; 0.0 si no hay perfil de atracción definido
atraccion_delta     → FLOAT (-1.0 – 1.0)  — tasa de cambio reciente (EMA)
instrucciones_llm   → STR (opcional — None si no hay instrucciones)
ult_mensaje         → DATETIME — fecha del último mensaje de la relación
satisfaccion_contacto → FLOAT (0.0 – 1.0) — nivel de contacto reciente satisfecho; decae con el tiempo

------------------------------------------------------

## PERFIL_USUARIO

Datos factuales y estables que el personaje ha aprendido sobre cualquier persona relevante en el contexto de una relación. Pares clave-valor estructurados que el sistema puede leer, actualizar y contrastar sin depender del LLM.

`sujeto` identifica de quién es el dato: el usuario, el propio personaje, o una tercera persona mencionada. La clave única es la tripleta `(relacion_id, sujeto, clave)`.

`confianza_llm` es la certeza que el LLM declaró al extraer el dato. El sistema la penaliza por `origen` para obtener la confianza final (`confianza_final = confianza_llm × factor_origen`). Ver lógica interna.

### Campos

num           → INT (PK)
relacion_id   → INT (FK -> RELACION.num)
sujeto        → STR ("usuario" | "personaje" | "tercero:<nombre>")
clave         → STR
valor         → STR
origen        → STR ("sistema" | "llm" | "usuario_explicito")
confianza_llm → FLOAT (0.0 – 1.0)

### Semántica de `sujeto`

| valor              | representa                                        | ejemplo         |
|--------------------|---------------------------------------------------|-----------------|
| `"usuario"`        | el usuario de la relación                         | Jorge           |
| `"personaje"`      | el propio personaje (información sobre sí mismo)  | Luna            |
| `"tercero:<nombre>"` | cualquier tercera persona mencionada            | "tercero:mama"  |

------------------------------------------------------

## RECUERDO

Memoria narrativa del personaje sobre la relación. Los datos factuales de personas pertenecen a PERFIL_USUARIO.

`importancia` es una propiedad intrínseca y estable del recuerdo, asignada por el LLM al crearlo; no muta. `vigencia` es `None` para recuerdos permanentes; cuando tiene valor marca la fecha tras la cual el recuerdo se considera expirado y se descarta **antes** de cualquier proceso de recuperación — calculada por el sistema según `categoria`, nunca por el LLM. `embedding` se deja None en el MVP y se popula en fase 2 para búsqueda semántica.

`mensaje_origen_num` vincula el recuerdo con el mensaje que provocó su creación. Permite saber si el recuerdo ya está representado en el historial que recibe el LLM, independientemente de si hubo respuesta del personaje o de cuántos mensajes compongan un turno. Es `None` para recuerdos antiguos o creados fuera de una conversación concreta.

`relevancia_activa` es una propiedad dinámica e independiente de `importancia`: se inicializa al crear el recuerdo, decae exponencialmente con el tiempo sin uso, y recibe un boost cada vez que el recuerdo es seleccionado en una conversación. Su techo natural es siempre `importancia`.

`emocion_asociada_id` e `emocion_asociada_intensidad` son **obligatorios**; usar `"neutro"` / `0.0` cuando no hay carga emocional.

Tipos (`tipo`):
- `"episodico"` — eventos concretos con dimensión temporal.
- `"relacional"` — momentos importantes del vínculo: promesas, discusiones, reconciliaciones.

Categorías (`categoria`):
- `"hecho_puntual"` — algo que ocurrió una vez, ligado a un momento concreto.
- `"rasgo"` — característica estable de una persona, cosa o lugar.
- `"hito"` — evento que marcó la relación; irrepetible en este estado.
- `"estado_temporal"` — cómo estaba alguien/algo durante un periodo acotado.

### Campos

num                         → INT (PK)
relacion_id                 → INT (FK -> RELACION.num)
evento_id                   → INT (FK -> EVENTO.num, opcional)
tipo                        → STR ("episodico" | "relacional")
categoria                   → STR ("hecho_puntual" | "rasgo" | "hito" | "estado_temporal")
contenido                   → STR
origen                      → STR ("sistema" | "llm")
importancia                 → FLOAT (0.0 – 1.0)  — propiedad fija; asignada al crear, no muta
emocion_asociada_id         → STR (FK -> EMOCION.codigo)
emocion_asociada_intensidad → FLOAT (0.0 – 1.0)
fecha_creacion              → DATETIME
relevancia_activa           → FLOAT (0.0 – 1.0)  — decae con tiempo; boost al recuperar; techo = importancia
vigencia                    → DATETIME (opcional — None = permanente; si expiró, se descarta)
mensaje_origen_id           → INT (FK -> MENSAJE.num, opcional)
ult_recuperacion            → DATETIME
embedding                   → VECTOR(384) (opcional — None en MVP; fase 2: pgvector, índice HNSW)

### Lógica de `vigencia` por `categoria`

| categoria        | vigencia                                                        |
|------------------|-----------------------------------------------------------------|
| `rasgo`          | permanente (None)                                               |
| `hito`           | permanente (None)                                               |
| `hecho_puntual`  | fecha_creacion + `vigencia_dias_hecho_puntual` (defecto: 30 d)  |
| `estado_temporal`| fecha_creacion + `vigencia_dias_estado_temporal` (defecto: 14 d)|

Excepción: si `importancia >= umbral_permanencia` (defecto: 0.85) o `emocion_asociada_intensidad >= umbral_permanencia`, el recuerdo es siempre permanente independientemente de la categoría.

Ver `logica_interna.md` para el pipeline completo de recuperación (filtro de vigencia, decaimiento, ranking y boost).

------------------------------------------------------

## MENSAJE

Historial cronológico de conversación. Los recuerdos se derivan de los mensajes pero son una entidad separada.

### Campos

num         → INT (PK)
relacion_id → INT (FK -> RELACION.num)
rol         → STR ("usuario" | "personaje")
contenido   → STR
fecha       → DATETIME

------------------------------------------------------

## EVENTO

Hecho objetivo ocurrido en la relación, registrado con impacto medible. Independiente de cómo lo recuerde el personaje.

### Campos

num              → INT (PK)
relacion_id      → INT (FK -> RELACION.num)
tipo_id          → STR (FK -> TIPO_EVENTO.codigo)
descripcion      → STR
fecha            → DATETIME
impacto          → FLOAT (-1.0 – 1.0)
resuelto         → BOOL
etapa_desde_id   → STR (FK -> ETAPA_RELACION.codigo, opcional — solo si tipo es "cambio_etapa")
etapa_hasta_id   → STR (FK -> ETAPA_RELACION.codigo, opcional — solo si tipo es "cambio_etapa")

------------------------------------------------------

## CONFLICTO

Especialización de un evento con naturaleza conflictiva. Modela su causa, evolución y resolución.

### Campos

num        → INT (PK)
evento_id  → INT (FK -> EVENTO.num)
causa      → STR
estado     → STR ("activo" | "escalado" | "latente" | "resuelto")
resolucion → STR (opcional)

------------------------------------------------------

## ETAPA_RELACION

Catálogo de las etapas posibles de una relación. Las transiciones válidas entre etapas se definen en TRANSICION_ETAPA. `descripcion` es solo informativa para UI.

### Campos

codigo      → STR (PK)
nombre      → STR
descripcion → STR

------------------------------------------------------

## TRANSICION_ETAPA

Grafo de transiciones válidas entre etapas. El sistema consulta esta entidad antes de aplicar cualquier cambio de etapa — si no existe el par `(desde_id, hasta_id)`, la transición no está permitida. Las condiciones de umbral para cada transición se definen en la lógica interna.

La etapa `interes_romantico` ha sido eliminada del grafo. El flujo de avance romántico es ahora:
`desconocidos → conocidos → amigos → amigos_cercanos → pareja`.
La transición `amigos_cercanos → pareja` requiere `atraccion >= atraccion_min_pareja` además de los umbrales habituales, y nunca puede activarse por impulso automático (solo por momento decisivo).

### Campos

desde_id → STR (FK -> ETAPA_RELACION.codigo)
hasta_id → STR (FK -> ETAPA_RELACION.codigo)
tipo     → STR ("avance" | "retroceso" | "ruptura")

------------------------------------------------------

## TIPO_EVENTO

Catálogo de los tipos de evento reconocidos por el sistema. `descripcion` es solo informativa para UI.

### Campos

codigo      → STR (PK)
nombre      → STR
descripcion → STR
categoria   → STR  CHECK ("cotidiano" | "significativo" | "extraordinario")

### Semántica de `categoria`

Determina el cap de velocidad de cambio que se aplica cuando el evento
actualiza las métricas de RELACION (ver logica_interna.md §Velocidad de cambio):

| categoria       | cap por turno | casos típicos                              |
|-----------------|---------------|--------------------------------------------|
| cotidiano       | ±0.03         | mensaje breve, conversación normal         |
| significativo   | ±0.10         | conversación larga, discusión real         |
| extraordinario  | sin límite    | confesión, promesa importante, traición    |

------------------------------------------------------

## Decisiones de persistencia

### Fase 1 — JSON en disco

Implementación actual. Todos los campos se serializan como JSON plano en `data/`.
El campo `embedding` se almacena como lista de floats en texto. Es ineficiente pero
funcional para el MVP con pocos recuerdos.

### Fase 2 — PostgreSQL + pgvector

**Decisión registrada:** la migración a base de datos usará **PostgreSQL** con la
extensión **pgvector**.

Detalles del campo `RECUERDO.embedding`:

- Tipo de columna: `vector(384)` (384 dimensiones — modelo `paraphrase-multilingual-MiniLM-L12-v2`)
- Índice: **HNSW** (`CREATE INDEX ON recuerdo USING hnsw (embedding vector_cosine_ops)`)
- Operador de búsqueda: `<=>` (distancia coseno)
- Tamaño en disco: 384 × 4 bytes = **1.536 bytes por fila** (frente a ~3–5 KB en JSON)

Ejemplo de consulta de recuperación por similitud:

```sql
SELECT * FROM recuerdo
WHERE relacion_id = $1
ORDER BY embedding <=> $2::vector
LIMIT 5;
```

La capa de dominio (`dominio/`) no cambia. Solo se sustituye el repositorio JSON
(`repositorios/json/operaciones_json.py`) por su equivalente Postgres
(`repositorios/postgres/operaciones_pg.py`), que recibe y devuelve las mismas
dataclasses definidas en `dominio/modelos.py`.
