"""Tests de caracterización de los informes de historial de paciente.

Fijan el contrato de los tres formatos (JSON, texto plano y PDF), el orden de
las consultas y el tratamiento de errores, antes de mover la generación a
`backend/reports/` y sacar la lógica del router.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import builtins

from tests.helpers import (
    crear_consulta,
    crear_paciente,
    hace_n_dias,
    registrar_y_loguear,
)


def sembrar_historial(db) -> int:
    """Un paciente con dos consultas (ayer y hoy) y una sin respuestas."""
    paciente_id = crear_paciente(db, ci="7001", edad=34, sexo="F", nombre="Ana", apellido="Quispe")
    crear_consulta(
        db,
        paciente_id=paciente_id,
        nivel="amarillo",
        fecha=hace_n_dias(1),
        motivo="dolor abdominal",
        sintomas="dolor abdominal de 2 días de evolución",
    )
    crear_consulta(
        db,
        paciente_id=paciente_id,
        nivel="rojo",
        fecha=hace_n_dias(0),
        motivo="dolor torácico",
        sintomas="dolor torácico opresivo con sudoración",
    )
    return paciente_id


class TestHistorialJson:
    def test_orden_descendente_y_contenido(self, client, sesion):
        headers = registrar_y_loguear(client)
        paciente_id = sembrar_historial(sesion)

        r = client.get(f"/api/informes/paciente/{paciente_id}", headers=headers)
        assert r.status_code == 200, r.text
        consultas = r.json()
        assert [c["nivel_urgencia"] for c in consultas] == ["rojo", "amarillo"]
        assert consultas[0]["motivo_consulta"] == "dolor torácico"
        assert consultas[0]["prompt_utilizado"] == "PROMPT DE PRUEBA"

    def test_paciente_inexistente(self, client):
        headers = registrar_y_loguear(client)
        assert (
            client.get("/api/informes/paciente/999", headers=headers).status_code == 404
        )

    def test_requiere_sesion(self, client, sesion):
        paciente_id = sembrar_historial(sesion)
        assert client.get(f"/api/informes/paciente/{paciente_id}").status_code == 401


class TestInformeTexto:
    def test_encabezado_y_consultas_en_orden_ascendente(self, client, sesion):
        headers = registrar_y_loguear(client)
        paciente_id = sembrar_historial(sesion)

        r = client.get(f"/api/informes/paciente/{paciente_id}/texto", headers=headers)
        assert r.status_code == 200, r.text
        informe = r.json()["informe"]

        assert "INFORME DE TRIAJE - HISTORIAL DEL PACIENTE" in informe
        assert "Generado por: Admin Test" in informe
        assert "Paciente: Ana Quispe" in informe
        assert "C.I.: 7001" in informe
        assert "Total de consultas: 2" in informe
        # Orden ascendente: la consulta de ayer (amarillo) va antes que la de hoy
        assert informe.index("Nivel de urgencia: amarillo") < informe.index(
            "Nivel de urgencia: rojo"
        )
        assert "--- Consulta 1 (" in informe and "--- Consulta 2 (" in informe
        assert "Prompt utilizado (auditoría):" in informe
        assert "Resultado:" in informe

    def test_paciente_inexistente(self, client):
        headers = registrar_y_loguear(client)
        assert (
            client.get("/api/informes/paciente/999/texto", headers=headers).status_code
            == 404
        )


class TestInformePdf:
    def test_pdf_descargable(self, client, sesion):
        headers = registrar_y_loguear(client)
        paciente_id = sembrar_historial(sesion)

        r = client.get(f"/api/informes/paciente/{paciente_id}/pdf", headers=headers)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF-")
        assert f"informe_paciente_{paciente_id}_" in r.headers["content-disposition"]

    def test_sin_reportlab_responde_500(self, client, sesion, monkeypatch):
        """Un servidor sin reportlab informa del problema, no revienta."""
        headers = registrar_y_loguear(client)
        paciente_id = sembrar_historial(sesion)

        importacion_real = builtins.__import__

        def importacion_sin_reportlab(nombre, *args, **kwargs):
            if nombre.startswith("reportlab"):
                raise ImportError("reportlab no disponible (test)")
            return importacion_real(nombre, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", importacion_sin_reportlab)

        r = client.get(f"/api/informes/paciente/{paciente_id}/pdf", headers=headers)
        assert r.status_code == 500
        assert "reportlab" in r.json()["detail"]

    def test_paciente_inexistente(self, client):
        headers = registrar_y_loguear(client)
        assert (
            client.get("/api/informes/paciente/999/pdf", headers=headers).status_code
            == 404
        )
