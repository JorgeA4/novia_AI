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

from aplicacion.cliente_llm import ClienteLLM, extraer_json_de_respuesta
from aplicacion.gestor_contexto import (
    construir_historial,
    construir_payload,
    construir_sistema,
)
from dominio.emociones import decaer_estado
from dominio.modelos import Evento, Mensaje, Relacion
from dominio.relacion import (
    CondicionTransicion,
    DeltasRelacion,
    aplicar_deltas_turno,
    aplicar_impacto_evento,
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
    deltas_turno: DeltasRelacion


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

        # --- 8. Inferir deltas del turno y actualizar métricas de la relación ---
        deltas = _inferir_deltas_turno(self._llm, texto_usuario, respuesta)
        # Guardar el evento con el impacto neto (promedio de los 4 deltas) para trazabilidad
        impacto_neto = (deltas.afecto + deltas.confianza + deltas.familiaridad - deltas.tension) / 4.0
        evento_turno = Evento(
            num=0,
            relacion_id=relacion_id,
            tipo="interaccion",
            descripcion=(
                f"Interacción: afecto={deltas.afecto:+.2f} "
                f"conf={deltas.confianza:+.2f} "
                f"fam={deltas.familiaridad:+.2f} "
                f"tens={deltas.tension:+.2f}"
            ),
            fecha=ahora,
            impacto=impacto_neto,
            resuelto=True,
        )
        repos.evento.guardar(evento_turno)
        relacion = aplicar_deltas_turno(relacion, deltas)
        repos.relacion.guardar(relacion)

        # --- 9 & 10. Evaluar y aplicar transición de etapa ---
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
            deltas_turno=deltas,
        )


# ---------------------------------------------------------------------------
# Inferencia de deltas del turno
# ---------------------------------------------------------------------------

def _inferir_deltas_turno(
    llm: ClienteLLM,
    mensaje_usuario: str,
    respuesta_personaje: str,
) -> DeltasRelacion:
    """
    Pide al LLM que evalúe el intercambio y devuelva variaciones independientes
    para cada dimensión de la relación.

    Cada valor está en [-1.0, 1.0]. Se permiten combinaciones asimétricas:
    p.ej. confianza +0.3, familiaridad 0.0, tension +0.1, afecto -0.1.

    Devuelve DeltasRelacion(0.0, 0.05, 0.05, 0.0) como fallback si el LLM
    no devuelve JSON válido (interacción neutra con mínimo avance de familiaridad).
    """
    prompt = [
        {
            "role": "system",
            "content": (
                "Eres un evaluador de relaciones interpersonales. "
                "Analiza el siguiente intercambio entre un usuario y un personaje "
                "y devuelve ÚNICAMENTE un objeto JSON con estas cuatro claves "
                "(cada una es un float entre -1.0 y 1.0):\n\n"
                "  afecto:       cambio en el cariño/apego emocional\n"
                "  confianza:    cambio en la confianza y apertura mutua\n"
                "  familiaridad: cambio en la comodidad y conocimiento acumulado\n"
                "  tension:      cambio en la tensión o incomodidad (positivo = más tensión)\n\n"
                "Guía de valores:\n"
                "  +0.3  = efecto notable y positivo en esa dimensión\n"
                "   0.0  = sin cambio en esa dimensión\n"
                "  -0.3  = efecto notable y negativo en esa dimensión\n\n"
                "Las dimensiones son INDEPENDIENTES. Una conversación profunda puede subir "
                "confianza sin mover familiaridad. Un coqueteo puede subir afecto y tension "
                "a la vez. Una pregunta íntima puede subir confianza pero no afecto aún.\n\n"
                "Responde solo con el JSON, sin texto adicional."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Usuario: {mensaje_usuario}\n"
                f"Personaje: {respuesta_personaje}"
            ),
        },
    ]

    try:
        texto = llm.completar(prompt)
        datos = extraer_json_de_respuesta(texto)
        if isinstance(datos, dict):
            def _extraer(clave: str) -> float:
                v = datos.get(clave, 0.0)
                return max(-1.0, min(1.0, float(v)))
            return DeltasRelacion(
                afecto=_extraer("afecto"),
                confianza=_extraer("confianza"),
                familiaridad=_extraer("familiaridad"),
                tension=_extraer("tension"),
            )
    except Exception:
        pass

    # Fallback: interacción neutra con mínimo avance de familiaridad
    return DeltasRelacion(afecto=0.0, confianza=0.05, familiaridad=0.05, tension=0.0)
