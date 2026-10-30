"""
Interfaces abstractas de repositorio — contratos que toda implementación
(JSON, base de datos, etc.) debe cumplir.

La capa de aplicación solo importa desde este módulo, nunca desde
implementaciones concretas. Esto garantiza que cambiar de JSON a BD
no requiere tocar ningún código de aplicación.

Regla: este módulo no importa nada de persistencia concreta ni de interfaz.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from dominio.modelos import (
    Conflicto,
    Emocion,
    Eneagrama,
    Estado,
    EtapaRelacion,
    Evento,
    Mbti,
    Mensaje,
    Personaje,
    PerfilUsuario,
    Recuerdo,
    Relacion,
    Temperamento,
    TipoEvento,
    TransicionEtapa,
    Usuario,
)


# ---------------------------------------------------------------------------
# Catálogos (solo lectura — se cargan al arranque)
# ---------------------------------------------------------------------------

@runtime_checkable
class RepositorioCatalogos(Protocol):
    """
    Catálogos de referencia. Son inmutables en tiempo de ejecución;
    se cargan una vez al arranque y se mantienen en memoria.
    """

    def obtener_emociones(self) -> list[Emocion]: ...
    def obtener_etapas_relacion(self) -> list[EtapaRelacion]: ...
    def obtener_transiciones_etapa(self) -> list[TransicionEtapa]: ...
    def obtener_tipos_evento(self) -> list[TipoEvento]: ...
    def obtener_mbti(self) -> list[Mbti]: ...
    def obtener_eneagramas(self) -> list[Eneagrama]: ...
    def obtener_temperamentos(self) -> list[Temperamento]: ...


# ---------------------------------------------------------------------------
# Personaje
# ---------------------------------------------------------------------------

@runtime_checkable
class RepositorioPersonaje(Protocol):
    def obtener(self, num: int) -> Personaje: ...
    def guardar(self, personaje: Personaje) -> None: ...
    def listar(self) -> list[Personaje]: ...


# ---------------------------------------------------------------------------
# Usuario
# ---------------------------------------------------------------------------

@runtime_checkable
class RepositorioUsuario(Protocol):
    def obtener(self, num: int) -> Usuario: ...
    def guardar(self, usuario: Usuario) -> None: ...
    def listar(self) -> list[Usuario]: ...


# ---------------------------------------------------------------------------
# Relacion
# ---------------------------------------------------------------------------

@runtime_checkable
class RepositorioRelacion(Protocol):
    def obtener(self, num: int) -> Relacion: ...
    def guardar(self, relacion: Relacion) -> None: ...
    def listar_por_personaje(self, personaje_id: int) -> list[Relacion]: ...
    def listar_por_usuario(self, usuario_id: int) -> list[Relacion]: ...


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------

@runtime_checkable
class RepositorioEstado(Protocol):
    def obtener(self, relacion_id: int) -> Estado: ...
    def guardar(self, estado: Estado) -> None: ...


# ---------------------------------------------------------------------------
# Mensaje
# ---------------------------------------------------------------------------

@runtime_checkable
class RepositorioMensaje(Protocol):
    def guardar(self, mensaje: Mensaje) -> None: ...
    def listar_por_relacion(self, relacion_id: int, limite: Optional[int] = None) -> list[Mensaje]: ...


# ---------------------------------------------------------------------------
# Evento
# ---------------------------------------------------------------------------

@runtime_checkable
class RepositorioEvento(Protocol):
    def obtener(self, num: int) -> Evento: ...
    def guardar(self, evento: Evento) -> None: ...
    def listar_por_relacion(self, relacion_id: int) -> list[Evento]: ...


# ---------------------------------------------------------------------------
# Conflicto
# ---------------------------------------------------------------------------

@runtime_checkable
class RepositorioConflicto(Protocol):
    def obtener(self, num: int) -> Conflicto: ...
    def guardar(self, conflicto: Conflicto) -> None: ...
    def listar_por_relacion(self, relacion_id: int) -> list[Conflicto]: ...
    def listar_activos(self, relacion_id: int) -> list[Conflicto]: ...


# ---------------------------------------------------------------------------
# Recuerdo
# ---------------------------------------------------------------------------

@runtime_checkable
class RepositorioRecuerdo(Protocol):
    def obtener(self, num: int) -> Recuerdo: ...
    def guardar(self, recuerdo: Recuerdo) -> None: ...
    def listar_por_relacion(
        self,
        relacion_id: int,
        importancia_minima: float = 0.0,
        limite: Optional[int] = None,
    ) -> list[Recuerdo]: ...


# ---------------------------------------------------------------------------
# PerfilUsuario
# ---------------------------------------------------------------------------

@runtime_checkable
class RepositorioPerfilUsuario(Protocol):
    def obtener(self, num: int) -> PerfilUsuario: ...
    def obtener_por_clave(self, relacion_id: int, clave: str) -> Optional[PerfilUsuario]: ...
    def guardar(self, entrada: PerfilUsuario) -> None: ...
    def eliminar(self, num: int) -> None: ...
    def listar_por_relacion(
        self,
        relacion_id: int,
        confianza_minima: float = 0.0,
    ) -> list[PerfilUsuario]: ...
