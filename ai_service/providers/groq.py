"""Proveedor Groq (nube, inferencia rápida).

Variables de entorno:
    GROQ_API_KEY: (obligatoria) API key de Groq.
    GROQ_MODEL: Modelo a usar (default: llama-3.1-8b-instant).
    GROQ_TEMPERATURE: Temperatura (default: 0.1).
    GROQ_MAX_TOKENS: Máximo de tokens de respuesta (default: 1024).
"""

import os
import logging

from ai_service.providers.base import LLMProvider
from ai_service.errors import ConfigurationError

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    nombre = "Groq (Nube - Rápido)"
    descripcion = "Inferencia en la nube vía Groq (requiere GROQ_API_KEY)"

    def disponible(self) -> bool:
        return bool(os.getenv("GROQ_API_KEY"))

    def crear(self):
        # Import diferido: solo se necesita el paquete si el provider se usa.
        from llama_index.llms.groq import Groq

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ConfigurationError(
                "❌ GROQ_API_KEY no encontrada. Configura la variable en .env"
            )

        modelo = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        temperature = float(os.getenv("GROQ_TEMPERATURE", "0.1"))
        max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "1024"))

        logger.info(f"Inicializando Groq con modelo '{modelo}'...")
        return Groq(
            model=modelo,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
