"""Interfaz Gradio mejorada con datos vitales del paciente."""

import logging
import gradio as gr
from typing import Dict
from ui.callbacks import procesar_triaje_con_vitales

logger = logging.getLogger(__name__)


def crear_interfaz_gradio_mejorada(index, llm_models: Dict) -> gr.Blocks:
    """
    Crea interfaz Gradio mejorada con campos de datos vitales.
    
    Args:
        index: VectorStoreIndex cargado
        llm_models: Diccionario de modelos LLM disponibles
        
    Returns:
        gr.Blocks: Interfaz Gradio configurada
    """
    
    with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue")) as demo:
        gr.Markdown("# 🏥 Sistema de Triaje Médico con RAG (NNAC Bolivia)")
        gr.Markdown(
            "Sistema inteligente de apoyo a la decisión clínica para postas rurales. "
            "Ingresa los datos del paciente y síntomas para obtener evaluación de triaje."
        )
        
        with gr.Row():
            # PANEL IZQUIERDO: DATOS DEL PACIENTE
            with gr.Column(scale=1):
                gr.Markdown("## 👤 Datos del Paciente")
                
                # Selector de modelo
                modelo = gr.Dropdown(
                    choices=list(llm_models.keys()),
                    value=list(llm_models.keys())[0],
                    label="🤖 Modelo LLM"
                )
                
                # Datos demográficos
                gr.Markdown("### Información Básica")
                with gr.Row():
                    edad = gr.Number(
                        value=40,
                        label="Edad (años)",
                        precision=0,
                        minimum=0,
                        maximum=150,
                        scale=1
                    )

                sexo = gr.Radio(
                    choices=["M", "F", "Otro"],
                    value="M",
                    label="Sexo",
                    scale=1
                )
                
                # Datos vitales
                gr.Markdown("### Signos Vitales")
                temperatura = gr.Slider(
                    minimum=30.0,
                    maximum=45.0,
                    step=0.1,
                    value=37.0,
                    label="Temperatura (°C)"
                )
                
                with gr.Row():
                    presion_sistolica = gr.Number(
                        value=120,
                        label="PA Sistólica (mmHg)",
                        precision=0,
                        minimum=40,
                        maximum=250
                    )
                    presion_diastolica = gr.Number(
                        value=80,
                        label="PA Diastólica (mmHg)",
                        precision=0,
                        minimum=20,
                        maximum=150
                    )
                
                frecuencia_cardiaca = gr.Number(
                    value=70,
                    label="Frecuencia Cardíaca (bpm)",
                    precision=0,
                    minimum=20,
                    maximum=200
                )
                
                saturacion = gr.Number(
                    value=98.0,
                    label="Saturación O2 (%)",
                    precision=1,
                    minimum=50,
                    maximum=100
                )
            
                
                # Nota legal
                gr.Markdown(
                    "⚠️ Prototipo. No reemplaza evaluación médica profesional."
                )

            # PANEL DERECHO: RESULTADOS
            with gr.Column(scale=2):
                gr.Markdown("### Descripción Clínica")
                pregunta = gr.Textbox(
                    lines=6,
                    placeholder=(
                        "Sé lo más específico posible. "
                        "Ej: Dolor torácico opresivo que irradia al brazo izquierdo, "
                        "diaforesis, disnea de 30 min de evolución, náuseas..."
                    ),
                    label="Síntomas y Presentación Clínica",
                    info="Describe detalladamente los síntomas del paciente"
                )
                
                # Botón de evaluación
                btn_triaje = gr.Button(
                    "🔍 Evaluar Triaje",
                    variant="primary",
                    size="lg"
                )
                gr.Markdown("## 📋 Evaluación de Triaje")
                
                # Indicador de tiempo
                tiempo_ui = gr.Markdown(
                    "⏱️ **Tiempo de generación:** --"
                )
                
                # Respuesta principal (con más espacio)
                respuesta_ui = gr.Textbox(
                    value="La evaluación aparecerá aquí...",
                    label="Resultado del Triaje",
                    lines=15,
                    interactive=False,
                    show_label=True
                )
                
                # Fuentes recuperadas
                with gr.Accordion(
                    "📚 Fuentes Recuperadas (Documentos NNAC)",
                    open=True
                ):
                    fuentes_ui = gr.Markdown(
                        "Las referencias a normas aparecerán aquí..."
                    )

        # Conectar el botón al callback
        btn_triaje.click(
            fn=lambda q, m, e, s, t, ps, pd, fc, sat: procesar_triaje_con_vitales(
                q, m, index, llm_models, int(e), s, float(t),
                int(ps), int(pd), int(fc), float(sat)
            ),
            inputs=[
                pregunta, modelo, edad, sexo, temperatura,
                presion_sistolica, presion_diastolica,
                frecuencia_cardiaca, saturacion
            ],
            outputs=[respuesta_ui, tiempo_ui, fuentes_ui],
            queue=True
        )
    
    return demo
