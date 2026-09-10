"""Tests del endpoint de informe PDF (/api/informes/paciente/{id}/pdf)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar modelos y app a nivel de módulo: garantiza que Base.metadata
# tenga las tablas registradas ANTES del create_all del fixture `client`.
import backend.app.main  # noqa: F401,E402
from backend.db.models import ConsultaTriage  # noqa: E402

ADMIN = {
    "ci": "4100004",
    "nombre_completo": "Admin Informes PDF",
    "email": "admin@pdf.bo",
    "password": "admin123",
    "rol": "admin",
}

PACIENTE = {
    "ci": "7777777", "nombre": "Maria", "apellido": "Gonzalez",
    "fecha_nacimiento": "1992-08-15", "sexo": "F",
}


def registrar_y_loguear(client, datos):
    r = client.post("/api/auth/registro", json=datos)
    assert r.status_code == 201, r.text
    r = client.post(
        "/api/auth/login", json={"email": datos["email"], "password": datos["password"]}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _agregar_consulta(paciente_id, nivel="rojo"):
    """Inserta una consulta de triaje directa en la BD de test (sin ejecutar RAG)."""
    from backend.db import session as db_session

    db = db_session.SessionLocal()
    db.add(ConsultaTriage(
        paciente_id=paciente_id,
        nivel_urgencia=nivel,
        motivo_consulta="Dolor abdominal intenso",
        temperatura=38.5,
        presion_sistolica=120,
        presion_diastolica=80,
        frecuencia_cardiaca=95,
        spo2=96,
        respuesta_llm="Acudir a emergencia de inmediato.",
        modelo_utilizado="Groq (Nube - Rapido)",
        tiempo_respuesta=1.234,
        tokens_consumidos=540,
    ))
    db.commit()
    db.close()


class TestInformePdf:
    def test_requiere_token(self, client):
        assert client.get("/api/informes/paciente/1/pdf").status_code == 401

    def test_paciente_inexistente(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        r = client.get("/api/informes/paciente/99999/pdf", headers=headers)
        assert r.status_code == 404

    def test_pdf_sin_consultas(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        pid = client.post("/api/pacientes", json=PACIENTE, headers=headers).json()["id"]
        r = client.get(f"/api/informes/paciente/{pid}/pdf", headers=headers)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
        assert "attachment" in r.headers.get("content-disposition", "")

    def test_pdf_con_consultas(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        pid = client.post("/api/pacientes", json=PACIENTE, headers=headers).json()["id"]
        _agregar_consulta(pid)
        r = client.get(f"/api/informes/paciente/{pid}/pdf", headers=headers)
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF")
        assert r.content.rstrip().endswith(b"%%EOF")
        # Sin compresión: los datos del paciente deben ser texto buscable
        texto = r.content.decode("latin-1", errors="ignore")
        assert "Paciente:" in texto
        assert "Gonzalez" in texto
        assert "Consulta 1" in texto
        assert "Rojo" in texto