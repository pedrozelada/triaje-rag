"""Tests de caracterización de las estadísticas del panel de administración.

Fijan el comportamiento actual (cifras, series rellenadas con ceros, filtros de
período y errores de validación) antes de unificar los dos endpoints casi
idénticos en un único núcleo de agregados. Si el refactor cambia un número, aquí
se ve.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta

from tests.helpers import (
    crear_consulta,
    crear_paciente,
    hace_n_anios,
    hace_n_dias,
    id_de,
    registrar_y_loguear,
)


def sembrar(db, usuario_id: int) -> dict:
    """Escenario con 7 pacientes, 4 consultas y un triaje fuera del mes.

    - 3 consultas dentro de los últimos 30 días (una de hoy, dos anteriores).
    - 1 consulta de hace 40 días, sin nivel, sin modelo y sin mediciones.
    - 7 pacientes que cubren todos los rangos etarios del desglose.
    """
    pacientes = {
        "nino": crear_paciente(db, ci="1001", edad=3, sexo="M"),
        "escuela": crear_paciente(db, ci="1002", edad=10, sexo="F"),
        "adolescente": crear_paciente(db, ci="1003", edad=15, sexo="M"),
        "joven": crear_paciente(db, ci="1004", edad=25, sexo="F"),
        "adulto": crear_paciente(db, ci="1005", edad=40, sexo="M"),
        "mayor": crear_paciente(db, ci="1006", edad=60, sexo="F"),
        "anciano": crear_paciente(db, ci="1007", edad=70, sexo="M"),
    }
    consultas = {
        "hoy": crear_consulta(
            db,
            paciente_id=pacientes["joven"],
            nivel="rojo",
            modelo="groq",
            tokens=100,
            tiempo=1.5,
            fecha=hace_n_dias(0),
            motivo="dolor torácico opresivo",
            sintomas="dolor torácico opresivo con sudoración",
            usuario_id=usuario_id,
        ),
        "dos_dias": crear_consulta(
            db,
            paciente_id=pacientes["adulto"],
            nivel="amarillo",
            modelo="groq",
            tokens=50,
            tiempo=2.5,
            fecha=hace_n_dias(2),
            sintomas="fiebre alta y tos",
            usuario_id=usuario_id,
        ),
        "ayer": crear_consulta(
            db,
            paciente_id=pacientes["joven"],
            nivel="verde",
            modelo="gemini",
            tokens=70,
            tiempo=3.5,
            fecha=hace_n_dias(1),
            sintomas="control de rutina",
            usuario_id=usuario_id,
        ),
        "vieja": crear_consulta(
            db,
            paciente_id=pacientes["anciano"],
            nivel=None,
            modelo=None,
            tokens=None,
            tiempo=None,
            fecha=hace_n_dias(40),
            motivo="control",
            usuario_id=None,
        ),
    }
    assert pacientes and consultas
    return {"pacientes": pacientes, "consultas": consultas}


class TestEstadisticasGenerales:
    def test_cifras_globales(self, client, sesion):
        headers = registrar_y_loguear(client)
        usuario_id = id_de(client, headers)
        sembrar(sesion, usuario_id)

        r = client.get("/api/admin/estadisticas", headers=headers)
        assert r.status_code == 200, r.text
        datos = r.json()

        assert datos["total_consultas"] == 4
        assert datos["total_pacientes"] == 7
        assert datos["total_usuarios"] == 1
        # (1.5 + 2.5 + 3.5) / 3: la consulta sin tiempo no entra en el promedio
        assert datos["promedio_tiempo_respuesta"] == 2.5
        assert datos["modelo_mas_usado"] == "groq"
        assert datos["total_tokens"] == 220

        por_nivel = {fila["nivel"]: fila["cantidad"] for fila in datos["por_nivel"]}
        assert por_nivel == {"rojo": 1, "amarillo": 1, "verde": 1, "sin_clasificar": 1}

        por_modelo = {fila["modelo"]: fila for fila in datos["por_modelo"]}
        assert por_modelo["groq"]["consultas"] == 2
        assert por_modelo["groq"]["tokens"] == 150
        assert por_modelo["gemini"]["consultas"] == 1
        assert por_modelo["gemini"]["tokens"] == 70

        assert len(datos["consultas_por_dia"]) == 30
        assert datos["consultas_por_dia"][-1]["fecha"] == date.today().isoformat()
        assert datos["consultas_por_dia"][-1]["cantidad"] == 1
        assert datos["consultas_por_dia"][-2]["cantidad"] == 1

        # Las tres consultas de los últimos días son del usuario registrado;
        # la de hace 40 días es anónima y no aparece.
        assert datos["actividad_usuarios"] == [
            {"usuario_id": usuario_id, "nombre": "Admin Test", "consultas": 3}
        ]

    def test_demografia_de_pacientes(self, client, sesion):
        """Los pacientes se agrupan por sexo y por rango etario, con ceros."""
        headers = registrar_y_loguear(client)
        sembrar(sesion, id_de(client, headers))

        datos = client.get("/api/admin/estadisticas", headers=headers).json()

        por_sexo = {fila["sexo"]: fila["cantidad"] for fila in datos["por_sexo"]}
        assert por_sexo == {"M": 4, "F": 3}

        por_rango = {fila["rango"]: fila["cantidad"] for fila in datos["por_rango_edad"]}
        assert por_rango == {
            "0-5": 1,
            "6-12": 1,
            "13-17": 1,
            "18-30": 1,
            "31-50": 1,
            "51-64": 1,
            "65+": 1,
        }

    def test_motivos_frecuentes_cuentan_palabras(self, client, sesion):
        headers = registrar_y_loguear(client)
        sembrar(sesion, id_de(client, headers))

        datos = client.get("/api/admin/estadisticas", headers=headers).json()
        palabras = {fila["palabra"]: fila["cantidad"] for fila in datos["motivos_frecuentes"]}

        assert palabras["dolor"] == 2
        assert palabras["fiebre"] == 1
        assert palabras["control"] == 2
        assert palabras["rutina"] == 1
        # "con" y "de" son stopwords y no aparecen
        assert "con" not in palabras
        assert "de" not in palabras

    def test_palabra_con_tilde_interna_se_parte(self, client, sesion):
        """Limitación actual, documentada a propósito.

        La normalización NFD deja el acento como carácter combinante y el
        `[a-z]+` corta ahí: "torácico" queda como "tora" + "ico". Se fija aquí
        para que corregirlo (por ejemplo quitando las marcas combinantes) sea
        una decisión explícita y no un cambio silencioso de las cifras.
        """
        headers = registrar_y_loguear(client)
        sembrar(sesion, id_de(client, headers))

        datos = client.get("/api/admin/estadisticas", headers=headers).json()
        palabras = {fila["palabra"]: fila["cantidad"] for fila in datos["motivos_frecuentes"]}

        assert palabras["tora"] == 2
        assert palabras["cico"] == 2
        assert "toracico" not in palabras

    def test_requiere_admin(self, client, sesion):
        headers = registrar_y_loguear(
            client,
            {
                "ci": "2000001",
                "nombre_completo": "Medico",
                "email": "medico@triaje.bo",
                "password": "clave123",
                "rol": "medico",
            },
        )
        assert client.get("/api/admin/estadisticas", headers=headers).status_code == 403


class TestEstadisticasPorPeriodo:
    def test_ultimos_dias(self, client, sesion):
        headers = registrar_y_loguear(client)
        sembrar(sesion, id_de(client, headers))

        r = client.get("/api/admin/estadisticas/triaje?dias=7", headers=headers)
        assert r.status_code == 200, r.text
        datos = r.json()

        hoy = date.today()
        assert datos["fecha_desde"] == (hoy - timedelta(days=6)).isoformat()
        assert datos["fecha_hasta"] == hoy.isoformat()
        assert datos["total_consultas"] == 3
        assert datos["total_tokens"] == 220
        assert len(datos["consultas_por_dia"]) == 7
        assert datos["consultas_por_dia"][-1]["cantidad"] == 1

        por_nivel = {fila["nivel"]: fila["cantidad"] for fila in datos["por_nivel"]}
        assert por_nivel == {"rojo": 1, "amarillo": 1, "verde": 1}

        # La demografía del período cuenta CONSULTAS, no pacientes distintos:
        # el paciente joven (F) consultó dos veces, así que aporta dos.
        por_sexo = {fila["sexo"]: fila["cantidad"] for fila in datos["por_sexo"]}
        assert por_sexo == {"F": 2, "M": 1}
        por_rango = {
            fila["rango"]: fila["cantidad"] for fila in datos["por_rango_edad"]
        }
        assert por_rango["18-30"] == 2
        assert por_rango["31-50"] == 1
        assert datos["promedio_tiempo_respuesta"] == 2.5

    def test_rango_explicito_inclusive(self, client, sesion):
        headers = registrar_y_loguear(client)
        sembrar(sesion, id_de(client, headers))

        hoy = date.today()
        desde = (hoy - timedelta(days=2)).isoformat()
        r = client.get(
            f"/api/admin/estadisticas/triaje?fecha_desde={desde}&fecha_hasta={hoy.isoformat()}",
            headers=headers,
        )
        datos = r.json()
        assert r.status_code == 200, r.text
        assert datos["total_consultas"] == 3
        assert len(datos["consultas_por_dia"]) == 3

    def test_sin_parametros_usa_el_ultimo_mes(self, client, sesion):
        headers = registrar_y_loguear(client)
        sembrar(sesion, id_de(client, headers))

        datos = client.get("/api/admin/estadisticas/triaje", headers=headers).json()
        assert datos["total_consultas"] == 3
        assert len(datos["consultas_por_dia"]) == 30

    def test_rango_invertido_rechazado(self, client):
        headers = registrar_y_loguear(client)
        hoy = date.today()
        r = client.get(
            "/api/admin/estadisticas/triaje"
            f"?fecha_desde={hoy.isoformat()}&fecha_hasta={(hoy - timedelta(days=3)).isoformat()}",
            headers=headers,
        )
        assert r.status_code == 400
        assert "posterior" in r.json()["detail"]

    def test_dias_invalido_rechazado(self, client):
        headers = registrar_y_loguear(client)
        assert (
            client.get("/api/admin/estadisticas/triaje?dias=0", headers=headers).status_code
            == 400
        )


class TestEstadisticasLLM:
    def test_rendimiento_por_modelo(self, client, sesion):
        headers = registrar_y_loguear(client)
        sembrar(sesion, id_de(client, headers))

        r = client.get("/api/admin/estadisticas/llm", headers=headers)
        assert r.status_code == 200, r.text
        datos = r.json()

        # La consulta sin modelo registrado queda fuera de estas cifras
        assert datos["total_consultas"] == 3
        assert datos["total_tokens"] == 220
        assert datos["tiempo_promedio"] == 2.5
        assert datos["tiempo_minimo"] == 1.5
        assert datos["tiempo_maximo"] == 3.5

        por_modelo = {fila["modelo"]: fila for fila in datos["por_modelo"]}
        assert por_modelo["groq"] == {
            "modelo": "groq",
            "consultas": 2,
            "tokens": 150,
            "tiempo_promedio": 2.0,
            "tiempo_minimo": 1.5,
            "tiempo_maximo": 2.5,
        }
        assert por_modelo["gemini"]["consultas"] == 1
        assert por_modelo["gemini"]["tiempo_promedio"] == 3.5

    def test_sin_datos_los_tiempos_son_nulos(self, client):
        headers = registrar_y_loguear(client)
        datos = client.get("/api/admin/estadisticas/llm", headers=headers).json()
        assert datos == {
            "total_consultas": 0,
            "total_tokens": 0,
            "tiempo_promedio": None,
            "tiempo_minimo": None,
            "tiempo_maximo": None,
            "por_modelo": [],
        }


def test_fechas_de_nacimiento_del_escenario():
    """El sembrado usa edades exactas: el cálculo de rangos depende de eso."""
    assert hace_n_anios(3) == date.today().replace(year=date.today().year - 3)
