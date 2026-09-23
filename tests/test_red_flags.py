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
from ai_service.rangos_pediatricos import clasificar_grupo_etario


def vitales(**kwargs) -> DatosVitales:
    """Vitales de un adulto de 40 años (grupo ADULTO)."""
    base = dict(edad=40, sexo="M")
    base.update(kwargs)
    return DatosVitales(**base)


def vitales_pediatricos(edad: int, edad_meses: int | None = None, **kwargs) -> DatosVitales:
    """Vitales de un paciente pediátrico (con edad en meses si aplica)."""
    base = dict(edad=edad, sexo="M", edad_meses=edad_meses)
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


class TestNegacionSintomas:
    """Un hallazgo enunciado como AUSENTE no debe activar su regla."""

    def test_caso_real_niega_dolor_toracico(self):
        sintomas = (
            "Dolor de garganta leve, congestión nasal, estornudos y cansancio. "
            "Niega dificultad para respirar, dolor torácico o vómitos."
        )
        assert evaluar_reglas(vitales(), sintomas) == []

    def test_niega_lista_larga_de_sintomas(self):
        assert evaluar_reglas(
            vitales(), "Niega fiebre, vómitos, diarrea y dolor torácico"
        ) == []

    def test_sin_dolor_toracico(self):
        assert evaluar_reglas(vitales(), "Paciente estable, sin dolor torácico") == []

    def test_no_presenta_ni_refiere(self):
        assert evaluar_reglas(
            vitales(), "No presenta dolor torácico ni dificultad respiratoria"
        ) == []

    def test_negacion_no_cruza_oraciones(self):
        alertas = evaluar_reglas(
            vitales(), "Niega vómitos. Ahora presenta dolor torácico opresivo."
        )
        assert any("torácico" in a.descripcion for a in alertas)

    def test_negacion_no_cruza_salto_de_linea(self):
        alertas = evaluar_reglas(
            vitales(), "Niega vómitos y fiebre\nPresenta dolor torácico"
        )
        assert any("torácico" in a.descripcion for a in alertas)

    def test_afirmacion_intermedia_rompe_la_negacion(self):
        alertas = evaluar_reglas(vitales(), "Niega vómitos pero tiene dolor torácico")
        assert any("torácico" in a.descripcion for a in alertas)

    def test_cue_posterior_no_anula_el_hallazgo(self):
        alertas = evaluar_reglas(vitales(), "Dolor torácico que no cede con reposo")
        assert any("torácico" in a.descripcion for a in alertas)

    def test_sin_dentro_de_palabra_no_es_cue(self):
        assert evaluar_reglas(
            vitales(), "Paciente con sinusitis sin dolor torácico"
        ) == []

    def test_hallazgo_afirmativo_sigue_disparando(self):
        alertas = evaluar_reglas(vitales(), "Refiere dificultad para respirar desde ayer")
        assert any(a.nivel == "naranja" for a in alertas)

    def test_dificultad_para_respirar_y_falta_de_aire(self):
        assert any(
            a.nivel == "naranja"
            for a in evaluar_reglas(vitales(), "Dificultad para respirar")
        )
        assert any(
            a.nivel == "naranja" for a in evaluar_reglas(vitales(), "Falta de aire en reposo")
        )
        assert evaluar_reglas(
            vitales(), "Niega dificultad para respirar y falta de aire"
        ) == []

    def test_doble_mencion_una_negada_y_otra_afirmada(self):
        alertas = evaluar_reglas(
            vitales(),
            "Niega dolor torácico, sin embargo presenta dolor torácico al caminar",
        )
        assert any("torácico" in a.descripcion for a in alertas)

    def test_sin_embargo_no_actua_como_negacion(self):
        alertas = evaluar_reglas(
            vitales(), "Sin embargo, dolor torácico irradiado al brazo izquierdo"
        )
        assert any("torácico" in a.descripcion for a in alertas)

    def test_sin_embargo_con_verbo_afirmativo(self):
        alertas = evaluar_reglas(vitales(), "Sin embargo, refiere dolor torácico")
        assert any("torácico" in a.descripcion for a in alertas)

    def test_punto_y_coma_corta_la_negacion(self):
        alertas = evaluar_reglas(vitales(), "Niega vómitos; dolor torácico esta noche")
        assert any("torácico" in a.descripcion for a in alertas)

    def test_no_tuvo_con_mencion_afirmada_posterior(self):
        alertas = evaluar_reglas(
            vitales(),
            "No tuvo dolor torácico previo, pero ahora presenta dolor torácico intenso",
        )
        assert any("torácico" in a.descripcion for a in alertas)

    def test_no_tuvo_solo_no_dispara(self):
        assert evaluar_reglas(vitales(), "No tuvo dolor torácico") == []


class TestClasificacionGrupoEtario:
    """La edad del paciente (en años y en meses) define el grupo etario."""

    def test_grupos_basicos(self):
        assert clasificar_grupo_etario(0, 0) == "neonato"
        assert clasificar_grupo_etario(0, 1) == "lactante"
        assert clasificar_grupo_etario(0, 11) == "lactante"
        assert clasificar_grupo_etario(1) == "preescolar"
        assert clasificar_grupo_etario(5) == "preescolar"
        assert clasificar_grupo_etario(6) == "escolar"
        assert clasificar_grupo_etario(11) == "escolar"
        assert clasificar_grupo_etario(12) == "adolescente"
        assert clasificar_grupo_etario(17) == "adolescente"
        assert clasificar_grupo_etario(18) == "adulto"
        assert clasificar_grupo_etario(64) == "adulto"
        assert clasificar_grupo_etario(65) == "adulto_mayor"

    def test_edad_en_meses_coherente_en_anios(self):
        assert clasificar_grupo_etario(45, 540) == "adulto"


class TestRedFlagsPediatricas:
    """Umbrales por edad: lo fisiológico en un niño NO debe disparar alertas.

    Es el riesgo central de CU-25: aplicar umbrales de adulto a la población
    pediátrica produce falsos positivos masivos (falsas alertas rojas/naranjas).
    """

    def test_lactante_fr_35_no_alerta(self):
        # FR 35 rpm es normal en un lactante; en adulto dispararía naranja.
        assert evaluar_reglas(
            vitales_pediatricos(0, 6, frecuencia_respiratoria=35), None
        ) == []
        assert evaluar_reglas(vitales(frecuencia_respiratoria=35), None) != []

    def test_lactante_fr_40_no_alerta(self):
        # El ejemplo explícito de la observación clínica (35-40 rpm normales).
        assert evaluar_reglas(
            vitales_pediatricos(0, 9, frecuencia_respiratoria=40), None
        ) == []

    def test_lactante_fc_140_no_alerta(self):
        assert evaluar_reglas(
            vitales_pediatricos(0, 6, frecuencia_cardiaca=140), None
        ) == []
        assert evaluar_reglas(vitales(frecuencia_cardiaca=140), None) != []

    def test_neonato_fr_en_limite_superior_normal_no_alerta(self):
        assert evaluar_reglas(
            vitales_pediatricos(0, 0, frecuencia_respiratoria=60), None
        ) == []

    def test_preescolar_fc_120_no_alerta(self):
        assert evaluar_reglas(
            vitales_pediatricos(3, frecuencia_cardiaca=120), None
        ) == []
        assert evaluar_reglas(vitales(frecuencia_cardiaca=120), None) == []

    def test_escolar_fc_120_no_alerta(self):
        assert evaluar_reglas(
            vitales_pediatricos(8, frecuencia_cardiaca=120), None
        ) == []

    def test_adolescente_fc_135_es_naranja(self):
        # 135 bpm es silente en un adulto, pero taquicardia en un adolescente.
        assert evaluar_reglas(vitales(frecuencia_cardiaca=135), None) == []
        assert any(
            a.nivel == "naranja"
            for a in evaluar_reglas(vitales_pediatricos(15, frecuencia_cardiaca=135), None)
        )

    def test_lactante_taquipnea_extrema_es_rojo(self):
        assert any(
            a.nivel == "rojo"
            for a in evaluar_reglas(
                vitales_pediatricos(0, 2, frecuencia_respiratoria=85), None
            )
        )

    def test_lactante_taquicardia_extrema_es_rojo(self):
        assert any(
            a.nivel == "rojo"
            for a in evaluar_reglas(
                vitales_pediatricos(0, 4, frecuencia_cardiaca=230), None
            )
        )

    def test_neonato_bradicardia_es_rojo(self):
        assert any(
            a.nivel == "rojo"
            for a in evaluar_reglas(
                vitales_pediatricos(0, 0, frecuencia_cardiaca=70), None
            )
        )

    def test_pas_lactante_normal_no_alerta(self):
        # PAS 85/50 es normal en un lactante y no debe alertar.
        assert evaluar_reglas(
            vitales_pediatricos(0, 8, presion_sistolica=85, presion_diastolica=50), None
        ) == []

    def test_pas_lactante_65_es_rojo(self):
        assert any(
            a.nivel == "rojo"
            for a in evaluar_reglas(
                vitales_pediatricos(0, 8, presion_sistolica=65, presion_diastolica=40), None
            )
        )

    def test_pas_escolar_85_es_naranja(self):
        assert any(
            a.nivel == "naranja"
            for a in evaluar_reglas(
                vitales_pediatricos(8, presion_sistolica=85, presion_diastolica=50), None
            )
        )

    def test_adulto_mayor_fc_125_es_naranja(self):
        assert any(
            a.nivel == "naranja"
            for a in evaluar_reglas(
                vitales_pediatricos(70, frecuencia_cardiaca=125), None
            )
        )

    def test_descripcion_identifica_el_grupo_etario(self):
        alertas = evaluar_reglas(
            vitales_pediatricos(0, 2, frecuencia_respiratoria=85), None
        )
        assert alertas and any("lactante" in a.descripcion for a in alertas)

    def test_umbrales_de_adulto_sin_cambios(self):
        """Regresión: los umbrales históricos del grupo ADULTO se conservan."""
        assert evaluar_reglas(vitales(frecuencia_cardiaca=39), None) != []
        assert evaluar_reglas(vitales(frecuencia_cardiaca=161), None) != []
        assert evaluar_reglas(vitales(frecuencia_cardiaca=160), None) != []
        assert evaluar_reglas(vitales(frecuencia_respiratoria=30), None) != []
        assert evaluar_reglas(vitales(frecuencia_respiratoria=29), None) == []
