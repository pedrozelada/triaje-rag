"""Tests de los proveedores LLM y su registro (sin llamadas de red)."""

import sys
import types

import pytest

from ai_service.errors import ConfigurationError
from ai_service.providers import PROVEEDORES
from ai_service.providers.gemini import DEFAULT_MODEL, GeminiProvider


@pytest.fixture()
def gemini_falso(monkeypatch):
    """Sustituye el paquete real de Gemini por un doble que captura los kwargs.

    Permite verificar la lógica del provider sin red y sin depender del
    paquete opcional instalado.
    """
    capturado: dict = {}

    class GoogleGenAIFalso:
        def __init__(self, **kwargs):
            capturado.update(kwargs)

    modulo = types.ModuleType("llama_index.llms.google_genai")
    modulo.GoogleGenAI = GoogleGenAIFalso
    monkeypatch.setitem(sys.modules, "llama_index.llms.google_genai", modulo)
    return capturado


class TestGeminiProvider:
    def test_sin_api_key_no_esta_disponible(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        assert GeminiProvider().disponible() is False

    def test_con_api_key_esta_disponible(self, monkeypatch, gemini_falso):
        monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
        assert GeminiProvider().disponible() is True

    def test_crear_sin_api_key_falla(self, monkeypatch, gemini_falso):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(ConfigurationError):
            GeminiProvider().crear()

    def test_crear_usa_el_modelo_por_defecto(self, monkeypatch, gemini_falso):
        monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        GeminiProvider().crear()
        assert gemini_falso["model"] == DEFAULT_MODEL
        assert gemini_falso["api_key"] == "clave-de-prueba"

    def test_crear_respeta_variables_de_entorno(self, monkeypatch, gemini_falso):
        monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
        monkeypatch.setenv("GEMINI_MODEL", "modelo-de-prueba")
        monkeypatch.setenv("GEMINI_TEMPERATURE", "0.5")
        monkeypatch.setenv("GEMINI_MAX_TOKENS", "512")
        monkeypatch.delenv("GEMINI_THINKING_BUDGET", raising=False)

        GeminiProvider().crear()

        assert gemini_falso["model"] == "modelo-de-prueba"
        assert gemini_falso["temperature"] == 0.5
        assert gemini_falso["max_tokens"] == 512

    def test_thinking_budget_construye_generation_config(self, monkeypatch, gemini_falso):
        """Con GEMINI_THINKING_BUDGET se arma la configuración completa.

        La librería ignora `temperature` y `max_tokens` cuando recibe
        `generation_config`, así que el provider debe replicarlos ahí.
        """
        monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
        monkeypatch.setenv("GEMINI_THINKING_BUDGET", "0")
        monkeypatch.setenv("GEMINI_MAX_TOKENS", "2048")

        GeminiProvider().crear()

        assert "max_tokens" not in gemini_falso
        config = gemini_falso["generation_config"]
        assert config.max_output_tokens == 2048
        assert config.thinking_config.thinking_budget == 0


class TestRegistroProveedores:
    def test_gemini_esta_registrado(self):
        assert GeminiProvider in PROVEEDORES

    def test_prioridad_groq_luego_gemini(self):
        assert PROVEEDORES[0].nombre.startswith("Groq")
        assert PROVEEDORES[1] is GeminiProvider
