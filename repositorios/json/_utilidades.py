"""
Utilidades compartidas por todos los repositorios JSON.

- Lectura y escritura atómica de ficheros JSON.
- Generación de IDs incrementales.
- Conversión entre dataclasses y dicts.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Lectura / escritura
# ---------------------------------------------------------------------------

def leer_json(ruta: Path) -> Any:
    """Lee un fichero JSON. Devuelve [] si no existe."""
    if not ruta.exists():
        return []
    with ruta.open("r", encoding="utf-8") as f:
        return json.load(f)


def escribir_json(ruta: Path, datos: Any) -> None:
    """Escribe datos en un fichero JSON de forma atómica (write + rename)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta_tmp = ruta.with_suffix(".tmp")
    with ruta_tmp.open("w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=_serializar)
    os.replace(ruta_tmp, ruta)


# ---------------------------------------------------------------------------
# Serialización de tipos especiales
# ---------------------------------------------------------------------------

def _serializar(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Tipo no serializable: {type(obj)}")


def parsear_datetime(valor: str | None) -> datetime | None:
    if valor is None:
        return None
    return datetime.fromisoformat(valor)


# ---------------------------------------------------------------------------
# Generación de IDs
# ---------------------------------------------------------------------------

def siguiente_id(registros: list[dict]) -> int:
    """Devuelve el siguiente ID entero disponible (máximo existente + 1)."""
    if not registros:
        return 1
    return max(r.get("num", 0) for r in registros) + 1
