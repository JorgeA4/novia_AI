# Modelo de datos — v3 — Decisiones y descartados

------------------------------------------------------

## Descartados

### `sesion_id` en MENSAJE

Agrupar mensajes por sesión de conversación — cada apertura de la app sería una sesión. Permite recuperar los mensajes de una sesión concreta sin filtrar por fecha, y permite que el personaje distinga entre cosas que ocurrieron en la misma conversación vs. en otra distinta. Se descarta para el MVP porque con `fecha` es suficiente para ordenar y filtrar el historial. Se retoma si en fases posteriores se necesita que el personaje trate una sesión como una unidad coherente de contexto.

### `procesado` en MENSAJE

Booleano que indica si un mensaje ya fue procesado para extraer recuerdos o actualizar estados — útil para evitar reprocesar si la app se cierra a mitad de una actualización. Se descarta para el MVP porque el flujo será síncrono: se procesa al momento y se guarda. Se retoma si el flujo de procesamiento se vuelve asíncrono o puede interrumpirse.

### `confianza` en RECUERDO

Qué tan seguro está el sistema de que un recuerdo inferido es correcto. Útil cuando el LLM genera recuerdos candidatos a partir de mensajes ambiguos — permite tratarlos con menos peso que hechos explícitos. Se descarta para el MVP porque inicialmente solo se crearán recuerdos explícitos y el problema no aparece todavía. Se retoma cuando el sistema de creación automática de recuerdos esté más desarrollado.

### `percepcion_estado_usuario` en ESTADO

La idea de que el personaje tenga una percepción persistente del estado emocional del usuario — del tipo "creo que está molesto". El concepto es válido psicológicamente, pero el lugar correcto no es una entidad persistente. Una percepción emocional sobre el usuario es una inferencia puntual que pertenece al contexto dinámico de la conversación activa: se genera al procesar el mensaje, se usa para construir la respuesta, y se descarta al terminar la sesión. Solo si el patrón se repite y es relevante para el futuro tendría sentido guardarlo, pero ya como recuerdo episódico, no como campo de estado. Se retoma al diseñar el sistema de contexto dinámico.

### `intimidad` en RELACION

Nivel de cercanía emocional y personal alcanzado entre personaje y usuario. Distinto de confianza — confianza es "te cuento cosas", intimidad es "hay un vínculo emocional profundo". Relevante para etapas avanzadas de la relación, especialmente románticas. Se descarta para el MVP porque la relación raramente llegará a etapas donde este campo sea significativo. Se retoma en fase 2 cuando las etapas avanzadas estén mejor modeladas.

### `objetivos_activos` en ESTADO

Los objetivos del personaje son dinámicos y tienen sentido en el estado interno, pero añaden una capa de complejidad que va más allá del MVP. Mezclarlos en ESTADO hace que la entidad crezca sin límite claro. Se pueden retomar como entidad propia o como campo de ESTADO en fases posteriores, cuando el sistema de eventos y autonomía del personaje esté más desarrollado.

### `notas_internas` en ESTADO

Campo libre donde el sistema guardaría observaciones sobre el estado actual del personaje que no encajan en campos estructurados. Útil en teoría, pero sin un uso bien definido tiene riesgo de convertirse en un cajón de sastre. Se retoma cuando haya casos concretos que justifiquen su existencia.

### `estado_base` en ESTADO

Un punto fijo de recuperación emocional al que el personaje volvería automáticamente con el tiempo. Se descartó porque genera dinámicas antinaturales: un personaje molesto que no ha recibido disculpa no debería recuperarse solo por el paso del tiempo. El concepto útil que había detrás se captura mejor con el campo `sentimiento`, que representa la capa emocional profunda construida por experiencias reales y que solo cambia por eventos reales, no mecánicamente.

### Relaciones causales y jerárquicas entre EVENTO y entre CONFLICTO

La idea de modelar que un evento puede desencadenar otro (`evento_origen_id`) o contener sub-eventos (`evento_padre_id`), y lo mismo para conflictos. El patrón es real — los eventos rara vez son aislados — pero el valor depende de que el sistema sea capaz de construir ese grafo correctamente al crear cada evento. Sin lógica de inferencia causal o una interfaz que permita al usuario construirlo manualmente, los campos estarían permanentemente en NULL. Un campo que nunca se rellena no aporta nada. Se retoma cuando el sistema pueda inferir causalidad automáticamente o cuando exista una interfaz para gestionar ese grafo.

### `defectos` en PERSONAJE

Los defectos de carácter del personaje podrían añadirse como campo explícito en PERSONAJE (del tipo `defectos → LIST[STR]`). Se descarta de forma definitiva porque los defectos ya están contemplados por el perfil psicológico — MBTI, eneagrama y temperamento modelan imperfecciones, sombras y contradicciones con mucha más precisión que una lista libre. Añadirlos como campo separado introduce tres riesgos: redundancia con el perfil psicológico, contradicciones entre el campo `defectos` y el tipo MBTI/eneagrama, y sesgo del LLM hacia personajes estereotípicos al recibir etiquetas negativas explícitas. No se retoma.

### `objetivos` como constante de identidad en PERSONAJE

Los objetivos del personaje podrían modelarse como atributo constante de identidad (ej: *"quiere ser escritora"*, *"busca independencia emocional"*). Se descarta porque, aunque los objetivos de vida son relativamente estables, la forma en que se activan y expresan depende del contexto y del estado de la relación — son más dinámicos que una constante. El lugar más correcto sería una entidad propia o un campo de ESTADO cuando el sistema de autonomía del personaje esté más desarrollado. Se retoma en fase 2 junto con `objetivos_activos` en ESTADO.

### HISTORIAL_ETAPA como entidad separada

Los cambios de etapa de relación podrían guardarse en una entidad propia `HISTORIAL_ETAPA`. Se descarta porque un cambio de etapa es un hecho objetivo con fecha e impacto — exactamente lo que modela EVENTO. Los EVENTOs de tipo `"cambio_etapa"` con los campos `etapa_desde_id` y `etapa_hasta_id` ya constituyen ese historial, sin necesidad de una entidad adicional redundante.

### Catálogos para valores de enum internos

Los campos `tipo` en TRANSICION_ETAPA, `estado` en CONFLICTO, `tipo` en RECUERDO y `capa` en EMOCION tienen un conjunto cerrado de valores válidos. Se evaluó crear catálogos para cada uno por consistencia con MBTI, ENEAGRAMA y similares. Se descarta porque existe una diferencia técnica real: los catálogos existentes son FK desde otras entidades o aportan campos adicionales que usa el sistema. Estos cuatro campos son valores internos de una sola entidad — nunca son FK desde ningún otro sitio. Crear una tabla para ellos añade joins sin añadir capacidad. Se modelan como enums con valores explícitos documentados en lógica interna. Se pueden promover a catálogo en fase 2 si aparece una razón concreta.

### `energia_social` en PERSONAJE

Campo que describiría el espectro introversión/extroversión de forma explícita e independiente del MBTI. Se descartó porque no hay consenso claro sobre si modelarla como valores discretos o espectro numérico, y porque el MBTI ya cubre esta dimensión de forma implícita. Se puede retomar si en la práctica el LLM no interpreta bien esta dimensión a partir del tipo MBTI solo.

------------------------------------------------------

## Decisiones

### Por qué el rango sigue siendo `0.0 – 1.0` y no se amplió a `0 – 100`

Ampliar el rango es matemáticamente equivalente a reducir el impacto de cada evento en la misma proporción — no resuelve nada, solo obliga a reescribir todas las fórmulas, comparaciones y umbrales del sistema. El problema real era la velocidad de cambio, no la resolución numérica. Se resolvió con dos mecanismos en la lógica interna: cap de impacto por tipo de evento y resistencia creciente en los extremos. Ver lógica interna, sección "Velocidad de cambio en métricas de RELACION".

### Por qué `disposicion` es un campo persistente y no calculado

Se evaluó calcular la disposición del personaje al contacto en tiempo real a partir de `afecto`, `estado_animo` y tiempo sin hablar, sin persistirla. Se descartó porque perdería la noción de que hay personajes que *por historia de la relación* buscan o evitan el contacto independientemente de su estado emocional inmediato. Un personaje puede estar de buen humor y aun así no querer hablar con alguien específico por razones acumuladas — esa tendencia estructural no se puede derivar del estado puntual.

La solución adoptada es un híbrido: `disposicion` persiste como tendencia base lenta (solo la mueven eventos reales), y `interes_actual` se calcula al vuelo combinando `disposicion`, el estado de ánimo presente y el tiempo sin hablar. Ver lógica interna.

### Por qué los `_delta` solo se añaden a `confianza`, `afecto` y `disposicion`

Los cinco campos de RELACION se evaluaron para añadirles `_delta`. Se descartó para `familiaridad` y `tension` por razones distintas:

- `familiaridad` — en la práctica solo sube; retrocede solo en casos extremos (olvido, distanciamiento largo). Una tendencia negativa sostenida en familiaridad sería señal de un problema de diseño más que un estado normal a modelar.
- `tension` — ya tiene carácter direccional implícito: un valor alto *es* la señal de alarma. No necesita delta para transmitir urgencia al LLM — el valor en sí lo hace.

`confianza`, `afecto` y `disposicion` son los campos donde la dirección del cambio tiene mayor impacto en el tono relacional y en la decisión de iniciativa, por lo que son los que justifican el campo adicional.

### Por qué el delta usa media exponencial ponderada y no valor anterior

Se evaluó guardar simplemente el valor anterior de cada métrica (`afecto_anterior`) y calcular la tendencia como la diferencia. Se descartó porque captura solo el último salto — un cambio de `0.5 → 0.52` después de diez eventos bajando daría delta positivo, lo que sería engañoso. La media exponencial acumula el historial de dirección reciente con decaimiento natural, produciendo una señal más robusta y menos ruidosa.

### Por qué el perfil psicológico en lugar de sliders en PERSONAJE

El modelo anterior proponía parámetros numéricos del tipo `humor: 0.7`, `afecto: 0.8`. El problema de ese enfoque es que el LLM decide qué significa cada valor y lo interpreta con sus sesgos de entrenamiento, produciendo personajes planos y estereotípicos.

Los marcos psicológicos (MBTI, eneagrama, temperamento) son sistemas documentados con miles de matices ya presentes en el entrenamiento del LLM. La combinación de varios marcos obliga al modelo a reconciliar características que pueden estar en tensión entre sí, lo que produce respuestas mucho menos predecibles y más ricas que un simple slider.