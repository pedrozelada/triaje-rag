"""Schemas de ConsultaTriage."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

# Rangos canónicos de signos vitales (espejo de ai_service/models.py).
# Valores fuera de rango => HTTP 422 (los datos imposibles no llegan al LLM).


class TriageCreate(BaseModel):
    """Datos enviados por el frontend para crear una consulta de triaje.

    Todos los signos vitales son opcionales: un campo ausente se trata como
    NO medido (nunca se sustituye por un valor normal). Los valores presentes
    fuera de rango se rechazan con 422.
    """

    paciente_id: int
    # Signos vitales (None = no medido)
    temperatura: float | None = Field(None, ge=30.0, le=45.0)
    presion_sistolica: int | None = Field(None, ge=40, le=300)
    presion_diastolica: int | None = Field(None, ge=20, le=200)
    frecuencia_cardiaca: int | None = Field(None, ge=20, le=300)
    frecuencia_respiratoria: int | None = Field(None, ge=4, le=80)
    spo2: int | None = Field(None, ge=50, le=100)
    # Clínica: se exige descripción para que el RAG tenga algo que clasificar
    sintomas: str = Field(..., min_length=10, max_length=2000)
    motivo_consulta: str | None = Field(None, max_length=200)
    # Modelo LLM elegido por el usuario (None = prioridad por defecto)
    modelo: str | None = None


class TriageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paciente_id: int
    usuario_id: Optional[int] = None
    fecha_hora: datetime
    temperatura: float | None = None
    presion_sistolica: int | None = None
    presion_diastolica: int | None = None
    frecuencia_cardiaca: int | None = None
    frecuencia_respiratoria: int | None = None
    spo2: int | None = None
    motivo_consulta: str | None = None
    sintomas: str | None = None
    nivel_urgencia: str | None = None
    respuesta_llm: str | None = None
    prompt_utilizado: str | None = None
    modelo_utilizado: str | None = None
    tiempo_respuesta: float | None = None
    tokens_consumidos: int | None = None
    reglas_activadas: list[str] = []