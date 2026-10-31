# Modelo de datos — v3

------------------------------------------------------

## PERSONAJE

Atributos constantes de identidad, historia y psicología del personaje.

### Campos

num             → INT (PK)
nombre          → STR
descripcion     → STR
historia        → STR
valores         → LIST[STR]
gustos          → LIST[STR]
aversiones      → LIST[STR]
mbti_id         → STR (FK -> MBTI.codigo)
eneagrama_id    → STR (FK -> ENEAGRAMA.codigo)
temperamento_id → STR (FK -> TEMPERAMENTO.codigo)

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
ultima_interaccion      → DATETIME

------------------------------------------------------

## RELACION

Vínculo entre un personaje y un usuario. Evoluciona con el tiempo y con los eventos.

Los campos `_delta` capturan la tasa de cambio reciente de su métrica asociada — calculada como media exponencial de los últimos cambios. Un delta positivo indica crecimiento sostenido; negativo, declive. Permiten distinguir un valor de 0.5 que va en subida de uno que va en bajada, lo que afecta tanto al tono de respuesta del personaje como al cálculo de `interes_actual`.

`disposicion` representa la tendencia base del personaje a buscar o recibir contacto con este usuario. No es aprecio (`afecto`) ni conocimiento (`familiaridad`), sino la tracción hacia el encuentro. `interes_actual` se calcula a partir de `disposicion`, el estado emocional presente y el tiempo sin hablar — ver lógica interna.

### Campos

num                 → INT (PK)
personaje_id        → INT (FK -> PERSONAJE.num)
usuario_id          → INT (FK -> USUARIO.num)
etapa               → STR (FK -> ETAPA_RELACION.codigo)
confianza           → FLOAT (0.0 – 1.0)
confianza_delta     → FLOAT (-1.0 – 1.0)
afecto              → FLOAT (0.0 – 1.0)
afecto_delta        → FLOAT (-1.0 – 1.0)
familiaridad        → FLOAT (0.0 – 1.0)
tension             → FLOAT (0.0 – 1.0)
disposicion         → FLOAT (0.0 – 1.0)
disposicion_delta   → FLOAT (-1.0 – 1.0)

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

`importancia` decae con el tiempo si el recuerdo no se reactiva; cuando cae bajo umbral el sistema deja de recuperarlo. `vigencia` es `None` para recuerdos permanentes; cuando tiene valor marca la fecha tras la cual puede borrarse físicamente si no se reactivó — calculada por el sistema según `categoria`, nunca por el LLM. `embedding` se deja NULL en MVP y se popula en fase 2 para búsqueda semántica.

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
importancia                 → FLOAT (0.0 – 1.0)
emocion_asociada_id         → STR (FK -> EMOCION.codigo)
emocion_asociada_intensidad → FLOAT (0.0 – 1.0)
fecha_creacion              → DATETIME
ultima_relevancia           → DATETIME
vigencia                    → DATETIME (opcional — None = permanente)
embedding                   → VECTOR (opcional — None en MVP, fase 2)

### Lógica de `vigencia` por `categoria`

| categoria        | vigencia                                                        |
|------------------|-----------------------------------------------------------------|
| `rasgo`          | permanente (None)                                               |
| `hito`           | permanente (None)                                               |
| `hecho_puntual`  | fecha_creacion + `vigencia_dias_hecho_puntual` (defecto: 30 d)  |
| `estado_temporal`| fecha_creacion + `vigencia_dias_estado_temporal` (defecto: 14 d)|

Excepción: si `importancia >= umbral_permanencia` (defecto: 0.85) o `emocion_asociada_intensidad >= umbral_permanencia`, el recuerdo es siempre permanente independientemente de la categoría.

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
tipo             → STR (FK -> TIPO_EVENTO.codigo)
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
