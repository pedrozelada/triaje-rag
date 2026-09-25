"""Pruebas del arnés de evaluación del Componente 2 (`scripts/evaluar.py`).

No llaman a ningún modelo ni a la red: comprueban que los 30 casos se validan,
que los lotes de una misma corrida se fusionan sin duplicar casos y que los
instrumentos para el médico se generan completos. Las corridas reales se hacen
con `python scripts/evaluar.py correr`.
"""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def arnes():
    """Carga `scripts/evaluar.py` como módulo, sin depender de un paquete."""
    spec = importlib.util.spec_from_file_location(
        "evaluar_arnes", RAIZ / "scripts" / "evaluar.py"
    )
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _run(run_id: str, casos: list[tuple[str, str | None]]) -> dict:
    """Corrida mínima con la forma que consumen `informe` e `instrumentos`."""
    return {
        "run_id": run_id,
        "variante": "rag",
        "config": {"modelo_usado": "Groq (Nube - Rápido)"},
        "entorno": {},
        "duracion_s": 1.0,
        "parcial": False,
        "casos": [
            {
                "id": cid,
                "repeticiones": (
                    [{"nivel_final": nivel}] if nivel else [{"error": "429"}]
                ),
            }
            for cid, nivel in casos
        ],
    }


class TestValidacionDeCasos:
    def test_los_30_casos_pasan_la_validacion(self, arnes, capsys):
        codigo = arnes.comando_validar(SimpleNamespace())
        salida = capsys.readouterr().out

        assert codigo == 0
        assert "Casos válidos" in salida
        assert "⚠️" not in salida

    def test_hay_20_clinicos_y_10_anti_alucinacion(self, arnes):
        casos = arnes.cargar_casos()
        clinicos = [c for c in casos if c.get("_grupo_archivo") == "clinico"]
        anti = [c for c in casos if c.get("_grupo_archivo") == "anti_alucinacion"]

        assert len(casos) == 30
        assert len(clinicos) == 20
        assert len(anti) == 10

    def test_cada_caso_clinico_declara_rango_aceptable(self, arnes):
        for caso in arnes.cargar_casos():
            if caso.get("_grupo_archivo") != "clinico":
                continue
            assert caso.get("nivel_esperado"), caso["id"]
            assert caso.get("nivel_permitido"), caso["id"]


class TestFusionDeLotes:
    def test_los_lotes_del_mismo_experimento_forman_una_variante(self, arnes):
        fusionados = arnes.fusionar_corridas(
            [
                _run("rag_1", [("C-01", "rojo"), ("C-02", "naranja")]),
                _run("rag_2", [("C-03", "verde")]),
            ]
        )

        assert len(fusionados) == 1
        assert [c["id"] for c in fusionados[0]["casos"]] == ["C-01", "C-02", "C-03"]

    def test_un_caso_repetido_no_duplica_y_conserva_la_corrida_exitosa(self, arnes):
        fusionados = arnes.fusionar_corridas(
            [
                _run("rag_1", [("C-01", None)]),
                _run("rag_2", [("C-01", "rojo")]),
            ]
        )

        casos = fusionados[0]["casos"]
        assert len(casos) == 1
        assert casos[0]["repeticiones"] == [{"nivel_final": "rojo"}]

    def test_variantes_distintas_no_se_mezclan(self, arnes):
        base = _run("base", [("C-01", "rojo")])
        base["variante"] = "sin-contexto"

        fusionados = arnes.fusionar_corridas([_run("rag", [("C-01", "rojo")]), base])

        assert len(fusionados) == 2


class TestInstrumentos:
    def test_la_rubrica_cubre_los_20_casos_con_el_nivel_del_sistema(
        self, arnes, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(arnes, "DIR_INSTRUMENTOS", tmp_path)
        ruta_run = tmp_path / "rag_1.json"
        ruta_run.write_text(
            json.dumps(_run("rag_1", [("C-01", "rojo"), ("C-02", "naranja")])),
            encoding="utf-8",
        )

        assert arnes.comando_instrumentos(SimpleNamespace(run=[str(ruta_run)])) == 0

        with open(tmp_path / "rubrica_clinica.csv", newline="", encoding="utf-8") as fh:
            filas = list(csv.DictReader(fh))
        assert len(filas) == 20
        niveles = {f["caso_id"]: f["nivel_sistema"] for f in filas}
        assert niveles["C-01"] == "rojo"
        assert niveles["C-02"] == "naranja"
        assert niveles["C-03"] == ""

    def test_sin_corrida_la_columna_del_sistema_queda_vacia(self, arnes, tmp_path, monkeypatch):
        monkeypatch.setattr(arnes, "DIR_INSTRUMENTOS", tmp_path)

        assert arnes.comando_instrumentos(SimpleNamespace(run=None)) == 0

        with open(tmp_path / "rubrica_clinica.csv", newline="", encoding="utf-8") as fh:
            filas = list(csv.DictReader(fh))
        assert all(f["nivel_sistema"] == "" for f in filas)

    def test_la_encuesta_sus_tiene_los_10_items(self, arnes, tmp_path, monkeypatch):
        monkeypatch.setattr(arnes, "DIR_INSTRUMENTOS", tmp_path)

        arnes.comando_instrumentos(SimpleNamespace(run=None))

        with open(tmp_path / "encuesta_sus.csv", newline="", encoding="utf-8") as fh:
            filas = list(csv.DictReader(fh))
        assert len(filas) == len(arnes.ITEMS_SUS) == 10
        assert all(f["respuesta_1_a_5"] == "" for f in filas)

    def test_rubrica_sin_respuestas_no_inventa_metricas(self, arnes, tmp_path, monkeypatch):
        monkeypatch.setattr(arnes, "DIR_INSTRUMENTOS", tmp_path)
        arnes.comando_instrumentos(SimpleNamespace(run=None))
        monkeypatch.setattr(arnes, "DIR_INFORMES", tmp_path)

        codigo = arnes.comando_rubrica(
            SimpleNamespace(
                rubrica=str(tmp_path / "rubrica_clinica.csv"),
                sus=str(tmp_path / "encuesta_sus.csv"),
                run=None,
            )
        )

        assert codigo == 0
        informe = (tmp_path / "informe_clinico.md").read_text(encoding="utf-8")
        assert "0 de 20" in informe
        assert "no cumple" in informe


class TestAnclajeDeCitas:
    """El detector de citas compara contra TODO lo que el modelo recibió.

    Regresión de un falso positivo real: la primera versión comparaba solo
    contra los fragmentos recuperados y acusaba de "cita no anclada" a los
    datos del propio paciente y a la plantilla de la respuesta, que el modelo
    tenía en su prompt.
    """

    CASO = {
        "id": "X-01",
        "nivel_esperado": None,
        "nivel_permitido": [],
        "criterios": {},
        "detectores": ["cita_no_anclada"],
        "fuentes_esperadas": [],
    }

    def _registro(self, respuesta: str, prompt: str = "") -> dict:
        return {
            "respuesta": respuesta,
            "prompt_utilizado": prompt,
            "recuperaciones": [],
            "nivel_final": "verde",
            "nivel_llm": "verde",
            "nivel_reglas": None,
        }

    def test_una_cita_de_los_datos_del_paciente_no_es_alucinacion(self, arnes):
        caso = dict(self.CASO, detectores=["cita_no_anclada"])
        registro = self._registro(
            'El paciente presenta "se le hunden las costillas" y SpO₂ 92.0 %',
            prompt="DATOS CLÍNICOS DEL PACIENTE: spo2: 92.0 % descripcion: "
            "se le hunden las costillas al respirar",
        )

        veredicto = arnes.evaluar_registro(caso, registro, {})

        assert veredicto["citas_no_ancladas"] == []
        assert veredicto["alucinacion"] is False

    def test_una_cita_de_la_plantilla_del_prompt_no_es_alucinacion(self, arnes):
        caso = dict(self.CASO, detectores=["cita_no_anclada"])
        registro = self._registro(
            'REFERENCIA: No. "Manejo y observación en la posta rural"',
            prompt="REFERENCIA: [Sí / No]. Manejo y observación en la posta rural",
        )

        veredicto = arnes.evaluar_registro(caso, registro, {})

        assert veredicto["citas_no_ancladas"] == []
        assert veredicto["alucinacion"] is False

    def test_una_cita_inventada_si_se_marca(self, arnes):
        caso = dict(self.CASO, detectores=["cita_no_anclada"])
        registro = self._registro(
            'Según la NNAC (pág. 4321): "administrar adrenalina intramuscular precoz en '
            'la anafilaxia del adulto",',
            prompt="DATOS CLÍNICOS DEL PACIENTE: fiebre de 38 grados",
        )

        veredicto = arnes.evaluar_registro(caso, registro, {})

        assert veredicto["citas_no_ancladas"]
        assert veredicto["alucinacion"] is True

    def test_el_material_entregado_incluye_el_prompt(self, arnes):
        material = arnes._material_entregado(
            {"prompt_utilizado": "Datos del paciente: Fiebre de 39 °C", "recuperaciones": []}
        )

        assert "datos del paciente" in material
        assert "39" in material

    def test_declara_limite_distingue_callar_de_admitir(self, arnes):
        caso = {
            "id": "X-02",
            "nivel_esperado": None,
            "nivel_permitido": [],
            "criterios": {},
            "detectores": [],
            "fuentes_esperadas": [],
        }
        admite = arnes.evaluar_registro(
            caso,
            self._registro("Ese fármaco no figura en las NNAC disponibles."),
            {},
        )
        calla = arnes.evaluar_registro(
            caso,
            self._registro("Medicación sugerida: paracetamol 500 mg cada 6 horas."),
            {},
        )

        assert admite["declara_limite"] is True
        assert calla["declara_limite"] is False

    def test_el_caso_real_c_02_ya_no_se_marca(self, arnes):
        """Regresión con la evidencia real: C-02 citaba los datos del paciente."""
        ruta = RAIZ / "evaluacion" / "resultados" / "rag_groq_1.json"
        if not ruta.exists():
            pytest.skip("no hay corridas guardadas en evaluacion/resultados")
        documento = json.loads(ruta.read_text(encoding="utf-8"))
        variante = arnes.agregar([documento])["variantes"][0]
        caso = next(c for c in variante["casos"] if c["id"] == "C-02")

        veredicto = caso["veredictos"][0]

        assert veredicto["citas_no_ancladas"] == []
        assert veredicto["alucinacion"] is False


class TestKappa:
    def test_acuerdo_perfecto_y_azar(self, arnes):
        assert arnes._kappa([True, False, True, False], [True, False, True, False]) == 1.0
        assert arnes._kappa([True, True, False, False], [False, False, True, True]) == -1.0
        assert arnes._kappa([], []) is None
