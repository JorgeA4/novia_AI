# Arquitectura del sistema — v3

---

## Capas

```
┌─────────────────────────────────────────┐
│           CAPA DE INTERFAZ              │  Fase 1: TUI (Textual)
├─────────────────────────────────────────┤
│         CAPA DE APLICACIÓN              │  Orquestación, casos de uso, LLM
├─────────────────────────────────────────┤
│         CAPA DE DOMINIO                 │  Lógica pura: emociones, relaciones,
│                                         │  transiciones, confianza
├─────────────────────────────────────────┤
│       CAPA DE REPOSITORIO               │  Fase 1: JSON en disco
│                                         │  Fase 2: SQLite / PostgreSQL
└─────────────────────────────────────────┘
```

La migración de Fase 1 a Fase 2 consiste en reemplazar únicamente la capa de repositorio (y opcionalmente ampliar la interfaz). Las capas de dominio y aplicación no se tocan.

---

## Capa de dominio (`dominio/`)

Lógica pura. No importa nada de persistencia ni de interfaz.

- `modelos.py` — dataclasses de las entidades del modelo de datos v3. Incluye `calcular_vigencia()`.
- `emociones.py` — espacio de Russell: cálculo de vector compuesto, detección por distancia euclidiana, decaimiento exponencial, Brechas 1/2/3 (presión de emoción sobre estado_animo, modulación por sentimiento, deriva del sentimiento en reposo).
- `relacion.py` — transiciones de etapa (`CondicionTransicion`, `buscar_transicion_elegible`), actualización de métricas con cap y resistencia en extremos, cálculo de `interes_actual`.
- `recuerdos.py` — pipeline de recuperación de recuerdos: filtro de vigencia, filtro por historial, decaimiento de `relevancia_activa`, filtro semántico por similitud coseno, ranking por señales intrínsecas, boost de recuperación.
- `embedding.py` — `ServicioEmbedding` (carga lazy del modelo sentence-transformers, `codificar`, `codificar_multiples`, `similitud_coseno`), `dividir_en_fragmentos`.
- `confianza.py` — `confianza_final = confianza_llm × factor_origen`, resolución de duplicados en PERFIL_USUARIO.
- `configuracion.py` — carga `data/configuracion.json` al arranque como singleton. Todos los parámetros numéricos del sistema se leen de ahí, incluidas las condiciones de umbral de transición de etapa (`transiciones_condiciones`).
- `valores_iniciales.py` — valores por defecto al crear una `Relacion` y un `Estado` nuevos. Única fuente de verdad para los defaults de una relación recién iniciada.

---

## Capa de repositorio (`repositorios/`)

Abstrae el acceso a datos. La capa de aplicación solo habla con interfaces abstractas.

- `interfaces.py` — Protocols para cada entidad + dataclass `Repositorios` (contenedor compartido por todas las implementaciones).
- `json/` — implementación Fase 1: un archivo JSON por entidad en `data/`.
  - `factoria.py` — ensambla el objeto `Repositorios` con todas las implementaciones JSON e importa `Repositorios` desde `interfaces`.

**Ficheros de datos:**

```
data/
├── catalogos/
│   ├── emociones.json
│   ├── etapas_relacion.json
│   ├── transiciones_etapa.json
│   ├── tipos_evento.json
│   ├── mbti.json
│   ├── eneagramas.json
│   └── temperamentos.json
├── configuracion.json          ← parámetros numéricos del sistema
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

Los catálogos y la configuración se cargan una vez al arranque. Los demás ficheros se leen y escriben por operación.

---

## Capa de aplicación (`aplicacion/`)

Orquesta los casos de uso. No importa nada de interfaz ni de JSON/SQL.

- `gestor_turno.py` — caso de uso principal: procesar un turno de conversación (ver flujo abajo).
- `gestor_contexto.py` — construye el payload que recibe el LLM: psicología del personaje, estado emocional (nombre, no vectores), etapa, recuerdos relevantes, perfil del usuario, instrucción de formato JSON.
- `cliente_llm.py` — abstracción sobre el proveedor. Implementaciones: `ClienteOpenAI` (compatible con Ollama/LM Studio), `ClienteGemini`, `ClienteStub`.

---

## Capa de interfaz (`interfaz/`)

TUI con Textual.

```
interfaz/
├── app.py                         — NoviApp: recibe repos y gestor inyectados desde main.py
├── pantallas/
│   ├── menu_principal.py          — lista de conversaciones activas
│   ├── seleccion_personaje.py     — modal para iniciar un nuevo chat
│   ├── opciones_chat.py           — modal para borrar conversación / editar instrucciones LLM
│   └── chat.py                    — historial + input + panel lateral de estado
└── widgets/
    ├── burbuja.py                 — burbuja de mensaje estándar
    ├── burbuja_diagnostico.py     — burbuja de diagnóstico interno (modo tester)
    └── indicador.py               — indicador de estado de la relación
```

Solo llama a la capa de aplicación. Nunca accede a lógica de dominio ni a repositorios directamente.

---

## Flujo de arranque

```
python main.py
    │
    ├─► cargar .env
    ├─► crear_repositorios(JSON)     ← Fase 1; sustituir por crear_repositorios(PG) en Fase 2
    ├─► _asegurar_datos_iniciales()
    ├─► _crear_cliente_llm()
    ├─► ServicioEmbedding(cfg.embedding.modelo)
    ├─► GestorTurno(repos, cliente, servicio_embedding)
    └─► NoviApp(repos=repos, gestor=gestor).run()
```

`NoviApp` recibe los repositorios y el gestor ya construidos. Cambiar de Fase 1 a Fase 2 requiere solo crear un `main_postgres.py` que llame a la factoría Postgres e inyecte a `NoviApp` — sin tocar la app ni la interfaz.

---

## Flujo de un turno

```
Usuario escribe
        │
        ▼
  interfaz/pantallas/chat.py → GestorTurno.procesar()
        │
        ├─► guardar MENSAJE (usuario)
        ├─► aplicar decaimiento al ESTADO (+ Brechas 3)
        ├─► construir contexto (gestor_contexto.py)
        │       ├─► filtro vigencia + historial + decaimiento relevancia_activa
        │       └─► filtro semántico + ranking → recuerdos seleccionados
        ├─► llamar al LLM → JSON con respuesta, emociones, deltas, recuerdos, perfil
        ├─► guardar MENSAJE (personaje)
        ├─► actualizar ESTADO (Brechas 1+2: presión emoción sobre estado_animo)
        ├─► aplicar deltas de relación + calcular delta disposicion
        ├─► persistir recuerdos (con embedding calculado) y perfil_usuario
        ├─► gestionar conflictos (crear / escalar / resolver)
        ├─► recalcular familiaridad
        ├─► evaluar transición de etapa (impulso o permiso)
        └─► persistir cambios → devolver ResultadoTurno a la interfaz
```

---

## Cambios de Fase 1 a Fase 2

| Componente | Fase 1 | Fase 2 |
|---|---|---|
| Repositorios | JSON en disco | PostgreSQL + pgvector |
| `embedding` en RECUERDO | `None` | `vector(384)`, índice HNSW |
| Búsqueda semántica | Degradación graceful (similitud 0.0) | Filtro coseno real |
| Lanzador | `main.py` → `crear_repositorios(JSON)` | `main_postgres.py` → `crear_repositorios(PG)` |
| Interfaz / Dominio / Aplicación | Sin cambios | Sin cambios |

---

## Pendiente de implementar

- Fórmulas de actualización del `sentimiento` por eventos (distinto de las Brechas 1/2/3 que ya existen).
- Decaimiento y reactivación de `importancia` en RECUERDO.
- Estrategia de prompting para extracción de recuerdos y perfil del usuario más allá del turno actual.
