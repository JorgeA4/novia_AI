"""
Repositorios JSON para: Personaje, Usuario, Relacion, Estado.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

from dominio.modelos import Estado, Personaje, Relacion, Usuario
from repositorios.json._utilidades import (
    escribir_json,
    leer_json,
    parsear_datetime,
    siguiente_id,
)


# ---------------------------------------------------------------------------
# Personaje
# ---------------------------------------------------------------------------

class PersonajeJson:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta

    def obtener(self, num: int) -> Personaje:
        for d in leer_json(self._ruta):
            if d["num"] == num:
                return _dict_a_personaje(d)
        raise KeyError(f"Personaje {num} no encontrado")

    def guardar(self, personaje: Personaje) -> None:
        registros = leer_json(self._ruta)
        registros = [r for r in registros if r["num"] != personaje.num]
        registros.append(asdict(personaje))
        escribir_json(self._ruta, registros)

    def listar(self) -> list[Personaje]:
        return [_dict_a_personaje(d) for d in leer_json(self._ruta)]


def _dict_a_personaje(d: dict) -> Personaje:
    return Personaje(
        num=d["num"],
        nombre=d["nombre"],
        descripcion=d["descripcion"],
        historia=d["historia"],
        valores=d["valores"],
        gustos=d["gustos"],
        aversiones=d["aversiones"],
        mbti_id=d["mbti_id"],
        eneagrama_id=d["eneagrama_id"],
        temperamento_id=d["temperamento_id"],
    )


# ---------------------------------------------------------------------------
# Usuario
# ---------------------------------------------------------------------------

class UsuarioJson:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta

    def obtener(self, num: int) -> Usuario:
        for d in leer_json(self._ruta):
            if d["num"] == num:
                return Usuario(num=d["num"], nombre=d["nombre"])
        raise KeyError(f"Usuario {num} no encontrado")

    def guardar(self, usuario: Usuario) -> None:
        registros = leer_json(self._ruta)
        registros = [r for r in registros if r["num"] != usuario.num]
        registros.append(asdict(usuario))
        escribir_json(self._ruta, registros)

    def listar(self) -> list[Usuario]:
        return [Usuario(num=d["num"], nombre=d["nombre"]) for d in leer_json(self._ruta)]


# ---------------------------------------------------------------------------
# Relacion
# ---------------------------------------------------------------------------

class RelacionJson:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta

    def obtener(self, num: int) -> Relacion:
        for d in leer_json(self._ruta):
            if d["num"] == num:
                return _dict_a_relacion(d)
        raise KeyError(f"Relacion {num} no encontrada")

    def guardar(self, relacion: Relacion) -> None:
        registros = leer_json(self._ruta)
        registros = [r for r in registros if r["num"] != relacion.num]
        registros.append(asdict(relacion))
        escribir_json(self._ruta, registros)

    def listar_por_personaje(self, personaje_id: int) -> list[Relacion]:
        return [_dict_a_relacion(d) for d in leer_json(self._ruta)
                if d["personaje_id"] == personaje_id]

    def listar_por_usuario(self, usuario_id: int) -> list[Relacion]:
        return [_dict_a_relacion(d) for d in leer_json(self._ruta)
                if d["usuario_id"] == usuario_id]


def _dict_a_relacion(d: dict) -> Relacion:
    return Relacion(
        num=d["num"],
        personaje_id=d["personaje_id"],
        usuario_id=d["usuario_id"],
        etapa=d["etapa"],
        confianza=d["confianza"],
        confianza_delta=d.get("confianza_delta", 0.0),
        afecto=d["afecto"],
        afecto_delta=d.get("afecto_delta", 0.0),
        familiaridad=d["familiaridad"],
        tension=d["tension"],
        disposicion=d.get("disposicion", 0.5),
        disposicion_delta=d.get("disposicion_delta", 0.0),
    )


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------

class EstadoJson:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta

    def obtener(self, relacion_id: int) -> Estado:
        for d in leer_json(self._ruta):
            if d["relacion_id"] == relacion_id:
                return _dict_a_estado(d)
        raise KeyError(f"Estado para relacion {relacion_id} no encontrado")

    def guardar(self, estado: Estado) -> None:
        registros = leer_json(self._ruta)
        registros = [r for r in registros if r["relacion_id"] != estado.relacion_id]
        d = asdict(estado)
        d["ultima_interaccion"] = estado.ultima_interaccion.isoformat()
        registros.append(d)
        escribir_json(self._ruta, registros)


def _dict_a_estado(d: dict) -> Estado:
    return Estado(
        relacion_id=d["relacion_id"],
        emocion_id=d["emocion_id"],
        emocion_intensidad=d["emocion_intensidad"],
        estado_animo_id=d["estado_animo_id"],
        estado_animo_intensidad=d["estado_animo_intensidad"],
        sentimiento_id=d["sentimiento_id"],
        sentimiento_intensidad=d["sentimiento_intensidad"],
        ultima_interaccion=parsear_datetime(d["ultima_interaccion"]),
    )
