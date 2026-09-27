"""Configuración de pytest y fixtures compartidas.

La base de datos de los tests es SQLite en memoria y se parchea en el módulo
`backend.db.session`, de modo que la API (que resuelve `get_db` por objeto de
función) use esa base y nunca toque `triaje.db`. Al terminar cada test se
restauran los objetos originales, así que ningún test hereda el estado de otro.
"""

import os
import sys

import pytest

# Agregar root al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# El lifespan de FastAPI SÍ corre en los tests (el fixture usa
# `with TestClient(app)`), y el lifespan precalienta el índice RAG. Sin esto,
# cada test cargaría el índice y el modelo de embeddings. Debe fijarse antes de
# importar `backend.core.config`, que lee el entorno al construirse.
os.environ["RAG_PRECALENTAR_AL_ARRANCAR"] = "false"


@pytest.fixture(autouse=True)
def sin_dobles_filtrados():
    """Ningún test debe dejar el motor RAG parcheado para los siguientes.

    Un `monkeypatch` sobre la INSTANCIA (`rag_service.analizar = doble`) deja un
    atributo propio que, al deshacerse, sobrescribe el método de la clase: los
    tests posteriores que parchean la clase llaman sin saberlo al motor real
    (con red y con LLM). Esta comprobación convierte ese error silencioso en un
    fallo explícito del test que lo provocó.
    """
    from backend.rag.service import RAGService, rag_service

    originales = {nombre: RAGService.__dict__[nombre] for nombre in ("analizar", "listar_modelos")}
    yield
    propios = sorted(set(vars(rag_service)) & set(originales))
    assert not propios, f"el servicio RAG quedó parcheado a nivel de instancia: {propios}"
    for nombre, original in originales.items():
        assert RAGService.__dict__[nombre] is original, f"RAGService.{nombre} quedó parcheado"


@pytest.fixture()
def db_prueba():
    """Base de datos de test aislada; devuelve su fábrica de sesiones."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import backend.db.session as db_session
    from backend.app.main import app
    from backend.db.base import Base

    engine_prueba = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine_prueba)
    sesiones = sessionmaker(bind=engine_prueba, future=True)

    originales = (db_session.engine, db_session.SessionLocal)
    db_session.engine = engine_prueba
    db_session.SessionLocal = sesiones

    def override_get_db():
        db = sesiones()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[db_session.get_db] = override_get_db
    try:
        yield sesiones
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine_prueba)
        engine_prueba.dispose()
        db_session.engine, db_session.SessionLocal = originales


@pytest.fixture()
def sesion(db_prueba):
    """Sesión de BD de test para sembrar datos antes de llamar a la API."""
    db = db_prueba()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(db_prueba):
    """TestClient con BD SQLite en memoria (aislado del triaje.db real)."""
    from fastapi.testclient import TestClient

    from backend.app.main import app

    with TestClient(app) as c:
        yield c
