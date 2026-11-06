# Plan: Atracción romántica como dimensión independiente

## Objetivo

Rediseñar cómo el sistema modela y gestiona el interés romántico, eliminando su carácter de "etapa inevitable" y convirtiéndolo en una dimensión autónoma de la relación que emerge solo cuando hay afinidad genuina entre el perfil de atracción del personaje y el comportamiento real del usuario.

## Alcance

- Eliminar `interes_romantico` como etapa del grafo relacional.
- Añadir `atraccion` como campo propio de `RELACION`.
- Añadir `tipo_atraccion`, `estilo_apego` y `matiz_atraccion` al modelo `PERSONAJE`.
- Añadir un catálogo pequeño `TIPO_ATRACCION` y extender `ESTILO_APEGO` con sus cuatro valores.
- Ajustar el flujo del turno para que el LLM evalúe y reporte `delta_atraccion`.
- Ajustar el grafo de transiciones: `amigos_cercanos → pareja` (directo), condicionado por `atraccion >= umbral`.
- Actualizar documentación: `modelo_datos_v3.md`, `logica_interna.md`, `arquitectura_v3.md`.

## No incluido en este plan

- Cambios en persistencia JSON ni en repositorios (los campos nuevos se serializan igual que los existentes).
- Cambios en la interfaz TUI (pantallas).
- Migración de datos existentes (los personajes existentes tendrán `tipo_atraccion = None` y `estilo_apego = None` hasta que se editen).

---

## Sub-tarea 1 — Nuevos catálogos: TIPO_ATRACCION y ESTILO_APEGO

**Estado:** `[ ] pendiente`

### Intent

Crear los dos catálogos que dan vocabulario controlado a los nuevos campos del personaje. Usar el mismo patrón que MBTI/ENEAGRAMA/TEMPERAMENTO: archivo JSON en `data/catalogos/`, dataclass en `dominio/modelos.py`, carga en `dominio/configuracion.py`.

### Expected Outcomes

- `data/catalogos/tipos_atraccion.json` con 5 entradas.
- `data/catalogos/estilos_apego.json` con 4 entradas.
- Dataclasses `TipoAtraccion` y `EstiloApego` en `dominio/modelos.py`.
- Repositorio de catálogos carga los dos nuevos archivos.

### Todo List

1. Crear `data/catalogos/tipos_atraccion.json` con los 5 tipos:

   | codigo         | nombre           | descripcion                                                  |
   |----------------|------------------|--------------------------------------------------------------|
   | `intelectual`  | Intelectual      | Atracción por la mente, el debate, la curiosidad y la profundidad de ideas |
   | `emocional`    | Emocional        | Atracción por la vulnerabilidad compartida, la empatía y la conexión genuina |
   | `vital`        | Vital            | Atracción por la energía, el humor, la espontaneidad y la aventura |
   | `valoral`      | Valoral          | Atracción por los principios, la coherencia ética y la autenticidad |
   | `sensorial`    | Sensorial        | Atracción por la presencia, el cuidado físico y los gestos concretos |

2. Crear `data/catalogos/estilos_apego.json` con los 4 estilos (Bowlby/Ainsworth):

   | codigo          | nombre           | descripcion                                                              |
   |-----------------|------------------|--------------------------------------------------------------------------|
   | `seguro`        | Seguro           | Florecimiento por conexión genuina sin condiciones especiales; cómodo con cercanía e independencia |
   | `ansioso`       | Ansioso          | Necesita atención sostenida y consistencia para sentirse seguro; la ambigüedad activa el alejamiento |
   | `evitativo`     | Evitativo        | La atracción crece cuando se respeta el espacio; la presión o urgencia la bloquea |
   | `desorganizado` | Desorganizado    | Respuestas contradictorias; mezcla de atracción e incomodidad ante la cercanía |

3. Añadir dataclasses `TipoAtraccion` y `EstiloApego` en `dominio/modelos.py`, en el bloque de catálogos junto a `Mbti`, `Eneagrama`, `Temperamento`.

4. Añadir campos en la dataclass `ConfigCatalogos` (o equivalente en `dominio/configuracion.py`) para cargar los dos archivos nuevos.

5. En el repositorio de catálogos (`repositorios/json/entidades_json.py` o similar), añadir los métodos `obtener_tipos_atraccion()` y `obtener_estilos_apego()`.

### Relevant Context

- Patrón a replicar: `data/catalogos/temperamentos.json` + dataclass `Temperamento` en `dominio/modelos.py`.
- Carga de catálogos: ver cómo se cargan `temperamentos` en `dominio/configuracion.py` y `repositorios/json/entidades_json.py`.

---

## Sub-tarea 2 — Campos de atracción en PERSONAJE

**Estado:** `[ ] pendiente`

### Intent

Añadir tres campos opcionales a `PERSONAJE` que definen el perfil de atracción del personaje. Opcionales para mantener compatibilidad con personajes existentes.

### Expected Outcomes

- `Personaje` en `dominio/modelos.py` tiene tres campos nuevos: `tipo_atraccion_id`, `estilo_apego_id`, `matiz_atraccion`.
- Los tres campos son `Optional[str]`, con default `None`.
- El repositorio JSON serializa y deserializa los tres campos correctamente.
- `modelo_datos_v3.md` refleja los tres campos nuevos.

### Todo List

1. En `dominio/modelos.py`, añadir a la dataclass `Personaje`:
   ```
   tipo_atraccion_id:            Optional[str] = None   # FK -> TIPO_ATRACCION.codigo
   estilo_apego_id:              Optional[str] = None   # FK -> ESTILO_APEGO.codigo
   matiz_atraccion:              Optional[str] = None   # texto libre, 1-2 frases
   ```

2. Verificar que el repositorio JSON de personajes (`repositorios/json/entidades_json.py`) serializa campos `Optional` correctamente (los campos con `None` deben guardarse como `null` o simplemente omitirse y rellenarse como `None` al cargar).

3. Actualizar `modelo_datos_v3.md`: añadir los tres campos a la sección `PERSONAJE`.

### Relevant Context

- `dominio/modelos.py` línea 101 — dataclass `Personaje`.
- `temperamento_secundario_id: Optional[str] = None` es el patrón a seguir para campos opcionales de FK a catálogo.
- `instrucciones_llm: Optional[str] = None` en `Relacion` es el patrón para texto libre opcional.

---

## Sub-tarea 3 — Campo `atraccion` en RELACION

**Estado:** `[ ] pendiente`

### Intent

Añadir `atraccion` y `atraccion_delta` a `RELACION`, con el mismo patrón que `afecto`/`afecto_delta`. Representa el grado de interés romántico que el personaje siente por este usuario en esta relación concreta — independiente de la etapa.

### Expected Outcomes

- `Relacion` en `dominio/modelos.py` tiene `atraccion: float` y `atraccion_delta: float`.
- `DeltasRelacion` en `dominio/relacion.py` tiene un campo `atraccion: float = 0.0`.
- La función `aplicar_deltas_turno()` aplica el delta de atracción con cap y resistencia, igual que `afecto`.
- `modelo_datos_v3.md` refleja los dos campos nuevos.

### Todo List

1. En `dominio/modelos.py`, añadir a la dataclass `Relacion`:
   ```
   atraccion:       float = 0.0   # [0.0, 1.0] — interés romántico del personaje hacia este usuario
   atraccion_delta: float = 0.0   # [-1.0, 1.0] — tasa de cambio reciente (EMA)
   ```
   Colocarlos después de `disposicion_delta`, antes de `instrucciones_llm`.

2. En `dominio/relacion.py`, añadir `atraccion: float = 0.0` a `DeltasRelacion`.

3. En `aplicar_deltas_turno()`, añadir el cálculo de `atraccion` con el mismo mecanismo de cap y resistencia que `afecto` y `confianza`:
   ```
   nuevo_atraccion, cambio_atraccion = _aplicar_cambio(relacion.atraccion, deltas.atraccion, cap)
   ```
   Y actualizar el `replace(...)` final para incluir `atraccion` y `atraccion_delta`.

4. En `valores_iniciales.py` (o donde se inicialice una `Relacion` nueva), asegurarse de que `atraccion` arranca en `0.0`.

5. Actualizar `modelo_datos_v3.md`: añadir los dos campos a la sección `RELACION` con su descripción semántica.

### Relevant Context

- `dominio/modelos.py` líneas 122–136 — dataclass `Relacion`.
- `dominio/relacion.py` líneas 46–57 — `DeltasRelacion`; líneas 346–386 — `aplicar_deltas_turno()`.
- Patrón exacto a replicar: `afecto` / `afecto_delta` / `_aplicar_cambio` / `_actualizar_ema`.

---

## Sub-tarea 4 — Rediseño del grafo de etapas: eliminar `interes_romantico`

**Estado:** `[ ] pendiente`

### Intent

Eliminar `interes_romantico` del grafo lineal de etapas. La cadena pasa a ser:
`desconocidos → conocidos → amigos → amigos_cercanos → pareja`.

La transición a `pareja` requiere las condiciones actuales de `amigos_cercanos` más `atraccion >= umbral_atraccion_pareja` (nuevo parámetro en config). El campo `atraccion` es el guardián de la puerta, no la etapa.

### Expected Outcomes

- `data/catalogos/etapas_relacion.json` ya no tiene la entrada `interes_romantico`.
- `data/catalogos/transiciones_etapa.json` ya no tiene las aristas que pasan por `interes_romantico`.
- `data/catalogos/transiciones_etapa.json` tiene la nueva arista directa `amigos_cercanos → pareja`.
- `data/configuracion.json` tiene la nueva clave `transiciones_condiciones` actualizada: la entrada `amigos_cercanos → pareja` incluye `atraccion_min` además de los umbrales habituales.
- `CondicionTransicion` en `dominio/relacion.py` tiene el campo opcional `atraccion_min: Optional[float] = None`.
- `condicion_cumplida()` evalúa `atraccion_min` si está presente.
- La descripción de `_DESCRIPCIONES_ETAPA` en `gestor_turno.py` se actualiza: eliminada la entrada `interes_romantico`, actualizada la descripción de `pareja`.
- `modelo_datos_v3.md` y `logica_interna.md` reflejan el nuevo grafo.

### Todo List

1. En `data/catalogos/etapas_relacion.json`: eliminar la entrada `{"codigo": "interes_romantico", ...}`.

2. En `data/catalogos/transiciones_etapa.json`:
   - Eliminar las dos aristas que usan `interes_romantico` como origen o destino.
   - Añadir la arista `{"desde_id": "amigos_cercanos", "hasta_id": "pareja", "tipo": "avance"}`.
   - Añadir la arista `{"desde_id": "pareja", "hasta_id": "amigos_cercanos", "tipo": "retroceso"}` (si procede — ver decisión en punto 2b de notas).

3. En `data/configuracion.json`, sección `transiciones_condiciones`:
   - Eliminar las dos entradas de `interes_romantico`.
   - Añadir la entrada `amigos_cercanos → pareja` con los umbrales apropiados más `atraccion_min`.
   - Añadir un nuevo parámetro `atraccion_min_pareja` en la sección `relacion` de config para que sea configurable sin tocar las condiciones.

4. En `dominio/relacion.py`, añadir `atraccion_min: Optional[float] = None` a la dataclass `CondicionTransicion`.

5. En `condicion_cumplida()`, añadir la comprobación de `atraccion_min`:
   ```python
   if condicion.atraccion_min is not None and relacion.atraccion < condicion.atraccion_min:
       return False
   ```

6. En `dominio/configuracion.py`, añadir soporte para el campo `atraccion_min` en `ConfigTransicionCondicion`.

7. En `aplicacion/gestor_turno.py`, función `_es_momento_decisivo()`:
   - Eliminar la entrada `"interes_romantico"` de `_DESCRIPCIONES_ETAPA`.
   - Actualizar la descripción de `"pareja"` para reflejar que requiere atracción real.

8. Actualizar `modelo_datos_v3.md`: sección `ETAPA_RELACION` y `TRANSICION_ETAPA`.

9. Actualizar `logica_interna.md`: sección de transiciones de etapa, reflejar el nuevo grafo y la condición de `atraccion_min`.

### Relevant Context

- `data/catalogos/etapas_relacion.json` — archivo a modificar.
- `data/catalogos/transiciones_etapa.json` — archivo a modificar.
- `data/configuracion.json` líneas 66–74 — `transiciones_condiciones`.
- `dominio/relacion.py` líneas 130–161 — `CondicionTransicion` y `condicion_cumplida()`.
- `dominio/configuracion.py` — `ConfigTransicionCondicion`.
- `aplicacion/gestor_turno.py` líneas 748–759 — `_DESCRIPCIONES_ETAPA`.

---

## Sub-tarea 5 — El LLM evalúa y reporta `delta_atraccion`

**Estado:** `[ ] pendiente`

### Intent

Hacer que el LLM, en cada turno, evalúe si el comportamiento del usuario resonó con el perfil de atracción del personaje y reporte un `delta_atraccion`. Para ello necesita:
1. Recibir en el system prompt el perfil de atracción del personaje (`tipo_atraccion`, `estilo_apego`, `matiz_atraccion`).
2. Recibir el valor actual de `atraccion` de la relación (como parte del bloque de relación).
3. Incluir `atraccion` en el esquema JSON de respuesta esperado.

El `delta_atraccion` sigue las mismas reglas de cap y resistencia que `afecto`.

### Expected Outcomes

- `aplicacion/gestor_contexto.py` incluye en el bloque de identidad del personaje una sección "Perfil de atracción" cuando los campos no son `None`.
- El bloque de relación en el system prompt incluye el valor actual de `atraccion`.
- El esquema JSON de respuesta del LLM incluye el campo `atraccion` (delta).
- `aplicacion/gestor_turno.py` lee `delta_atraccion` de la respuesta y lo incluye en `DeltasRelacion`.
- `logica_interna.md` documenta la semántica de `delta_atraccion` para el LLM.

### Todo List

1. En `aplicacion/gestor_contexto.py`, en la función que construye el bloque de identidad del personaje (cerca de donde se muestran MBTI, eneagrama, temperamento): añadir una sección "Perfil de atracción" que muestre:
   - `Tipo de atracción: <nombre del tipo>` (si `tipo_atraccion_id` no es `None`).
   - `Estilo de apego: <nombre del estilo>` (si `estilo_apego_id` no es `None`).
   - `Matiz: <texto>` (si `matiz_atraccion` no es `None`).
   Esta sección solo aparece si al menos uno de los tres campos está definido.

2. En el bloque de relación del system prompt, añadir `atraccion` al listado de métricas (junto a `confianza`, `afecto`, `familiaridad`, `tension`, `disposicion`).

3. En la instrucción de formato de respuesta (la parte del system prompt que define el JSON esperado), añadir el campo `atraccion` como delta opcional:
   - Rango: `-0.3` a `+0.3` (igual que `afecto`).
   - Semántica: cuánto resonó este turno con el perfil de atracción del personaje.
   - Valor `0.0` si el turno fue neutral respecto a la atracción.

4. En `aplicacion/gestor_turno.py`, en el paso que construye `DeltasRelacion` a partir de la respuesta del LLM: leer el campo `atraccion` (con fallback a `0.0` si no viene) e incluirlo en `DeltasRelacion`.

5. En `logica_interna.md`, añadir una sección "Atracción romántica" que documente:
   - Qué es `atraccion` en `RELACION` (semántica, rango).
   - Qué es `delta_atraccion` para el LLM (cómo debe usarlo, magnitudes de referencia).
   - Cómo se usan `tipo_atraccion`, `estilo_apego` y `matiz_atraccion` en el razonamiento del LLM.
   - La condición de `atraccion_min` en la transición a `pareja`.

### Relevant Context

- `aplicacion/gestor_contexto.py` — función `construir_sistema()` o equivalente; buscar el bloque donde se pone MBTI/eneagrama.
- Bloque de relación actual en el system prompt: incluye `confianza`, `afecto`, `familiaridad`, `tension`, `interes_ahora`.
- Instrucción de formato de respuesta: buscar en `gestor_contexto.py` el JSON schema que se le pide al LLM.
- `aplicacion/gestor_turno.py` — el paso donde se lee la respuesta del LLM y se construye `DeltasRelacion`.

---

## Sub-tarea 6 — Eliminar el modo `impulso` para la transición a `pareja`

**Estado:** `[ ] pendiente`

### Intent

La transición `amigos_cercanos → pareja` (que absorbe la anterior `→ interes_romantico`) nunca debe ocurrir por impulso automático. Debe requerir siempre un momento decisivo explícito en la conversación.

Esta es la corrección del "punto 1" del análisis original: stats altos solos no bastan para que alguien decida ser pareja de otra persona.

### Expected Outcomes

- Existe en `data/configuracion.json` una lista `transiciones_solo_permiso` con los identificadores de transiciones que no pueden activarse por impulso.
- `buscar_transicion_elegible()` o `evaluar_transicion()` en `dominio/relacion.py` respeta esa lista: si la transición está en `transiciones_solo_permiso`, fuerza `modo = "permiso"` aunque los umbrales se superen con margen.
- La transición `amigos_cercanos → pareja` está en esa lista.
- `logica_interna.md` documenta este mecanismo.

### Todo List

1. En `data/configuracion.json`, añadir la clave:
   ```json
   "transiciones_solo_permiso": [
     {"desde_id": "amigos_cercanos", "hasta_id": "pareja"}
   ]
   ```

2. En `dominio/configuracion.py`, añadir la lectura de `transiciones_solo_permiso` como lista de tuplas `(desde_id, hasta_id)`.

3. En `dominio/relacion.py`, modificar `evaluar_transicion()` para que, si la transición está en la lista de solo-permiso, nunca devuelva `"impulso"` — siempre `"permiso"` cuando las condiciones se cumplen.

4. En `logica_interna.md`, sección de transiciones: documentar el mecanismo `transiciones_solo_permiso` y por qué `amigos_cercanos → pareja` está en esa lista.

### Relevant Context

- `dominio/relacion.py` líneas 168–191 — `evaluar_transicion()`.
- `data/configuracion.json` línea 66 — sección `transiciones_condiciones` (añadir la nueva clave al mismo nivel).
- `dominio/configuracion.py` — donde se lee `transiciones_condiciones`; añadir lectura análoga para la nueva clave.

---

## Sub-tarea 7 — Actualizar documentación completa

**Estado:** `[ ] pendiente`

### Intent

Dejar `modelo_datos_v3.md`, `logica_interna.md` y `arquitectura_v3.md` completamente al día con todos los cambios de las sub-tareas 1–6. Cada sub-tarea menciona cambios parciales de documentación; esta sub-tarea hace la revisión final y añade lo que falta.

### Expected Outcomes

- `modelo_datos_v3.md`: secciones `PERSONAJE`, `RELACION`, `ETAPA_RELACION`, `TRANSICION_ETAPA` actualizadas; nuevas secciones `TIPO_ATRACCION` y `ESTILO_APEGO`.
- `logica_interna.md`: nueva sección "Atracción romántica" completa; sección de transiciones actualizada con el nuevo grafo y `transiciones_solo_permiso`.
- `arquitectura_v3.md`: si hay alguna referencia a `interes_romantico` como etapa, actualizarla.
- `AGENTS.md`: si hay reglas relacionadas con etapas que mencionan `interes_romantico`, actualizarlas.

### Todo List

1. Revisar `modelo_datos_v3.md` en busca de referencias a `interes_romantico` y actualizarlas.
2. Revisar `logica_interna.md` — completar la sección "Atracción romántica" si la sub-tarea 5 la dejó incompleta.
3. Revisar `arquitectura_v3.md` — buscar referencias a `interes_romantico` o al grafo de etapas.
4. Revisar `AGENTS.md` — buscar reglas que mencionen `interes_romantico` o el flujo de transiciones.

### Relevant Context

- Archivos a revisar: `documentacion/modelo_datos_v3.md`, `documentacion/logica_interna.md`, `documentacion/arquitectura_v3.md`, `AGENTS.md`.

---

## Notas de diseño abiertas

### Nota A — Retroceso desde `pareja`

Con el nuevo grafo, cuando una relación de `pareja` se deteriora, ¿va a `amigos_cercanos` directamente?  
La arista de retroceso `pareja → distanciamiento` ya existe. El `distanciamiento` sigue siendo la salida natural de una ruptura de pareja. No es necesario cambiar esto.

Sin embargo: si `atraccion` baja mucho mientras siguen siendo pareja, ¿se fuerza retroceso automático? Por ahora **no** — `atraccion` es condición de entrada a `pareja`, no condición de permanencia. Si en el futuro se quiere añadir esa lógica, sería un nuevo mecanismo de "presión de retroceso" que está fuera del alcance de este plan.

### Nota B — Personajes sin perfil de atracción

Si `tipo_atraccion_id` y `estilo_apego_id` son `None`, el LLM no recibe ninguna guía de atracción. En ese caso `delta_atraccion` debería ser siempre `0.0`. La instrucción al LLM debe ser explícita: "Si no hay perfil de atracción definido, devuelve `atraccion: 0.0`".

Esto implica que personajes creados antes de este cambio nunca desarrollarán atracción hasta que se editen sus campos — comportamiento correcto y esperado.

### Nota C — `atraccion` como señal narrativa para el LLM

El valor de `atraccion` en el bloque de relación que recibe el LLM también actúa como señal sobre cómo debe comportarse el personaje. Un `atraccion` alto justifica nerviosismo, detalles especiales, lenguaje más cercano — incluso si la etapa formal es solo `amigos_cercanos`. Esto es precisamente la ganancia de la opción B de la decisión 2: el estado emocional es más rico y el LLM puede reflejarlo.
