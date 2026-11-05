# Plan: Similitud Semántica para Recuperación de Recuerdos

**Fecha:** 2026-11-03  
**Estado:** pendiente de implementación

---

## Contexto actual

Los recuerdos se pasan al LLM **filtrados solo por `importancia >= 0.4` y cortados a los primeros 5** (orden de inserción). La deduplicación usa **Jaccard de tokens**, que es léxica, no semántica. El campo `Recuerdo.embedding` existe pero es `None` — está reservado exactamente para esto.

---

## Problema que resuelve

Con solo importancia + orden de inserción, el LLM recibe los 5 recuerdos *más antiguos relevantes*, no los más pertinentes al mensaje actual. Si el usuario dice "¿te acuerdas de cuando te hablé de mi trabajo?", el sistema no puede recuperar ese recuerdo específico entre 50 — simplemente los trunca.

Con similitud semántica, el sistema selecciona los recuerdos **conceptualmente más cercanos al mensaje del usuario** antes de pasarlos al LLM.

---

## Modelo de embedding

**`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`**

- Multilingüe (español nativo)
- 384 dimensiones — compacto, < 120 MB
- Corre 100% local, sin API externa, sin costo por llamada
- Velocidad: ~5 ms por texto en CPU
- Librería: `sentence-transformers` (wrappea PyTorch)

---

## Arquitectura

```
Mensaje usuario
       │
       ▼
ServicioEmbedding  (dominio/embedding.py)
       │  vector 384-dim
       ▼
seleccionar_recuerdos_relevantes  (dominio/recuerdos.py)
       │  consulta Recuerdo.embedding en JSON
       │  Top-K por coseno + filtro importancia
       ▼
gestor_contexto.py → construir_sistema()


Al guardar recuerdo nuevo (gestor_turno.py paso 9b):
  contenido → ServicioEmbedding → embedding → Recuerdo.embedding → JSON
```

---

## Fórmula de ranking

```
score_final = peso_semantico × similitud_coseno(mensaje, recuerdo)
            + (1 − peso_semantico) × recuerdo.importancia
```

Con `peso_semantico = 0.6` (configurable en `configuracion.json`):
- 60 % relevancia semántica al mensaje actual
- 40 % importancia intrínseca del recuerdo
- Recuerdos sin embedding (`null`) contribuyen 0.0 en la parte semántica → degradación graceful

---

## Archivos afectados

| Archivo | Cambio | Tipo |
|---|---|---|
| `dominio/embedding.py` | `ServicioEmbedding` — carga el modelo lazy, `codificar(texto) → list[float]`, `similitud_coseno(a, b) → float` | **nuevo** |
| `dominio/recuerdos.py` | `seleccionar_recuerdos_relevantes(mensaje, recuerdos, servicio, k)` — mezcla similitud semántica + importancia | **nuevo** |
| `dominio/configuracion.py` | nueva dataclass `ConfigEmbedding`, añadida a `Configuracion` | modificar |
| `data/configuracion.json` | nuevo bloque `"embedding"` con `modelo`, `top_k_semantico`, `peso_semantico` | modificar |
| `repositorios/json/operaciones_json.py` | serializar/deserializar `embedding` como lista de floats en JSON (ahora se ignora) | modificar |
| `aplicacion/gestor_turno.py` paso 5 | llamar a `seleccionar_recuerdos_relevantes` en lugar del filtro plano | modificar |
| `aplicacion/gestor_turno.py` paso 9b | calcular embedding antes de persistir cada recuerdo nuevo | modificar |
| `scripts/recalcular_embeddings.py` | script opcional para poblar `embedding` en recuerdos ya guardados | **nuevo** (opcional) |

---

## Configuración (bloque a añadir en `data/configuracion.json`)

```json
"embedding": {
  "modelo": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
  "top_k_semantico": 5,
  "peso_semantico": 0.6
}
```

---

## Detalles de implementación

### `ServicioEmbedding` (dominio/embedding.py)

```python
class ServicioEmbedding:
    def __init__(self, nombre_modelo: str) -> None:
        self._nombre_modelo = nombre_modelo
        self._modelo = None  # lazy load

    def _cargar(self):
        if self._modelo is None:
            from sentence_transformers import SentenceTransformer
            self._modelo = SentenceTransformer(self._nombre_modelo)

    def codificar(self, texto: str) -> list[float]:
        self._cargar()
        return self._modelo.encode(texto).tolist()

    def similitud_coseno(self, a: list[float], b: list[float]) -> float:
        # producto punto normalizado
        ...
```

### `seleccionar_recuerdos_relevantes` (dominio/recuerdos.py)

```python
def seleccionar_recuerdos_relevantes(
    mensaje: str,
    recuerdos: list[Recuerdo],
    servicio: ServicioEmbedding,
    k: int,
    peso_semantico: float,
) -> list[Recuerdo]:
    embedding_msg = servicio.codificar(mensaje)
    scored = []
    for r in recuerdos:
        if r.embedding is not None:
            sim = servicio.similitud_coseno(embedding_msg, r.embedding)
        else:
            sim = 0.0
        score = peso_semantico * sim + (1 - peso_semantico) * r.importancia
        scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:k]]
```

---

## Migración de recuerdos existentes

Los recuerdos ya guardados tienen `embedding: null`.  
Se tratarán con score semántico = 0.0 → **funcionan igual que antes** hasta que se recalculen.

**Script opcional:** `scripts/recalcular_embeddings.py`  
Lee todos los recuerdos sin embedding de un `relacion_id`, calcula el vector y lo persiste.  
No es bloqueante para el MVP.

---

## Decisiones de diseño

1. **Sin base de datos vectorial (FAISS/Chroma)** — con ~500 recuerdos por relación, una búsqueda coseno en Python pura tarda < 2 ms. No necesitamos infraestructura extra.

2. **Modelo local** — sin dependencias de API externa. El modelo se descarga una vez y queda cacheado en `~/.cache/huggingface`.

3. **Lazy loading** — el modelo no se carga al importar el módulo, solo cuando se llama a `codificar()` por primera vez. El arranque de la app no se penaliza.

4. **Sin romper recuerdos existentes** — `embedding: null` sigue funcionando con degradación graceful.

5. **Instancia única del servicio** — el `ServicioEmbedding` se instancia una vez en la factoría o en `main.py` y se pasa al `GestorTurno` por inyección de dependencias, para no recargar el modelo en cada turno.

---

## Orden de implementación

```
[ ] Instalar sentence-transformers (pip install sentence-transformers)
[ ] dominio/embedding.py — ServicioEmbedding
[ ] data/configuracion.json + dominio/configuracion.py — bloque embedding
[ ] repositorios/json/operaciones_json.py — serialización de embedding
[ ] dominio/recuerdos.py — seleccionar_recuerdos_relevantes
[ ] aplicacion/gestor_turno.py — integrar en paso 5 y paso 9b
[ ] (opcional) scripts/recalcular_embeddings.py
```
