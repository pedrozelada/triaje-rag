"""Gestión de la sesión/engine de SQLAlchemy."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings

# SQLite no soporta threading entre conexiones; se desactiva check_same_thread.
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    """
    Dependencia de FastAPI que provee una sesión de DB por request.
    Cierra la sesión automáticamente al terminar.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()