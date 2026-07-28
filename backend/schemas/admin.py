"""Schemas de administración (estadísticas, reportes)."""

from pydantic import BaseModel


class NivelCount(BaseModel):
    """Conteo de consultas por nivel de urgencia."""
    nivel: str
    cantidad: int


class EstadisticasOut(BaseModel):
    """Estadísticas generales del sistema."""
    total_consultas: int
    total_pacientes: int
    total_usuarios: int
    por_nivel: list[NivelCount]
    promedio_tiempo_respuesta: float | None = None
    modelo_mas_usado: str | None = None
