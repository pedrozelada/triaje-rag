"""Tests para modelos de datos y validación de datos vitales."""

import pytest
from ai_service.models import DatosVitales, DATOS_VITALES_DEFAULT
from ai_service.utils import validar_datos_vitales, obtener_nivel_urgencia_color


class TestDatosVitales:
    """Tests para la validación clínica de DatosVitales."""

    def test_datos_validos_pasan(self):
        v = DatosVitales(40, "M", 37.0, 120, 80, 70, 98.0)
        assert v.es_valido() is True

    def test_edad_fuera_de_rango_falla(self):
        v = DatosVitales(200, "M", 37.0, 120, 80, 70, 98.0)
        assert v.es_valido() is False

    def test_sexo_invalido_falla(self):
        v = DatosVitales(40, "X", 37.0, 120, 80, 70, 98.0)
        assert v.es_valido() is False

    def test_temperatura_extrema_falla(self):
        v = DatosVitales(40, "M", 43.0, 120, 80, 70, 98.0)
        assert v.es_valido() is False

    def test_presion_sistolica_menor_a_diastolica_falla(self):
        v = DatosVitales(40, "M", 37.0, 70, 80, 70, 98.0)
        assert v.es_valido() is False

    def test_saturacion_fuera_de_rango_falla(self):
        v = DatosVitales(
            edad=40, sexo="M", temperatura=37.0, presion_sistolica=120,
            presion_diastolica=80, frecuencia_cardiaca=70, saturacion=30.0
        )
        assert v.es_valido() is False

    def test_default_valido(self):
        assert DATOS_VITALES_DEFAULT.es_valido() is True

    def test_a_diccionario(self):
        d = DATOS_VITALES_DEFAULT.a_diccionario()
        assert d["edad"] == 40
        assert d["sexo"] == "M"


class TestValidarDatosVitales:
    """Tests para validar_datos_vitales (dict -> Tuple[bool, str])."""

    def test_dict_valido(self):
        es_valido, msg = validar_datos_vitales({
            "edad": 30, "sexo": "F", "temperatura": 38.5,
            "presion_sistolica": 110, "presion_diastolica": 70,
            "frecuencia_cardiaca": 90, "saturacion": 96.0
        })
        assert es_valido is True
        assert msg is None

    def test_dict_invalido_devuelve_mensaje(self):
        es_valido, msg = validar_datos_vitales({
            "edad": 999, "sexo": "M", "temperatura": 37.0,
            "presion_sistolica": 120, "presion_diastolica": 80,
            "frecuencia_cardiaca": 70, "saturacion": 98.0
        })
        assert es_valido is False
        assert msg is not None

    def test_dict_mal_formato_devuelve_error(self):
        es_valido, msg = validar_datos_vitales({
            "edad": "no-es-numero", "sexo": "M", "temperatura": 37.0,
            "presion_sistolica": 120, "presion_diastolica": 80,
            "frecuencia_cardiaca": 70, "saturacion": 98.0
        })
        assert es_valido is False
        assert "formato" in msg.lower()


class TestObtenerNivelUrgencia:
    """Tests para la detección robusta del nivel de urgencia (Manchester)."""

    def test_parseo_estructurado_rojo(self):
        resp = "NIVEL DE URGENCIA: rojo\nJUSTIFICACIÓN: dolor torácico"
        assert obtener_nivel_urgencia_color(resp) == "rojo"

    def test_parseo_estructurado_naranja(self):
        resp = "NIVEL DE URGENCIA: naranja\nOtras cosas"
        assert obtener_nivel_urgencia_color(resp) == "naranja"

    def test_parseo_estructurado_amarillo(self):
        resp = "nivel de urgencia: amarillo"
        assert obtener_nivel_urgencia_color(resp) == "amarillo"

    def test_parseo_estructurado_verde(self):
        resp = "NIVEL DE URGENCIA: verde"
        assert obtener_nivel_urgencia_color(resp) == "verde"

    def test_respaldo_texto_libre(self):
        resp = "El paciente presenta una EMERGENCIA vital"
        assert obtener_nivel_urgencia_color(resp) == "rojo"

    def test_sin_coincidencia_devuelve_verde(self):
        resp = "No se pudo determinar el nivel"
        assert obtener_nivel_urgencia_color(resp) == "verde"
