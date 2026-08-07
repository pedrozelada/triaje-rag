"""Registro de proveedores LLM.

Para agregar un nuevo proveedor de nube:
1. Crear `ai_service/providers/<nombre>.py` con una clase que herede
   de `LLMProvider` (ver `openai.py` como plantilla).
2. Agregar la clase a la lista `PROVEEDORES` de este archivo.
3. Instalar el paquete de llama-index correspondiente (si aplica).

No es necesario modificar ningún otro módulo: backend, UI y CLI
usan `get_llm_models()`, que recorre el registro automáticamente.
"""

import logging
from typing import Dict, List, Type

from ai_service.providers.base import LLMProvider
from ai_service.providers.groq import GroqProvider
from ai_service.providers.ollama import OllamaProvider
from ai_service.providers.openai import OpenAIProvider
from ai_service.errors import ConfigurationError

logger = logging.getLogger(__name__)

#: Registro de proveedores. El orden define la prioridad de selección
#: cuando no se especifica un modelo explícitamente.
PROVEEDORES: List[Type[LLMProvider]] = [
    GroqProvider,
    OpenAIProvider,
    OllamaProvider,
]


def get_llm_models() -> Dict[str, object]:
    """
    Carga todos los modelos LLM disponibles según el registro.

    Recorre `PROVEEDORES`, descarta los que no están disponibles
    (sin API key, paquete faltante, etc.) e intenta instanciar el resto.
    Un fallo de instanciación nunca tumba al sistema: se registra un
    warning y se continúa con el siguiente proveedor.

    Returns:
        Dict: Diccionario con modelos {nombre: instancia}.

    Raises:
        ConfigurationError: Si ningún proveedor está disponible.
    """
    models: Dict[str, object] = {}

    for clase in PROVEEDORES:
        proveedor = clase()
        try:
            if not proveedor.disponible():
                logger.debug(f"Proveedor no disponible: {proveedor.nombre}")
                continue
            models[proveedor.nombre] = proveedor.crear()
            logger.info(f"✅ {proveedor.nombre} disponible")
        except Exception as e:
            logger.warning(f"⚠️  No se pudo cargar {proveedor.nombre}: {e}")

    if not models:
        raise ConfigurationError(
            "❌ No hay modelos LLM disponibles. Configura Groq, OpenAI u Ollama."
        )

    return models


__all__ = [
    "LLMProvider",
    "PROVEEDORES",
    "get_llm_models",
    "GroqProvider",
    "OllamaProvider",
    "OpenAIProvider",
]
