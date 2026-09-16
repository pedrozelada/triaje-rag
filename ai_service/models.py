"""Modelos de datos para el sistema de triaje."""

from dataclasses import dataclass, asdict
from typing import Optional

# Rangos fisiológicos canónicos (únicos para toda la app; el espejo de estos
# límites vive en backend/schemas/triage.py para la validación HTTP).
RANGO_TEMPERATURA = (30.0, 45.0)
RANGO_PRESION_SISTOLICA = (40, 300)
RANGO_PRESION_DIASTOLICA = (20, 200)
RANGO_FRECUENCIA_CARDIACA = (20, 300)
RANGO_FRECUENCIA_RESPIRATORIA = (4, 80)
RANGO_SATURACION = (50, 100)


@dataclass
class DatosVitales:
    """Signos vitales del paciente para triaje médico.

    Los campos Optional representan valores NO medidos (`None`). Nunca se
    sustituyen por valores normales por defecto: el prompt muestra
    "No registrado" para que el LLM no reciba datos inventados.
    """

    edad: int
    sexo: str  # M, F, Otro
    temperatura: Optional[float] = None
    presion_sistolica: Optional[int] = None
    presion_diastolica: Optional[int] = None
    frecuencia_cardiaca: Optional[int] = None
    frecuencia_respiratoria: Optional[int] = None
    saturacion: Optional[float] = None

    @staticmethod
    def _en_rango(valor: Optional[float], rango: tuple[float, float]) -> bool:
        if valor is None:
            return True  # No medido: no es inválido.
        minimo, maximo = rango
        return minimo <= valor <= maximo

    def es_valido(self) -> bool:
        """Valida los valores presentes (los ausentes no invalidan el triaje)."""
        if not (0 < self.edad < 150):
            return False

        if self.sexo not in ["M", "F", "Otro"]:
            return False

        if not self._en_rango(self.temperatura, RANGO_TEMPERATURA):
            return False

        if not self._en_rango(self.presion_sistolica, RANGO_PRESION_SISTOLICA):
            return False

        if not self._en_rango(self.presion_diastolica, RANGO_PRESION_DIASTOLICA):
            return False

        # PA sistólica debe superar a la diastólica cuando ambas existen.
        if (
            self.presion_sistolica is not None
            and self.presion_diastolica is not None
            and self.presion_sistolica <= self.presion_diastolica
        ):
            return False

        if not self._en_rango(self.frecuencia_cardiaca, RANGO_FRECUENCIA_CARDIACA):
            return False

        if not self._en_rango(self.frecuencia_respiratoria, RANGO_FRECUENCIA_RESPIRATORIA):
            return False

        if not self._en_rango(self.saturacion, RANGO_SATURACION):
            return False

        return True

    def a_diccionario(self) -> dict:
        """Convierte a diccionario para usar en contextos."""
        return asdict(self)

    def a_texto_prompt(self) -> str:
        """Representación para el prompt/auditoría: cada vital medido o 'No registrado'.

        Fuente única de verdad: prompt del LLM y texto de auditoría usan esto.
        """
        def fmt(valor, unidad: str) -> str:
            if valor is None:
                return "No registrado"
            return f"{valor} {unidad}".rstrip()

        temperatura = (
            "No registrado"
            if self.temperatura is None
            else f"{self.temperatura:.1f} °C"
        )
        presion = (
            "No registrado"
            if self.presion_sistolica is None and self.presion_diastolica is None
            else (
                f"{self.presion_sistolica}/{self.presion_diastolica} mmHg"
                if self.presion_sistolica is not None and self.presion_diastolica is not None
                else (
                    f"Sistólica {self.presion_sistolica} mmHg (diastólica no registrada)"
                    if self.presion_sistolica is not None
                    else f"Diastólica {self.presion_diastolica} mmHg (sistólica no registrada)"
                )
            )
        )

        sexo_nombre = {
            "M": "Masculino",
            "F": "Femenino",
            "Otro": "Otro"
        }.get(self.sexo, self.sexo)

        return f"""- Edad: {self.edad} años
- Sexo: {sexo_nombre}
- Temperatura: {temperatura}
- Presión Arterial: {presion}
- Frecuencia Cardíaca: {fmt(self.frecuencia_cardiaca, "bpm")}
- Frecuencia Respiratoria: {fmt(self.frecuencia_respiratoria, "rpm")}
- SpO2: {fmt(self.saturacion, "%")}"""


# Instancia de referencia con todos los vitales ausentes (edad/sexo obligatorios).
DATOS_VITALES_SIN_MEDICION = DatosVitales(edad=0, sexo="M")

# Compatibilidad: instancia con valores normales, explícitamente marcada como
# demo (NO usar en la ruta clínica: solo UI legacy/tests).
DATOS_VITALES_DEFAULT = DatosVitales(
    edad=40,
    sexo="M",
    temperatura=37.0,
    presion_sistolica=120,
    presion_diastolica=80,
    frecuencia_cardiaca=70,
    saturacion=98.0,
)
