"""Proveedor OpenAI (nube).

Sirve además como plantilla para agregar nuevos proveedores de nube:
heredar `LLMProvider`, registrar la clase en `providers/__init__.py`
y agregar la dependencia de llama-index correspondiente.

Variables de entorno:
    OPENAI_API_KEY: (obligatoria) API key de OpenAI.
    OPENAI_MODEL: Modelo a usar (default: gpt-4o-mini).
    OPENAI_TEMPERATURE: Temperatura (default: 0.1).
    OPENAI_MAX_TOKENS: Máximo de tokens de respuesta (default: 1024).

Requiere el paquete opcional:
    pip install llama-index-llms-openai
"""

import os
import logging

from ai_service.providers.base import LLMProvider
from ai_service.errors import ConfigurationError

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    nombre = "OpenAI (Nube - GPT)"
    descripcion = "Modelos GPT vía OpenAI (requiere OPENAI_API_KEY)"

    def disponible(self) -> bool:
        if not os.getenv("OPENAI_API_KEY"):
            return False
        # Verificar que el paquete opcional esté instalado.
        try:
            import llama_index.llms.openai  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "⚠️  OPENAI_API_KEY configurada pero falta el paquete "
                "llama-index-llms-openai. Instálalo con: "
                "pip install llama-index-llms-openai"
            )
            return False

    def crear(self):
        # Import diferido: solo se necesita el paquete si el provider se usa.
        from llama_index.llms.openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ConfigurationError(
                "❌ OPENAI_API_KEY no encontrada. Configura la variable en .env"
            )

        modelo = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
        max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "1024"))

        logger.info(f"Inicializando OpenAI con modelo '{modelo}'...")
        return OpenAI(
            model=modelo,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
