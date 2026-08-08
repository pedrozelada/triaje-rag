"""Tests del backend: cálculo de edad, modelos y API (CRUD pacientes)."""

import os
import sys

# Asegurar que la raíz esté en el path para imports de `backend` y `ai_service`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta

from backend.db.models import calcular_edad


class TestCalcularEdad:
    def test_edad_exacta(self):
        hace_30_anos = date.today().replace(year=date.today().year - 30)
        assert calcular_edad(hace_30_anos) == 30

    def test_edad_antes_del_cumpleanos(self):
        # Nacido hace 30 años + 1 día (aún no cumple este año).
        fecha = date.today() - timedelta(days=30 * 365 + 1)
        assert calcular_edad(fecha) == 29

    def test_bebe(self):
        ayer = date.today() - timedelta(days=1)
        assert calcular_edad(ayer) == 0


class TestPacientesAPI:
    def test_crear_y_obtener_paciente(self, client):
        payload = {
            "ci": "1234567",
            "nombre": "Juan",
            "apellido": "Perez",
            "fecha_nacimiento": "1990-05-10",
            "sexo": "M",
            "telefono": "77712345",
        }
        r = client.post("/api/pacientes", json=payload)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["id"] > 0
        assert data["edad"] == (date.today().year - 1990)
        assert data["ci"] == "1234567"

        # Obtener por id
        rid = data["id"]
        r2 = client.get(f"/api/pacientes/{rid}")
        assert r2.status_code == 200
        assert r2.json()["nombre"] == "Juan"

    def test_ci_duplicado_rechazado(self, client):
        payload = {
            "ci": "9999999", "nombre": "A", "apellido": "B",
            "fecha_nacimiento": "2000-01-01", "sexo": "F",
        }
        assert client.post("/api/pacientes", json=payload).status_code == 201
        r = client.post("/api/pacientes", json=payload)
        assert r.status_code == 400

    def test_actualizar_paciente(self, client):
        payload = {
            "ci": "5555555", "nombre": "Ana", "apellido": "Lopez",
            "fecha_nacimiento": "1985-03-20", "sexo": "F",
        }
        pid = client.post("/api/pacientes", json=payload).json()["id"]
        r = client.put(f"/api/pacientes/{pid}", json={"telefono": "60000000"})
        assert r.status_code == 200
        assert r.json()["telefono"] == "60000000"

    def test_health(self, client):
        assert client.get("/api/health").json()["status"] == "ok"