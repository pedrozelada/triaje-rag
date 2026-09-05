"""Tests de seguridad: autenticación obligatoria y bootstrap de admins."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ADMIN = {
    "ci": "7000007",
    "nombre_completo": "Admin Seguridad",
    "email": "admin@seguridad.bo",
    "password": "admin123",
    "rol": "admin",
}

PACIENTE = {
    "ci": "1234567", "nombre": "Juan", "apellido": "Perez",
    "fecha_nacimiento": "1990-05-10", "sexo": "M",
}


def registrar_y_loguear(client, datos):
    r = client.post("/api/auth/registro", json=datos)
    assert r.status_code == 201, r.text
    r = client.post(
        "/api/auth/login", json={"email": datos["email"], "password": datos["password"]}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestAutenticacionObligatoria:
    """Sin token, los datos clínicos deben ser inaccesibles."""

    def test_pacientes_requieren_token(self, client):
        assert client.get("/api/pacientes").status_code == 401
        assert client.post("/api/pacientes", json=PACIENTE).status_code == 401
        assert client.put("/api/pacientes/1", json={"nombre": "X"}).status_code == 401
        assert client.delete("/api/pacientes/1").status_code == 401

    def test_informes_requieren_token(self, client):
        assert client.get("/api/informes/paciente/1").status_code == 401
        assert client.get("/api/informes/paciente/1/texto").status_code == 401

    def test_triage_consultas_requieren_token(self, client):
        assert client.get("/api/triage").status_code == 401
        assert client.get("/api/triage/1").status_code == 401

    def test_token_invalido_rechazado(self, client):
        headers = {"Authorization": "Bearer token-falso"}
        assert client.get("/api/pacientes", headers=headers).status_code == 401

    def test_acceso_con_token_funciona(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        r = client.post("/api/pacientes", json=PACIENTE, headers=headers)
        assert r.status_code == 201
        assert client.get("/api/pacientes", headers=headers).status_code == 200


class TestRegistroSeguro:
    """Roles válidos y bootstrap del primer administrador."""

    def test_rol_invalido_rechazado(self, client):
        r = client.post(
            "/api/auth/registro",
            json={**ADMIN, "rol": "superusuario", "email": "x@x.bo", "ci": "1"},
        )
        assert r.status_code == 400

    def test_bootstrap_solo_primer_admin(self, client):
        # El primer admin se permite (bootstrap para BD nueva)
        assert client.post("/api/auth/registro", json=ADMIN).status_code == 201
        # Un segundo admin ya no puede auto-registrarse
        r = client.post(
            "/api/auth/registro",
            json={**ADMIN, "ci": "8000008", "email": "admin2@seguridad.bo"},
        )
        assert r.status_code == 403
        # Los roles clínicos siguen siendo registro libre
        r2 = client.post(
            "/api/auth/registro",
            json={**ADMIN, "rol": "medico", "ci": "6000006", "email": "med@seguridad.bo"},
        )
        assert r2.status_code == 201

    def test_admin_panel_puede_crear_admin(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        r = client.post(
            "/api/admin/usuarios",
            json={
                "ci": "5000005",
                "nombre_completo": "Admin Dos",
                "email": "admin2@panel.bo",
                "password": "clave123",
                "rol": "admin",
            },
            headers=headers,
        )
        assert r.status_code == 201
        assert r.json()["rol"] == "admin"