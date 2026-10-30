"""
Gestor de turno — orquesta el caso de uso principal del sistema.

Flujo de un turno:
    1. Recibir el mensaje del usuario.
    2. Guardar MENSAJE (rol: usuario).
    3. Calcular segundos desde la última interacción y aplicar decaimiento al ESTADO.
    4. Construir el contexto para el LLM.
    5. Llamar al LLM → obtener respuesta en texto.
    6. Guardar MENSAJE (rol: personaje).
    7. Persistir el ESTADO decaído.
    8. Evaluar si hay transición de etapa elegible.
    9. Si hay impulso automático → aplicar transición y registrar EVENTO.
   10. Devolver la respuesta para que la interfaz la muestre.

Regla: este módulo no importa nada de interfaz ni de JSON/SQL directamente.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import NamedTuple

from aplicacion.cliente_llm import ClienteLLM
from aplicacion.gestor_contexto import (
    construir_historial,
    construir_payload,
    construir_sistema,
)
from dominio.emociones import decaer_estado
from dominio.modelos import Evento, Mensaje, Relacion
from dominio.relacion import (
    CondicionTransicion,
    buscar_transicion_elegible,
)
from repositorios.json.factoria import Repositorios


# ---------------------------------------------------------------------------
# Condiciones de transición de etapa
# ---------------------------------------------------------------------------
# TODO: mover a un fichero de configuración o catálogo cuando el diseño
# de las condiciones exactas esté finalizado (ver logica_interna.md).

CONDICIONES_TRANSICION: list[CondicionTransicion] = [
    CondicionTransicion(
        desde_id="desconocidos",
        hasta_id="conocidos",
        familiaridad_min=0.20,
    ),
    CondicionTransicion(
        desde_id="conocidos",
        hasta_id="amigos",
        familiaridad_min=0.45,
        confianza_min=0.35,
    ),
    CondicionTransicion(
        desde_id="amigos",
        hasta_id="amigos_cercanos",
        confianza_min=0.55,
        afecto_min=0.50,
        tension_max=0.40,
    ),
    CondicionTransicion(
        desde_id="amigos_cercanos",
        hasta_id="interes_romantico",
        confianza_min=0.65,
        afecto_min=0.65,
        tension_max=0.25,
    ),
    CondicionTransicion(
        desde_id="interes_romantico",
        hasta_id="pareja",
        confianza_min=0.75,
        afecto_min=0.80,
        tension_max=0.20,
    ),
    # Retrocesos
    CondicionTransicion(
        desde_id="amigos",
        hasta_id="conocidos",
        tension_max=None,  # sin restricción — solo requiere evento
        afecto_min=None,
    ),
    CondicionTransicion(
        desde_id="pareja",
        hasta_id="distanciamiento",
        tension_max=None,
        afecto_min=None,
    ),
]


# ---------------------------------------------------------------------------
# Resultado del turno
# ---------------------------------------------------------------------------

class ResultadoTurno(NamedTuple):
    respuesta: str
    transicion_aplicada: bool
    etapa_anterior: str | None
    etapa_nueva: str | None


# ---------------------------------------------------------------------------
# Gestor de turno
# ---------------------------------------------------------------------------

class GestorTurno:
    def __init__(self, repos: Repositorios, cliente_llm: ClienteLLM) -> None:
        self._repos = repos
        self._llm = cliente_llm

    def procesar(self, relacion_id: int, texto_usuario: str) -> ResultadoTurno:
        """
        Procesa un turno completo de conversación y devuelve el resultado.
        """
        repos = self._repos
        ahora = datetime.now(timezone.utc).replace(tzinfo=None)

        # --- 1. Cargar entidades necesarias ---
        relacion = repos.relacion.obtener(relacion_id)
        personaje = repos.personaje.obtener(relacion.personaje_id)
        usuario = repos.usuario.obtener(relacion.usuario_id)
        estado = repos.estado.obtener(relacion_id)

        # --- 2. Guardar mensaje del usuario ---
        repos.mensaje.guardar(Mensaje(
            num=0,
            relacion_id=relacion_id,
            rol="usuario",
            contenido=texto_usuario,
            fecha=ahora,
        ))

        # --- 3. Decaimiento emocional ---
        segundos = (ahora - estado.ultima_interaccion).total_seconds()
        if segundos > 0:
            estado = decaer_estado(estado, segundos)

        # --- 4. Construir contexto ---
        catalogo_emociones = repos.catalogos.obtener_emociones()
        etapas = {e.codigo: e for e in repos.catalogos.obtener_etapas_relacion()}
        mbtis = {m.codigo: m for m in repos.catalogos.obtener_mbti()}
        eneagramas = {e.codigo: e for e in repos.catalogos.obtener_eneagramas()}
        temperamentos = {t.codigo: t for t in repos.catalogos.obtener_temperamentos()}

        mensajes_previos = repos.mensaje.listar_por_relacion(relacion_id)
        recuerdos = repos.recuerdo.listar_por_relacion(relacion_id)
        perfil = repos.perfil_usuario.listar_por_relacion(relacion_id)

        sistema = construir_sistema(
            personaje=personaje,
            relacion=relacion,
            estado=estado,
            etapa=etapas[relacion.etapa],
            mbti=mbtis[personaje.mbti_id],
            eneagrama=eneagramas[personaje.eneagrama_id],
            temperamento=temperamentos[personaje.temperamento_id],
            catalogo_emociones=catalogo_emociones,
            recuerdos=recuerdos,
            perfil_usuario=perfil,
            nombre_usuario=usuario.nombre,
        )
        historial = construir_historial(mensajes_previos)
        payload = construir_payload(sistema, historial, texto_usuario)

        # --- 5. Llamar al LLM ---
        respuesta = self._llm.completar(payload)

        # --- 6. Guardar respuesta del personaje ---
        repos.mensaje.guardar(Mensaje(
            num=0,
            relacion_id=relacion_id,
            rol="personaje",
            contenido=respuesta,
            fecha=ahora,
        ))

        # --- 7. Persistir estado decaído con timestamp actualizado ---
        estado = replace(estado, ultima_interaccion=ahora)
        repos.estado.guardar(estado)

        # --- 8 & 9. Evaluar y aplicar transición de etapa ---
        transicion_aplicada = False
        etapa_anterior = None
        etapa_nueva = None

        transiciones = repos.catalogos.obtener_transiciones_etapa()
        resultado_transicion = buscar_transicion_elegible(
            relacion, transiciones, CONDICIONES_TRANSICION
        )

        if resultado_transicion is not None:
            transicion, modo = resultado_transicion
            if modo == "impulso":
                etapa_anterior = relacion.etapa
                etapa_nueva = transicion.hasta_id

                # Actualizar etapa en la relación
                relacion = replace(relacion, etapa=etapa_nueva)
                repos.relacion.guardar(relacion)

                # Registrar el cambio de etapa como EVENTO
                repos.evento.guardar(Evento(
                    num=0,
                    relacion_id=relacion_id,
                    tipo="cambio_etapa",
                    descripcion=(
                        f"Transición automática: {etapa_anterior} → {etapa_nueva}"
                    ),
                    fecha=ahora,
                    impacto=0.2,
                    resuelto=True,
                    etapa_desde_id=etapa_anterior,
                    etapa_hasta_id=etapa_nueva,
                ))
                transicion_aplicada = True

        return ResultadoTurno(
            respuesta=respuesta,
            transicion_aplicada=transicion_aplicada,
            etapa_anterior=etapa_anterior,
            etapa_nueva=etapa_nueva,
        )
