"""
Servicio de embeddings semánticos — encapsula el modelo sentence-transformers.

Carga el modelo de forma lazy (solo cuando se codifica por primera vez),
por lo que importar este módulo no penaliza el arranque de la aplicación.

Uso:
    from dominio.embedding import ServicioEmbedding

    servicio = ServicioEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    vector = servicio.codificar("hola mundo")
    sim = servicio.similitud_coseno(vector, otro_vector)
"""

from __future__ import annotations

import math
import re


class ServicioEmbedding:
    """Codifica textos en vectores y calcula similitud coseno."""

    def __init__(self, nombre_modelo: str) -> None:
        self._nombre_modelo = nombre_modelo
        self._modelo = None  # lazy load

    def _cargar(self) -> None:
        if self._modelo is None:
            from sentence_transformers import SentenceTransformer
            self._modelo = SentenceTransformer(self._nombre_modelo)

    def codificar(self, texto: str) -> list[float]:
        """Devuelve el embedding del texto como lista de floats."""
        self._cargar()
        return self._modelo.encode(texto).tolist()

    def codificar_multiples(self, textos: list[str]) -> list[list[float]]:
        """Codifica varios textos en una sola llamada al modelo."""
        if not textos:
            return []
        self._cargar()
        return self._modelo.encode(textos).tolist()

    def similitud_coseno(self, a: list[float], b: list[float]) -> float:
        """
        Similitud coseno entre dos vectores de la misma dimensión.
        Devuelve un valor en [-1.0, 1.0]; para embeddings normalizados
        el rango efectivo es [0.0, 1.0].
        """
        punto = sum(x * y for x, y in zip(a, b))
        norma_a = math.sqrt(sum(x * x for x in a))
        norma_b = math.sqrt(sum(y * y for y in b))
        if norma_a == 0.0 or norma_b == 0.0:
            return 0.0
        return punto / (norma_a * norma_b)


def dividir_en_fragmentos(texto: str) -> list[str]:
    """Divide un mensaje en oraciones conservando su puntuación."""
    fragmentos = re.split(r"(?<=[.!?…])\s+|[\r\n]+", texto.strip())
    return [fragmento.strip() for fragmento in fragmentos if fragmento.strip()]
