"""Schemas de Paciente."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

FECHA_NACIMIENTO_MINIMA = date(1900, 1, 1)


def _validar_fecha_nacimiento(valor: date) -> date:
    """Rechaza fechas futuras o imposibles.

    El frontend ya valida esto, pero la API es la última línea de defensa: una
    fecha futura produce una edad negativa y rompería el cálculo del grupo
    etario de las reglas de seguridad (red flags).
    """
    if valor > date.today():
        raise ValueError("La fecha de nacimiento no puede ser futura.")
    if valor < FECHA_NACIMIENTO_MINIMA:
        raise ValueError("La fecha de nacimiento no es válida.")
    return valor


class PacienteBase(BaseModel):
    ci: str = Field(..., min_length=1, max_length=30)
    nombre: str = Field(..., min_length=1, max_length=100)
    apellido: str = Field(..., min_length=1, max_length=100)
    fecha_nacimiento: date
    # Mismo catálogo que backend.db.models.SEXO_ENUM. Se valida aquí para que
    # un sexo inválido no llegue a DatosVitales y falle recién en el triaje.
    sexo: str = Field(..., pattern="^(M|F|Otro)$")
    telefono: str | None = None
    direccion: str | None = None

    @field_validator("fecha_nacimiento")
    @classmethod
    def _fecha_nacimiento_coherente(cls, valor: date) -> date:
        return _validar_fecha_nacimiento(valor)


class PacienteCreate(PacienteBase):
    pass


class PacienteUpdate(BaseModel):
    ci: str | None = None
    nombre: str | None = None
    apellido: str | None = None
    fecha_nacimiento: date | None = None
    sexo: str | None = Field(None, pattern="^(M|F|Otro)$")
    telefono: str | None = None
    direccion: str | None = None

    @field_validator("fecha_nacimiento")
    @classmethod
    def _fecha_nacimiento_coherente(cls, valor: date | None) -> date | None:
        if valor is None:
            return valor
        return _validar_fecha_nacimiento(valor)


class PacienteOut(PacienteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    edad: int
    # Edad en meses: obligatoria en la UI para pacientes menores de 1 año.
    edad_meses: int
    fecha_registro: datetime
    fecha_actualizacion: datetime | None = None
