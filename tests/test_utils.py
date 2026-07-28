"""Tests básicos del sistema RAG."""

import pytest
from src.errors import ConfigurationError
from src.utils import (
    validar_entrada_pregunta,
    formatear_tiempo,
    obtener_respuesta_segura
)


class TestValidacionEntrada:
    """Tests para validación de entrada."""
    
    def test_pregunta_valida(self):
        """Pregunta válida debe pasar validación."""
        result = validar_entrada_pregunta("Paciente de 45 años con dolor torácico")
        assert result is True
    
    def test_pregunta_muy_corta(self):
        """Pregunta muy corta debe fallar."""
        result = validar_entrada_pregunta("Corta")
        assert result is False
    
    def test_pregunta_vacia(self):
        """Pregunta vacía debe fallar."""
        result = validar_entrada_pregunta("")
        assert result is False


class TestFormateoTiempo:
    """Tests para formateo de tiempo."""
    
    def test_tiempo_en_milisegundos(self):
        """Tiempo < 1s debe formatearse en ms."""
        result = formatear_tiempo(0.5)
        assert "ms" in result
        assert "500" in result
    
    def test_tiempo_en_segundos(self):
        """Tiempo >= 1s debe formatearse en segundos."""
        result = formatear_tiempo(2.5)
        assert "segundos" in result
        assert "2.50" in result


class TestObtenerRespuesta:
    """Tests para obtención segura de respuesta."""
    
    def test_respuesta_valida(self):
        """Respuesta válida debe extraerse correctamente."""
        class MockResponse:
            response = "Evaluación: Urgencia Mayor"
        
        result = obtener_respuesta_segura(MockResponse())
        assert "Urgencia Mayor" in result
    
    def test_respuesta_none(self):
        """Respuesta None debe retornar mensaje de error."""
        class MockResponse:
            response = None
        
        result = obtener_respuesta_segura(MockResponse())
        assert "❌" in result or "error" in result.lower()
