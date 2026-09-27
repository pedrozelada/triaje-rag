"""Contrato de rutas de la API.

Modularizar los routers (`backend/api/admin.py` pasa a ser un paquete) no debe
perder ni renombrar ni un endpoint. Este test congela el conjunto exacto de
pares (método, ruta) del prefijo `/api`, que es el contrato que consume el
frontend.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RUTAS_ESPERADAS = {
    ("GET", "/api/health"),
    ("GET", "/api/auth/me"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/registro"),
    ("GET", "/api/pacientes"),
    ("POST", "/api/pacientes"),
    ("GET", "/api/pacientes/{paciente_id}"),
    ("PUT", "/api/pacientes/{paciente_id}"),
    ("DELETE", "/api/pacientes/{paciente_id}"),
    ("GET", "/api/triage"),
    ("POST", "/api/triage"),
    ("GET", "/api/triage/modelos"),
    ("GET", "/api/triage/{consulta_id}"),
    ("GET", "/api/informes/paciente/{paciente_id}"),
    ("GET", "/api/informes/paciente/{paciente_id}/texto"),
    ("GET", "/api/informes/paciente/{paciente_id}/pdf"),
    ("GET", "/api/admin/estadisticas"),
    ("GET", "/api/admin/estadisticas/triaje"),
    ("GET", "/api/admin/estadisticas/llm"),
    ("GET", "/api/admin/indice"),
    ("GET", "/api/admin/usuarios"),
    ("POST", "/api/admin/usuarios"),
    ("PUT", "/api/admin/usuarios/{usuario_id}"),
    ("DELETE", "/api/admin/usuarios/{usuario_id}"),
}

TAGS_ESPERADOS = {
    "/api/admin": "admin",
    "/api/auth": "auth",
    "/api/informes": "informes",
    "/api/pacientes": "pacientes",
    "/api/triage": "triage",
}


def rutas_api(app) -> set[tuple[str, str]]:
    """Pares (método, ruta) de las rutas de la aplicación bajo `/api`."""
    return {
        (metodo, ruta.path)
        for ruta in app.routes
        if getattr(ruta, "path", "").startswith("/api")
        for metodo in getattr(ruta, "methods", set())
        if metodo != "HEAD"
    }


class TestContratoDeRutas:
    def test_rutas_exactas(self):
        from backend.app.main import app

        assert rutas_api(app) == RUTAS_ESPERADAS

    def test_prefijos_y_tags_del_openapi(self):
        """Cada familia de rutas conserva su prefijo y su tag."""
        from backend.app.main import app

        for ruta in app.routes:
            path = getattr(ruta, "path", "")
            for prefijo, tag in TAGS_ESPERADOS.items():
                if path.startswith(prefijo):
                    assert tag in ruta.tags, f"{path} perdió el tag {tag}"

    def test_schemas_de_respuesta_declarados(self):
        """Los endpoints que devuelven datos declaran su response_model."""
        from backend.app.main import app

        esperados = {
            "/api/admin/estadisticas",
            "/api/admin/estadisticas/triaje",
            "/api/admin/estadisticas/llm",
            "/api/admin/indice",
            "/api/admin/usuarios",
            "/api/informes/paciente/{paciente_id}",
            "/api/pacientes",
            "/api/pacientes/{paciente_id}",
            "/api/triage",
            "/api/triage/{consulta_id}",
        }
        con_schema = {
            ruta.path
            for ruta in app.routes
            if getattr(ruta, "response_model", None) is not None
        }
        assert esperados <= con_schema
