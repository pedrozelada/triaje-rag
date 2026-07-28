"""Schemas de Paciente."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PacienteBase(BaseModel):
    ci: str = Field(..., min_length=1, max_length=30)
    nombre: str = Field(..., min_length=1, max_length=100)
    apellido: str = Field(..., min_length=1, max_length=100)
    fecha_nacimiento: date
    sexo: str  # M / F / Otro
    telefono: str | None = None
    direccion: str | None = None


class PacienteCreate(PacienteBase):
    pass


class PacienteUpdate(BaseModel):
    ci: str | None = None
    nombre: str | None = None
    apellido: str | None = None
    fecha_nacimiento: date | None = None
    sexo: str | None = None
    telefono: str | None = None
    direccion: str | None = None


class PacienteOut(PacienteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    edad: int
    fecha_registro: datetime
    fecha_actualizacion: datetime | None = None
