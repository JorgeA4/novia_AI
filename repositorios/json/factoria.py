"""
Factoría de repositorios JSON.

Punto de entrada único para construir todos los repositorios apuntando
al directorio de datos. La capa de aplicación recibe estas instancias
por inyección de dependencias.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from repositorios.json.catalogos_json import CatalogosJson
from repositorios.json.entidades_json import (
    EstadoJson,
    PersonajeJson,
    RelacionJson,
    UsuarioJson,
)
from repositorios.json.operaciones_json import (
    ConflictoJsonConEventos,
    EventoJson,
    MensajeJson,
    PerfilUsuarioJson,
    RecuerdoJson,
)


@dataclass
class Repositorios:
    """Contenedor con todos los repositorios instanciados."""
    catalogos: CatalogosJson
    personaje: PersonajeJson
    usuario: UsuarioJson
    relacion: RelacionJson
    estado: EstadoJson
    mensaje: MensajeJson
    evento: EventoJson
    conflicto: ConflictoJsonConEventos
    recuerdo: RecuerdoJson
    perfil_usuario: PerfilUsuarioJson


def crear_repositorios(directorio_datos: Path) -> Repositorios:
    """
    Construye todos los repositorios JSON apuntando a `directorio_datos`.

    Estructura esperada:
        directorio_datos/
        ├── catalogos/
        │   ├── emociones.json
        │   ├── etapas_relacion.json
        │   ├── transiciones_etapa.json
        │   ├── tipos_evento.json
        │   ├── mbti.json
        │   ├── eneagramas.json
        │   └── temperamentos.json
        ├── personajes.json
        ├── usuarios.json
        ├── relaciones.json
        ├── estados.json
        ├── mensajes.json
        ├── eventos.json
        ├── conflictos.json
        ├── recuerdos.json
        └── perfil_usuario.json
    """
    ruta_eventos = directorio_datos / "eventos.json"

    return Repositorios(
        catalogos=CatalogosJson(directorio_datos / "catalogos"),
        personaje=PersonajeJson(directorio_datos / "personajes.json"),
        usuario=UsuarioJson(directorio_datos / "usuarios.json"),
        relacion=RelacionJson(directorio_datos / "relaciones.json"),
        estado=EstadoJson(directorio_datos / "estados.json"),
        mensaje=MensajeJson(directorio_datos / "mensajes.json"),
        evento=EventoJson(ruta_eventos),
        conflicto=ConflictoJsonConEventos(
            directorio_datos / "conflictos.json", ruta_eventos
        ),
        recuerdo=RecuerdoJson(directorio_datos / "recuerdos.json"),
        perfil_usuario=PerfilUsuarioJson(directorio_datos / "perfil_usuario.json"),
    )
