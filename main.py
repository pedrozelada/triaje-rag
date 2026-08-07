"""Entry point del sistema de triaje médico."""

import logging
import sys
import argparse
import subprocess
import os
from config import DATA_DIR, CHROMA_PATH
from ai_service.rag_pipeline import cargar_o_crear_indice
from ai_service.providers import get_llm_models
from ai_service.errors import RAGError
from ui.gradio_mejorada import crear_interfaz_gradio_mejorada

logger = logging.getLogger(__name__)


def main():
    """Inicializa el sistema y lanza la interfaz seleccionada."""
    
    parser = argparse.ArgumentParser(description="Sistema de Triaje Médico con RAG")
    parser.add_argument(
        "--interface",
        choices=["gradio", "streamlit"],
        default="gradio",
        help="Interfaz a utilizar (default: gradio)"
    )
    args = parser.parse_args()
    
    try:
        logger.info("=" * 60)
        logger.info("🏥 Sistema de Triaje Médico con RAG (NNAC Bolivia)")
        logger.info("=" * 60)
        
        # Cargar modelos LLM
        logger.info("\n📦 Cargando modelos LLM...")
        llm_models = get_llm_models()
        logger.info(f"✅ Modelos disponibles: {list(llm_models.keys())}")
        
        # Cargar o crear índice
        logger.info("\n📚 Inicializando índice vectorial...")
        index = cargar_o_crear_indice(
            data_dir=DATA_DIR,
            chroma_path=CHROMA_PATH
        )
        logger.info("✅ Índice cargado correctamente")
        
        # Lanzar interfaz seleccionada
        if args.interface == "streamlit":
            logger.info("\n🎨 Lanzando interfaz Streamlit...")
            logger.info("Accede a http://localhost:8501")
            
            # Usar subprocess para lanzar Streamlit en nuevo proceso
            streamlit_path = os.path.join(os.path.dirname(__file__), "ui", "streamlit_app.py")
            subprocess.run(
                ["streamlit", "run", streamlit_path, "--logger.level=info"],
                check=False
            )
        else:
            # Gradio (por defecto)
            logger.info("\n🎨 Creando interfaz Gradio mejorada...")
            demo = crear_interfaz_gradio_mejorada(index, llm_models)
            
            # Lanzar aplicación
            logger.info("\n🚀 Lanzando aplicación...")
            logger.info("Accede a http://localhost:7860")
            demo.launch()
        
    except RAGError as e:
        logger.error(f"❌ Error del sistema RAG: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error inesperado: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
