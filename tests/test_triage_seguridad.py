"""Tests de integración de la ruta /api/triage: seguridad clínica.

No llama al LLM: `rag_service.analizar` se reemplaza por un doble que
simula la respuesta del modelo, para probar la validación de la API,
el prompt de auditoría y la persistencia de reglas activadas.
"""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.rag.service as rag_service_module
from ai_service.red_flags import evaluar_reglas
from backend.rag.service import ResultadoTriage

ADMIN = {
    "ci": "9100001",
    "nombre_completo": "Admin Triaje Seguro",
    "email": "admin@triajetest.bo",
    "password": "admin123",
    "rol": "admin",
}

PACIENTE = {
    "ci": "7777777", "nombre": "Rosa", "apellido": "Mamani",
    "fecha_nacimiento": "1985-04-12", "sexo": "F",
}


def registrar_y_loguear(client, datos):
    client.post("/api/auth/registro", json=datos)
    r = client.post(
        "/api/auth/login", json={"email": datos["email"], "password": datos["password"]}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def crear_paciente(client, headers, ci="7777777"):
    payload = {**PACIENTE, "ci": ci}
    r = client.post("/api/pacientes", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _instalar_doble_analizar(monkeypatch, respuesta_llm="NIVEL DE URGENCIA: verde"):
    capturado = {}

    def doble_analizar(self, datos_vitales, sintomas, modelo_nombre=None):
        capturado["datos_vitales"] = datos_vitales
        capturado["sintomas"] = sintomas
        capturado["prompt"] = (
            "DATOS CLÍNICOS DEL PACIENTE:\n"
            f"{datos_vitales.a_texto_prompt()}\n"
            f"DESCRIPCIÓN: {sintomas}"
        )
        return ResultadoTriage(
            respuesta=respuesta_llm,
            nivel_urgencia="verde" if "NIVEL DE URGENCIA" in respuesta_llm else None,
            prompt_utilizado=capturado["prompt"],
            modelo_utilizado=modelo_nombre or "Groq (Nube - Rápido)",
            tiempo_respuesta=0.1,
            tokens_consumidos=None,
            fuentes=["nnac_test.pdf"],
        )

    monkeypatch.setattr(rag_service_module.RAGService, "analizar", doble_analizar)
    return capturado


class TestVitalesAusentes:
    def test_no_se_falsifican_valores_normales(self, client, monkeypatch):
        """El bug crítico: vitales no medidos NO deben aparecer como 37.0/120/80."""
        headers = registrar_y_loguear(client, ADMIN)
        paciente_id = crear_paciente(client, headers)
        capturado = _instalar_doble_analizar(monkeypatch)

        r = client.post("/api/triage", json={
            "paciente_id": paciente_id,
            "sintomas": "Dolor de garganta leve desde ayer",
        }, headers=headers)
        assert r.status_code == 201, r.text

        # El bloque de datos que llega al LLM usa la misma fuente que la auditoría
        texto = capturado["datos_vitales"].a_texto_prompt()
        assert "No registrado" in texto
        assert "37.0" not in texto
        assert "120" not in texto
        assert "98.0" not in texto
        # Y se persiste como None (no como valor normal) en la respuesta
        data = r.json()
        assert data["temperatura"] is None
        assert data["presion_sistolica"] is None

    def test_sintomas_vacios_rechazados(self, client, monkeypatch):
        headers = registrar_y_loguear(client, ADMIN)
        paciente_id = crear_paciente(client, headers, ci="7777778")
        _instalar_doble_analizar(monkeypatch)

        r = client.post("/api/triage", json={
            "paciente_id": paciente_id,
            "sintomas": "",
        }, headers=headers)
        assert r.status_code == 422

    def test_sintomas_muy_cortos_rechazados(self, client, monkeypatch):
        headers = registrar_y_loguear(client, ADMIN)
        paciente_id = crear_paciente(client, headers, ci="7777779")
        _instalar_doble_analizar(monkeypatch)

        r = client.post("/api/triage", json={
            "paciente_id": paciente_id,
            "sintomas": "tos",
        }, headers=headers)
        assert r.status_code == 422


class TestValidacionVitales:
    def test_vital_imposible_rechazado_422(self, client, monkeypatch):
        headers = registrar_y_loguear(client, ADMIN)
        paciente_id = crear_paciente(client, headers, ci="7777780")
        _instalar_doble_analizar(monkeypatch)

        r = client.post("/api/triage", json={
            "paciente_id": paciente_id,
            "temperatura": 20.0,  # imposible: fuera del rango canónico
            "sintomas": "Dolor abdominal leve desde hace dos dias",
        }, headers=headers)
        assert r.status_code == 422

    def test_presion_incoherente_rechazada(self, client, monkeypatch):
        """Defensa en profundidad: sistólica <= diastólica cruza el 422 del endpoint."""
        headers = registrar_y_loguear(client, ADMIN)
        paciente_id = crear_paciente(client, headers, ci="7777781")
        _instalar_doble_analizar(monkeypatch)

        # 90/110 pasa el schema (cada campo en rango) pero es incoherente
        r = client.post("/api/triage", json={
            "paciente_id": paciente_id,
            "presion_sistolica": 90,
            "presion_diastolica": 110,
            "sintomas": "Control de presion arterial de rutina mensual",
        }, headers=headers)
        assert r.status_code == 422

    def test_vitales_validos_aceptados(self, client, monkeypatch):
        headers = registrar_y_loguear(client, ADMIN)
        paciente_id = crear_paciente(client, headers, ci="7777782")
        _instalar_doble_analizar(monkeypatch)

        r = client.post("/api/triage", json={
            "paciente_id": paciente_id,
            "temperatura": 38.5,
            "presion_sistolica": 110,
            "presion_diastolica": 70,
            "frecuencia_cardiaca": 92,
            "spo2": 96,
            "sintomas": "Tos con flema y fiebre de tres dias",
        }, headers=headers)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["temperatura"] == 38.5
        assert data["spo2"] == 96


class TestTriajeLactante:
    """Antes el sistema no podía triar bebés: `edad=0` rompía la validación.

    Además, con umbrales de adulto un lactante con FC 140 / FR 40 (ambos
    fisiológicos) generaba alertas rojas/naranjas falsas.
    """

    def _crear_lactante(self, client, headers, ci="8888881"):
        hace_4_meses = (date.today() - timedelta(days=120)).isoformat()
        r = client.post("/api/pacientes", json={
            "ci": ci, "nombre": "Luz", "apellido": "Quispe",
            "fecha_nacimiento": hace_4_meses, "sexo": "F",
        }, headers=headers)
        assert r.status_code == 201, r.text
        assert r.json()["edad"] == 0
        return r.json()["id"]

    def test_lactante_puede_ser_triado(self, client, monkeypatch):
        headers = registrar_y_loguear(client, ADMIN)
        paciente_id = self._crear_lactante(client, headers)
        capturado = _instalar_doble_analizar(monkeypatch)

        r = client.post("/api/triage", json={
            "paciente_id": paciente_id,
            "frecuencia_cardiaca": 140,
            "frecuencia_respiratoria": 40,
            "temperatura": 37.2,
            "sintomas": "Lactante con tos leve y buen estado general desde ayer",
        }, headers=headers)
        assert r.status_code == 201, r.text

        # El grupo etario llega al motor de reglas con la edad en meses.
        datos = capturado["datos_vitales"]
        assert datos.grupo_etario == "lactante"
        assert 0 < datos.edad_meses < 12
        # FC 140 y FR 40 son normales en un lactante: CERO alertas falsas.
        assert evaluar_reglas(datos, None) == []
        assert r.json()["reglas_activadas"] == []

    def test_lactante_grave_si_alerta(self, client, monkeypatch):
        """La seguridad pediátrica no debe volverse permisiva."""
        headers = registrar_y_loguear(client, ADMIN)
        paciente_id = self._crear_lactante(client, headers, ci="8888882")
        capturado = _instalar_doble_analizar(monkeypatch)

        r = client.post("/api/triage", json={
            "paciente_id": paciente_id,
            "frecuencia_respiratoria": 85,
            "spo2": 88,
            "sintomas": "Lactante con dificultad respiratoria marcada y quejido",
        }, headers=headers)
        assert r.status_code == 201, r.text

        alertas = evaluar_reglas(capturado["datos_vitales"], None)
        assert any(a.nivel == "rojo" for a in alertas)


class TestReglasYSinClasificar:
    def test_reglas_activadas_persistidas(self, client, monkeypatch):
        """Una consulta con SpO2 bajo debe registrar las reglas en la respuesta."""
        headers = registrar_y_loguear(client, ADMIN)
        paciente_id = crear_paciente(client, headers, ci="7777783")

        def doble_con_reglas(self, datos_vitales, sintomas, modelo_nombre=None):
            return ResultadoTriage(
                respuesta="NIVEL DE URGENCIA: verde",
                nivel_urgencia="rojo",  # elevado por reglas en el servicio real
                prompt_utilizado="x",
                modelo_utilizado="Groq (Nube - Rápido)",
                tiempo_respuesta=0.1,
                reglas_activadas=["SpO2 85% (< 90): hipoxemia severa"],
            )

        monkeypatch.setattr(rag_service_module.RAGService, "analizar", doble_con_reglas)

        r = client.post("/api/triage", json={
            "paciente_id": paciente_id,
            "sintomas": "Dificultad respiratoria con tos persistente",
        }, headers=headers)
        assert r.status_code == 201, r.text
        assert r.json()["reglas_activadas"] == ["SpO2 85% (< 90): hipoxemia severa"]

    def test_llm_sin_nivel_parseable(self, client, monkeypatch):
        """Si el LLM no da nivel parseable, el doble devuelve None y se persiste NULL."""
        headers = registrar_y_loguear(client, ADMIN)
        paciente_id = crear_paciente(client, headers, ci="7777784")
        _instalar_doble_analizar(monkeypatch, respuesta_llm="No hay suficiente información en las NNAC.")

        r = client.post("/api/triage", json={
            "paciente_id": paciente_id,
            "sintomas": "Consulta general sin hallazgos relevantes hoy",
        }, headers=headers)
        assert r.status_code == 201, r.text
        # El servicio real compone el nivel; el doble devuelve None sin reglas
        assert r.json()["nivel_urgencia"] is None
