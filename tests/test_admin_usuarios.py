"""Tests del CRUD de usuarios del panel de administración."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ADMIN = {
    "ci": "1000001",
    "nombre_completo": "Admin Root",
    "email": "admin@test.bo",
    "password": "admin123",
    "rol": "admin",
}


def registrar_y_loguear(client, datos):
    """Registra un usuario y devuelve los headers con su JWT."""
    assert client.post("/api/auth/registro", json=datos).status_code == 201
    r = client.post(
        "/api/auth/login", json={"email": datos["email"], "password": datos["password"]}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestUsuariosAdmin:
    def test_requiere_rol_admin(self, client):
        headers = registrar_y_loguear(client, {**ADMIN, "rol": "medico"})
        assert client.get("/api/admin/usuarios", headers=headers).status_code == 403
        assert client.post(
            "/api/admin/usuarios", json={**ADMIN, "ci": "2", "email": "x@x.bo"}, headers=headers
        ).status_code == 403

    def test_crear_usuario(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        payload = {
            "ci": "2000002",
            "nombre_completo": "María Pérez",
            "email": "maria@test.bo",
            "password": "clave123",
            "rol": "medico",
            "centro_salud": "Posta San Antonio",
        }
        r = client.post("/api/admin/usuarios", json=payload, headers=headers)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["nombre_completo"] == "María Pérez"
        assert data["rol"] == "medico"
        assert data["activo"] is True
        assert "password" not in data

        # Duplicados rechazados
        r2 = client.post("/api/admin/usuarios", json=payload, headers=headers)
        assert r2.status_code == 400
        r3 = client.post(
            "/api/admin/usuarios",
            json={**payload, "ci": "2000002", "email": "otra@test.bo"},
            headers=headers,
        )
        assert r3.status_code == 400

    def test_actualizar_usuario_y_password(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        creado = client.post(
            "/api/admin/usuarios",
            json={
                "ci": "3000003",
                "nombre_completo": "Luis Rojas",
                "email": "luis@test.bo",
                "password": "clave123",
                "rol": "enfermero_triage",
            },
            headers=headers,
        ).json()

        r = client.put(
            f"/api/admin/usuarios/{creado['id']}",
            json={
                "nombre_completo": "Luis Alberto Rojas",
                "rol": "medico",
                "activo": False,
                "password": "nuevaclave1",
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["nombre_completo"] == "Luis Alberto Rojas"
        assert data["rol"] == "medico"
        assert data["activo"] is False

        # Inactivo no puede loguearse
        r_login = client.post(
            "/api/auth/login", json={"email": "luis@test.bo", "password": "nuevaclave1"}
        )
        assert r_login.status_code == 401

        # Reactivado: la contraseña nueva funciona
        client.put(
            f"/api/admin/usuarios/{creado['id']}", json={"activo": True}, headers=headers
        )
        r_login2 = client.post(
            "/api/auth/login", json={"email": "luis@test.bo", "password": "nuevaclave1"}
        )
        assert r_login2.status_code == 200

    def test_email_duplicado_en_edicion(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        otro = client.post(
            "/api/admin/usuarios",
            json={
                "ci": "4000004",
                "nombre_completo": "Elena Gil",
                "email": "elena@test.bo",
                "password": "clave123",
            },
            headers=headers,
        ).json()
        r = client.put(
            f"/api/admin/usuarios/{otro['id']}",
            json={"email": ADMIN["email"]},
            headers=headers,
        )
        assert r.status_code == 400

    def test_eliminar_usuario(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        creado = client.post(
            "/api/admin/usuarios",
            json={
                "ci": "5000005",
                "nombre_completo": "Por Eliminar",
                "email": "bye@test.bo",
                "password": "clave123",
            },
            headers=headers,
        ).json()

        r = client.delete(f"/api/admin/usuarios/{creado['id']}", headers=headers)
        assert r.status_code == 204

        restante = client.get("/api/admin/usuarios", headers=headers).json()
        assert all(u["id"] != creado["id"] for u in restante)

        # Ya no puede loguearse
        r_login = client.post(
            "/api/auth/login", json={"email": "bye@test.bo", "password": "clave123"}
        )
        assert r_login.status_code == 401

    def test_no_eliminar_usuario_propio(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        propio = client.get("/api/auth/me", headers=headers).json()
        r = client.delete(f"/api/admin/usuarios/{propio['id']}", headers=headers)
        assert r.status_code == 400

    def test_eliminar_inexistente(self, client):
        headers = registrar_y_loguear(client, ADMIN)
        assert client.delete("/api/admin/usuarios/99999", headers=headers).status_code == 404
