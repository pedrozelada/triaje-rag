"""Reglas deterministas de alerta (red flags) para el triaje.

Capa de seguridad independiente del LLM: las reglas NUNCA bajan el nivel
asignado por el modelo, solo pueden ELEVARLO. Si el LLM no produce un nivel
parseable pero una regla se activa, manda el nivel de la regla.

Escala Manchester (orden creciente de urgencia):
    azul < verde < amarillo < naranja < rojo

Todos los umbrales son constantes nombradas para facilitar su ajuste clínico.
"""

import re
from dataclasses import dataclass

from ai_service.models import DatosVitales

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

# SpO2 (%): hipoxemia
SPO2_ROJO = 90.0   # < 90 -> rojo (hipoxemia severa)
SPO2_NARANJA = 94.0  # < 94 (y >= 90) -> naranja (hipoxemia moderada)

# PA sistólica (mmHg): hipotensión
PAS_ROJO = 80.0    # < 80 -> rojo (shock)
PAS_NARANJA = 90.0  # < 90 (y >= 80) -> naranja

# Frecuencia cardíaca (bpm)
FC_ROJO_BAJA = 40.0
FC_ROJO_ALTA = 160.0
FC_NARANJA_ALTA = 140.0  # >= 140 (y <= 160) -> naranja
FC_NARANJA_BAJA = 45.0   # < 45 (y >= 40) -> naranja

# Temperatura (°C)
TEMP_ROJO_ALTA = 41.0
TEMP_ROJO_BAJA = 33.0
TEMP_NARANJA_ALTA = 40.0  # >= 40 (y < 41) -> naranja
TEMP_NARANJA_BAJA = 35.0  # < 35 (y >= 33) -> naranja

# Frecuencia respiratoria (rpm)
FR_ROJO_BAJA = 8.0
FR_ROJO_ALTA = 40.0
FR_NARANJA_ALTA = 30.0  # >= 30 (y <= 40) -> naranja
FR_NARANJA_BAJA = 12.0  # < 12 (y >= 8) -> naranja


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
    (r"dificultad\s+respiratoria|disnea|ahogo", "Dificultad respiratoria"),
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


def _alerta_sintomas(texto: str | None) -> list[Alerta]:
    if not texto:
        return []
    texto_normalizado = _normalizar(texto)
    alertas: list[Alerta] = []
    for patron, descripcion in _SINTOMAS_NARANJA:
        if re.search(patron, texto_normalizado):
            alertas.append(Alerta(nivel="naranja", descripcion=descripcion))
    return alertas


def evaluar_reglas(datos: DatosVitales, sintomas: str | None = None) -> list[Alerta]:
    """Evalúa todas las reglas deterministas sobre vitales + síntomas.

    Args:
        datos: Signos vitales (los campos None = no medidos no disparan reglas).
        sintomas: Descripción clínica libre (motivo + síntomas).

    Returns:
        Lista de alertas activadas (vacía si todo está dentro de parámetros).
    """
    alertas: list[Alerta] = []

    # --- SpO2 ---
    if datos.saturacion is not None:
        if datos.saturacion < SPO2_ROJO:
            alertas.append(Alerta("rojo", f"SpO2 {datos.saturacion}% (< {SPO2_ROJO:.0f}%): hipoxemia severa"))
        elif datos.saturacion < SPO2_NARANJA:
            alertas.append(Alerta("naranja", f"SpO2 {datos.saturacion}% (< {SPO2_NARANJA:.0f}%): hipoxemia moderada"))

    # --- PA sistólica ---
    if datos.presion_sistolica is not None:
        if datos.presion_sistolica < PAS_ROJO:
            alertas.append(Alerta("rojo", f"PA sistólica {datos.presion_sistolica} mmHg (< {PAS_ROJO:.0f}): hipotensión severa (shock)"))
        elif datos.presion_sistolica < PAS_NARANJA:
            alertas.append(Alerta("naranja", f"PA sistólica {datos.presion_sistolica} mmHg (< {PAS_NARANJA:.0f}): hipotensión moderada"))

    # --- Frecuencia cardíaca ---
    if datos.frecuencia_cardiaca is not None:
        if datos.frecuencia_cardiaca < FC_ROJO_BAJA or datos.frecuencia_cardiaca > FC_ROJO_ALTA:
            alertas.append(Alerta("rojo", f"FC {datos.frecuencia_cardiaca} bpm (fuera de {FC_ROJO_BAJA:.0f}-{FC_ROJO_ALTA:.0f}): bradicardia/taquicardia extrema"))
        elif datos.frecuencia_cardiaca >= FC_NARANJA_ALTA:
            alertas.append(Alerta("naranja", f"FC {datos.frecuencia_cardiaca} bpm (>= {FC_NARANJA_ALTA:.0f}): taquicardia severa"))
        elif datos.frecuencia_cardiaca < FC_NARANJA_BAJA:
            alertas.append(Alerta("naranja", f"FC {datos.frecuencia_cardiaca} bpm (< {FC_NARANJA_BAJA:.0f}): bradicardia"))

    # --- Temperatura ---
    if datos.temperatura is not None:
        if datos.temperatura >= TEMP_ROJO_ALTA or datos.temperatura < TEMP_ROJO_BAJA:
            alertas.append(Alerta("rojo", f"Temperatura {datos.temperatura:.1f} °C (>= {TEMP_ROJO_ALTA:.0f} o < {TEMP_ROJO_BAJA:.0f}): hiper/hipotermia severa"))
        elif datos.temperatura >= TEMP_NARANJA_ALTA:
            alertas.append(Alerta("naranja", f"Temperatura {datos.temperatura:.1f} °C (>= {TEMP_NARANJA_ALTA:.0f}): hiperpirexia"))
        elif datos.temperatura < TEMP_NARANJA_BAJA:
            alertas.append(Alerta("naranja", f"Temperatura {datos.temperatura:.1f} °C (< {TEMP_NARANJA_BAJA:.0f}): hipotermia"))

    # --- Frecuencia respiratoria ---
    if datos.frecuencia_respiratoria is not None:
        if datos.frecuencia_respiratoria < FR_ROJO_BAJA or datos.frecuencia_respiratoria > FR_ROJO_ALTA:
            alertas.append(Alerta("rojo", f"FR {datos.frecuencia_respiratoria} rpm (fuera de {FR_ROJO_BAJA:.0f}-{FR_ROJO_ALTA:.0f}): bradipnea/taquipnea extrema"))
        elif datos.frecuencia_respiratoria >= FR_NARANJA_ALTA:
            alertas.append(Alerta("naranja", f"FR {datos.frecuencia_respiratoria} rpm (>= {FR_NARANJA_ALTA:.0f}): taquipnea"))
        elif datos.frecuencia_respiratoria < FR_NARANJA_BAJA:
            alertas.append(Alerta("naranja", f"FR {datos.frecuencia_respiratoria} rpm (< {FR_NARANJA_BAJA:.0f}): bradipnea"))

    # --- Síntomas de alta precisión ---
    alertas.extend(_alerta_sintomas(sintomas))

    return alertas
