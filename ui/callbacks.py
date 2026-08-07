"""Manejadores de eventos y callbacks para la interfaz Gradio."""

import time
import logging
from typing import Tuple, Dict, Any, Optional
from ai_service.rag_pipeline import obtener_query_engine, obtener_query_engine_con_vitales
from ai_service.models import DatosVitales, DATOS_VITALES_DEFAULT
from ai_service.utils import (
    validar_entrada_pregunta,
    formatear_fuentes_con_archivo,
    obtener_respuesta_segura,
    formatear_tiempo,
    validar_datos_vitales
)
from ai_service.errors import QueryExecutionError

logger = logging.getLogger(__name__)


def procesar_triaje(
    pregunta: str,
    modelo_seleccionado: str,
    index,
    llm_models: dict
) -> Tuple[str, str, str]:
    """
    Procesa la consulta de triaje con manejo robusto de errores.
    
    Args:
        pregunta: Descripción de síntomas del paciente
        modelo_seleccionado: Nombre del modelo LLM a usar
        index: VectorStoreIndex cargado
        llm_models: Diccionario de modelos disponibles
        
    Returns:
        Tuple: (respuesta, tiempo, fuentes) o (error_msg, "", "")
    """
    
    # Validar entrada
    if not validar_entrada_pregunta(pregunta):
        return (
            "❌ Por favor ingresa una descripción válida de los síntomas (mínimo 10 caracteres).",
            "",
            ""
        )
    
    # Validar que el modelo esté disponible
    if modelo_seleccionado not in llm_models:
        return (
            f"❌ Modelo '{modelo_seleccionado}' no disponible.",
            "",
            ""
        )
    
    try:
        start_time = time.time()
        logger.info(f"Procesando consulta con {modelo_seleccionado}...")
        
        # Obtener el modelo LLM
        llm_model = llm_models[modelo_seleccionado]
        
        # Configurar query engine (sin datos vitales)
        query_engine = obtener_query_engine(index, llm_model)
        
        # Ejecutar consulta
        response = query_engine.query(pregunta)
        
        end_time = time.time()
        tiempo_respuesta = end_time - start_time
        
        # Validar response
        if response is None:
            raise QueryExecutionError("Response es None")
        
        # Extraer respuesta y fuentes de forma segura
        respuesta_texto = obtener_respuesta_segura(response)
        fuentes_texto = formatear_fuentes_con_archivo(response)
        tiempo_texto = formatear_tiempo(tiempo_respuesta)
        
        logger.info(f"✅ Consulta procesada en {tiempo_respuesta:.2f}s")
        
        return (respuesta_texto, tiempo_texto, fuentes_texto)
        
    except QueryExecutionError as e:
        logger.error(f"Error de ejecución: {e}")
        return (
            f"❌ Error al ejecutar la consulta: {str(e)}",
            "",
            ""
        )
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        return (
            f"❌ Error inesperado: {str(e)}. Intenta de nuevo.",
            "",
            ""
        )


def procesar_triaje_con_vitales(
    pregunta: str,
    modelo_seleccionado: str,
    index,
    llm_models: dict,
    edad: int,
    sexo: str,
    temperatura: float,
    presion_sistolica: int,
    presion_diastolica: int,
    frecuencia_cardiaca: int,
    saturacion: float
) -> Tuple[str, str, str]:
    """
    Procesa triaje incluyendo datos vitales del paciente.
    
    Args:
        pregunta: Síntomas
        modelo_seleccionado: Modelo LLM
        index: VectorStoreIndex
        llm_models: Diccionario de modelos
        edad: Edad en años
        sexo: M/F/Otro
        temperatura: Temperatura en °C
        presion_sistolica: PA sistólica
        presion_diastolica: PA diastólica
        frecuencia_cardiaca: FC en bpm
        saturacion: SatO2 en %
        
    Returns:
        Tuple: (respuesta, tiempo, fuentes)
    """
    
    # Validar entrada
    if not validar_entrada_pregunta(pregunta):
        return (
            "❌ Por favor ingresa una descripción válida de los síntomas (mínimo 10 caracteres).",
            "",
            ""
        )
    
    # Validar modelo
    if modelo_seleccionado not in llm_models:
        return (
            f"❌ Modelo '{modelo_seleccionado}' no disponible.",
            "",
            ""
        )
    
    # Validar datos vitales
    datos_dict = {
        "edad": edad,
        "sexo": sexo,
        "temperatura": temperatura,
        "presion_sistolica": presion_sistolica,
        "presion_diastolica": presion_diastolica,
        "frecuencia_cardiaca": frecuencia_cardiaca,
        "saturacion": saturacion
    }
    
    es_valido, error_msg = validar_datos_vitales(datos_dict)
    if not es_valido:
        return (f"❌ {error_msg}", "", "")
    
    try:
        start_time = time.time()
        logger.info(f"Procesando consulta con vitales usando {modelo_seleccionado}...")
        
        # Crear objeto DatosVitales
        datos_vitales = DatosVitales(
            edad=edad,
            sexo=sexo,
            temperatura=temperatura,
            presion_sistolica=presion_sistolica,
            presion_diastolica=presion_diastolica,
            frecuencia_cardiaca=frecuencia_cardiaca,
            saturacion=saturacion
        )
        
        # Obtener modelo
        llm_model = llm_models[modelo_seleccionado]
        
        # Configurar query engine CON datos vitales
        query_engine = obtener_query_engine_con_vitales(index, llm_model, datos_vitales)
        
        # Ejecutar consulta
        response = query_engine.query(pregunta)
        
        end_time = time.time()
        tiempo_respuesta = end_time - start_time
        
        if response is None:
            raise QueryExecutionError("Response es None")
        
        # Extraer y formatear respuesta
        respuesta_texto = obtener_respuesta_segura(response)
        fuentes_texto = formatear_fuentes_con_archivo(response)
        tiempo_texto = formatear_tiempo(tiempo_respuesta)
        
        logger.info(f"✅ Triaje con vitales procesado en {tiempo_respuesta:.2f}s")
        
        return (respuesta_texto, tiempo_texto, fuentes_texto)
        
    except QueryExecutionError as e:
        logger.error(f"Error de ejecución: {e}")
        return (f"❌ Error al ejecutar la consulta: {str(e)}", "", "")
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        return (f"❌ Error inesperado: {str(e)}. Intenta de nuevo.", "", "")
