"""Utilidades: validaciones, formateo, manejo de datos."""

import logging
import re
from typing import Dict, Any, Tuple, Optional
from ai_service.models import DatosVitales

logger = logging.getLogger(__name__)


def validar_entrada_pregunta(pregunta: str, min_length: int = 10) -> bool:
    """
    Valida que la pregunta sea válida.
    
    Args:
        pregunta: Texto de la pregunta
        min_length: Longitud mínima requerida
        
    Returns:
        bool: True si es válida
    """
    if not pregunta:
        logger.warning("Pregunta vacía")
        return False
    
    if len(pregunta.strip()) < min_length:
        logger.warning(f"Pregunta muy corta: {len(pregunta)} caracteres")
        return False
    
    return True


def obtener_respuesta_segura(response: Any) -> str:
    """
    Obtiene la respuesta de forma segura, con validaciones.
    
    Args:
        response: Objeto response de llama-index
        
    Returns:
        str: Texto de la respuesta o mensaje de error
    """
    try:
        response_text = getattr(response, 'response', None)
        
        if not response_text:
            return "❌ No se pudo generar respuesta. Intenta de nuevo."
        
        return str(response_text).strip()
        
    except Exception as e:
        logger.error(f"Error obteniendo respuesta: {e}")
        return "❌ Error al procesar la respuesta."


def formatear_tiempo(segundos: float) -> str:
    """
    Formatea tiempo en segundos.
    
    Args:
        segundos: Tiempo en segundos
        
    Returns:
        str: Tiempo formateado
    """
    if segundos < 1:
        return f"⏱️ **Tiempo de generación:** {segundos*1000:.0f} ms"
    return f"⏱️ **Tiempo de generación:** {segundos:.2f} segundos"


def validar_datos_vitales(datos: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Valida los datos vitales ingresados por el usuario.

    Los campos ausentes se tratan como NO medidos (None), nunca como valores
    normales por defecto. Solo se rechazan valores PRESENTES fuera de rango.

    Args:
        datos: Diccionario con datos vitales

    Returns:
        Tuple: (es_valido, mensaje_error)
    """
    try:
        def _num(clave: str, casteo):
            valor = datos.get(clave)
            return None if valor is None else casteo(valor)

        # Crear instancia de DatosVitales (edad/sexo obligatorios; el resto
        # puede estar ausente = no medido). Se castea para tolerar strings
        # numéricos que llegan de interfaces legacy.
        vitales = DatosVitales(
            edad=int(datos.get("edad", 0)),
            sexo=datos.get("sexo", "M"),
            temperatura=_num("temperatura", float),
            presion_sistolica=_num("presion_sistolica", int),
            presion_diastolica=_num("presion_diastolica", int),
            frecuencia_cardiaca=_num("frecuencia_cardiaca", int),
            saturacion=_num("saturacion", float)
        )
        
        # Validar
        if not vitales.es_valido():
            return False, "❌ Algunos valores están fuera de rango. Verifica los datos."
        
        return True, None
        
    except (ValueError, TypeError) as e:
        logger.error(f"Error validando datos vitales: {e}")
        return False, "❌ Error en el formato de los datos vitales."


def formatear_fuentes_con_archivo(response: Any) -> str:
    """
    Extrae y formatea las fuentes incluyendo el archivo PDF.
    
    Args:
        response: Objeto response de llama-index
        
    Returns:
        str: Markdown con fuentes formateadas
    """
    try:
        source_nodes = getattr(response, 'source_nodes', None)
        
        if not source_nodes:
            return "No se recuperaron fuentes claras."
        
        fuentes = []
        for i, source_node in enumerate(source_nodes, 1):
            score = getattr(source_node, 'score', 0.0) or 0.0
            texto = str(source_node.text)[:150].replace('\n', ' ').strip()
            
            # Obtener archivo del metadata
            metadata = getattr(source_node, 'metadata', {}) or {}
            archivo = metadata.get('archivo', 'Documento Desconocido')
            
            fuentes.append(
                f"**Fuente {i}** ({archivo}) [Score: {score:.3f}]: {texto}..."
            )
        
        return "\n\n".join(fuentes) if fuentes else "No se recuperaron fuentes claras."
        
    except Exception as e:
        logger.error(f"Error formateando fuentes: {e}")
        return "Error al procesar fuentes."


def obtener_nivel_urgencia_color(respuesta: str) -> Optional[str]:
    """
    Extrae el nivel de urgencia de la respuesta del LLM de forma robusta.

    Busca primero la línea estructurada "NIVEL DE URGENCIA: [valor]" que se
    pide en el prompt. Si no la encuentra, aplica respaldos de ALTA precisión
    (frases clínicas inequívocas). Nunca escanea palabras de color sueltas:
    una negación como "no es rojo" o una mención en la justificación no debe
    clasificar el caso.

    Args:
        respuesta: Texto de la respuesta del LLM

    Returns:
        Optional[str]: Nivel (rojo, naranja, amarillo, verde, azul) o None si
        no se pudo determinar (el llamador debe marcar el caso como
        sin_clasificar para revisión manual, NUNCA asumir un nivel por defecto).
    """
    if not respuesta:
        return None

    # 1) Parseo estructurado de la línea "NIVEL DE URGENCIA: ..."
    match = re.search(
        r"NIVEL\s+DE\s+URGENCIA\s*:\s*([^\n]*)",
        respuesta,
        flags=re.IGNORECASE
    )
    if match:
        valor = match.group(1).strip().lower()
        nivel = _nivel_desde_linea(valor)
        if nivel:
            return nivel

    # 2) Respaldo de alta precisión sobre todo el texto (solo frases
    #    inequívocas: nunca palabras de color sueltas, para evitar que una
    #    negación como "no es rojo" o una mención en la justificación
    #    clasifique el caso).
    return _nivel_desde_texto_libre(respuesta.lower())


def _nivel_desde_linea(valor: str) -> Optional[str]:
    """Resuelve el nivel desde el contenido de la línea estructurada.

    Aquí sí se aceptan colores: el prompt pide llenar la línea con un color
    de Manchester, por lo que la mención es de alta precisión.
    """
    for color in ("rojo", "naranja", "amarillo", "verde", "azul"):
        if re.search(rf"\b{color}\b", valor):
            return color
    return _nivel_desde_texto_libre(valor)


def _nivel_desde_texto_libre(texto: str) -> Optional[str]:
    """Frases clínicas inequívocas; None si no hay coincidencia."""
    if "emergencia" in texto:
        return "rojo"
    if "urgencia mayor" in texto:
        return "naranja"
    if "urgencia menor" in texto:
        return "amarillo"
    if "no urgente" in texto or "no urgencia" in texto:
        return "verde"
    if "autosanamiento" in texto or "orientaci" in texto:
        return "azul"
    return None


COLORES_URGENCIA = {
    "rojo": {"gradio": "#FF0000", "streamlit": "🔴", "hex": "#EF553B", "label": "ROJO - Emergencia"},
    "naranja": {"gradio": "#FF6B35", "streamlit": "🟠", "hex": "#FF6B35", "label": "NARANJA - Urgencia Mayor"},
    "amarillo": {"gradio": "#FFD700", "streamlit": "🟡", "hex": "#FECB52", "label": "AMARILLO - Urgencia Menor"},
    "verde": {"gradio": "#00B050", "streamlit": "🟢", "hex": "#00CC96", "label": "VERDE - No Urgente"},
    "azul": {"gradio": "#007BFF", "streamlit": "🔵", "hex": "#007BFF", "label": "AZUL - Autosanamiento"},
}
