"""Schemas de administración (estadísticas, reportes)."""

from datetime import date

from pydantic import BaseModel


class NivelCount(BaseModel):
    """Conteo de consultas por nivel de urgencia."""
    nivel: str
    cantidad: int


class SexoCount(BaseModel):
    """Conteo de pacientes por sexo."""
    sexo: str
    cantidad: int


class EdadRangeCount(BaseModel):
    """Conteo de pacientes por rango etario (ej. '18-30')."""
    rango: str
    cantidad: int


class DiaCount(BaseModel):
    """Conteo de consultas en un día concreto."""
    fecha: date
    cantidad: int


class ModeloCount(BaseModel):
    """Uso de un proveedor LLM: consultas y tokens consumidos."""
    modelo: str
    consultas: int
    tokens: int


class UsuarioActividad(BaseModel):
    """Cantidad de triajes realizados por un usuario."""
    usuario_id: int
    nombre: str
    consultas: int


class MotivoFrecuente(BaseModel):
    """Palabra clave frecuente extraída de motivos de consulta/síntomas."""
    palabra: str
    cantidad: int


class EstadisticasOut(BaseModel):
    """Estadísticas generales del sistema."""
    total_consultas: int
    total_pacientes: int
    total_usuarios: int
    por_nivel: list[NivelCount]
    promedio_tiempo_respuesta: float | None = None
    modelo_mas_usado: str | None = None
    # Demografía de pacientes
    por_sexo: list[SexoCount] = []
    por_rango_edad: list[EdadRangeCount] = []
    # Actividad temporal y operativa
    consultas_por_dia: list[DiaCount] = []
    por_modelo: list[ModeloCount] = []
    total_tokens: int = 0
    actividad_usuarios: list[UsuarioActividad] = []
    motivos_frecuentes: list[MotivoFrecuente] = []


class EstadisticasTriajeOut(BaseModel):
    """Estadísticas de triaje filtradas por un período de fechas."""
    fecha_desde: date
    fecha_hasta: date
    total_consultas: int
    por_nivel: list[NivelCount] = []
    promedio_tiempo_respuesta: float | None = None
    modelo_mas_usado: str | None = None
    # Demografía de pacientes que consultaron en el período
    por_sexo: list[SexoCount] = []
    por_rango_edad: list[EdadRangeCount] = []
    # Actividad temporal y operativa del período
    consultas_por_dia: list[DiaCount] = []
    total_tokens: int = 0
    actividad_usuarios: list[UsuarioActividad] = []
    motivos_frecuentes: list[MotivoFrecuente] = []
