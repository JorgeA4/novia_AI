# AGENTS.md — Guía para el agente de IA

---

## Mapa del repositorio

```
novia_AI/
├── dominio/                   # Lógica pura (sin dependencias externas)
│   ├── modelos.py             # Dataclasses de todas las entidades
│   ├── configuracion.py       # Singleton que carga data/configuracion.json
│   ├── emociones.py           # Espacio de Russell, decaimiento, Brechas 1/2/3
│   ├── relacion.py            # Transiciones de etapa, métricas, interes_actual
│   ├── confianza.py           # confianza_final, resolución de duplicados en perfil
│   ├── recuerdos.py           # Filtro de vigencia, relevancia_activa, pipeline de recuperación
│   └── embedding.py           # ServicioEmbedding (similitud coseno; embeddings = fase 2)
│
├── aplicacion/                # Casos de uso (orquesta dominio + repositorios + LLM)
│   ├── gestor_turno.py        # Caso de uso principal: procesar un turno de conversación
│   ├── gestor_contexto.py     # Construye el payload que recibe el LLM
│   └── cliente_llm.py         # Abstracción de proveedor (OpenAI/Gemini/Stub)
│
├── repositorios/              # Capa de persistencia
│   ├── interfaces.py          # Protocols por entidad
│   └── json/                  # Implementación fase 1: JSON en disco
│       └── factoria.py        # Ensambla el objeto Repositorios
│
├── interfaz/                  # TUI con Textual
│   ├── app.py
│   ├── pantallas/chat.py
│   └── widgets/
│
├── data/
│   ├── configuracion.json     # TODOS los parámetros numéricos del sistema
│   └── catalogos/             # Emociones, etapas, transiciones, MBTI, etc.
│
└── documentacion/
    ├── modelo_datos_v3.md          # Esquema de entidades y campos
    ├── logica_interna.md           # Decisiones de comportamiento y fórmulas
    ├── arquitectura_v3.md          # Capas, flujo de un turno, mapa de archivos
    └── plan_similitud_semantica.md # Hoja de ruta para embeddings (fase 2)
```

---

## Documentación de referencia

Antes de modificar cualquier lógica existente, consultar:

| Qué necesitas saber                          | Archivo                                    |
|----------------------------------------------|--------------------------------------------|
| Campos y tipos de una entidad                | `documentacion/modelo_datos_v3.md`         |
| Fórmulas, reglas de comportamiento           | `documentacion/logica_interna.md`          |
| Qué hace cada módulo y cómo se conectan      | `documentacion/arquitectura_v3.md`         |
| Parámetros numéricos configurables           | `data/configuracion.json`                  |

---

## Reglas de programación

- Todo el código, comentarios, nombres de variables, funciones y clases en **español**; solo las keywords del lenguaje en inglés.
- Lenguaje: **Python 3.11+**. Framework TUI: **Textual**. Persistencia fase 1: **JSON en disco**.
- La capa de dominio (`dominio/`) no importa nada de persistencia ni de interfaz.
- La capa de interfaz (`interfaz/`) solo llama a la capa de aplicación; nunca accede a dominio ni repositorios directamente.
- Todos los parámetros numéricos se leen de `data/configuracion.json` vía `dominio/configuracion.py`. No hardcodear ningún valor de configuración en el código.
- Los campos reservados para fase 2 (`embedding` en `Recuerdo`) deben existir en el esquema con valor `None`; no omitirlos, no implementar su lógica aún.
- Las transiciones de tipo `ruptura` son irreversibles; no implementar rollback para ellas.

## Reglas de estilo

- Producir el cambio mínimo que resuelva el problema. No refactorizar código no relacionado con la tarea.
- Seguir el estilo del archivo que se edita (indentación, comillas, orden de imports).
- No añadir manejo de errores para escenarios que no pueden ocurrir en el flujo real.
- Comando de desarrollo: `python -m interfaz` para arrancar. No hay test runner definido aún.
