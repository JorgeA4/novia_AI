# Project Coding Rules (Non-Obvious Only)

- Todo el código, comentarios, nombres de variables, funciones y clases deben estar en **español**; solo las keywords del lenguaje van en inglés.
- Las 3 capas emocionales (`emocion`, `estado_animo`, `sentimiento`) se calculan con pesos fijos (0.50 / 0.35 / 0.15) leídos de `data/configuracion.json`. No convertirlos en parámetros dinámicos en runtime.
- La detección de emoción resultante es por **distancia euclidiana** al catálogo `EMOCION`. No implementar umbrales ni reglas if/else para esto.
- Los campos reservados para fase 2 (`embedding` en RECUERDO) deben existir en el esquema con valor None — no omitirlos, no implementar su lógica aún.
- La penalización LLM (`× 0.7` por defecto) se lee de `configuracion.json` (`confianza_llm.penalizacion_inferencia`). No hardcodearla.
- Las transiciones `ruptura` son irreversibles en el modelo; no implementar rollback para ellas.
- Lenguaje: **Python 3.11+**. Framework TUI: **Textual**. Persistencia fase 1: **JSON en disco**.
- Comandos de desarrollo: `python -m interfaz` para arrancar, no hay test runner definido aún.
