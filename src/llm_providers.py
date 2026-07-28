"""Configuración de proveedores LLM (Groq, Ollama)."""

import os
import logging
from typing import Dict
from llama_index.llms.groq import Groq
from llama_index.llms.openai_like import OpenAILike
from src.errors import ConfigurationError

logger = logging.getLogger(__name__)


def get_groq_model() -> Groq:
    """
    Configura el modelo Groq desde variables de entorno.
    
    Returns:
        Groq: Instancia del modelo Groq.
        
    Raises:
        ConfigurationError: Si GROQ_API_KEY no está configurada.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ConfigurationError(
            "❌ GROQ_API_KEY no encontrada. Configura la variable en .env"
        )
    
    logger.info("Inicializando Groq...")
    return Groq(
        model="llama-3.1-8b-instant",
        api_key=api_key,
        temperature=0.1,
        max_tokens=1024
    )


def get_ollama_model() -> OpenAILike:
    """
    Configura el modelo local (LM Studio / Ollama / servidor OpenAI-compatible).

    El nombre del modelo y el timeout se leen desde variables de entorno para
    facilitar la configuración sin editar código.

    Returns:
        OpenAILike: Instancia del modelo local.
    """
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:1234/v1")
    ollama_model = os.getenv("OLLAMA_MODEL", "local-model")
    ollama_timeout = int(os.getenv("OLLAMA_TIMEOUT", "300"))

    logger.info(f"Inicializando modelo local '{ollama_model}' en {ollama_url}...")
    return OpenAILike(
        model=ollama_model,
        api_base=ollama_url,
        api_key="sk-local-test-key",
        is_chat_model=True,
        context_window=8192,
        temperature=0.1,
        max_tokens=4096,
        timeout=ollama_timeout
    )


def get_llm_models() -> Dict[str, object]:
    """
    Carga todos los modelos LLM disponibles.
    
    Returns:
        Dict: Diccionario con modelos {nombre: instancia}
    """
    models = {}
    
    # Intentar cargar Groq
    try:
        models["Groq (Nube - Rápido)"] = get_groq_model()
        logger.info("✅ Groq disponible")
    except ConfigurationError as e:
        logger.warning(f"⚠️  {e}")
    
    # Intentar cargar modelo local
    try:
        models["Ollama (Local - Privado)"] = get_ollama_model()
        logger.info("✅ Modelo local disponible")
    except Exception as e:
        logger.warning(f"⚠️  No se pudo conectar a Ollama: {e}")
    
    if not models:
        raise ConfigurationError(
            "❌ No hay modelos LLM disponibles. Configura Groq o Ollama."
        )
    
    return models
