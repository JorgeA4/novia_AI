"""
Repositorio de catálogos — implementación JSON.

Los catálogos se cargan una vez desde data/catalogos/ y se mantienen en memoria.
Son inmutables en tiempo de ejecución.
"""

from __future__ import annotations

from pathlib import Path

from dominio.modelos import (
    Emocion,
    Eneagrama,
    EtapaRelacion,
    Mbti,
    Temperamento,
    TipoEvento,
    TransicionEtapa,
)
from repositorios.json._utilidades import leer_json


class CatalogosJson:
    def __init__(self, directorio: Path) -> None:
        self._dir = directorio
        self._emociones: list[Emocion] | None = None
        self._etapas: list[EtapaRelacion] | None = None
        self._transiciones: list[TransicionEtapa] | None = None
        self._tipos_evento: list[TipoEvento] | None = None
        self._mbti: list[Mbti] | None = None
        self._eneagramas: list[Eneagrama] | None = None
        self._temperamentos: list[Temperamento] | None = None

    # --- Emocion ---

    def obtener_emociones(self) -> list[Emocion]:
        if self._emociones is None:
            datos = leer_json(self._dir / "emociones.json")
            self._emociones = [
                Emocion(
                    codigo=d["codigo"],
                    nombre=d["nombre"],
                    valencia=d["valencia"],
                    activacion=d["activacion"],
                    capa=d["capa"],
                    descripcion=d.get("descripcion", ""),
                )
                for d in datos
            ]
        return self._emociones

    # --- EtapaRelacion ---

    def obtener_etapas_relacion(self) -> list[EtapaRelacion]:
        if self._etapas is None:
            datos = leer_json(self._dir / "etapas_relacion.json")
            self._etapas = [
                EtapaRelacion(
                    codigo=d["codigo"],
                    nombre=d["nombre"],
                    descripcion=d.get("descripcion", ""),
                )
                for d in datos
            ]
        return self._etapas

    # --- TransicionEtapa ---

    def obtener_transiciones_etapa(self) -> list[TransicionEtapa]:
        if self._transiciones is None:
            datos = leer_json(self._dir / "transiciones_etapa.json")
            self._transiciones = [
                TransicionEtapa(
                    desde_id=d["desde_id"],
                    hasta_id=d["hasta_id"],
                    tipo=d["tipo"],
                )
                for d in datos
            ]
        return self._transiciones

    # --- TipoEvento ---

    def obtener_tipos_evento(self) -> list[TipoEvento]:
        if self._tipos_evento is None:
            datos = leer_json(self._dir / "tipos_evento.json")
            self._tipos_evento = [
                TipoEvento(
                    codigo=d["codigo"],
                    nombre=d["nombre"],
                    descripcion=d.get("descripcion", ""),
                    categoria=d.get("categoria", "cotidiano"),
                )
                for d in datos
            ]
        return self._tipos_evento

    # --- Mbti ---

    def obtener_mbti(self) -> list[Mbti]:
        if self._mbti is None:
            datos = leer_json(self._dir / "mbti.json")
            self._mbti = [
                Mbti(
                    codigo=d["codigo"],
                    siglas=d["siglas"],
                    descripcion=d.get("descripcion", ""),
                )
                for d in datos
            ]
        return self._mbti

    # --- Eneagrama ---

    def obtener_eneagramas(self) -> list[Eneagrama]:
        if self._eneagramas is None:
            datos = leer_json(self._dir / "eneagramas.json")
            self._eneagramas = [
                Eneagrama(
                    codigo=d["codigo"],
                    siglas=d["siglas"],
                    descripcion=d.get("descripcion", ""),
                )
                for d in datos
            ]
        return self._eneagramas

    # --- Temperamento ---

    def obtener_temperamentos(self) -> list[Temperamento]:
        if self._temperamentos is None:
            datos = leer_json(self._dir / "temperamentos.json")
            self._temperamentos = [
                Temperamento(
                    codigo=d["codigo"],
                    nombre=d["nombre"],
                    descripcion=d.get("descripcion", ""),
                )
                for d in datos
            ]
        return self._temperamentos
