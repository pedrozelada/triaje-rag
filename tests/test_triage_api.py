"""Tests de caracterización del router de triaje (auditoría y consultas).

El motor RAG se reemplaza por un doble, así que ningún test llama a un modelo.
La validación clínica de los signos vitales y el comportamiento de los lactantes
ya están cubiertos en `test_triage_seguridad.py`; aquí se fija lo que ese
archivo no toca: qué se persiste como auditoría, con qué se llama al motor, el
modo anónimo, el listado con filtros y el catálogo de modelos.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import HTTPException

from backend.rag.service import RAGService, Recuperacion, ResultadoTriage
from tests.helpers import (
    ADMIN,
    crear_consulta,
    crear_paciente,
    id_de,
    registrar_y_loguear,
)

SINTOMAS = "dolor torácico opresivo con sudoración profusa"


class MotorFalso:
    """Doble de `rag_service.analizar` que registra con qué se lo llamó."""

    def __init__(self, resultado: ResultadoTriage | None = None, error: Exception | None = None):
        self.llamadas: list[dict] = []
        self._resultado = resultado or ResultadoTriage(
            respuesta="NIVEL DE URGENCIA: naranja\nDerivar a emergencias.",
            nivel_urgencia="naranja",
            prompt_utilizado="PROMPT DE PRUEBA",
            modelo_utilizado="groq",
            tiempo_respuesta=1.234,
            tokens_consumidos=321,
            fuentes=["NNAC.pdf"],
            reglas_activadas=["taquicardia"],
            recuperaciones=[Recuperacion(rank=1, archivo="NNAC.pdf", page_label="12")],
        )
        self._error = error

    def analizar(self, *, datos_vitales, sintomas, modelo_nombre=None, medir_tokens=None):
        self.llamadas.append(
            {
                "datos_vitales": datos_vitales,
                "sintomas": sintomas,
                "modelo_nombre": modelo_nombre,
                "medir_tokens": medir_tokens,
            }
        )
        if self._error is not None:
            raise self._error
        return self._resultado


@pytest.fixture()
def motor(monkeypatch):
    """Instala el doble en la clase del servicio RAG.

    Se parchea la CLASE y no la instancia única: un atributo de instancia
    quedaría por delante de un parche posterior de la clase y haría que otros
    tests llamaran al motor real sin darse cuenta.
    """
    falso = MotorFalso()
    monkeypatch.setattr(RAGService, "analizar", falso.analizar)
    return falso


CUERPO = {
    "temperatura": 38.4,
    "presion_sistolica": 110,
    "presion_diastolica": 70,
    "frecuencia_cardiaca": 118,
    "frecuencia_respiratoria": 22,
    "spo2": 94,
    "motivo_consulta": "Dolor en el pecho",
    "sintomas": SINTOMAS,
    "modelo": "groq",
}


class TestCrearTriage:
    def test_persiste_la_auditoria(self, client, sesion, motor):
        headers = registrar_y_loguear(client)
        usuario_id = id_de(client, headers)
        paciente_id = crear_paciente(sesion, ci="8001", edad=56, sexo="M")

        r = client.post(
            "/api/triage",
            json={"paciente_id": paciente_id, **CUERPO},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        datos = r.json()
        assert datos["nivel_urgencia"] == "naranja"
        assert datos["usuario_id"] == usuario_id
        assert datos["modelo_utilizado"] == "groq"
        assert datos["tiempo_respuesta"] == 1.234
        assert datos["tokens_consumidos"] == 321
        assert datos["reglas_activadas"] == ["taquicardia"]
        assert datos["respuesta_llm"].startswith("NIVEL DE URGENCIA: naranja")
        assert datos["prompt_utilizado"] == "PROMPT DE PRUEBA"
        assert datos["spo2"] == 94

        # Y queda persistido: se puede volver a leer
        assert (
            client.get(f"/api/triage/{datos['id']}", headers=headers).json()["id"]
            == datos["id"]
        )

    def test_triaje_anonimo_deja_usuario_nulo(self, client, sesion, motor):
        paciente_id = crear_paciente(sesion, ci="8002", edad=30, sexo="F")
        r = client.post("/api/triage", json={"paciente_id": paciente_id, **CUERPO})
        assert r.status_code == 201, r.text
        assert r.json()["usuario_id"] is None

    def test_arma_los_vitales_y_la_descripcion(self, client, sesion, motor):
        """El motor recibe el paciente completo y motivo + síntomas unidos."""
        headers = registrar_y_loguear(client)
        paciente_id = crear_paciente(
            sesion, ci="8003", edad=0, sexo="F", nombre="Bebe", apellido="Mamani"
        )

        client.post(
            "/api/triage",
            json={"paciente_id": paciente_id, **CUERPO},
            headers=headers,
        )

        llamada = motor.llamadas[0]
        vitales = llamada["datos_vitales"]
        assert vitales.edad == 0
        assert vitales.edad_meses is not None and vitales.edad_meses >= 0
        assert vitales.sexo == "F"
        assert vitales.temperatura == 38.4
        assert vitales.saturacion == 94
        assert llamada["sintomas"] == f"Dolor en el pecho\n{SINTOMAS}"
        assert llamada["modelo_nombre"] == "groq"

    def test_paciente_inexistente(self, client, motor):
        headers = registrar_y_loguear(client)
        r = client.post("/api/triage", json={"paciente_id": 999, **CUERPO}, headers=headers)
        assert r.status_code == 404
        assert motor.llamadas == []


class TestListarTriage:
    def test_filtra_por_nivel_y_paciente(self, client, sesion):
        headers = registrar_y_loguear(client)
        paciente_id = crear_paciente(sesion, ci="8101", edad=45, sexo="M")
        otro_id = crear_paciente(sesion, ci="8102", edad=22, sexo="F")
        crear_consulta(sesion, paciente_id=paciente_id, nivel="rojo")
        crear_consulta(sesion, paciente_id=paciente_id, nivel="verde")
        crear_consulta(sesion, paciente_id=otro_id, nivel="rojo")

        rojos = client.get("/api/triage?nivel_urgencia=rojo", headers=headers).json()
        assert len(rojos) == 2
        propios = client.get(f"/api/triage?paciente_id={paciente_id}", headers=headers).json()
        assert len(propios) == 2

    def test_requiere_sesion(self, client):
        assert client.get("/api/triage").status_code == 401

    def test_consulta_inexistente(self, client):
        headers = registrar_y_loguear(client)
        assert client.get("/api/triage/999", headers=headers).status_code == 404


class TestModelos:
    def test_lista_modelos(self, client, monkeypatch):
        monkeypatch.setattr(RAGService, "listar_modelos", lambda self: ["groq", "gemini"])
        assert client.get("/api/triage/modelos").json() == ["groq", "gemini"]

    def test_sin_modelos_disponibles(self, client, monkeypatch):
        def falla(self):
            raise HTTPException(status_code=503, detail="no hay")

        monkeypatch.setattr(RAGService, "listar_modelos", falla)
        r = client.get("/api/triage/modelos")
        assert r.status_code == 503
        assert "no hay modelos" in r.json()["detail"].lower()


def test_admin_de_los_helpers_tiene_rol_admin():
    assert ADMIN["rol"] == "admin"
