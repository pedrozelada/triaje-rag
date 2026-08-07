"""Proveedor local (Ollama / LM Studio / cualquier servidor OpenAI-compatible).

Variables de entorno:
    OLLAMA_BASE_URL: URL del servidor (default: http://localhost:1234/v1).
    OLLAMA_MODEL: Nombre del modelo (default: local-model).
    OLLAMA_TIMEOUT: Timeout en segundos (default: 300).
    OLLAMA_CONTEXT_WINDOW: Ventana de contexto (default: 8192).
"""

import os
import logging

from ai_service.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    nombre = "Ollama (Local - Privado)"
    descripcion = "Modelo local vía servidor OpenAI-compatible (Ollama/LM Studio)"

    def disponible(self) -> bool:
        # El proveedor local siempre se intenta cargar; si el servidor no
        # responde, get_llm_models() lo descartará con un warning.
        return True

    def crear(self):
        # Import diferido para no requerir el paquete si no se usa.
        from llama_index.llms.openai_like import OpenAILike

        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:1234/v1")
        ollama_model = os.getenv("OLLAMA_MODEL", "local-model")
        ollama_timeout = int(os.getenv("OLLAMA_TIMEOUT", "300"))
        context_window = int(os.getenv("OLLAMA_CONTEXT_WINDOW", "8192"))

        logger.info(f"Inicializando modelo local '{ollama_model}' en {ollama_url}...")
        return OpenAILike(
            model=ollama_model,
            api_base=ollama_url,
            api_key="sk-local-test-key",
            is_chat_model=True,
            context_window=context_window,
            temperature=0.1,
            max_tokens=4096,
            timeout=ollama_timeout,
        )
