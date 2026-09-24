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


class ModeloRendimiento(BaseModel):
    """Rendimiento de un proveedor LLM: consultas, tokens y tiempos."""
    modelo: str
    consultas: int
    tokens: int
    tiempo_promedio: float | None = None
    tiempo_minimo: float | None = None
    tiempo_maximo: float | None = None


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


class EstadisticasLLMOut(BaseModel):
    """Estadísticas globales de uso y rendimiento de los modelos LLM."""
    total_consultas: int
    total_tokens: int
    tiempo_promedio: float | None = None
    tiempo_minimo: float | None = None
    tiempo_maximo: float | None = None
    por_modelo: list[ModeloRendimiento] = []


class ArchivoIndice(BaseModel):
    """Documento indexado: huella del contenido y chunks que aporta."""
    nombre: str
    sha256: str
    tamano: int
    chunks: int


class PlanIndice(BaseModel):
    """Diferencia entre los documentos de `data/` y lo realmente indexado."""
    nuevos: list[str] = []
    modificados: list[str] = []
    eliminados: list[str] = []
    sin_cambios: list[str] = []
    motivo_reconstruccion: str | None = None
    requiere_reconstruccion: bool = False
    requiere_abortar: bool = False
    a_indexar: list[str] = []
    a_eliminar: list[str] = []


class EstadoIndiceOut(BaseModel):
    """Estado del índice vectorial y su vigencia respecto del corpus NNAC.

    `actualizado` es la respuesta a "¿el índice refleja los PDFs actuales?":
    exige que exista índice, que no haya cambios pendientes y que su forma
    (modelo de embeddings y segmentación) coincida con la configuración actual.
    """
    coleccion: str
    data_dir: str
    chroma_path: str
    existe_indice: bool
    chunks: int
    archivos: list[ArchivoIndice] = []
    completo: bool = False
    adoptado: bool = False
    # Sin manifiesto pero con chunks: al arrancar se adopta el índice existente
    # (registro de la huella actual, sin re-embeber).
    adoptara: bool = False
    indexado_en: str | None = None
    embedding_model: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    plan: PlanIndice | None = None
    actualizado: bool = False
    error: str | None = None
