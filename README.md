# novia_AI

IA que simula una relación con el usuario — desde que se conocen hasta llegar a ser pareja. El sistema gestiona el estado interno del personaje (emociones, relación, memoria) y usa un LLM para convertirlo en lenguaje natural.

---

## Requisitos

- Python 3.11+
- Una clave de API de **OpenAI**, **Google Gemini**, o un servidor local compatible (Ollama, LM Studio)

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

### Con Google Gemini (recomendado — gratuito con límite generoso)

```bash
GEMINI_API_KEY=AIza... python -m interfaz
```

Con un modelo concreto (por defecto `gemini-1.5-flash`):

```bash
GEMINI_API_KEY=AIza... NOVIA_MODELO=gemini-2.0-flash-exp python -m interfaz
```

### Con OpenAI

```bash
OPENAI_API_KEY=sk-... python -m interfaz
```

### Con Ollama (local, sin clave)

```bash
NOVIA_URL_BASE=http://localhost:11434/v1 NOVIA_MODELO=llama3.2 python -m interfaz
```

### Modo desarrollo sin LLM

```bash
NOVIA_STUB=1 python -m interfaz
```

---

## Variables de entorno

| Variable          | Por defecto          | Descripción                                              |
|-------------------|----------------------|----------------------------------------------------------|
| `GEMINI_API_KEY`  | —                    | Clave de API de Google Gemini (activa el proveedor Gemini) |
| `OPENAI_API_KEY`  | —                    | Clave de API de OpenAI (usado si no hay GEMINI_API_KEY)  |
| `NOVIA_MODELO`    | según proveedor*     | Modelo a usar                                            |
| `NOVIA_URL_BASE`  | API de OpenAI        | URL base alternativa para OpenAI (Ollama, LM Studio…)    |
| `NOVIA_DATOS`     | `./data`             | Directorio donde se guardan los datos                    |
| `NOVIA_STUB`      | —                    | Si está definida, responde con texto fijo (sin LLM)      |

\* Por defecto: `gemini-1.5-flash` con Gemini, `gpt-4o-mini` con OpenAI.

**Prioridad de proveedor:** `NOVIA_STUB` > `GEMINI_API_KEY` > `OPENAI_API_KEY`

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
