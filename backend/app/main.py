"""Punto de entrada de la API FastAPI del sistema de triaje."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.db.base import Base
from backend.db.session import engine
from backend.api import admin, auth, pacientes, triage, informes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Advertencia de seguridad: secret key por defecto (solo para desarrollo).
if settings.secret_key == "cambia-este-secreto-en-produccion":
    logger.warning(
        "⚠️ JWT_SECRET_KEY no configurada: se está usando el valor por defecto. "
        "Define JWT_SECRET_KEY en el archivo .env antes de pasar a producción."
    )

app = FastAPI(
    title="Triaje Médico RAG API",
    description="Backend del sistema de triaje con RAG, CRUD de pacientes y auditoría.",
    version="1.0.0",
)

# CORS para el frontend (Streamlit/React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear tablas al arrancar (SQLite/desarrollo). En producción usar Alembic.
Base.metadata.create_all(bind=engine)


def _migraciones_ligeras():
    """Migraciones idempotentes para SQLite (puente hasta adoptar Alembic).

    create_all no altera tablas existentes, así que las columnas nuevas se
    agregan aquí con ALTER TABLE protegido por inspección.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "consulta_triage" not in inspector.get_table_names():
        return
    columnas = {c["name"] for c in inspector.get_columns("consulta_triage")}
    if "reglas_activadas" not in columnas:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE consulta_triage "
                "ADD COLUMN reglas_activadas TEXT DEFAULT '[]' NOT NULL"
            ))
        logger.info("Migración aplicada: consulta_triage.reglas_activadas añadida.")


_migraciones_ligeras()

app.include_router(auth.router)
app.include_router(pacientes.router)
app.include_router(triage.router)
app.include_router(informes.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "servicio": "triaje-rag-backend"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)