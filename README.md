# novia_AI

IA que simula una relación con el usuario — desde que se conocen hasta llegar a ser pareja. El sistema gestiona el estado interno del personaje (emociones, relación, memoria) y usa un LLM para convertirlo en lenguaje natural.

---

## Requisitos

- Python 3.11+
- Una clave de API de OpenAI **o** un servidor local compatible (Ollama, LM Studio)

---

## Instalación

```bash
git clone https://github.com/JorgeA4/novia_AI
cd novia_AI
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Ejecución

### Con OpenAI

```bash
OPENAI_API_KEY=sk-... python -m interfaz
```

### Con Ollama (local)

```bash
NOVIA_URL_BASE=http://localhost:11434/v1 NOVIA_MODELO=llama3.2 python -m interfaz
```

### Modo desarrollo sin LLM

```bash
NOVIA_STUB=1 python -m interfaz
```

---

## Variables de entorno

| Variable         | Por defecto     | Descripción                                      |
|------------------|-----------------|--------------------------------------------------|
| `OPENAI_API_KEY` | —               | Clave de API de OpenAI                           |
| `NOVIA_MODELO`   | `gpt-4o-mini`   | Modelo a usar                                    |
| `NOVIA_URL_BASE` | API de OpenAI   | URL base alternativa (Ollama, LM Studio, etc.)   |
| `NOVIA_DATOS`    | `./data`        | Directorio donde se guardan los datos            |
| `NOVIA_STUB`     | —               | Si está definida, responde con texto fijo (tests)|

---

## Controles en la TUI

| Atajo    | Acción                          |
|----------|---------------------------------|
| `Ctrl+E` | Mostrar / ocultar panel estado  |
| `Ctrl+Q` | Salir                           |
| `Enter`  | Enviar mensaje                  |

---

## Estructura del proyecto

```
novia_AI/
├── dominio/          # Lógica pura: emociones, relación, confianza
├── repositorios/     # Interfaces abstractas + implementación JSON
├── aplicacion/       # Orquestación: gestor de turno, contexto, cliente LLM
├── interfaz/         # TUI con Textual
├── data/             # Datos persistidos y catálogos
└── documentacion/    # Diseño, modelo de datos y decisiones arquitectónicas
```

Los datos se guardan automáticamente en `./data/` en formato JSON. La primera ejecución crea el personaje por defecto (Luna).
