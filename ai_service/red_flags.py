"""Reglas deterministas de alerta (red flags) para el triaje.

Capa de seguridad independiente del LLM: las reglas NUNCA bajan el nivel
asignado por el modelo, solo pueden ELEVARLO. Si el LLM no produce un nivel
parseable pero una regla se activa, manda el nivel de la regla.

Escala Manchester (orden creciente de urgencia):
    azul < verde < amarillo < naranja < rojo

Los umbrales de signos vitales NO son constantes: dependen del GRUPO ETARIO
(neonato, lactante, preescolar, escolar, adolescente, adulto, adulto mayor),
calculado desde la edad del paciente. Un lactante sano tiene FC 140 lpm y
FR 40 rpm; aplicarles los umbrales de adulto generaría falsos positivos
masivos. La tabla de umbrales vive en ``ai_service.rangos_pediatricos``.

Negación: las reglas de síntomas respetan que un hallazgo sea enunciado como
AUSENTE ("niega dolor torácico", "sin dificultad respiratoria", "no presenta
vómitos"). Un hallazgo negado de forma explícita no activa su alerta; un
hallazgo enunciado en afirmativo sigue activándola siempre.
"""

import re
from dataclasses import dataclass

from ai_service.models import DatosVitales
from ai_service.rangos_pediatricos import (
    ADULTO,
    FC_POR_GRUPO,
    FR_POR_GRUPO,
    NOMBRES_CORTOS,
    PAS_POR_GRUPO,
    UmbralesVitales,
    clasificar_grupo_etario,
)

# Orden Manchester: menor a mayor urgencia.
ORDEN_MANCHESTER = ("azul", "verde", "amarillo", "naranja", "rojo")
_POSICION = {nivel: i for i, nivel in enumerate(ORDEN_MANCHESTER)}


def nivel_maximo(a: str | None, b: str | None) -> str | None:
    """Devuelve el nivel más urgente de los dos (None-safe)."""
    if a is None:
        return b
    if b is None:
        return a
    return a if _POSICION[a] >= _POSICION[b] else b


# --- Umbrales de signos vitales (se evalúan solo si el valor fue medido) ---
#
# Semántica, para un valor medido `v`:
#     v < rojo_baja     -> rojo
#     v > rojo_alta     -> rojo
#     v < naranja_baja  -> naranja
#     v >= naranja_alta -> naranja
#     resto             -> sin alerta
#
# Las constantes siguientes son las del grupo ADULTO. Se conservan con su
# nombre histórico por compatibilidad de tests/objetos de configuración; el
# motor NO las usa directamente: consulta la tabla por grupo etario.

# SpO2 (%): hipoxemia. El umbral es común a todos los grupos etarios.
SPO2_ROJO = 90.0   # < 90 -> rojo (hipoxemia severa)
SPO2_NARANJA = 94.0  # < 94 (y >= 90) -> naranja (hipoxemia moderada)

# PA sistólica (mmHg): hipotensión (umbral del grupo ADULTO).
PAS_ROJO = PAS_POR_GRUPO[ADULTO].rojo
PAS_NARANJA = PAS_POR_GRUPO[ADULTO].naranja

# Frecuencia cardíaca (bpm) (umbrales del grupo ADULTO).
_FC_ADULTO = FC_POR_GRUPO[ADULTO]
FC_ROJO_BAJA = _FC_ADULTO.rojo_baja
FC_ROJO_ALTA = _FC_ADULTO.rojo_alta
FC_NARANJA_ALTA = _FC_ADULTO.naranja_alta
FC_NARANJA_BAJA = _FC_ADULTO.naranja_baja

# Temperatura (°C). El umbral es común a todos los grupos etarios.
TEMP_ROJO_ALTA = 41.0
TEMP_ROJO_BAJA = 33.0
TEMP_NARANJA_ALTA = 40.0  # >= 40 (y < 41) -> naranja
TEMP_NARANJA_BAJA = 35.0  # < 35 (y >= 33) -> naranja

# Frecuencia respiratoria (rpm) (umbrales del grupo ADULTO).
_FR_ADULTO = FR_POR_GRUPO[ADULTO]
FR_ROJO_BAJA = _FR_ADULTO.rojo_baja
FR_ROJO_ALTA = _FR_ADULTO.rojo_alta
FR_NARANJA_ALTA = _FR_ADULTO.naranja_alta
FR_NARANJA_BAJA = _FR_ADULTO.naranja_baja


@dataclass(frozen=True)
class Alerta:
    """Una regla de seguridad activada."""

    nivel: str          # nivel mínimo de Manchester que exige la regla
    descripcion: str    # texto legible para auditoría/UI


# Frases de alta precisión (evitan falsos positivos por menciones sueltas).
# Se normaliza el texto antes de buscar: minúsculas, sin tildes.
_SINTOMAS_NARANJA: tuple[tuple[str, str], ...] = (
    (r"dolor\s+tor[áa]cico", "Dolor torácico (posible síndrome coronario)"),
    (r"dolor\s+opresivo", "Dolor opresivo (posible síndrome coronario)"),
    (r"convulsion", "Convulsiones activas o recientes"),
    (r"inconsciente|sin\s+conciencia|no\s+responde", "Alteración de conciencia"),
    (r"sangrado\s+abundante|hemorragia\s+(abundante|masiva|activa)", "Sangrado abundante"),
    (
        r"dificultad\s+(?:respiratoria|para\s+respirar)|disnea|ahogo|falta\s+de\s+aire",
        "Dificultad respiratoria",
    ),
    (r"vomito\s+con\s+sangre|hematemesis|vomita\s+sangre", "Hematemesis (vómito con sangre)"),
    (r"heces\s+con\s+sangre|melena|sangre\s+en\s+heces", "Sangrado digestivo bajo"),
    (r"dolor\s+abdominal\s+(severo|intenso)", "Dolor abdominal severo"),
    (r"cefalea\s+(severa|intensa|sudden)|peor\s+dolor|dolor\s+de\s+cabeza\s+sever", "Cefalea severa de inicio brusco"),
    (r"rigidez\s+de\s+cuello", "Rigidez de cuello (posible meningitis)"),
    (r"no\s+orina|\b[áa]uria\b|orina\s+ausencia", "Anuria (ausencia de orina)"),
)


def _normalizar(texto: str) -> str:
    """Minúsculas y sin tildes para matching tolerante."""
    import unicodedata

    normalizado = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn")


# --- Negación explícita -----------------------------------------------------
# El texto clínico suele enunciar la AUSENCIA de un hallazgo ("niega dolor
# torácico"). Sin este tratamiento, el matching léxico activaría la alerta del
# hallazgo negado (falso positivo que eleva el nivel indebidamente).
#
# Alcance de la negación: hacia adelante, dentro de la cláusula y hasta que
# aparezca un cue afirmativo. Tres cuidados finos:
#   1) "sin embargo" es contraste, no ausencia: no actúa como cue.
#   2) el punto y coma corta el alcance, igual que el punto.
#   3) se revisan TODAS las menciones de un síntoma en la cláusula, para no
#      perder una mención afirmada que sigue a otra negada.

#: Cue de negación: invalida los hallazgos enunciados a continuación.
_CUES_NEGACION = re.compile(
    r"\bniega\w*|\bnega\w*|\bnegad\w*"
    r"|\bno\s+(?:presenta\w*|refiere\w*|tiene\w*|tuvo\w*|menciona\w*|reporta\w*"
    r"|se\s+acompa\w*|se\s+evidencia\w*|hay)\b"
    # "sin embargo" queda excluido: es un conector de contraste.
    r"|\bsin\b(?!\s+embargo\b)|\bausencia\s+de\b|\blibre\s+de\b|\bnegativo\s+para\b"
    r"|\bdescart\w*"
)

#: Cue de afirmación: si aparece ENTRE la negación y el hallazgo, rompe el
#: alcance de la negación ("niega vómitos PERO TIENE dolor torácico").
_CUES_AFIRMACION = re.compile(
    r"\b(?:presenta\w*|refiere\w*|tiene\w*|siente\w*|pero|aunque|"
    r"ahora|hoy|actualmente)\b"
)

#: Frontera de cláusula: el alcance de una negación nunca cruza estos signos.
#: Incluye ";" además de ".", "!", "?" y salto de línea: dos ideas separadas
#: por ";" no comparten alcance de negación.
_FRONTERA_CLAUSULA = re.compile(r"[^.!?;\n]+")


def _esta_negado(fragmento: str, pos_hallazgo: int) -> bool:
    """Indica si un hallazgo está enunciado como AUSENTE en su cláusula.

    El alcance de la negación es hacia adelante: solo anula hallazgos que
    aparecen después del cue, mientras no exista un cue afirmativo en medio.
    Así "niega dolor torácico" no dispara, pero "dolor torácico que no cede"
    (cue posterior al hallazgo) sí lo hace.

    Args:
        fragmento: cláusula normalizada (sin tildes, minúsculas).
        pos_hallazgo: posición inicial del hallazgo dentro del fragmento.

    Returns:
        True si el hallazgo está negado de forma explícita.
    """
    for cue in _CUES_NEGACION.finditer(fragmento):
        if cue.end() > pos_hallazgo:
            continue  # El cue aparece después del hallazgo: no lo niega.
        if not _CUES_AFIRMACION.search(fragmento, cue.end(), pos_hallazgo):
            return True
    return False


def _alerta_sintomas(texto: str | None) -> list[Alerta]:
    """Evalúa los patrones de síntomas respetando la negación explícita.

    El texto se evalúa cláusula por cláusula (separadas por ``. ; ! ?`` o
    salto de línea) para que una negación no alcance a otra oración:
    "Niega vómitos. Presenta dolor torácico." sí activa la alerta torácica.

    Dentro de cada cláusula se revisan TODAS las coincidencias de un patrón
    (no solo la primera): "niega dolor torácico, sin embargo presenta dolor
    torácico al caminar" debe activarse por la segunda mención, aunque la
    primera esté negada.
    """
    if not texto:
        return []
    texto_normalizado = _normalizar(texto)
    alertas: list[Alerta] = []
    descripciones_vistas: set[str] = set()

    for clausula in _FRONTERA_CLAUSULA.finditer(texto_normalizado):
        fragmento = clausula.group()
        for patron, descripcion in _SINTOMAS_NARANJA:
            if descripcion in descripciones_vistas:
                continue  # Una alerta por patrón, como máximo.
            for coincidencia in re.finditer(patron, fragmento):
                if not _esta_negado(fragmento, coincidencia.start()):
                    alertas.append(Alerta(nivel="naranja", descripcion=descripcion))
                    descripciones_vistas.add(descripcion)
                    break  # Ya se activó este patrón; no hace falta seguir.

    return alertas


def _alerta_umbrales(
    valor: float,
    umbrales: UmbralesVitales,
    nombre: str,
    unidad: str,
    corto: str,
    etiqueta_baja: str,
    etiqueta_alta: str,
) -> list[Alerta]:
    """Aplica umbrales bilaterales (bajos y altos) a un signo vital.

    Args:
        valor: Valor medido del signo vital.
        umbrales: Umbrales del grupo etario del paciente.
        nombre: Nombre del signo vital para la descripción.
        unidad: Unidad de medida.
        corto: Nombre corto del grupo etario ("lactante", "adulto", ...).
        etiqueta_baja: Descripción del hallazgo por debajo del rango.
        etiqueta_alta: Descripción del hallazgo por encima del rango.

    Returns:
        Alertas activadas (0 o 1): las reglas son mutuamente excluyentes.
    """
    if valor < umbrales.rojo_baja or valor > umbrales.rojo_alta:
        return [
            Alerta(
                "rojo",
                f"{nombre} {valor:g} {unidad} (fuera de {umbrales.rojo_baja:.0f}-{umbrales.rojo_alta:.0f}"
                f"): {etiqueta_baja}/{etiqueta_alta} extrema en {corto}",
            )
        ]
    if valor >= umbrales.naranja_alta:
        return [
            Alerta(
                "naranja",
                f"{nombre} {valor:g} {unidad} (>= {umbrales.naranja_alta:.0f}): "
                f"{etiqueta_alta} en {corto}",
            )
        ]
    if valor < umbrales.naranja_baja:
        return [
            Alerta(
                "naranja",
                f"{nombre} {valor:g} {unidad} (< {umbrales.naranja_baja:.0f}): "
                f"{etiqueta_baja} en {corto}",
            )
        ]
    return []


def evaluar_reglas(datos: DatosVitales, sintomas: str | None = None) -> list[Alerta]:
    """Evalúa todas las reglas deterministas sobre vitales + síntomas.

    Los umbrales de los signos vitales se eligen según el GRUPO ETARIO del
    paciente (calculado desde ``edad`` y ``edad_meses``), de modo que un
    lactante con FC 140 bpm o FR 40 rpm no dispare alertas espurias.

    Args:
        datos: Signos vitales (los campos None = no medidos no disparan reglas).
        sintomas: Descripción clínica libre (motivo + síntomas).

    Returns:
        Lista de alertas activadas (vacía si todo está dentro de parámetros).
    """
    alertas: list[Alerta] = []

    grupo = clasificar_grupo_etario(datos.edad, datos.edad_meses)
    corto = NOMBRES_CORTOS.get(grupo, grupo)

    # --- SpO2 (umbral común a todos los grupos etarios) ---
    if datos.saturacion is not None:
        if datos.saturacion < SPO2_ROJO:
            alertas.append(Alerta("rojo", f"SpO2 {datos.saturacion}% (< {SPO2_ROJO:.0f}%): hipoxemia severa"))
        elif datos.saturacion < SPO2_NARANJA:
            alertas.append(Alerta("naranja", f"SpO2 {datos.saturacion}% (< {SPO2_NARANJA:.0f}%): hipoxemia moderada"))

    # --- PA sistólica (hipotensión; umbral por grupo etario) ---
    if datos.presion_sistolica is not None:
        pas = PAS_POR_GRUPO[grupo]
        if datos.presion_sistolica < pas.rojo:
            alertas.append(Alerta(
                "rojo",
                f"PA sistólica {datos.presion_sistolica} mmHg (< {pas.rojo:.0f}): "
                f"hipotensión severa (shock) en {corto}",
            ))
        elif datos.presion_sistolica < pas.naranja:
            alertas.append(Alerta(
                "naranja",
                f"PA sistólica {datos.presion_sistolica} mmHg (< {pas.naranja:.0f}): "
                f"hipotensión moderada en {corto}",
            ))

    # --- Frecuencia cardíaca (umbral por grupo etario) ---
    if datos.frecuencia_cardiaca is not None:
        alertas.extend(_alerta_umbrales(
            float(datos.frecuencia_cardiaca),
            FC_POR_GRUPO[grupo],
            "FC",
            "bpm",
            corto,
            "bradicardia",
            "taquicardia",
        ))

    # --- Temperatura (umbral común a todos los grupos etarios) ---
    if datos.temperatura is not None:
        if datos.temperatura >= TEMP_ROJO_ALTA or datos.temperatura < TEMP_ROJO_BAJA:
            alertas.append(Alerta("rojo", f"Temperatura {datos.temperatura:.1f} °C (>= {TEMP_ROJO_ALTA:.0f} o < {TEMP_ROJO_BAJA:.0f}): hiper/hipotermia severa"))
        elif datos.temperatura >= TEMP_NARANJA_ALTA:
            alertas.append(Alerta("naranja", f"Temperatura {datos.temperatura:.1f} °C (>= {TEMP_NARANJA_ALTA:.0f}): hiperpirexia"))
        elif datos.temperatura < TEMP_NARANJA_BAJA:
            alertas.append(Alerta("naranja", f"Temperatura {datos.temperatura:.1f} °C (< {TEMP_NARANJA_BAJA:.0f}): hipotermia"))

    # --- Frecuencia respiratoria (umbral por grupo etario) ---
    if datos.frecuencia_respiratoria is not None:
        alertas.extend(_alerta_umbrales(
            float(datos.frecuencia_respiratoria),
            FR_POR_GRUPO[grupo],
            "FR",
            "rpm",
            corto,
            "bradipnea",
            "taquipnea",
        ))

    # --- Síntomas de alta precisión ---
    alertas.extend(_alerta_sintomas(sintomas))

    return alertas
