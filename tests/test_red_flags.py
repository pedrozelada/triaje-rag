"""Tests del motor de reglas deterministas (red flags)."""

import pytest

from ai_service.models import DatosVitales
from ai_service.red_flags import (
    FC_NARANJA_ALTA,
    FR_NARANJA_ALTA,
    PAS_NARANJA,
    SPO2_NARANJA,
    TEMP_NARANJA_ALTA,
    Alerta,
    evaluar_reglas,
    nivel_maximo,
)


def vitales(**kwargs) -> DatosVitales:
    base = dict(edad=40, sexo="M")
    base.update(kwargs)
    return DatosVitales(**base)


class TestOrdenManchester:
    def test_orden_completo(self):
        from ai_service.red_flags import ORDEN_MANCHESTER
        assert ORDEN_MANCHESTER == ("azul", "verde", "amarillo", "naranja", "rojo")

    def test_nivel_maximo_basico(self):
        assert nivel_maximo("verde", "naranja") == "naranja"
        assert nivel_maximo("rojo", "amarillo") == "rojo"
        assert nivel_maximo("azul", "azul") == "azul"

    def test_nivel_maximo_con_none(self):
        assert nivel_maximo(None, "rojo") == "rojo"
        assert nivel_maximo("verde", None) == "verde"
        assert nivel_maximo(None, None) is None


class TestReglasVitales:
    def test_sin_medicion_sin_alertas(self):
        assert evaluar_reglas(vitales(), None) == []

    def test_vitales_normales_sin_alertas(self):
        v = vitales(
            temperatura=37.0, presion_sistolica=120, presion_diastolica=80,
            frecuencia_cardiaca=70, saturacion=98.0, frecuencia_respiratoria=16,
        )
        assert evaluar_reglas(v, "cefalea leve desde hace 2 dias") == []

    def test_spo2_bajo_90_es_rojo(self):
        alertas = evaluar_reglas(vitales(saturacion=89.0), None)
        assert any(a.nivel == "rojo" for a in alertas)

    def test_spo2_frontera_naranja(self):
        alertas = evaluar_reglas(vitales(saturacion=SPO2_NARANJA - 1), None)
        assert alertas and all(a.nivel == "naranja" for a in alertas)

    def test_spo2_en_94_no_alerta(self):
        assert evaluar_reglas(vitales(saturacion=SPO2_NARANJA), None) == []

    def test_pas_bajo_80_es_rojo(self):
        alertas = evaluar_reglas(vitales(presion_sistolica=79, presion_diastolica=50), None)
        assert any(a.nivel == "rojo" for a in alertas)

    def test_pas_frontera_naranja(self):
        alertas = evaluar_reglas(vitales(presion_sistolica=PAS_NARANJA - 1, presion_diastolica=60), None)
        assert any(a.nivel == "naranja" for a in alertas)

    def test_fc_extrema_es_rojo(self):
        assert any(a.nivel == "rojo" for a in evaluar_reglas(vitales(frecuencia_cardiaca=39), None))
        assert any(a.nivel == "rojo" for a in evaluar_reglas(vitales(frecuencia_cardiaca=161), None))

    def test_fc_140_es_naranja(self):
        alertas = evaluar_reglas(vitales(frecuencia_cardiaca=FC_NARANJA_ALTA), None)
        assert any(a.nivel == "naranja" for a in alertas)

    def test_temperatura_41_es_rojo(self):
        alertas = evaluar_reglas(vitales(temperatura=41.0), None)
        assert any(a.nivel == "rojo" for a in alertas)

    def test_temperatura_40_es_naranja(self):
        alertas = evaluar_reglas(vitales(temperatura=TEMP_NARANJA_ALTA), None)
        assert any(a.nivel == "naranja" for a in alertas)

    def test_temperatura_baja_es_naranja(self):
        alertas = evaluar_reglas(vitales(temperatura=34.5), None)
        assert any(a.nivel == "naranja" for a in alertas)

    def test_fr_30_es_naranja(self):
        alertas = evaluar_reglas(vitales(frecuencia_respiratoria=FR_NARANJA_ALTA), None)
        assert any(a.nivel == "naranja" for a in alertas)

    def test_fr_extrema_es_rojo(self):
        assert any(a.nivel == "rojo" for a in evaluar_reglas(vitales(frecuencia_respiratoria=42), None))
        assert any(a.nivel == "rojo" for a in evaluar_reglas(vitales(frecuencia_respiratoria=7), None))


class TestReglasSintomas:
    def test_dolor_toracico_dispara_naranja(self):
        alertas = evaluar_reglas(vitales(), "Dolor torácico opresivo de 30 minutos")
        assert any(a.nivel == "naranja" and "torácico" in a.descripcion for a in alertas)

    def test_convulsiones_disparan_naranja(self):
        alertas = evaluar_reglas(vitales(), "Presentó convulsiones hace 1 hora")
        assert any(a.nivel == "naranja" for a in alertas)

    def test_tildes_y_mayusculas_toleradas(self):
        alertas = evaluar_reglas(vitales(), "DIFICULTAD RESPIRATORIA marcada")
        assert any(a.nivel == "naranja" for a in alertas)

    def test_mencion_inocua_no_dispara(self):
        alertas = evaluar_reglas(vitales(), "Refiere dolor de garganta leve al tragar")
        assert alertas == []

    def test_texto_vacio_sin_alertas(self):
        assert evaluar_reglas(vitales(), "") == []
        assert evaluar_reglas(vitales(), None) == []


class TestEvaluacionMultiple:
    def test_multiples_reglas_se_acumulan(self):
        v = vitales(saturacion=88.0, frecuencia_cardiaca=145)
        alertas = evaluar_reglas(v, "dolor torácico")
        niveles = {a.nivel for a in alertas}
        assert "rojo" in niveles
        assert "naranja" in niveles

    def test_alerta_incluye_descripcion_legible(self):
        alertas = evaluar_reglas(vitales(saturacion=85.0), None)
        assert alertas and "SpO2" in alertas[0].descripcion
