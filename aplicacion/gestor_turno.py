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
from typing import NamedTuple, Optional

from aplicacion.cliente_llm import ClienteLLM, extraer_json_de_respuesta
from aplicacion.gestor_contexto import (
    construir_historial,
    construir_payload,
    construir_sistema,
)
from dominio.emociones import aplicar_inercia_estado_animo, decaer_estado
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

        # --- 7. Inferir estado emocional resultante y persistir ---
        catalogo_solo_emociones = catalogo_emociones  # ya cargado en paso 4
        nuevo_estado = _inferir_estado_emocional(
            self._llm, texto_usuario, respuesta, estado, catalogo_solo_emociones
        )
        nuevo_estado = replace(nuevo_estado, ultima_interaccion=ahora)
        repos.estado.guardar(nuevo_estado)
        estado = nuevo_estado

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

            # Decidir si se aplica la transición:
            #   "impulso"  → las métricas superan los umbrales con margen amplio: avance automático
            #   "permiso"  → las métricas superan los umbrales justo; solo avanzar si el LLM
            #                confirma que este turno fue un momento decisivo en la relación
            debe_avanzar = (modo == "impulso") or (
                modo == "permiso"
                and _es_momento_decisivo(self._llm, texto_usuario, respuesta, transicion.hasta_id)
            )

            if debe_avanzar:
                etapa_anterior = relacion.etapa
                etapa_nueva = transicion.hasta_id

                relacion = replace(relacion, etapa=etapa_nueva)
                repos.relacion.guardar(relacion)

                repos.evento.guardar(Evento(
                    num=0,
                    relacion_id=relacion_id,
                    tipo="cambio_etapa",
                    descripcion=(
                        f"Transición {'automática' if modo == 'impulso' else 'por momento decisivo'}: "
                        f"{etapa_anterior} → {etapa_nueva}"
                    ),
                    fecha=ahora,
                    impacto=0.2,
                    resuelto=True,
                    etapa_desde_id=etapa_anterior,
                    etapa_hasta_id=etapa_nueva,
                ))
                transicion_aplicada = True

                # Actualizar sentimiento cuando la etapa avanza a una romántica
                sentimiento_nuevo = _sentimiento_para_etapa(etapa_nueva, catalogo_emociones)
                if sentimiento_nuevo is not None:
                    estado = replace(
                        estado,
                        sentimiento_id=sentimiento_nuevo.codigo,
                        sentimiento_intensidad=min(1.0, estado.sentimiento_intensidad + 0.2),
                    )
                    repos.estado.guardar(estado)

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


def _es_momento_decisivo(
    llm: ClienteLLM,
    mensaje_usuario: str,
    respuesta_personaje: str,
    etapa_destino: str,
) -> bool:
    """
    Consulta al LLM si el intercambio actual representa un momento decisivo
    que justifica avanzar a la etapa `etapa_destino`.

    Se usa cuando la transición está en modo "permiso": las métricas ya
    superan los umbrales, pero la etapa es delicada (ej. interes_romantico
    → pareja) y no debe avanzar por simple acumulación pasiva — requiere
    que haya ocurrido algo concreto y significativo en el texto.

    Devuelve False ante cualquier error para no forzar transiciones no deseadas.
    """
    _DESCRIPCIONES_ETAPA = {
        "conocidos":        "pasar de extraños a personas que se conocen",
        "amigos":           "pasar a ser amigos",
        "amigos_cercanos":  "pasar a ser amigos cercanos con confianza real",
        "interes_romantico":"surgir un interés romántico mutuo explícito",
        "pareja":           "decidir ser pareja, con una declaración o compromiso claro",
        "distanciamiento":  "distanciarse o alejarse emocionalmente",
    }
    descripcion = _DESCRIPCIONES_ETAPA.get(etapa_destino, f"avanzar a la etapa '{etapa_destino}'")

    prompt = [
        {
            "role": "system",
            "content": (
                "Eres un analista de relaciones interpersonales. "
                "Analiza el siguiente intercambio y responde ÚNICAMENTE con un objeto JSON "
                "con la clave 'decisivo' (true o false).\n\n"
                f"Pregunta: ¿Este intercambio representa un momento claro de '{descripcion}'? "
                "Solo responde true si hay evidencia explícita en el texto "
                "(palabras, gestos, confesiones, decisiones concretas). "
                "Si el intercambio es positivo pero ordinario, responde false.\n\n"
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
        if isinstance(datos, dict) and "decisivo" in datos:
            return bool(datos["decisivo"])
    except Exception:
        pass

    return False


# ---------------------------------------------------------------------------
# Inferencia de estado emocional tras el turno
# ---------------------------------------------------------------------------

def _inferir_estado_emocional(
    llm: ClienteLLM,
    mensaje_usuario: str,
    respuesta_personaje: str,
    estado_actual: "Estado",
    catalogo: "list[Emocion]",
) -> "Estado":
    """
    Pide al LLM que evalúe qué emoción inmediata y qué estado de ánimo de fondo
    quedaron en el personaje tras el intercambio.

    Capas y reglas de actualización:
      - emocion:      se reemplaza directamente — es la respuesta inmediata del momento,
                      puede cambiar por completo en un solo turno (ej. una carcajada).
      - estado_animo: se actualiza con INERCIA — es el tono de fondo (horas/días),
                      no puede borrarse de golpe por un turno positivo si venía negativo.
                      Se interpola 25% hacia el nuevo valor por turno.
      - sentimiento:  no se toca aquí — solo cambia ante eventos muy significativos.

    Valida que los códigos existan en el catálogo con la capa correcta.
    Si la validación falla, conserva el estado actual sin cambios.
    """
    from dominio.modelos import Emocion, Estado

    codigos_emocion = {
        e.codigo: e for e in catalogo if e.capa in ("emocion", "cualquiera")
    }
    codigos_estado_animo = {
        e.codigo: e for e in catalogo if e.capa in ("estado_animo", "cualquiera")
    }

    lista_emocion = ", ".join(codigos_emocion.keys())
    lista_estado_animo = ", ".join(codigos_estado_animo.keys())

    prompt = [
        {
            "role": "system",
            "content": (
                "Eres un analista emocional. Analiza el siguiente intercambio "
                "y determina qué siente el PERSONAJE (no el usuario) al terminar.\n\n"
                "Devuelve ÚNICAMENTE un objeto JSON con estas claves:\n"
                "  emocion_id:              emoción inmediata del momento (string)\n"
                "  emocion_intensidad:      intensidad de esa emoción, float [0.0, 1.0]\n"
                "  estado_animo_id:         tono emocional de fondo que queda (string)\n"
                "  estado_animo_intensidad: intensidad del estado de ánimo, float [0.0, 1.0]\n\n"
                f"Valores válidos para emocion_id: {lista_emocion}\n"
                f"Valores válidos para estado_animo_id: {lista_estado_animo}\n\n"
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
            emo_id = str(datos.get("emocion_id", "")).strip()
            emo_int = max(0.0, min(1.0, float(datos.get("emocion_intensidad", 0.5))))
            animo_id = str(datos.get("estado_animo_id", "")).strip()
            animo_int = max(0.0, min(1.0, float(datos.get("estado_animo_intensidad", 0.3))))

            # Validar que los códigos existen en el catálogo con la capa correcta
            if emo_id not in codigos_emocion or animo_id not in codigos_estado_animo:
                return estado_actual  # conservar estado si código inválido

            # emocion: reemplazo directo (capa inmediata — puede cambiar en un turno)
            # estado_animo: inercia — se interpola hacia el nuevo valor, no se reemplaza
            animo_id_final, animo_int_final = aplicar_inercia_estado_animo(
                estado_actual, animo_id, animo_int, catalogo
            )

            return replace(
                estado_actual,
                emocion_id=emo_id,
                emocion_intensidad=emo_int,
                estado_animo_id=animo_id_final,
                estado_animo_intensidad=animo_int_final,
            )
    except Exception:
        pass

    return estado_actual


def _sentimiento_para_etapa(
    etapa_id: str,
    catalogo: "list[Emocion]",
) -> "Optional[Emocion]":
    """
    Devuelve la emoción de tipo sentimiento asociada a una etapa romántica,
    o None si la etapa no tiene sentimiento asignado.

    Se usa cuando hay una transición de etapa para subir gradualmente
    el sentimiento profundo del personaje.
    """
    from dominio.modelos import Emocion

    _ETAPA_A_SENTIMIENTO = {
        "amigos_cercanos":   "carino",
        "interes_romantico": "carino",
        "pareja":            "amor",
    }
    codigo = _ETAPA_A_SENTIMIENTO.get(etapa_id)
    if codigo is None:
        return None
    for e in catalogo:
        if e.codigo == codigo:
            return e
    return None
