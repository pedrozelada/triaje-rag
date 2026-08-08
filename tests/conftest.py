"""Configuración de pytest."""

import pytest
import sys
import os

# Agregar root al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def client():
    """TestClient con BD SQLite en memoria (aislado del triaje.db real)."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend.db.base import Base

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(bind=test_engine, future=True)

    # Parchear la session del módulo deps/app para usar la BD de test.
    import backend.db.session as db_session
    import backend.app.main as main

    db_session.engine = test_engine
    db_session.SessionLocal = TestingSessionLocal
    main.SessionLocal = TestingSessionLocal

    from backend.app.main import app

    # Reemplazar la dependencia get_db por una que use la BD de test.
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[db_session.get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
