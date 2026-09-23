"""Rangos de referencia de signos vitales POR GRUPO ETARIO.

Motivación clínica
------------------
Los umbrales de los signos vitales NO son universales: lo que en un adulto es
taquipnea (FR 35 rpm) o taquicardia (FC 140 lpm) es FISIOLÓGICO en un lactante.
Aplicar umbrales estáticos de adulto a pacientes pediátricos genera falsos
positivos masivos (alertas rojas/naranjas espurias).

Por eso las reglas deterministas de seguridad (``red_flags``) parametrizan sus
umbrales según la edad del paciente, leída de la fecha de nacimiento.

Fuente de los umbrales
----------------------
Límites de evaluación urgente derivados de las tablas de referencia pediátrica
habituales (PALS/AHA) y de las NNAC para el primer nivel de atención. Están
expresados como umbrales de ALERTA (no como rangos "normales"): entre el rango
normal y el umbral de alerta existe una zona gris que las reglas no escalan.

Semántica de los umbrales (idéntica a la del módulo ``red_flags``)
------------------------------------------------------------------
Para un valor medido ``v``::

    v < rojo_baja    -> rojo
    v > rojo_alta    -> rojo
    v < naranja_baja -> naranja
    v >= naranja_alta -> naranja
    resto            -> sin alerta

El grupo ``ADULTO`` reproduce exactamente los umbrales históricos del sistema,
para no alterar el comportamiento ya validado en adultos.
"""

from dataclasses import dataclass
from typing import Optional

# --- Grupos etarios ---------------------------------------------------------

NEONATO = "neonato"
LACTANTE = "lactante"
PREESCOLAR = "preescolar"
ESCOLAR = "escolar"
ADOLESCENTE = "adolescente"
ADULTO = "adulto"
ADULTO_MAYOR = "adulto_mayor"

GRUPOS_ETARIOS: tuple[str, ...] = (
    NEONATO,
    LACTANTE,
    PREESCOLAR,
    ESCOLAR,
    ADOLESCENTE,
    ADULTO,
    ADULTO_MAYOR,
)

#: Grupos que exigen rangos pediátricos en el prompt y en las reglas.
GRUPOS_PEDIATRICOS: frozenset[str] = frozenset(
    {NEONATO, LACTANTE, PREESCOLAR, ESCOLAR, ADOLESCENTE}
)

#: Etiqueta legible (para UI, auditoría y prompt del LLM).
ETIQUETAS: dict[str, str] = {
    NEONATO: "Neonato (< 1 mes)",
    LACTANTE: "Lactante (1-11 meses)",
    PREESCOLAR: "Preescolar (1-5 años)",
    ESCOLAR: "Escolar (6-11 años)",
    ADOLESCENTE: "Adolescente (12-17 años)",
    ADULTO: "Adulto (18-64 años)",
    ADULTO_MAYOR: "Adulto mayor (≥ 65 años)",
}

#: Nombre corto para las descripciones de alerta.
NOMBRES_CORTOS: dict[str, str] = {
    NEONATO: "neonato",
    LACTANTE: "lactante",
    PREESCOLAR: "preescolar",
    ESCOLAR: "escolar",
    ADOLESCENTE: "adolescente",
    ADULTO: "adulto",
    ADULTO_MAYOR: "adulto mayor",
}


@dataclass(frozen=True)
class UmbralesVitales:
    """Umbrales de alerta bilaterales (bajos y altos) de un signo vital."""

    naranja_baja: float
    rojo_baja: float
    rojo_alta: float
    naranja_alta: float


@dataclass(frozen=True)
class UmbralesPresion:
    """Umbrales de hipotensión (solo por debajo; la hipertensión no es red flag)."""

    rojo: float
    naranja: float


# --- Frecuencia respiratoria (rpm) ------------------------------------------
# Normal: neonato 30-60 · lactante 25-50 · preescolar 20-30 · escolar 18-25
# · adolescente 12-20 · adulto 12-20.
# Los umbrales se fijan POR ENCIMA del límite superior normal para que un
# paciente en el borde de lo fisiológico (p. ej. FR 60 en un neonato) no
# dispare una alerta.
FR_POR_GRUPO: dict[str, UmbralesVitales] = {
    NEONATO: UmbralesVitales(naranja_baja=28, rojo_baja=20, rojo_alta=90, naranja_alta=70),
    LACTANTE: UmbralesVitales(naranja_baja=22, rojo_baja=14, rojo_alta=80, naranja_alta=60),
    PREESCOLAR: UmbralesVitales(naranja_baja=18, rojo_baja=12, rojo_alta=55, naranja_alta=40),
    ESCOLAR: UmbralesVitales(naranja_baja=14, rojo_baja=10, rojo_alta=45, naranja_alta=30),
    ADOLESCENTE: UmbralesVitales(naranja_baja=12, rojo_baja=8, rojo_alta=38, naranja_alta=26),
    ADULTO: UmbralesVitales(naranja_baja=12, rojo_baja=8, rojo_alta=40, naranja_alta=30),
    ADULTO_MAYOR: UmbralesVitales(naranja_baja=12, rojo_baja=8, rojo_alta=32, naranja_alta=24),
}

# --- Frecuencia cardíaca (bpm) ----------------------------------------------
# Normal en vigilia: neonato 100-180 · lactante 90-160 · preescolar 80-140
# · escolar 70-120 · adolescente 60-100 · adulto 60-100.
# Nota: FC 140 lpm es NORMAL en un lactante (fiebre/llanto) y no debe alertar.
FC_POR_GRUPO: dict[str, UmbralesVitales] = {
    NEONATO: UmbralesVitales(naranja_baja=90, rojo_baja=80, rojo_alta=220, naranja_alta=180),
    LACTANTE: UmbralesVitales(naranja_baja=90, rojo_baja=70, rojo_alta=220, naranja_alta=180),
    PREESCOLAR: UmbralesVitales(naranja_baja=80, rojo_baja=60, rojo_alta=200, naranja_alta=160),
    ESCOLAR: UmbralesVitales(naranja_baja=70, rojo_baja=50, rojo_alta=180, naranja_alta=140),
    ADOLESCENTE: UmbralesVitales(naranja_baja=55, rojo_baja=45, rojo_alta=170, naranja_alta=130),
    ADULTO: UmbralesVitales(naranja_baja=45, rojo_baja=40, rojo_alta=160, naranja_alta=140),
    ADULTO_MAYOR: UmbralesVitales(naranja_baja=50, rojo_baja=40, rojo_alta=150, naranja_alta=120),
}

# --- Presión arterial sistólica (mmHg) — hipotensión -------------------------
# Hipotensión pediátrica (PALS): PAS < 70 + 2·edad para 1-10 años.
PAS_POR_GRUPO: dict[str, UmbralesPresion] = {
    NEONATO: UmbralesPresion(rojo=60, naranja=70),
    LACTANTE: UmbralesPresion(rojo=70, naranja=80),
    PREESCOLAR: UmbralesPresion(rojo=75, naranja=85),
    ESCOLAR: UmbralesPresion(rojo=80, naranja=90),
    ADOLESCENTE: UmbralesPresion(rojo=90, naranja=100),
    ADULTO: UmbralesPresion(rojo=80, naranja=90),
    ADULTO_MAYOR: UmbralesPresion(rojo=90, naranja=100),
}


def clasificar_grupo_etario(edad_anios: int, edad_meses: Optional[int] = None) -> str:
    """Determina el grupo etario clínico del paciente.

    Args:
        edad_anios: Edad en años cumplidos (0 para menores de 1 año).
        edad_meses: Edad en meses cumplidos. Obligatoria para ``edad_anios == 0``
            (el primer mes de vida corresponde al grupo ``NEONATO``).

    Returns:
        Uno de los valores de :data:`GRUPOS_ETARIOS`.

    Examples:
        >>> clasificar_grupo_etario(0, 0)
        'neonato'
        >>> clasificar_grupo_etario(0, 6)
        'lactante'
        >>> clasificar_grupo_etario(40)
        'adulto'
        >>> clasificar_grupo_etario(70)
        'adulto_mayor'
    """
    if edad_anios > 0:
        meses = edad_anios * 12
    else:
        meses = edad_meses if edad_meses is not None else 0

    if meses < 1:
        return NEONATO
    if meses < 12:
        return LACTANTE

    anios = edad_anios if edad_anios > 0 else meses // 12
    if anios <= 5:
        return PREESCOLAR
    if anios <= 11:
        return ESCOLAR
    if anios <= 17:
        return ADOLESCENTE
    if anios <= 64:
        return ADULTO
    return ADULTO_MAYOR


def es_grupo_pediatrico(grupo: str) -> bool:
    """Indica si el grupo requiere rangos pediátricos (y no de adulto)."""
    return grupo in GRUPOS_PEDIATRICOS


def etiqueta_grupo(grupo: str) -> str:
    """Etiqueta legible del grupo etario (con su rango de edad)."""
    return ETIQUETAS.get(grupo, grupo)
