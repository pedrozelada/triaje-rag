"""Configuración centralizada del sistema."""

import os
import logging
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Rutas
DATA_DIR = os.getenv("DATA_DIR", "./data")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")

# Validar que .env esté configurado (no fatal al importar: sólo advierte).
# Algunas herramientas (tests, scripts auxiliares) importan config sin .env.
if not os.path.exists(".env"):
    logger.warning(
        "⚠️ Archivo .env no encontrado. "
        "Copia .env.example a .env y configura tus credenciales "
        "antes de ejecutar la aplicación."
    )
