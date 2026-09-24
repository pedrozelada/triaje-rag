"""Configuración centralizada del backend (FastAPI + SQLAlchemy)."""

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Cargar .env en os.environ para que los proveedores LLM (ai_service)
# puedan leer GROQ_API_KEY / OPENAI_API_KEY directamente del entorno.
load_dotenv()


class Settings(BaseSettings):
    """Configuración vía variables de entorno / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base de datos (SQLite por defecto; cambiar a PostgreSQL si el docente pide)
    database_url: str = "sqlite:///./triaje.db"

    # Seguridad JWT
    secret_key: str = os.getenv(
        "JWT_SECRET_KEY", "cambia-este-secreto-en-produccion"
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8  # 8 horas

    # CORS (el frontend React correrá en otro puerto)
    cors_origins: list[str] = ["http://localhost:8501", "http://localhost:3000"]

    # Motor RAG: rutas del corpus y del índice vectorial.
    data_dir: str = "./data"
    chroma_path: str = "./chroma_db"

    # Precalienta el índice al arrancar para que el primer triaje no espere a
    # cargar los modelos. La carga se hace aparte en los tests (donde el
    # lifespan corre con cada cliente de prueba).
    rag_precalentar_al_arrancar: bool = True

    # Si el índice fue construido con otro modelo de embeddings u otra
    # segmentación, sus vectores no son comparables con los de las consultas.
    # Por defecto se aborta (mejor fallar de forma visible que responder con
    # recuperaciones inválidas); activando esto se reconstruye automáticamente.
    rag_reconstruccion_automatica: bool = False


settings = Settings()