"""
Script de migración: calcula y persiste los embeddings de los recuerdos
que aún tienen embedding=None.

Uso:
    python scripts/recalcular_embeddings.py [relacion_id]

Si se pasa un relacion_id, solo procesa los recuerdos de esa relación.
Si no se pasa ninguno, procesa todas las relaciones.

El script es idempotente: omite recuerdos que ya tienen embedding.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

# Permitir importaciones desde la raíz del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from dominio.configuracion import cfg
from dominio.embedding import ServicioEmbedding
from repositorios.json.factoria import crear_repositorios


def recalcular(relacion_id: int | None = None) -> None:
    ruta_datos = Path(__file__).parent.parent / "data"
    repos = crear_repositorios(ruta_datos)
    servicio = ServicioEmbedding(cfg.embedding.modelo)

    # Obtener relaciones a procesar
    if relacion_id is not None:
        ids_relacion = [relacion_id]
    else:
        import json
        relaciones_raw = json.loads((ruta_datos / "relaciones.json").read_text(encoding="utf-8"))
        ids_relacion = [r["num"] for r in relaciones_raw]

    total_actualizados = 0

    for rid in ids_relacion:
        recuerdos = repos.recuerdo.listar_por_relacion(rid)
        sin_embedding = [r for r in recuerdos if r.embedding is None]

        if not sin_embedding:
            print(f"Relación {rid}: todos los recuerdos ya tienen embedding.")
            continue

        print(f"Relación {rid}: procesando {len(sin_embedding)} recuerdos sin embedding...")

        embeddings = servicio.codificar_multiples(
            [recuerdo.contenido for recuerdo in sin_embedding]
        )
        for recuerdo, embedding in zip(sin_embedding, embeddings):
            recuerdo_actualizado = replace(recuerdo, embedding=embedding)
            repos.recuerdo.guardar(recuerdo_actualizado)

        total_actualizados += len(sin_embedding)
        print(f"Relación {rid}: ✓ {len(sin_embedding)} recuerdos actualizados.")

    print(f"Total actualizado: {total_actualizados} recuerdos.")


if __name__ == "__main__":
    rid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    recalcular(rid)
