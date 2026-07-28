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