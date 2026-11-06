# Plan: Tensión bidireccional (el LLM puede subirla y bajarla)

## Resumen

Actualmente el campo `tension` que devuelve el LLM es unidireccional: solo acepta valores
`>= 0.0` y los valores negativos se descartan silenciosamente en `_extraer_tension()`.
Esto significa que el único canal directo para bajar la tensión está bloqueado por diseño.

El objetivo es hacer la tensión **bidireccional**: el LLM puede reportar un valor negativo
para indicar que el turno fue relajante/conciliador, y ese valor se aplica igual que los
positivos. El resto de la lógica (decaimiento temporal, reducción por afecto) no cambia.

---

## Sub-tareas

---

### Sub-tarea 1 — Actualizar el prompt del sistema

**Intent**
El LLM actualmente recibe instrucciones explícitas de que `tension` es `SOLO positivo o 0.0`
y que para indicar bajada debe usar `0.0`. Hay que cambiar esas instrucciones para que el
LLM entienda que puede reportar valores negativos cuando el turno fue positivo/relajante.

**Expected Outcomes**
- El comentario `(float 0.0–1.0)` pasa a `(float -1.0–1.0)`.
- La guía que dice "NUNCA va en negativo" se reemplaza por ejemplos bidireccionales.
- La frase sobre "el sistema la gestiona aparte" desaparece (ya no es responsabilidad solo del sistema).

**Todo List**
1. En [`aplicacion/gestor_contexto.py`](aplicacion/gestor_contexto.py:226), cambiar la línea de descripción de `tension` de `(float 0.0–1.0)` a `(float -1.0–1.0)`.
2. Reemplazar el bloque de guía de tensión (líneas 234–240) con un bloque bidireccional que explique:
   - Valores positivos: fricción/incomodidad generada en el turno.
   - Valores negativos: turno relajante, conciliador, que disuelve tensión existente.
   - Valor 0.0: turno neutro, sin efecto en la tensión.
   - Mismos ejemplos de magnitud pero en ambas direcciones (ej. conversación amigable → -0.05 a -0.10).

**Relevant Context**
- Archivo: [`aplicacion/gestor_contexto.py`](aplicacion/gestor_contexto.py)
- Líneas a modificar: 226 y 234–240

**Status**
[x] done

---

### Sub-tarea 2 — Hacer bidireccional la extracción en `gestor_turno.py`

**Intent**
La función `_extraer_tension()` (línea 316) aplica `max(0.0, ...)` que descarta valores
negativos. Hay que cambiarla para que acepte el rango completo `[-1.0, 1.0]`, igual que
`_extraer_delta()` que ya lo hace para afecto y confianza.

**Expected Outcomes**
- `_extraer_tension()` acepta y devuelve valores negativos en `[-1.0, 0.0]`.
- Los comentarios internos de la función reflejan el nuevo comportamiento.
- El campo `tension` en `DeltasRelacion` puede tener valor negativo.

**Todo List**
1. En [`aplicacion/gestor_turno.py`](aplicacion/gestor_turno.py:316), cambiar `_extraer_tension()`:
   - Reemplazar `max(0.0, min(1.0, float(v)))` por `max(-1.0, min(1.0, float(v)))`.
   - Actualizar el comentario de la función para reflejar el rango `[-1.0, 1.0]`.

**Relevant Context**
- Archivo: [`aplicacion/gestor_turno.py`](aplicacion/gestor_turno.py:316)

**Status**
[x] done

---

### Sub-tarea 3 — Proteger la gestión de conflictos contra valores negativos

**Intent**
La lógica de `_gestionar_conflictos()` usa `tension_delta` para decidir si crear o escalar
conflictos (líneas 619 y 633). Si ahora `tension_delta` puede ser negativo, los umbrales
`umbral_tension_crear` y `umbral_tension_escalar` seguirán funcionando correctamente
**solo si se comparan contra el valor ya con signo** — un turno relajante (`tension_delta < 0`)
nunca superará esos umbrales positivos, así que no hay nada que cambiar en la lógica.

Sin embargo, hay dos lugares donde `tension_delta` se usa como `impacto` de un evento de
conflicto con signo negativo (`impacto=-tension_delta`, líneas 596 y 643). Si `tension_delta`
es negativo, `-tension_delta` sería positivo — el evento de conflicto tendría impacto
positivo, lo cual no tiene sentido semántico.

**Expected Outcomes**
- El `impacto` del evento de conflicto siempre es `<= 0` (los conflictos son negativos).
- Un `tension_delta` negativo (turno relajante) nunca genera conflicto (ya es así por los umbrales).

**Todo List**
1. En [`aplicacion/gestor_turno.py`](aplicacion/gestor_turno.py:596), cambiar `impacto=-tension_delta` por `impacto=-abs(tension_delta)` en la creación del evento de conflicto por LLM.
2. En la línea 643, hacer lo mismo: `impacto=-abs(tension_delta)` en la creación del evento de conflicto automático.

**Relevant Context**
- Archivo: [`aplicacion/gestor_turno.py`](aplicacion/gestor_turno.py)
- Líneas 596 y 643

**Status**
[x] done

---

### Sub-tarea 4 — Ajustar el widget de diagnóstico para tensión negativa

**Intent**
En [`interfaz/widgets/burbuja_diagnostico.py`](interfaz/widgets/burbuja_diagnostico.py:159),
la línea de tensión usa el prefijo `+` fijo (`f"  tensión:   +{d.delta_tension:.2f}"`).
Si `delta_tension` ahora puede ser negativo, el prefijo `+` fijo quedaría como `+-0.05`,
que es incorrecto. También la condición de color (línea 160) solo marca como negativo
cuando `>= 0.05` — hay que añadir el caso negativo para colorear bajadas de tensión
de forma diferente (bajada = buena noticia visualmente).

**Expected Outcomes**
- El formato usa `{d.delta_tension:+.2f}` (el signo lo pone Python automáticamente).
- La condición de clase CSS distingue subidas (`>= 0.05`), bajadas (`<= -0.05`) y neutro.

**Todo List**
1. En [`interfaz/widgets/burbuja_diagnostico.py`](interfaz/widgets/burbuja_diagnostico.py:159), cambiar el string de format para tensión de `+{d.delta_tension:.2f}` a `{d.delta_tension:+.2f}`.
2. Revisar la condición de la clase CSS en línea 160 y añadir el caso de bajada significativa.

**Relevant Context**
- Archivo: [`interfaz/widgets/burbuja_diagnostico.py`](interfaz/widgets/burbuja_diagnostico.py)
- Líneas 159–160

**Status**
[x] done

---

### Sub-tarea 5 — Eliminar `reduccion_por_afecto` de la tensión

**Intent**
Con la tensión bidireccional, el mecanismo secundario de reducción proporcional al afecto
(`reduccion_por_afecto`) es redundante: el LLM ya gestiona directamente cuánto baja la
tensión. Mantenerlo añadiría un efecto oculto que distorsiona lo que el LLM decide, y
haría más difícil calibrar el sistema.

Hay que eliminarlo en tres lugares: la fórmula en `dominio/relacion.py`, el parámetro
en `dominio/configuracion.py`, y el valor en `data/configuracion.json`.

**Expected Outcomes**
- `aplicar_deltas_turno()` aplica `nuevo_tension = _recortar(relacion.tension + deltas.tension)` sin el término `reduccion_por_afecto`.
- El campo `cambio_afecto` ya no se necesita en ese bloque (pero sigue existiendo para actualizar `afecto_delta`).
- `ConfigRelacion` ya no tiene el campo `tension_reduccion_por_afecto`.
- `data/configuracion.json` ya no tiene la clave `tension_reduccion_por_afecto`.
- El docstring de `aplicar_deltas_turno()` se actualiza para no mencionar la reducción.

**Todo List**
1. En [`dominio/relacion.py`](dominio/relacion.py:382), eliminar el bloque de `reduccion_por_afecto` y simplificar la línea a `nuevo_tension = _recortar(relacion.tension + deltas.tension)`. Actualizar el docstring.
2. En [`dominio/configuracion.py`](dominio/configuracion.py:96), eliminar el campo `tension_reduccion_por_afecto` del dataclass `ConfigRelacion`.
3. En [`data/configuracion.json`](data/configuracion.json:49), eliminar la clave `"tension_reduccion_por_afecto"`.

**Relevant Context**
- [`dominio/relacion.py`](dominio/relacion.py:382) — líneas 382–386 y docstring 371–374
- [`dominio/configuracion.py`](dominio/configuracion.py:96) — línea 96
- [`data/configuracion.json`](data/configuracion.json:49) — línea 49

**Status**
[x] done

---

## Notas adicionales

- **El decaimiento temporal no cambia**: `decaer_tension()` opera sobre el valor almacenado,
  no sobre los deltas.
- **El campo `tension` en `DeltasRelacion`** es un `float` sin restricción en el dataclass —
  no hay que cambiar la definición de dominio.
- **`impacto_neto`** en la línea 339 ya resta la tensión: `(afecto + confianza - tension) / 3.0`.
  Con tensión negativa (bajada), `-tension` será positivo, lo que contribuye positivamente al
  `impacto_neto`. Esto es correcto: un turno relajante mejora el impacto neto del evento.
