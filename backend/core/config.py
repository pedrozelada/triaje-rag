"""Configuración centralizada del backend (FastAPI + SQLAlchemy)."""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # CORS (el frontend Streamlit/React correrá en otro puerto)
    cors_origins: list[str] = ["http://localhost:8501", "http://localhost:3000"]


settings = Settings()