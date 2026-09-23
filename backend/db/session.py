"""Gestión de la sesión/engine de SQLAlchemy.

Concurrencia con SQLite
-----------------------
FastAPI/Uvicorn atiende requests en varios hilos y SQLite bloquea la base
completa durante una escritura. En una posta con varios enfermeros registrando
triajes en paralelo, el modo por defecto (rollback journal + sin espera)
producía ``sqlite3.OperationalError: database is locked``.

Medidas aplicadas:
  1. ``timeout`` de 30 s en la conexión: un escritor espera a que el lock se
     libere en lugar de fallar de inmediato.
  2. ``PRAGMA journal_mode=WAL``: los lectores no bloquean al escritor ni
     viceversa (lecturas concurrentes durante una escritura).
  3. ``PRAGMA busy_timeout=30000``: refuerzo del timeout a nivel de driver.
  4. ``PRAGMA synchronous=NORMAL``: seguro y con bajo costo bajo WAL.
  5. ``PRAGMA foreign_keys=ON``: SQLite las ignora por defecto, y el esquema
     usa FKs con ON DELETE CASCADE / SET NULL.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings

# SQLite no soporta threading entre conexiones; se desactiva check_same_thread.
es_sqlite = settings.database_url.startswith("sqlite")

connect_args: dict = {}
if es_sqlite:
    connect_args = {
        "check_same_thread": False,
        # Espera hasta 30 s antes de rendirse con "database is locked".
        "timeout": 30,
    }

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    future=True,
)


if es_sqlite:

    @event.listens_for(engine, "connect")
    def _configurar_pragmas_sqlite(dbapi_connection, connection_record):
        """Aplica los PRAGMA de concurrencia y de integridad por conexión.

        El journal_mode es persistente a nivel de base, pero el busy_timeout y
        foreign_keys son por conexión, por lo que se fijan en cada apertura.
        """
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

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