"""Interfaz Gradio para el Sistema de Triaje Médico."""

import logging
import gradio as gr
from typing import Dict
from ui.callbacks import procesar_triaje as callback_procesar_triaje

logger = logging.getLogger(__name__)


def crear_interfaz_gradio(index, llm_models: Dict) -> gr.Blocks:
    """
    Crea la interfaz Gradio para el sistema de triaje.
    
    Args:
        index: VectorStoreIndex cargado
        llm_models: Diccionario de modelos LLM disponibles
        
    Returns:
        gr.Blocks: Interfaz Gradio configurada
    """
    
    with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue")) as demo:
        gr.Markdown("# 🏥 Sistema de Triaje Médico con RAG (NNAC Bolivia)")
        gr.Markdown(
            "Sistema de apoyo a la decisión clínica para postas rurales. "
            "Compara la velocidad y respuestas entre la nube (Groq) y local (Ollama)."
        )
        
        with gr.Row():
            with gr.Column(scale=1):
                # Selector de modelo
                modelo = gr.Dropdown(
                    choices=list(llm_models.keys()),
                    value=list(llm_models.keys())[0],
                    label="Seleccionar Modelo LLM"
                )
                
                # Campo de entrada de síntomas
                pregunta = gr.Textbox(
                    lines=4,
                    placeholder=(
                        "Ej: Paciente de 45 años con dolor torácico opresivo "
                        "que irradia al brazo izquierdo, diaforesis y disnea "
                        "de 30 minutos de evolución..."
                    ),
                    label="Descripción de los síntomas del paciente"
                )
                
                # Botón de evaluación
                btn_triaje = gr.Button("🔍 Evaluar Triaje", variant="primary")
                
                # Nota legal
                gr.Markdown("### ⚠️ Nota:")
                gr.Markdown(
                    "Esta herramienta es de apoyo y no reemplaza el criterio médico profesional."
                )

            with gr.Column(scale=2):
                # Tiempo de generación
                tiempo_ui = gr.Markdown("⏱️ **Tiempo de generación:** --")
                
                # Respuesta (mejorado: usando Textbox para mejor manejo)
                respuesta_ui = gr.Textbox(
                    value="La respuesta aparecerá aquí...",
                    label="Evaluación y Recomendación de Triaje",
                    lines=12,
                    interactive=False
                )
                
                # Fuentes recuperadas
                with gr.Accordion("📚 Ver Fuentes Recuperadas (Chunks)", open=False):
                    fuentes_ui = gr.Markdown("Las fuentes aparecerán aquí...")

        # Conectar el botón al callback
        btn_triaje.click(
            fn=lambda q, m: callback_procesar_triaje(q, m, index, llm_models),
            inputs=[pregunta, modelo],
            outputs=[respuesta_ui, tiempo_ui, fuentes_ui],
            queue=True  # Habilitar queue para mejor manejo de concurrencia
        )
    
    return demo
