"""Schemas de ConsultaTriage."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TriageCreate(BaseModel):
    """Datos enviados por el frontend para crear una consulta de triaje."""

    paciente_id: int
    # Signos vitales
    temperatura: float | None = Field(None, ge=20, le=45)
    presion_sistolica: int | None = Field(None, ge=40, le=300)
    presion_diastolica: int | None = Field(None, ge=20, le=200)
    frecuencia_cardiaca: int | None = Field(None, ge=20, le=300)
    frecuencia_respiratoria: int | None = Field(None, ge=0, le=100)
    spo2: int | None = Field(None, ge=0, le=100)
    # Clínica
    motivo_consulta: str | None = None
    sintomas: str | None = None
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