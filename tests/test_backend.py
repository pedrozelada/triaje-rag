"""Tests del backend: cálculo de edad, modelos y API (CRUD pacientes)."""

import os
import sys

# Asegurar que la raíz esté en el path para imports de `backend` y `ai_service`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta

from backend.db.models import calcular_edad, calcular_edad_en_meses

# Usuario admin de prueba (el registro permite el primer admin como bootstrap).
ADMIN = {
    "ci": "9000009",
    "nombre_completo": "Admin Test",
    "email": "admin@pacientes.bo",
    "password": "admin123",
    "rol": "admin",
}


def registrar_y_loguear(client, datos):
    """Registra un usuario y devuelve headers con su JWT."""
    r = client.post("/api/auth/registro", json=datos)
    assert r.status_code == 201, r.text
    r = client.post(
        "/api/auth/login", json={"email": datos["email"], "password": datos["password"]}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


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


def hace_n_meses(n: int) -> date:
    """Fecha de nacimiento de exactamente `n` meses cumplidos hoy."""
    hoy = date.today()
    total = hoy.year * 12 + (hoy.month - 1) - n
    anio, mes = divmod(total, 12)
    return date(anio, mes + 1, min(hoy.day, 28))


class TestCalcularEdadEnMeses:
    """La edad en meses es lo que permite triar a los menores de 1 año."""

    def test_recien_nacido(self):
        assert calcular_edad_en_meses(date.today()) == 0

    def test_seis_meses(self):
        assert calcular_edad_en_meses(hace_n_meses(6)) == 6

    def test_once_meses(self):
        assert calcular_edad_en_meses(hace_n_meses(11)) == 11

    def test_menor_de_un_mes_no_es_negativo(self):
        assert calcular_edad_en_meses(date.today() - timedelta(days=3)) == 0

    def test_un_ano_son_doce_meses(self):
        hace_1_ano = date.today().replace(year=date.today().year - 1)
        assert calcular_edad_en_meses(hace_1_ano) == 12

    def test_adulto(self):
        hace_30_anos = date.today().replace(year=date.today().year - 30)
        assert calcular_edad_en_meses(hace_30_anos) == 360


class TestPacientesAPI:
    def test_crear_y_obtener_paciente(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        payload = {
            "ci": "1234567",
            "nombre": "Juan",
            "apellido": "Perez",
            "fecha_nacimiento": "1990-05-10",
            "sexo": "M",
            "telefono": "77712345",
        }
        r = client.post("/api/pacientes", json=payload, headers=headers)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["id"] > 0
        assert data["edad"] == (date.today().year - 1990)
        assert data["ci"] == "1234567"

        # Obtener por id
        rid = data["id"]
        r2 = client.get(f"/api/pacientes/{rid}", headers=headers)
        assert r2.status_code == 200
        assert r2.json()["nombre"] == "Juan"

    def test_ci_duplicado_rechazado(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        payload = {
            "ci": "9999999", "nombre": "A", "apellido": "B",
            "fecha_nacimiento": "2000-01-01", "sexo": "F",
        }
        assert client.post("/api/pacientes", json=payload, headers=headers).status_code == 201
        r = client.post("/api/pacientes", json=payload, headers=headers)
        assert r.status_code == 400

    def test_actualizar_paciente(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        payload = {
            "ci": "5555555", "nombre": "Ana", "apellido": "Lopez",
            "fecha_nacimiento": "1985-03-20", "sexo": "F",
        }
        pid = client.post("/api/pacientes", json=payload, headers=headers).json()["id"]
        r = client.put(f"/api/pacientes/{pid}", json={"telefono": "60000000"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["telefono"] == "60000000"

    def test_eliminar_paciente(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        payload = {
            "ci": "6666666", "nombre": "Bol", "apellido": "Borrar",
            "fecha_nacimiento": "1980-01-01", "sexo": "M",
        }
        pid = client.post("/api/pacientes", json=payload, headers=headers).json()["id"]
        assert client.delete(f"/api/pacientes/{pid}", headers=headers).status_code == 204

    def test_health(self, client):
        assert client.get("/api/health").json()["status"] == "ok"

    def test_paciente_lactante_expone_edad_en_meses(self, client):
        """Antes el sistema no podía triar bebés: solo devolvía `edad=0`."""
        headers = registrar_y_loguear(client, ADMIN)
        payload = {
            "ci": "3333333", "nombre": "Bebe", "apellido": "Mamani",
            "fecha_nacimiento": hace_n_meses(5).isoformat(), "sexo": "F",
        }
        r = client.post("/api/pacientes", json=payload, headers=headers)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["edad"] == 0
        assert data["edad_meses"] == 5

    def test_fecha_nacimiento_futura_rechazada(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        manana = (date.today() + timedelta(days=1)).isoformat()
        payload = {
            "ci": "4444444", "nombre": "Futuro", "apellido": "Paciente",
            "fecha_nacimiento": manana, "sexo": "M",
        }
        assert client.post("/api/pacientes", json=payload, headers=headers).status_code == 422

    def test_sexo_invalido_rechazado(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        payload = {
            "ci": "2222222", "nombre": "X", "apellido": "Y",
            "fecha_nacimiento": "1990-01-01", "sexo": "Z",
        }
        assert client.post("/api/pacientes", json=payload, headers=headers).status_code == 422