"""Configuración de modelos de embeddings."""

from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import logging

logger = logging.getLogger(__name__)

# Nombre único del modelo de embeddings. Se usa también como parte de la
# "forma" del índice: si cambia, los vectores guardados dejan de ser
# comparables con los de las consultas y el índice debe reconstruirse.
MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def get_embedding_model():
    """
    Carga el modelo de embeddings multilingüe.
    
    Returns:
        HuggingFaceEmbedding: Modelo de embeddings configurado.
    """
    logger.info("Cargando modelo de embeddings...")
    
    try:
        embed_model = HuggingFaceEmbedding(model_name=MODELO_EMBEDDINGS)
        logger.info("Modelo de embeddings cargado exitosamente")
        return embed_model
    except Exception as e:
        logger.error(f"Error al cargar embeddings: {e}")
        raise
