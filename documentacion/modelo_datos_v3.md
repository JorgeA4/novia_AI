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

### Campos

num           → INT (PK)
personaje_id  → INT (FK -> PERSONAJE.num)
usuario_id    → INT (FK -> USUARIO.num)
etapa         → STR (FK -> ETAPA_RELACION.codigo)
confianza     → FLOAT (0.0 – 1.0)
afecto        → FLOAT (0.0 – 1.0)
familiaridad  → FLOAT (0.0 – 1.0)
tension       → FLOAT (0.0 – 1.0)

------------------------------------------------------

## PERFIL_USUARIO

Datos factuales y estables que el personaje ha aprendido sobre el usuario. Pares clave-valor estructurados que el sistema puede leer, actualizar y contrastar sin depender del LLM.

`confianza_llm` es la certeza que el LLM declaró al extraer el dato. El sistema la penaliza por `origen` para obtener la confianza final (`confianza_final = confianza_llm × factor_origen`). Ver lógica interna.

### Campos

num           → INT (PK)
relacion_id   → INT (FK -> RELACION.num)
clave         → STR
valor         → STR
origen        → STR ("sistema" | "llm" | "usuario_explicito")
confianza_llm → FLOAT (0.0 – 1.0)

------------------------------------------------------

## RECUERDO

Memoria narrativa del personaje sobre la relación. Los datos factuales del usuario pertenecen a PERFIL_USUARIO.

`importancia` decae con el tiempo si el recuerdo no se reactiva; cuando cae bajo umbral el sistema deja de recuperarlo. `vigencia` marca la fecha tras la cual puede borrarse físicamente si no se reactivó. `embedding` se deja NULL en MVP y se popula en fase 2 para búsqueda semántica.

Tipos:
- `episodico` — eventos concretos con dimensión temporal.
- `relacional` — momentos importantes del vínculo: promesas, discusiones, reconciliaciones.

### Campos

num                         → INT (PK)
relacion_id                 → INT (FK -> RELACION.num)
evento_id                   → INT (FK -> EVENTO.num, opcional)
tipo                        → STR ("episodico" | "relacional")
contenido                   → STR
origen                      → STR ("sistema" | "llm")
importancia                 → FLOAT (0.0 – 1.0)
emocion_asociada_id         → STR (FK -> EMOCION.codigo, opcional)
emocion_asociada_intensidad → FLOAT (0.0 – 1.0, opcional)
fecha_creacion              → DATETIME
ultima_relevancia           → DATETIME
vigencia                    → DATETIME
embedding                   → VECTOR (opcional)

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
