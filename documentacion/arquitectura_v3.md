# Arquitectura del sistema — v3

---

## Principio guía: capas intercambiables

El sistema se divide en **cuatro capas verticales** con interfaces contractuales entre sí. La Fase 1 y la Fase 2 comparten exactamente las mismas capas y contratos; lo que cambia es la tecnología interna de cada capa, no su interfaz hacia afuera.

```
┌─────────────────────────────────────────┐
│           CAPA DE INTERFAZ              │  Fase 1: Textual (TUI)
│         (presentación / UI)             │  Fase 2: TUI ampliada o GUI web
├─────────────────────────────────────────┤
│         CAPA DE APLICACIÓN              │  Igual en ambas fases
│   (orquestación, casos de uso, LLM)     │
├─────────────────────────────────────────┤
│         CAPA DE DOMINIO                 │  Igual en ambas fases
│  (lógica pura: emociones, relaciones,   │
│   transiciones, confianza)              │
├─────────────────────────────────────────┤
│       CAPA DE REPOSITORIO               │  Fase 1: JSON en disco
│   (persistencia — interfaz abstracta)   │  Fase 2: SQLite / PostgreSQL
└─────────────────────────────────────────┘
```

La migración de Fase 1 a Fase 2 consiste en **reemplazar únicamente la capa de repositorio** (y opcionalmente ampliar la interfaz). Las capas de dominio y aplicación no se tocan.

---

## Las cuatro capas en detalle

### 1. Capa de dominio

Contiene la lógica pura del sistema. No importa nada de persistencia ni de interfaz.

**Módulos:**

- `dominio/modelos.py` — dataclasses que reflejan las entidades del modelo de datos v3:
  `Personaje`, `Usuario`, `Relacion`, `Estado`, `Mensaje`, `Evento`, `Conflicto`,
  `Recuerdo`, `PerfilUsuario`, `EtapaRelacion`, `TransicionEtapa`, `Emocion`.

- `dominio/emociones.py` — lógica del espacio de Russell:
  - Calcular `estado_compuesto` (suma ponderada de las tres capas con pesos 0.50/0.35/0.15).
  - Detectar `emocion_actual` por distancia euclidiana al catálogo.
  - Aplicar decaimiento de intensidad por capa.

- `dominio/relacion.py` — lógica de la relación:
  - Evaluar condiciones de transición (`TRANSICION_ETAPA`).
  - Determinar si una transición es por permiso o por impulso automático.
  - Actualizar `confianza`, `afecto`, `familiaridad`, `tension` tras un evento.

- `dominio/confianza.py` — cálculo de `confianza_final` en `PERFIL_USUARIO`:
  - Aplicar factores de origen (`usuario_explicito` → 1.0, `sistema` → 1.0, `llm` → 0.7).
  - Resolver duplicados por clave.

**Regla:** esta capa no conoce JSON, SQL, ni Textual. Solo opera con dataclasses y devuelve dataclasses.

---

### 2. Capa de repositorio

Abstrae todo acceso a datos detrás de interfaces (clases abstractas o protocolos de Python). La capa de aplicación solo habla con estas interfaces — nunca con JSON ni con SQL directamente.

**Interfaz base (ejemplo):**

```python
class RepositorioRelacion(Protocol):
    def obtener(self, num: int) -> Relacion: ...
    def guardar(self, relacion: Relacion) -> None: ...
    def listar_por_personaje(self, personaje_id: int) -> list[Relacion]: ...
```

**Implementación Fase 1 — JSON:**
- `repositorios/json/relacion_json.py` — lee y escribe `data/relaciones.json`.
- Un archivo JSON por entidad principal: `personajes.json`, `relaciones.json`, `mensajes.json`, `estados.json`, etc.
- La estructura interna del JSON refleja directamente los campos del modelo de datos v3.

**Implementación Fase 2 — Base de datos:**
- `repositorios/db/relacion_db.py` — misma interfaz, implementación con ORM o SQL crudo.
- Mismos métodos, mismos contratos. La capa de aplicación no cambia.

**Ficheros de datos (Fase 1):**

```
data/
├── catalogos/
│   ├── emociones.json
│   ├── etapas_relacion.json
│   ├── transiciones_etapa.json
│   ├── tipos_evento.json
│   ├── mbti.json
│   ├── eneagrama.json
│   └── temperamento.json
├── personajes.json
├── usuarios.json
├── relaciones.json
├── estados.json
├── mensajes.json
├── eventos.json
├── conflictos.json
├── recuerdos.json
└── perfil_usuario.json
```

Los catálogos se cargan una vez al arranque y se mantienen en memoria. Los demás ficheros se leen y escriben por operación.

---

### 3. Capa de aplicación

Orquesta los casos de uso del sistema. Recibe input de la interfaz, coordina dominio y repositorio, y devuelve el resultado.

**Módulos:**

- `aplicacion/gestor_turno.py` — caso de uso principal: procesar un turno de conversación.
  1. Recibir mensaje del usuario.
  2. Guardar `MENSAJE` (rol: "usuario").
  3. Llamar al LLM con el contexto construido → obtener respuesta en lenguaje natural.
  4. Guardar `MENSAJE` (rol: "personaje").
  5. Actualizar `ESTADO` (aplicar decaimiento, calcular nuevo estado emocional).
  6. Extraer `RECUERDO` y actualizar `PERFIL_USUARIO` si corresponde.
  7. Evaluar si hay transición de etapa.
  8. Persistir todos los cambios.

- `aplicacion/gestor_contexto.py` — construye el contexto que recibe el LLM:
  - Psicología del personaje (MBTI + Eneagrama + Temperamento).
  - Estado emocional actual (nombre de emoción, sin vectores).
  - Etapa de relación actual.
  - Recuerdos relevantes (por importancia; en Fase 2 también por similitud semántica).
  - Últimos N mensajes.
  - Perfil del usuario (datos de alta confianza).

- `aplicacion/cliente_llm.py` — interfaz hacia el modelo de lenguaje:
  - Abstrae el proveedor (OpenAI, Ollama, etc.).
  - Recibe el contexto estructurado, devuelve texto.
  - Aplica el factor `× 0.7` a `confianza_llm` en las extracciones de `PERFIL_USUARIO`.

**Regla:** esta capa no importa nada de Textual ni de JSON/SQL. Solo importa dominio y repositorios (a través de sus interfaces).

---

### 4. Capa de interfaz

Construida con **Textual** en ambas fases. En Fase 1 es mínima; en Fase 2 se puede ampliar con pantallas adicionales, sin tocar las capas inferiores.

**Estructura Fase 1 (TUI mínima):**

```
interfaz/
├── app.py            — App principal de Textual
├── pantallas/
│   ├── chat.py       — Pantalla principal: historial de mensajes + input
│   └── estado.py     — Panel lateral: etapa actual, estado emocional, métricas de relación
└── widgets/
    ├── burbuja.py    — Widget de mensaje (usuario vs. personaje)
    └── indicador.py  — Indicador visual de estado emocional
```

**Pantalla de chat (Fase 1):**
- Panel izquierdo: historial de conversación con burbujas diferenciadas por rol.
- Panel derecho (colapsable): estado emocional del personaje, etapa de relación, valores de `confianza`, `afecto`, `familiaridad`, `tension`.
- Input inferior: campo de texto para el mensaje del usuario.

**Regla:** la interfaz solo llama a la capa de aplicación. Nunca accede a dominio ni a repositorios directamente.

---

## Estructura de directorios del proyecto

```
novia_AI/
├── documentacion/
│   ├── modelo_datos_v3.md
│   ├── modelo_datos_decisiones_v3.md
│   ├── logica_interna.md
│   └── arquitectura_v3.md         ← este archivo
├── dominio/
│   ├── modelos.py
│   ├── emociones.py
│   ├── relacion.py
│   └── confianza.py
├── repositorios/
│   ├── interfaces.py               ← clases abstractas / Protocols
│   └── json/
│       ├── personaje_json.py
│       ├── relacion_json.py
│       ├── estado_json.py
│       ├── mensaje_json.py
│       └── ...
├── aplicacion/
│   ├── gestor_turno.py
│   ├── gestor_contexto.py
│   └── cliente_llm.py
├── interfaz/
│   ├── app.py
│   ├── pantallas/
│   │   ├── chat.py
│   │   └── estado.py
│   └── widgets/
│       ├── burbuja.py
│       └── indicador.py
├── data/
│   ├── catalogos/
│   └── ...
├── requirements.txt
└── .venv/
```

---

## Flujo de un turno de conversación

```
Usuario escribe mensaje
        │
        ▼
  interfaz/app.py
        │  llama a
        ▼
  aplicacion/gestor_turno.py
        │
        ├─► repositorios: guardar MENSAJE (usuario)
        │
        ├─► gestor_contexto.py
        │       │
        │       ├─► repositorios: leer ESTADO, RELACION, RECUERDOS, PERFIL_USUARIO
        │       └─► dominio/emociones.py: calcular emocion_actual
        │
        ├─► cliente_llm.py → LLM → respuesta en texto
        │
        ├─► repositorios: guardar MENSAJE (personaje)
        │
        ├─► dominio/emociones.py: aplicar decaimiento + calcular nuevo ESTADO
        │
        ├─► repositorios: actualizar ESTADO
        │
        ├─► dominio/relacion.py: evaluar transición de etapa
        │
        └─► repositorios: persistir cambios
        │
        ▼
  interfaz: mostrar respuesta + actualizar panel de estado
```

---

## Cambios al pasar de Fase 1 a Fase 2

| Componente | Fase 1 | Fase 2 | Cambio requerido |
|---|---|---|---|
| Repositorios | JSON en disco | SQLite / PostgreSQL | Nuevas implementaciones en `repositorios/db/` |
| Inyección de dependencias | Manual en `app.py` | Manual o con contenedor | Cambiar qué implementación se inyecta |
| Búsqueda de recuerdos | Por importancia | Semántica (embeddings) | Añadir lógica en `gestor_contexto.py` |
| Campo `embedding` en RECUERDO | NULL | Poblado | Activar en `gestor_turno.py` |
| Interfaz | TUI mínima | TUI ampliada (o GUI) | Añadir pantallas sin tocar capas inferiores |
| Dominio | Sin cambios | Sin cambios | — |
| Aplicación | Sin cambios (salvo embeddings) | Sin cambios | — |

**La capa de dominio no se toca en la transición.**

---

## Decisiones de implementación pendientes

Las siguientes áreas de la lógica interna aún no tienen fórmulas definidas y **no deben implementarse hasta tener consenso** (ver `logica_interna.md`):

- Tasas de decaimiento concretas por capa emocional (lineal vs. exponencial).
- Cómo los eventos modifican la intensidad de cada capa.
- Fórmulas de actualización de `confianza`, `afecto`, `familiaridad`, `tension` en RELACION.
- Decaimiento y reactivación de `importancia` en RECUERDO.
- Estrategia de prompting para extracción de recuerdos e inferencia de PERFIL_USUARIO.
