"""Tests para modelos de datos y validación de datos vitales."""

import pytest
from ai_service.models import DatosVitales, DATOS_VITALES_DEFAULT
from ai_service.utils import validar_datos_vitales, obtener_nivel_urgencia_color


class TestDatosVitales:
    """Tests para la validación clínica de DatosVitales."""

    def test_datos_validos_pasan(self):
        v = DatosVitales(
            edad=40, sexo="M", temperatura=37.0,
            presion_sistolica=120, presion_diastolica=80,
            frecuencia_cardiaca=70, saturacion=98.0,
        )
        assert v.es_valido() is True

    def test_edad_fuera_de_rango_falla(self):
        v = DatosVitales(200, "M", 37.0, 120, 80, 70, 98.0)
        assert v.es_valido() is False

    def test_sexo_invalido_falla(self):
        v = DatosVitales(40, "X", 37.0, 120, 80, 70, 98.0)
        assert v.es_valido() is False

    def test_temperatura_extrema_falla(self):
        v = DatosVitales(40, "M", 46.0, 120, 80, 70, 98.0)
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


class TestDatosVitalesOpcionales:
    """Vitales ausentes (None) = no medidos: válidos y nunca falseados."""

    def test_vitales_ausentes_son_validos(self):
        v = DatosVitales(edad=35, sexo="F")
        assert v.es_valido() is True

    def test_vital_presente_fuera_de_rango_falla(self):
        v = DatosVitales(edad=35, sexo="F", temperatura=50.0)
        assert v.es_valido() is False

    def test_fr_fuera_de_rango_falla(self):
        v = DatosVitales(edad=35, sexo="F", frecuencia_respiratoria=2)
        assert v.es_valido() is False

    def test_a_texto_prompt_marca_no_registrado(self):
        v = DatosVitales(edad=35, sexo="F")
        texto = v.a_texto_prompt()
        assert "No registrado" in texto
        assert "37.0" not in texto
        assert "120" not in texto
        assert "35 años" in texto

    def test_a_texto_prompt_con_valores(self):
        v = DatosVitales(
            edad=35, sexo="F", temperatura=38.5,
            presion_sistolica=110, presion_diastolica=70,
            frecuencia_cardiaca=90, saturacion=96.0,
        )
        texto = v.a_texto_prompt()
        assert "38.5 °C" in texto
        assert "110/70 mmHg" in texto
        assert "90 bpm" in texto
        assert "96.0 %" in texto

    def test_a_texto_prompt_presion_parcial(self):
        v = DatosVitales(edad=35, sexo="F", presion_sistolica=110)
        texto = v.a_texto_prompt()
        assert "Sistólica 110 mmHg" in texto
        assert "diastólica no registrada" in texto


class TestDatosVitalesLactante:
    """Menores de 1 año: `edad` vale 0 y la granularidad viene de `edad_meses`."""

    def test_lactante_con_meses_es_valido(self):
        assert DatosVitales(edad=0, sexo="F", edad_meses=6).es_valido() is True

    def test_neonato_es_valido(self):
        assert DatosVitales(edad=0, sexo="M", edad_meses=0).es_valido() is True

    def test_edad_cero_sin_meses_es_invalida(self):
        """Sin meses no se puede determinar el grupo etario: se rechaza."""
        assert DatosVitales(edad=0, sexo="M").es_valido() is False

    def test_edad_cero_con_meses_absurdos_es_invalida(self):
        assert DatosVitales(edad=0, sexo="M", edad_meses=40).es_valido() is False

    def test_grupo_etario_se_deriva_de_la_edad(self):
        assert DatosVitales(edad=0, sexo="M", edad_meses=6).grupo_etario == "lactante"
        assert DatosVitales(edad=0, sexo="M", edad_meses=0).grupo_etario == "neonato"
        assert DatosVitales(edad=3, sexo="M").grupo_etario == "preescolar"
        assert DatosVitales(edad=40, sexo="M").grupo_etario == "adulto"

    def test_fr_alta_es_valida_para_lactante(self):
        """Un lactante en insuficiencia respiratoria puede superar 80 rpm."""
        assert DatosVitales(
            edad=0, sexo="M", edad_meses=2, frecuencia_respiratoria=100
        ).es_valido() is True

    def test_prompt_de_lactante_usa_meses_y_avisa_pediatrico(self):
        texto = DatosVitales(edad=0, sexo="F", edad_meses=8).a_texto_prompt()
        assert "8 meses" in texto
        assert "Lactante" in texto
        assert "pediátrico" in texto.lower()
        assert "No registrado" in texto

    def test_prompt_de_adulto_mantiene_formato_en_anios(self):
        texto = DatosVitales(edad=35, sexo="F").a_texto_prompt()
        assert "35 años" in texto
        assert "pediátrico" not in texto.lower()


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

    def test_dict_frecuencia_respiratoria_imposible_se_detecta(self):
        """Regresión: la FR se omitía y un valor imposible pasaba la validación."""
        es_valido, msg = validar_datos_vitales({
            "edad": 30, "sexo": "M", "frecuencia_respiratoria": 2
        })
        assert es_valido is False
        assert msg is not None

    def test_dict_lactante_con_meses_es_valido(self):
        es_valido, msg = validar_datos_vitales({
            "edad": 0, "edad_meses": 6, "sexo": "F", "frecuencia_cardiaca": 130
        })
        assert es_valido is True
        assert msg is None

    def test_dict_lactante_sin_meses_es_invalido(self):
        es_valido, msg = validar_datos_vitales({"edad": 0, "sexo": "F"})
        assert es_valido is False
        assert msg is not None


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

    def test_sin_coincidencia_devuelve_none(self):
        """Sin nivel parseable => None (sin_clasificar), NUNCA 'verde' por defecto."""
        resp = "No se pudo determinar el nivel"
        assert obtener_nivel_urgencia_color(resp) is None

    def test_respuesta_vacia_devuelve_none(self):
        assert obtener_nivel_urgencia_color("") is None

    def test_negacion_de_color_no_clasifica(self):
        """Mención de color fuera de la línea estructurada no clasifica."""
        resp = "El cuadro NO corresponde a un cuadro rojo ni naranja según las NNAC"
        assert obtener_nivel_urgencia_color(resp) is None

    def test_color_en_justificacion_no_clasifica(self):
        resp = (
            "NIVEL DE URGENCIA: naranja\n"
            "JUSTIFICACIÓN: se descarta categoria rojo por estabilidad hemodinámica"
        )
        assert obtener_nivel_urgencia_color(resp) == "naranja"
