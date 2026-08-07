"""Excepciones personalizadas para el sistema RAG."""


class RAGError(Exception):
    """Excepción base para errores del sistema RAG."""
    pass


class IndexInitializationError(RAGError):
    """Error al inicializar o cargar el índice vectorial."""
    pass


class QueryExecutionError(RAGError):
    """Error al ejecutar una consulta."""
    pass


class ConfigurationError(RAGError):
    """Error en la configuración del sistema."""
    pass


class EmbeddingError(RAGError):
    """Error al procesar embeddings."""
    pass
