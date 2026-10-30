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

- `modelos.py` — dataclasses de las entidades del modelo de datos v3.
- `emociones.py` — espacio de Russell: cálculo de vector compuesto, detección por distancia euclidiana, decaimiento exponencial, Brechas 1/2/3 (presión de emoción sobre estado_animo, modulación por sentimiento, deriva del sentimiento en reposo).
- `relacion.py` — transiciones de etapa, actualización de métricas con cap y resistencia en extremos, cálculo de `interes_actual`.
- `confianza.py` — `confianza_final = confianza_llm × factor_origen`, resolución de duplicados en PERFIL_USUARIO.
- `configuracion.py` — carga `data/configuracion.json` al arranque como singleton. Todos los parámetros numéricos del sistema se leen de ahí.

---

## Capa de repositorio (`repositorios/`)

Abstrae el acceso a datos. La capa de aplicación solo habla con interfaces abstractas.

- `interfaces.py` — Protocols para cada entidad.
- `json/` — implementación Fase 1: un archivo JSON por entidad en `data/`.
  - `factoria.py` — ensambla el objeto `Repositorios` con todas las implementaciones JSON.

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
├── app.py
├── pantallas/
│   └── chat.py       — historial + input + panel lateral de estado
└── widgets/
    ├── burbuja.py
    └── indicador.py
```

Solo llama a la capa de aplicación. Nunca accede a dominio ni repositorios directamente.

---

## Flujo de un turno

```
Usuario escribe
        │
        ▼
  interfaz/app.py → gestor_turno.py
        │
        ├─► guardar MENSAJE (usuario)
        ├─► aplicar decaimiento al ESTADO (+ Brechas 3)
        ├─► construir contexto (gestor_contexto.py)
        ├─► llamar al LLM → JSON con respuesta, emociones, deltas, recuerdos, perfil
        ├─► guardar MENSAJE (personaje)
        ├─► actualizar ESTADO (Brechas 1+2: presión emoción sobre estado_animo)
        ├─► aplicar deltas de relación + calcular delta disposicion
        ├─► persistir recuerdos y perfil_usuario extraídos
        ├─► evaluar transición de etapa (impulso o permiso)
        └─► persistir cambios → devolver respuesta a la interfaz
```

---

## Cambios de Fase 1 a Fase 2

| Componente | Fase 1 | Fase 2 |
|---|---|---|
| Repositorios | JSON en disco | SQLite / PostgreSQL |
| Búsqueda de recuerdos | Por importancia | Semántica (embeddings) |
| `embedding` en RECUERDO | None | Poblado |
| Interfaz | TUI mínima | TUI ampliada (o GUI) |
| Dominio / Aplicación | Sin cambios | Sin cambios |

---

## Pendiente de implementar

- Fórmulas de actualización del `sentimiento` por eventos (distinto de las Brechas 1/2/3 que ya existen).
- Decaimiento y reactivación de `importancia` en RECUERDO.
- Estrategia de prompting para extracción de recuerdos y perfil del usuario más allá del turno actual.
