"""
Gestor de contexto — construye el payload que recibe el LLM en cada turno.

El LLM nunca recibe vectores numéricos ni estados crudos. Solo recibe
lenguaje natural + nombre de emoción inferido.

Estructura del contexto que se construye:
    - system: instrucción de personaje (psicología, valores, etapa, emoción actual)
    - history: últimos N mensajes de la conversación
"""

from __future__ import annotations

from dominio.emociones import calcular_emocion_actual
from dominio.modelos import (
    Emocion,
    Eneagrama,
    EtapaRelacion,
    Mbti,
    Mensaje,
    PerfilUsuario,
    Personaje,
    Recuerdo,
    Relacion,
    Estado,
    Temperamento,
)
from dominio.confianza import confianza_final_de

# Número máximo de mensajes del historial que se envían al LLM
LIMITE_HISTORIAL: int = 20

# Importancia mínima para incluir un recuerdo en el contexto
IMPORTANCIA_MINIMA_RECUERDO: float = 0.4

# Número máximo de recuerdos incluidos en el contexto
LIMITE_RECUERDOS: int = 5

# Confianza mínima para incluir un dato de PERFIL_USUARIO en el contexto
CONFIANZA_MINIMA_PERFIL: float = 0.5


def construir_sistema(
    personaje: Personaje,
    relacion: Relacion,
    estado: Estado,
    etapa: EtapaRelacion,
    mbti: Mbti,
    eneagrama: Eneagrama,
    temperamento: Temperamento,
    catalogo_emociones: list[Emocion],
    recuerdos: list[Recuerdo],
    perfil_usuario: list[PerfilUsuario],
    nombre_usuario: str,
) -> str:
    """
    Construye el mensaje de sistema que define al personaje para el LLM.

    Incluye:
        - Identidad y psicología del personaje
        - Etapa y métricas actuales de la relación
        - Emoción actual (nombre, no vectores)
        - Recuerdos relevantes
        - Datos conocidos del usuario (alta confianza)
        - Instrucción de formato JSON unificado para la respuesta
    """
    emocion_actual = calcular_emocion_actual(estado, catalogo_emociones)

    secciones: list[str] = []

    # --- Identidad ---
    secciones.append(
        f"Eres {personaje.nombre}. {personaje.descripcion}\n"
        f"Historia: {personaje.historia}"
    )

    # --- Psicología ---
    secciones.append(
        f"Perfil psicológico:\n"
        f"  - MBTI: {mbti.siglas} — {mbti.descripcion}\n"
        f"  - Eneagrama: {eneagrama.siglas} — {eneagrama.descripcion}\n"
        f"  - Temperamento: {temperamento.nombre} — {temperamento.descripcion}"
    )

    # --- Valores y gustos ---
    if personaje.valores:
        secciones.append(f"Valores: {', '.join(personaje.valores)}")
    if personaje.gustos:
        secciones.append(f"Te gusta: {', '.join(personaje.gustos)}")
    if personaje.aversiones:
        secciones.append(f"No soportas: {', '.join(personaje.aversiones)}")

    # --- Estado relacional ---
    secciones.append(
        f"Tu relación con {nombre_usuario} está en etapa: {etapa.nombre}.\n"
        f"  Confianza: {relacion.confianza:.2f} | "
        f"Afecto: {relacion.afecto:.2f} | "
        f"Familiaridad: {relacion.familiaridad:.2f} | "
        f"Tensión: {relacion.tension:.2f}"
    )

    # --- Estado emocional actual ---
    secciones.append(
        f"En este momento sientes: {emocion_actual.nombre}."
    )

    # --- Recuerdos relevantes ---
    recuerdos_relevantes = [
        r for r in recuerdos
        if r.importancia >= IMPORTANCIA_MINIMA_RECUERDO
    ][:LIMITE_RECUERDOS]

    if recuerdos_relevantes:
        lineas = [f"  - {r.contenido}" for r in recuerdos_relevantes]
        secciones.append("Recuerdas sobre esta relación:\n" + "\n".join(lineas))

    # --- Perfil del usuario ---
    perfil_relevante = [
        p for p in perfil_usuario
        if confianza_final_de(p) >= CONFIANZA_MINIMA_PERFIL
    ]
    if perfil_relevante:
        lineas = [f"  - {p.clave}: {p.valor}" for p in perfil_relevante]
        secciones.append(f"Lo que sabes de {nombre_usuario}:\n" + "\n".join(lineas))

    # --- Instrucción de formato de respuesta ---
    codigos_emocion = ", ".join(
        e.codigo for e in catalogo_emociones if e.capa in ("emocion", "cualquiera")
    )
    codigos_estado_animo = ", ".join(
        e.codigo for e in catalogo_emociones if e.capa in ("estado_animo", "cualquiera")
    )
    secciones.append(
        "FORMATO DE RESPUESTA OBLIGATORIO — responde SIEMPRE con un único objeto JSON "
        "con exactamente estas claves (sin texto antes ni después):\n\n"
        "  respuesta           (string) — tu respuesta en primera persona como el personaje\n"
        "  emocion_id          (string) — emoción inmediata que sientes al terminar este turno\n"
        "  emocion_intensidad  (float 0.0–1.0) — intensidad de esa emoción\n"
        "  estado_animo_id     (string) — tono emocional de fondo que te queda\n"
        "  estado_animo_intensidad (float 0.0–1.0) — intensidad del estado de ánimo\n"
        "  afecto              (float -1.0–1.0) — cambio en el cariño/apego emocional\n"
        "  confianza           (float -1.0–1.0) — cambio en la confianza y apertura mutua\n"
        "  familiaridad        (float -1.0–1.0) — cambio en la comodidad y conocimiento acumulado\n"
        "  tension             (float -1.0–1.0) — cambio en la tensión (positivo = más tensión)\n"
        "  recuerdos           (array) — lista de recuerdos a guardar; vacía [] si no hay nada memorable\n"
        "  perfil              (array) — lista de datos factuales aprendidos del usuario; vacía [] si ninguno\n\n"
        "Guía para los deltas de relación (+0.3 = efecto notable positivo, 0.0 = sin cambio, "
        "-0.3 = efecto notable negativo). Las cuatro dimensiones son independientes.\n\n"
        f"Valores válidos para emocion_id: {codigos_emocion}\n"
        f"Valores válidos para estado_animo_id: {codigos_estado_animo}\n\n"
        "Formato de cada elemento en recuerdos:\n"
        "  { \"tipo\": \"episodico\" | \"relacional\", \"contenido\": \"...\", \"importancia\": 0.5–1.0 }\n"
        "  Solo incluye un recuerdo si el intercambio contiene algo concreto y singular "
        "(una confesión, un dato personal, un momento emocional fuerte). Máximo 2 por turno.\n\n"
        "Formato de cada elemento en perfil:\n"
        "  { \"clave\": \"...\", \"valor\": \"...\", \"confianza_llm\": 0.5–1.0 }\n"
        "  Solo incluye datos factuales explícitos del usuario (nombre, profesión, ciudad, hobby…). "
        "0.9 = lo dijo directamente, 0.5 = se infirió del contexto."
    )

    return "\n\n".join(secciones)


def construir_historial(mensajes: list[Mensaje]) -> list[dict[str, str]]:
    """
    Convierte los últimos LIMITE_HISTORIAL mensajes al formato {role, content}
    que espera la API del LLM.

        rol "usuario"   → role "user"
        rol "personaje" → role "assistant"
    """
    ultimos = mensajes[-LIMITE_HISTORIAL:]
    mapa_rol = {"usuario": "user", "personaje": "assistant"}
    return [
        {"role": mapa_rol.get(m.rol, "user"), "content": m.contenido}
        for m in ultimos
    ]


def construir_payload(
    sistema: str,
    historial: list[dict[str, str]],
    mensaje_nuevo: str,
) -> list[dict[str, str]]:
    """
    Ensambla el payload completo listo para enviar al LLM:
        [system] + historial + mensaje_nuevo del usuario
    """
    payload: list[dict[str, str]] = [{"role": "system", "content": sistema}]
    payload.extend(historial)
    payload.append({"role": "user", "content": mensaje_nuevo})
    return payload
