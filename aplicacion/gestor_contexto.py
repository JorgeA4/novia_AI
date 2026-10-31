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
    instrucciones_llm: str | None = None,
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
        f"Perfil psicológico: {mbti.siglas} · {eneagrama.siglas} · {temperamento.nombre}"
    )

    # --- Valores y gustos ---
    if personaje.valores:
        secciones.append(f"Valores: {', '.join(personaje.valores)}")
    if personaje.gustos:
        secciones.append(f"Te gusta: {', '.join(personaje.gustos)}")
    if personaje.aversiones:
        secciones.append(f"No soportas: {', '.join(personaje.aversiones)}")

    # --- Estado relacional ---
    # Línea de tendencias: solo incluye las métricas con _delta significativo (≥ 0.01)
    tendencias: list[str] = []
    for nombre_campo, valor_delta in (
        ("confianza", relacion.confianza_delta),
        ("afecto",    relacion.afecto_delta),
        ("disp",      relacion.disposicion_delta),
    ):
        if abs(valor_delta) >= 0.01:
            tendencias.append(f"{nombre_campo}={valor_delta:+.2f}")

    linea_metricas = (
        f"métricas  confianza={relacion.confianza:.2f}  afecto={relacion.afecto:.2f}"
        f"  familiaridad={relacion.familiaridad:.2f}  tension={relacion.tension:.2f}"
        f"  disp={relacion.disposicion:.2f}"
    )
    linea_tendencias = (
        ("tendencia " + "  ".join(tendencias)) if tendencias else ""
    )

    bloque_relacion = f"RELACIÓN · etapa: {etapa.nombre}\n{linea_metricas}"
    if linea_tendencias:
        bloque_relacion += f"\n{linea_tendencias}"

    secciones.append(bloque_relacion)

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

    # --- Perfil de personas relevantes ---
    perfil_relevante = [
        p for p in perfil_usuario
        if confianza_final_de(p) >= CONFIANZA_MINIMA_PERFIL
    ]
    if perfil_relevante:
        # Agrupar por sujeto
        por_sujeto: dict[str, list[PerfilUsuario]] = {}
        for p in perfil_relevante:
            por_sujeto.setdefault(p.sujeto, []).append(p)

        bloques: list[str] = []
        # Orden preferente: usuario primero, personaje segundo, terceros al final
        orden = ["usuario", "personaje"] + sorted(
            s for s in por_sujeto if s not in ("usuario", "personaje")
        )
        for sujeto in orden:
            if sujeto not in por_sujeto:
                continue
            if sujeto == "usuario":
                etiqueta = nombre_usuario
            elif sujeto == "personaje":
                etiqueta = f"{personaje.nombre} (tú)"
            else:
                etiqueta = sujeto.replace("tercero:", "", 1)
            lineas = [f"    - {p.clave}: {p.valor}" for p in por_sujeto[sujeto]]
            bloques.append(f"  [{etiqueta}]\n" + "\n".join(lineas))

        secciones.append("Lo que sabes de las personas relevantes:\n" + "\n".join(bloques))

    # --- Instrucciones de comportamiento del usuario ---
    if instrucciones_llm:
        secciones.append(f"Instrucciones de comportamiento:\n{instrucciones_llm}")

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
        "  tension             (float -1.0–1.0) — cambio en la tensión (positivo = más tensión)\n"
        "  recuerdos           (array) — lista de recuerdos a guardar; vacía [] si no hay nada memorable\n"
        "  perfil              (array) — lista de datos factuales aprendidos del usuario; vacía [] si ninguno\n\n"
        "Guía para los deltas de relación (+0.3 = efecto notable positivo, 0.0 = sin cambio, "
        "-0.3 = efecto notable negativo). Las tres dimensiones son independientes.\n"
        "La familiaridad y la disposición a buscar contacto las calcula el sistema — no las incluyas en tu respuesta.\n\n"
        f"Valores válidos para emocion_id: {codigos_emocion}\n"
        f"Valores válidos para estado_animo_id: {codigos_estado_animo}\n"
        f"Valores válidos para emocion_asociada_id en recuerdos: neutro, {codigos_emocion}, {codigos_estado_animo}\n\n"
        "Formato de cada elemento en recuerdos:\n"
        "  {\n"
        "    \"tipo\": \"episodico\" | \"relacional\",\n"
        "    \"categoria\": \"hecho_puntual\" | \"rasgo\" | \"hito\" | \"estado_temporal\",\n"
        "    \"contenido\": \"...\",\n"
        "    \"importancia\": 0.5–1.0,\n"
        "    \"emocion_asociada_id\": \"<codigo>\",\n"
        "    \"emocion_asociada_intensidad\": 0.0–1.0\n"
        "  }\n\n"
        "  Categorías:\n"
        "    \"hecho_puntual\"   — algo que ocurrió una vez en un momento concreto\n"
        "    \"rasgo\"           — característica estable de una persona, cosa o lugar\n"
        "    \"hito\"            — evento que marcó la relación; irrepetible en este estado\n"
        "    \"estado_temporal\" — cómo estaba alguien o algo durante un periodo\n\n"
        "  Regla de formato para `contenido`: oración completa con sujeto explícito + verbo en pasado.\n"
        "  Si el sujeto eres tú, usa primera persona ('Admití que...', 'Sentí que...', 'Reconocí que...').\n"
        "  Si el sujeto es otra persona o cosa, nómbrala ('Jorge dijo que...', 'El clima estaba...').\n"
        "  No uses fragmentos ni frases sin verbo ('Le gusta leer' → incorrecto).\n\n"
        "  `emocion_asociada_id` es obligatorio: usa \"neutro\" si no hay carga emocional.\n"
        "  ANTES de añadir un recuerdo, comprueba la lista de recuerdos que ya tienes arriba.\n"
        "  Solo incluye un recuerdo si cumple LAS DOS condiciones:\n"
        "    1. El intercambio contiene algo concreto y singular (confesión, dato personal, momento emocional fuerte).\n"
        "    2. Ninguno de los recuerdos existentes ya cubre ese mismo hecho o emoción.\n"
        "  Si el hecho ya está registrado, devuelve recuerdos: [].\n"
        "  Máximo 2 por turno.\n\n"
        "Formato de cada elemento en perfil:\n"
        "  { \"sujeto\": \"usuario\"|\"personaje\"|\"tercero:<nombre>\", \"clave\": \"...\", \"valor\": \"...\", \"confianza_llm\": 0.5–1.0 }\n"
        "  `sujeto` indica de quién es el dato: \"usuario\" para el usuario, \"personaje\" para ti mismo,\n"
        "  \"tercero:<nombre>\" para cualquier otra persona mencionada (ej. \"tercero:mama\").\n"
        "  Solo incluye datos factuales explícitos (nombre, profesión, ciudad, hobby, edad…). "
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
