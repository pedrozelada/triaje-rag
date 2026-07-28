"""Modelos ORM del sistema de triaje."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

# Enums reutilizables
SEXO_ENUM = ("M", "F", "Otro")
ROL_ENUM = ("admin", "medico", "enfermero_triage")
NIVEL_URGENCIA_ENUM = ("rojo", "naranja", "amarillo", "verde", "azul")


def calcular_edad(fecha_nacimiento: date) -> int:
    """Calcula la edad en años a partir de la fecha de nacimiento."""
    hoy = date.today()
    edad = hoy.year - fecha_nacimiento.year
    if (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
        edad -= 1
    return edad


class Paciente(Base):
    __tablename__ = "paciente"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ci: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    apellido: Mapped[str] = mapped_column(String, nullable=False)
    fecha_nacimiento: Mapped[date] = mapped_column(Date, nullable=False)
    sexo: Mapped[str] = mapped_column(SAEnum(*SEXO_ENUM), nullable=False)
    telefono: Mapped[str | None] = mapped_column(String, nullable=True)
    direccion: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    fecha_actualizacion: Mapped[datetime | None] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    consultas: Mapped[list["ConsultaTriage"]] = relationship(
        back_populates="paciente", cascade="all, delete-orphan"
    )

    @property
    def edad(self) -> int:
        """Edad calculada dinámicamente (no se almacena)."""
        return calcular_edad(self.fecha_nacimiento)


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ci: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    rol: Mapped[str] = mapped_column(
        SAEnum(*ROL_ENUM), default="enfermero_triage", nullable=False
    )
    centro_salud: Mapped[str | None] = mapped_column(String, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    consultas: Mapped[list["ConsultaTriage"]] = relationship(
        back_populates="usuario"
    )


class ConsultaTriage(Base):
    __tablename__ = "consulta_triage"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    paciente_id: Mapped[int] = mapped_column(
        ForeignKey("paciente.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Auditores: puede ser NULL si el triaje se hace sin login (modo anónimo).
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True, index=True
    )
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Signos vitales
    temperatura: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    presion_sistolica: Mapped[int | None] = mapped_column(Integer, nullable=True)
    presion_diastolica: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frecuencia_cardiaca: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frecuencia_respiratoria: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spo2: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Clínica
    motivo_consulta: Mapped[str | None] = mapped_column(Text, nullable=True)
    sintomas: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Resultados y auditoría de la LLM
    nivel_urgencia: Mapped[str | None] = mapped_column(
        SAEnum(*NIVEL_URGENCIA_ENUM), nullable=True
    )
    respuesta_llm: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_utilizado: Mapped[str | None] = mapped_column(Text, nullable=True)
    modelo_utilizado: Mapped[str | None] = mapped_column(String, nullable=True)
    tiempo_respuesta: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    tokens_consumidos: Mapped[int | None] = mapped_column(Integer, nullable=True)

    paciente: Mapped["Paciente"] = relationship(back_populates="consultas")
    usuario: Mapped["Usuario | None"] = relationship(back_populates="consultas")