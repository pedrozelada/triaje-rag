"""Modelos de datos para el sistema de triaje."""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class DatosVitales:
    """Datos vitales del paciente para triaje médico."""
    
    edad: int
    sexo: str  # M, F, Otro
    temperatura: float
    presion_sistolica: int
    presion_diastolica: int
    frecuencia_cardiaca: int
    frecuencia_respiratoria: int = 16
    saturacion: float = 98.0

    def es_valido(self) -> bool:
        """
        Valida que los datos vitales estén en rangos razonables.
        
        Returns:
            bool: True si todos los datos son válidos
        """
        # Rango de edad
        if not (0 < self.edad < 150):
            return False
        
        # Sexo válido
        if self.sexo not in ["M", "F", "Otro"]:
            return False
        
        # Temperatura (34-42°C es razonable)
        if not (34 <= self.temperatura <= 42):
            return False
        
        # Presión sistólica (40-250 mmHg)
        if not (40 <= self.presion_sistolica <= 250):
            return False
        
        # Presión diastólica (20-150 mmHg)
        if not (20 <= self.presion_diastolica <= 150):
            return False
        
        # PA sistólica > PA diastólica
        if self.presion_sistolica <= self.presion_diastolica:
            return False
        
        # Frecuencia cardíaca (20-200 bpm)
        if not (20 <= self.frecuencia_cardiaca <= 200):
            return False
        
        # Saturación O2 (50-100%)
        if not (50 <= self.saturacion <= 100):
            return False
        
        return True
    
    def a_diccionario(self) -> dict:
        """Convierte a diccionario para usar en contextos."""
        return asdict(self)
    
    def __str__(self) -> str:
        """Representación legible de los datos vitales."""
        sexo_nombre = {
            "M": "Masculino",
            "F": "Femenino",
            "Otro": "Otro"
        }.get(self.sexo, self.sexo)
        
        return f"""
DATOS DEL PACIENTE:
- Edad: {self.edad} años
- Sexo: {sexo_nombre}
- Temperatura: {self.temperatura}°C
- Presión Arterial: {self.presion_sistolica}/{self.presion_diastolica} mmHg
- Frecuencia Cardíaca: {self.frecuencia_cardiaca} bpm
- Saturación O2: {self.saturacion}%
"""


# Valores por defecto realistas
DATOS_VITALES_DEFAULT = DatosVitales(
    edad=40,
    sexo="M",
    temperatura=37.0,
    presion_sistolica=120,
    presion_diastolica=80,
    frecuencia_cardiaca=70,
    saturacion=98.0
)
