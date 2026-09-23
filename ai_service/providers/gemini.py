"""Proveedor Google Gemini (nube).

Variables de entorno:
    GEMINI_API_KEY: (obligatoria) API key de Google AI Studio.
    GEMINI_MODEL: Modelo a usar (default: gemini-3.5-flash).
    GEMINI_TEMPERATURE: Temperatura (default: 0.1).
    GEMINI_MAX_TOKENS: Máximo de tokens de respuesta (default: 4096).
    GEMINI_THINKING_BUDGET: (opcional) Presupuesto de tokens de razonamiento.
        Los modelos Gemini 3 razonan ("thinking") antes de responder y eso
        añade latencia; con 0 se responde directo. Si no se define, se usa el
        comportamiento por defecto del modelo.

Requiere el paquete opcional:
    pip install llama-index-llms-google-genai
"""

import os
import logging

from ai_service.providers.base import LLMProvider
from ai_service.errors import ConfigurationError

logger = logging.getLogger(__name__)

#: Modelo por defecto. Debe ser un modelo vigente del catálogo de Gemini: los
#: nombres retirados o restringidos para cuentas nuevas devuelven 404, y los
#: que están saturados devuelven 503 (la librería reintenta automáticamente).
DEFAULT_MODEL = "gemini-3.5-flash"


class GeminiProvider(LLMProvider):
    nombre = "Gemini (Nube - Google)"
    descripcion = "Modelos Gemini vía Google AI Studio (requiere GEMINI_API_KEY)"

    def disponible(self) -> bool:
        if not os.getenv("GEMINI_API_KEY"):
            return False
        # Verificar que el paquete opcional esté instalado.
        try:
            import llama_index.llms.google_genai  # noqa: F401

            return True
        except ImportError:
            logger.warning(
                "⚠️  GEMINI_API_KEY configurada pero falta el paquete "
                "llama-index-llms-google-genai. Instálalo con: "
                "pip install llama-index-llms-google-genai"
            )
            return False

    def crear(self):
        # Import diferido: solo se necesita el paquete si el provider se usa.
        from llama_index.llms.google_genai import GoogleGenAI

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ConfigurationError(
                "❌ GEMINI_API_KEY no encontrada. Configura la variable en .env"
            )

        modelo = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.1"))
        max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", "4096"))

        kwargs: dict = {
            "model": modelo,
            "api_key": api_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Presupuesto de razonamiento opcional. La librería ignora
        # `temperature` y `max_tokens` cuando recibe `generation_config`, por
        # eso ese camino construye la configuración completa.
        thinking_budget = os.getenv("GEMINI_THINKING_BUDGET", "").strip()
        if thinking_budget:
            from google.genai import types

            kwargs.pop("max_tokens")
            kwargs["generation_config"] = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                thinking_config=types.ThinkingConfig(
                    thinking_budget=int(thinking_budget)
                ),
            )

        logger.info(f"Inicializando Gemini con modelo '{modelo}'...")
        return GoogleGenAI(**kwargs)
