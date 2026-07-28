"""Configuración de modelos de embeddings."""

from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import logging

logger = logging.getLogger(__name__)


def get_embedding_model():
    """
    Carga el modelo de embeddings multilingüe.
    
    Returns:
        HuggingFaceEmbedding: Modelo de embeddings configurado.
    """
    logger.info("Cargando modelo de embeddings...")
    
    try:
        embed_model = HuggingFaceEmbedding(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        logger.info("Modelo de embeddings cargado exitosamente")
        return embed_model
    except Exception as e:
        logger.error(f"Error al cargar embeddings: {e}")
        raise
