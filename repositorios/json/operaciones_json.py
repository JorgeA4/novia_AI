"""
Repositorios JSON para: Mensaje, Evento, Conflicto, Recuerdo, PerfilUsuario.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

from dominio.modelos import Conflicto, Evento, Mensaje, PerfilUsuario, Recuerdo
from repositorios.json._utilidades import (
    escribir_json,
    leer_json,
    parsear_datetime,
    siguiente_id,
)


# ---------------------------------------------------------------------------
# Mensaje
# ---------------------------------------------------------------------------

class MensajeJson:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta

    def guardar(self, mensaje: Mensaje) -> None:
        registros = leer_json(self._ruta)
        if mensaje.num == 0:
            mensaje = Mensaje(
                num=siguiente_id(registros),
                relacion_id=mensaje.relacion_id,
                rol=mensaje.rol,
                contenido=mensaje.contenido,
                fecha=mensaje.fecha,
            )
        registros = [r for r in registros if r["num"] != mensaje.num]
        d = asdict(mensaje)
        d["fecha"] = mensaje.fecha.isoformat()
        registros.append(d)
        escribir_json(self._ruta, registros)

    def listar_por_relacion(
        self, relacion_id: int, limite: Optional[int] = None
    ) -> list[Mensaje]:
        todos = [
            _dict_a_mensaje(d)
            for d in leer_json(self._ruta)
            if d["relacion_id"] == relacion_id
        ]
        todos.sort(key=lambda m: m.fecha)
        if limite is not None:
            todos = todos[-limite:]
        return todos


def _dict_a_mensaje(d: dict) -> Mensaje:
    return Mensaje(
        num=d["num"],
        relacion_id=d["relacion_id"],
        rol=d["rol"],
        contenido=d["contenido"],
        fecha=parsear_datetime(d["fecha"]),
    )


# ---------------------------------------------------------------------------
# Evento
# ---------------------------------------------------------------------------

class EventoJson:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta

    def obtener(self, num: int) -> Evento:
        for d in leer_json(self._ruta):
            if d["num"] == num:
                return _dict_a_evento(d)
        raise KeyError(f"Evento {num} no encontrado")

    def guardar(self, evento: Evento) -> None:
        registros = leer_json(self._ruta)
        if evento.num == 0:
            evento = Evento(
                num=siguiente_id(registros),
                relacion_id=evento.relacion_id,
                tipo=evento.tipo,
                descripcion=evento.descripcion,
                fecha=evento.fecha,
                impacto=evento.impacto,
                resuelto=evento.resuelto,
                etapa_desde_id=evento.etapa_desde_id,
                etapa_hasta_id=evento.etapa_hasta_id,
            )
        registros = [r for r in registros if r["num"] != evento.num]
        d = asdict(evento)
        d["fecha"] = evento.fecha.isoformat()
        registros.append(d)
        escribir_json(self._ruta, registros)

    def listar_por_relacion(self, relacion_id: int) -> list[Evento]:
        return [
            _dict_a_evento(d)
            for d in leer_json(self._ruta)
            if d["relacion_id"] == relacion_id
        ]


def _dict_a_evento(d: dict) -> Evento:
    return Evento(
        num=d["num"],
        relacion_id=d["relacion_id"],
        tipo=d["tipo"],
        descripcion=d["descripcion"],
        fecha=parsear_datetime(d["fecha"]),
        impacto=d["impacto"],
        resuelto=d["resuelto"],
        etapa_desde_id=d.get("etapa_desde_id"),
        etapa_hasta_id=d.get("etapa_hasta_id"),
    )


# ---------------------------------------------------------------------------
# Conflicto
# ---------------------------------------------------------------------------

class ConflictoJson:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta

    def obtener(self, num: int) -> Conflicto:
        for d in leer_json(self._ruta):
            if d["num"] == num:
                return _dict_a_conflicto(d)
        raise KeyError(f"Conflicto {num} no encontrado")

    def guardar(self, conflicto: Conflicto) -> None:
        registros = leer_json(self._ruta)
        if conflicto.num == 0:
            conflicto = Conflicto(
                num=siguiente_id(registros),
                evento_id=conflicto.evento_id,
                causa=conflicto.causa,
                estado=conflicto.estado,
                resolucion=conflicto.resolucion,
            )
        registros = [r for r in registros if r["num"] != conflicto.num]
        registros.append(asdict(conflicto))
        escribir_json(self._ruta, registros)

    def listar_por_relacion(self, relacion_id: int) -> list[Conflicto]:
        eventos_ids = self._ids_eventos_de_relacion(relacion_id)
        return [
            _dict_a_conflicto(d)
            for d in leer_json(self._ruta)
            if d["evento_id"] in eventos_ids
        ]

    def listar_activos(self, relacion_id: int) -> list[Conflicto]:
        return [
            c for c in self.listar_por_relacion(relacion_id)
            if c.estado in ("activo", "escalado")
        ]

    def _ids_eventos_de_relacion(self, relacion_id: int) -> set[int]:
        from repositorios.json._utilidades import leer_json as _leer
        # Necesita acceso a eventos.json — se resuelve en la factoría
        # devolviendo todos los IDs; en MVP la lista es pequeña
        return set()  # placeholder — ver ConflictoJsonConEventos


def _dict_a_conflicto(d: dict) -> Conflicto:
    return Conflicto(
        num=d["num"],
        evento_id=d["evento_id"],
        causa=d["causa"],
        estado=d["estado"],
        resolucion=d.get("resolucion"),
    )


class ConflictoJsonConEventos(ConflictoJson):
    """
    Versión de ConflictoJson que recibe la ruta de eventos.json para
    poder filtrar conflictos por relacion_id correctamente.
    """
    def __init__(self, ruta: Path, ruta_eventos: Path) -> None:
        super().__init__(ruta)
        self._ruta_eventos = ruta_eventos

    def _ids_eventos_de_relacion(self, relacion_id: int) -> set[int]:
        return {
            d["num"]
            for d in leer_json(self._ruta_eventos)
            if d["relacion_id"] == relacion_id
        }


# ---------------------------------------------------------------------------
# Recuerdo
# ---------------------------------------------------------------------------

class RecuerdoJson:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta

    def obtener(self, num: int) -> Recuerdo:
        for d in leer_json(self._ruta):
            if d["num"] == num:
                return _dict_a_recuerdo(d)
        raise KeyError(f"Recuerdo {num} no encontrado")

    def guardar(self, recuerdo: Recuerdo) -> None:
        registros = leer_json(self._ruta)
        if recuerdo.num == 0:
            recuerdo = Recuerdo(
                num=siguiente_id(registros),
                relacion_id=recuerdo.relacion_id,
                tipo=recuerdo.tipo,
                categoria=recuerdo.categoria,
                contenido=recuerdo.contenido,
                origen=recuerdo.origen,
                importancia=recuerdo.importancia,
                fecha_creacion=recuerdo.fecha_creacion,
                ultima_relevancia=recuerdo.ultima_relevancia,
                emocion_asociada_id=recuerdo.emocion_asociada_id,
                emocion_asociada_intensidad=recuerdo.emocion_asociada_intensidad,
                vigencia=recuerdo.vigencia,
                evento_id=recuerdo.evento_id,
                embedding=recuerdo.embedding,
            )
        registros = [r for r in registros if r["num"] != recuerdo.num]
        d = asdict(recuerdo)
        d["fecha_creacion"] = recuerdo.fecha_creacion.isoformat()
        d["ultima_relevancia"] = recuerdo.ultima_relevancia.isoformat()
        d["vigencia"] = recuerdo.vigencia.isoformat() if recuerdo.vigencia is not None else None
        registros.append(d)
        escribir_json(self._ruta, registros)

    def listar_por_relacion(
        self,
        relacion_id: int,
        importancia_minima: float = 0.0,
        limite: Optional[int] = None,
    ) -> list[Recuerdo]:
        todos = [
            _dict_a_recuerdo(d)
            for d in leer_json(self._ruta)
            if d["relacion_id"] == relacion_id
            and d["importancia"] >= importancia_minima
        ]
        todos.sort(key=lambda r: r.importancia, reverse=True)
        if limite is not None:
            todos = todos[:limite]
        return todos


def _dict_a_recuerdo(d: dict) -> Recuerdo:
    vigencia_raw = d.get("vigencia")
    return Recuerdo(
        num=d["num"],
        relacion_id=d["relacion_id"],
        tipo=d["tipo"],
        categoria=d.get("categoria", "hecho_puntual"),
        contenido=d["contenido"],
        origen=d["origen"],
        importancia=d["importancia"],
        fecha_creacion=parsear_datetime(d["fecha_creacion"]),
        ultima_relevancia=parsear_datetime(d["ultima_relevancia"]),
        emocion_asociada_id=d.get("emocion_asociada_id") or "neutro",
        emocion_asociada_intensidad=d.get("emocion_asociada_intensidad") or 0.0,
        vigencia=parsear_datetime(vigencia_raw) if vigencia_raw else None,
        evento_id=d.get("evento_id"),
        embedding=d.get("embedding"),
    )


# ---------------------------------------------------------------------------
# PerfilUsuario
# ---------------------------------------------------------------------------

class PerfilUsuarioJson:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta

    def obtener(self, num: int) -> PerfilUsuario:
        for d in leer_json(self._ruta):
            if d["num"] == num:
                return _dict_a_perfil(d)
        raise KeyError(f"PerfilUsuario {num} no encontrado")

    def obtener_por_clave(self, relacion_id: int, sujeto: str, clave: str) -> Optional[PerfilUsuario]:
        for d in leer_json(self._ruta):
            if d["relacion_id"] == relacion_id and d["sujeto"] == sujeto and d["clave"] == clave:
                return _dict_a_perfil(d)
        return None

    def guardar(self, entrada: PerfilUsuario) -> None:
        registros = leer_json(self._ruta)
        if entrada.num == 0:
            entrada = PerfilUsuario(
                num=siguiente_id(registros),
                relacion_id=entrada.relacion_id,
                sujeto=entrada.sujeto,
                clave=entrada.clave,
                valor=entrada.valor,
                origen=entrada.origen,
                confianza_llm=entrada.confianza_llm,
            )
        registros = [r for r in registros if r["num"] != entrada.num]
        registros.append(asdict(entrada))
        escribir_json(self._ruta, registros)

    def eliminar(self, num: int) -> None:
        registros = leer_json(self._ruta)
        registros = [r for r in registros if r["num"] != num]
        escribir_json(self._ruta, registros)

    def listar_por_relacion(
        self,
        relacion_id: int,
        confianza_minima: float = 0.0,
    ) -> list[PerfilUsuario]:
        from dominio.confianza import confianza_final_de
        return [
            p for d in leer_json(self._ruta)
            if d["relacion_id"] == relacion_id
            for p in [_dict_a_perfil(d)]
            if confianza_final_de(p) >= confianza_minima
        ]


def _dict_a_perfil(d: dict) -> PerfilUsuario:
    return PerfilUsuario(
        num=d["num"],
        relacion_id=d["relacion_id"],
        sujeto=d.get("sujeto", "usuario"),
        clave=d["clave"],
        valor=d["valor"],
        origen=d["origen"],
        confianza_llm=d["confianza_llm"],
    )
