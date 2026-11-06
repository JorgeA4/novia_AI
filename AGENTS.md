# AGENTS.md — Guía para el agente de IA

---

## Mapa del repositorio

Ver `documentacion/arquitectura_v3.md` para el mapa completo de capas, módulos, flujo de arranque y flujo de un turno.

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
- El campo `embedding` en `Recuerdo` existe con valor `None` en recuerdos sin vectorizar; no omitirlo.
- Las transiciones de tipo `ruptura` son irreversibles; no implementar rollback para ellas.

## Reglas de estilo

- Producir el cambio mínimo que resuelva el problema. No refactorizar código no relacionado con la tarea.
- Seguir el estilo del archivo que se edita (indentación, comillas, orden de imports).
- No añadir manejo de errores para escenarios que no pueden ocurrir en el flujo real.
- Comando de desarrollo: `python -m interfaz` para arrancar. No hay test runner definido aún.
