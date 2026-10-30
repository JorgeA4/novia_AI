"""
Gestor de turno — orquesta el caso de uso principal del sistema.

Flujo de un turno:
    1. Recibir el mensaje del usuario.
    2. Guardar MENSAJE (rol: usuario).
    3. Calcular segundos desde la última interacción y aplicar decaimiento al ESTADO.
    4. Construir el contexto para el LLM.
    5. Llamar al LLM → obtener un único JSON con respuesta, estado emocional,
       deltas de relación, recuerdos candidatos y datos de perfil del usuario.
    6. Guardar MENSAJE (rol: personaje).
    7. Persistir el ESTADO decaído con las emociones inferidas.
    8. Persistir recuerdos y datos de perfil extraídos.
    9. Evaluar si hay transición de etapa elegible.
   10. Si hay impulso automático → aplicar transición y registrar EVENTO.
   11. Devolver la respuesta para que la interfaz la muestre.

Regla: este módulo no importa nada de interfaz ni de JSON/SQL directamente.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import NamedTuple, Optional

from aplicacion.cliente_llm import ClienteLLM, extraer_json_de_respuesta
from aplicacion.gestor_contexto import (
    construir_historial,
    construir_payload,
    construir_sistema,
)
from dominio.configuracion import cfg
from dominio.emociones import aplicar_presion_emocion_sobre_animo, decaer_estado
from dominio.modelos import Evento, Mensaje, PerfilUsuario, Recuerdo, Relacion
from dominio.relacion import (
    CondicionTransicion,
    DeltasRelacion,
    aplicar_deltas_turno,
    buscar_transicion_elegible,
    calcular_delta_disposicion,
)
from dominio.confianza import confianza_final_de, resolver_duplicado
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
        tension_max=None,
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
        catalogo_emociones = repos.catalogos.obtener_emociones()

        # --- 2. Guardar mensaje del usuario ---
        repos.mensaje.guardar(Mensaje(
            num=0,
            relacion_id=relacion_id,
            rol="usuario",
            contenido=texto_usuario,
            fecha=ahora,
        ))

        # --- 3. Decaimiento emocional (incluye deriva del sentimiento — Brecha 3) ---
        segundos = (ahora - estado.ultima_interaccion).total_seconds()
        if segundos > 0:
            estado = decaer_estado(estado, segundos, catalogo_emociones)

        # --- 4. Construir contexto ---
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

        # --- 5. Llamar al LLM (única llamada del turno) ---
        texto_llm = self._llm.completar(payload)
        turno = _parsear_respuesta_turno(texto_llm)

        respuesta = turno["respuesta"]

        # --- 6. Guardar respuesta del personaje ---
        repos.mensaje.guardar(Mensaje(
            num=0,
            relacion_id=relacion_id,
            rol="personaje",
            contenido=respuesta,
            fecha=ahora,
        ))

        # --- 7. Actualizar estado emocional ---
        codigos_emocion = {
            e.codigo for e in catalogo_emociones if e.capa in ("emocion", "cualquiera")
        }
        codigos_estado_animo = {
            e.codigo for e in catalogo_emociones if e.capa in ("estado_animo", "cualquiera")
        }

        emo_id = str(turno.get("emocion_id", "")).strip()
        emo_int = max(0.0, min(1.0, float(turno.get("emocion_intensidad", 0.5))))
        animo_id = str(turno.get("estado_animo_id", "")).strip()
        animo_int = max(0.0, min(1.0, float(turno.get("estado_animo_intensidad", 0.3))))

        if emo_id in codigos_emocion:
            # Brecha 1 + 2: la emoción empuja al estado_animo con presión acumulativa
            # moderada por el sentimiento. El estado_animo sugerido por el LLM no se
            # descarta — se usa como señal de referencia para verificar coherencia, pero
            # la posición real la decide la presión sobre el espacio de Russell.
            animo_id_final, animo_int_final = aplicar_presion_emocion_sobre_animo(
                estado, emo_id, emo_int, catalogo_emociones
            )
            estado = replace(
                estado,
                emocion_id=emo_id,
                emocion_intensidad=emo_int,
                estado_animo_id=animo_id_final,
                estado_animo_intensidad=animo_int_final,
            )

        estado = replace(estado, ultima_interaccion=ahora)
        repos.estado.guardar(estado)

        # --- 8a. Persistir deltas de relación ---
        def _extraer_delta(clave: str) -> float:
            v = turno.get(clave, 0.0)
            return max(-1.0, min(1.0, float(v)))

        deltas = DeltasRelacion(
            afecto=_extraer_delta("afecto"),
            confianza=_extraer_delta("confianza"),
            familiaridad=_extraer_delta("familiaridad"),
            tension=_extraer_delta("tension"),
            # disposicion se deriva de las tendencias de afecto y confianza
            # tras aplicar los deltas anteriores — se calcula abajo
        )

        # Aplicar primero los deltas del LLM para que afecto_delta y confianza_delta
        # reflejen el turno actual antes de calcular el impulso de disposicion
        relacion = aplicar_deltas_turno(relacion, deltas)
        delta_disposicion = calcular_delta_disposicion(relacion)
        deltas_disposicion = DeltasRelacion(disposicion=delta_disposicion)
        relacion = aplicar_deltas_turno(relacion, deltas_disposicion)

        impacto_neto = (deltas.afecto + deltas.confianza + deltas.familiaridad - deltas.tension) / 4.0
        repos.evento.guardar(Evento(
            num=0,
            relacion_id=relacion_id,
            tipo="interaccion",
            descripcion=(
                f"Interacción: afecto={deltas.afecto:+.2f} "
                f"conf={deltas.confianza:+.2f} "
                f"fam={deltas.familiaridad:+.2f} "
                f"tens={deltas.tension:+.2f} "
                f"disp={delta_disposicion:+.4f}"
            ),
            fecha=ahora,
            impacto=impacto_neto,
            resuelto=True,
        ))
        repos.relacion.guardar(relacion)

        # --- 8b. Persistir recuerdos extraídos ---
        vigencia = ahora + timedelta(days=cfg.recuerdos.vigencia_dias)
        for r in turno.get("recuerdos", []):
            try:
                repos.recuerdo.guardar(Recuerdo(
                    num=0,
                    relacion_id=relacion_id,
                    tipo=str(r.get("tipo", "episodico")),
                    contenido=str(r["contenido"]),
                    origen="llm",
                    importancia=max(0.0, min(1.0, float(r.get("importancia", 0.6)))),
                    fecha_creacion=ahora,
                    ultima_relevancia=ahora,
                    vigencia=vigencia,
                    embedding=None,
                ))
            except (KeyError, TypeError, ValueError):
                pass  # recuerdo malformado — ignorar silenciosamente

        # --- 8c. Persistir datos de perfil extraídos ---
        for p in turno.get("perfil", []):
            try:
                clave = str(p["clave"]).strip()
                valor = str(p["valor"]).strip()
                confianza_llm = max(0.0, min(1.0, float(p.get("confianza_llm", 0.7))))
                if not clave or not valor:
                    continue

                nueva = PerfilUsuario(
                    num=0,
                    relacion_id=relacion_id,
                    clave=clave,
                    valor=valor,
                    origen="llm",
                    confianza_llm=confianza_llm,
                )
                existente = repos.perfil_usuario.obtener_por_clave(relacion_id, clave)
                if existente is None:
                    repos.perfil_usuario.guardar(nueva)
                else:
                    ganadora, _ = resolver_duplicado(existente, nueva)
                    if ganadora.num != existente.num:
                        # La nueva gana: eliminar la existente y guardar la nueva
                        repos.perfil_usuario.eliminar(existente.num)
                        repos.perfil_usuario.guardar(nueva)
            except (KeyError, TypeError, ValueError):
                pass  # dato malformado — ignorar silenciosamente

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
                    impacto=cfg.transicion_etapa.impacto_evento,
                    resuelto=True,
                    etapa_desde_id=etapa_anterior,
                    etapa_hasta_id=etapa_nueva,
                ))
                transicion_aplicada = True

                sentimiento_nuevo = _sentimiento_para_etapa(etapa_nueva, catalogo_emociones)
                if sentimiento_nuevo is not None:
                    estado = replace(
                        estado,
                        sentimiento_id=sentimiento_nuevo.codigo,
                        sentimiento_intensidad=min(
                            1.0,
                            estado.sentimiento_intensidad + cfg.transicion_etapa.delta_sentimiento_al_avanzar,
                        ),
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
# Parseo de la respuesta unificada del LLM
# ---------------------------------------------------------------------------

def _parsear_respuesta_turno(texto: str) -> dict:
    """
    Intenta extraer el JSON estructurado de la respuesta del LLM.

    Si el LLM no devolvió JSON válido, usa el texto completo como respuesta
    y deja el resto de campos con valores neutros (fallback seguro).
    """
    datos = extraer_json_de_respuesta(texto)
    if isinstance(datos, dict) and "respuesta" in datos:
        return datos

    # Fallback: el LLM respondió en texto plano — conservar como respuesta,
    # no persistir ni emociones ni deltas ni recuerdos ni perfil este turno.
    return {
        "respuesta": texto,
        "emocion_id": "",
        "emocion_intensidad": 0.5,
        "estado_animo_id": "",
        "estado_animo_intensidad": 0.3,
        "afecto": 0.0,
        "confianza": 0.05,
        "familiaridad": 0.05,
        "tension": 0.0,
        "recuerdos": [],
        "perfil": [],
    }


# ---------------------------------------------------------------------------
# Transición de etapa — momento decisivo
# ---------------------------------------------------------------------------

def _es_momento_decisivo(
    llm: ClienteLLM,
    mensaje_usuario: str,
    respuesta_personaje: str,
    etapa_destino: str,
) -> bool:
    """
    Consulta al LLM si el intercambio actual representa un momento decisivo
    que justifica avanzar a la etapa `etapa_destino`.

    Es la única llamada auxiliar al LLM que permanece fuera del turno principal,
    porque solo se dispara ocasionalmente (modo "permiso") y su lógica es
    independiente del contexto del personaje.

    Devuelve False ante cualquier error para no forzar transiciones no deseadas.
    """
    _DESCRIPCIONES_ETAPA = {
        "conocidos":         "pasar de extraños a personas que se conocen",
        "amigos":            "pasar a ser amigos",
        "amigos_cercanos":   "pasar a ser amigos cercanos con confianza real",
        "interes_romantico": "surgir un interés romántico mutuo explícito",
        "pareja":            "decidir ser pareja, con una declaración o compromiso claro",
        "distanciamiento":   "distanciarse o alejarse emocionalmente",
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
# Sentimiento para etapa romántica
# ---------------------------------------------------------------------------

def _sentimiento_para_etapa(
    etapa_id: str,
    catalogo: "list[Emocion]",
) -> "Optional[Emocion]":
    """
    Devuelve la emoción de tipo sentimiento asociada a una etapa romántica,
    o None si la etapa no tiene sentimiento asignado.
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
