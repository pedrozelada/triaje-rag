"""Utilidades compartidas por los tests de API.

Aquí vive lo que antes estaba copiado en cinco archivos de test: el alta de un
usuario de prueba y la obtención de su JWT. Sembrar datos de dominio (pacientes,
consultas) se hace en los tests concretos, porque cada uno necesita su propio
escenario.
"""

from datetime import date, datetime, timedelta

ADMIN = {
    "ci": "9000001",
    "nombre_completo": "Admin Test",
    "email": "admin@triaje.bo",
    "password": "admin123",
    "rol": "admin",
}


def registrar_y_loguear(client, datos: dict | None = None) -> dict[str, str]:
    """Registra un usuario y devuelve los headers con su JWT.

    El primer usuario que se registra en una base vacía puede ser admin
    (bootstrap); los tests parten siempre de una base vacía.
    """
    datos = datos or ADMIN
    r = client.post("/api/auth/registro", json=datos)
    assert r.status_code == 201, r.text
    r = client.post(
        "/api/auth/login",
        json={"email": datos["email"], "password": datos["password"]},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def id_de(client, headers: dict[str, str]) -> int:
    """Id del usuario autenticado con esos headers."""
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def hace_n_anios(n: int) -> date:
    """Fecha de nacimiento de exactamente `n` años cumplidos hoy."""
    hoy = date.today()
    return hoy.replace(year=hoy.year - n)


def hace_n_dias(n: int, hora: int = 10) -> datetime:
    """Marca de tiempo de hace `n` días (n=0 es hoy), a una hora fija."""
    return (datetime.now() - timedelta(days=n)).replace(
        hour=hora, minute=0, second=0, microsecond=0
    )


def crear_paciente(
    db, *, ci: str, edad: int | None = 30, sexo: str = "M", **extra
) -> int:
    """Inserta un paciente y devuelve su id (sin pasar por la API)."""
    from backend.db.models import Paciente

    paciente = Paciente(
        ci=ci,
        nombre=extra.pop("nombre", f"Paciente {ci}"),
        apellido=extra.pop("apellido", "Test"),
        fecha_nacimiento=extra.pop("fecha_nacimiento", hace_n_anios(edad)),
        sexo=sexo,
        **extra,
    )
    db.add(paciente)
    db.commit()
    db.refresh(paciente)
    return paciente.id


def crear_consulta(
    db,
    *,
    paciente_id: int,
    nivel: str | None = "verde",
    modelo: str | None = "groq",
    tokens: int | None = None,
    tiempo: float | None = None,
    fecha: datetime | None = None,
    motivo: str | None = None,
    sintomas: str | None = None,
    usuario_id: int | None = None,
) -> int:
    """Inserta una consulta de triaje y devuelve su id (sin pasar por la API)."""
    from backend.db.models import ConsultaTriage

    consulta = ConsultaTriage(
        paciente_id=paciente_id,
        usuario_id=usuario_id,
        fecha_hora=fecha or hace_n_dias(0),
        nivel_urgencia=nivel,
        modelo_utilizado=modelo,
        tokens_consumidos=tokens,
        tiempo_respuesta=tiempo,
        motivo_consulta=motivo,
        sintomas=sintomas,
        respuesta_llm="NIVEL DE URGENCIA: verde",
        prompt_utilizado="PROMPT DE PRUEBA",
        reglas_activadas=[],
    )
    db.add(consulta)
    db.commit()
    db.refresh(consulta)
    return consulta.id
