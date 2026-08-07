"""Servicio que envuelve el motor RAG y devuelve un resultado estructurado.

Esto permite que el backend persista la auditoría (prompt, respuesta,
modelo, tiempo, tokens) sin acoplarse a llama-index directamente.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional

from ai_service.models import DatosVitales
from ai_service.rag_pipeline import (
    cargar_o_crear_indice,
    obtener_query_engine_con_vitales,
)
from ai_service.providers import get_llm_models
from ai_service.utils import obtener_nivel_urgencia_color

logger = logging.getLogger(__name__)


@dataclass
class ResultadoTriage:
    """Resultado estructurado de una consulta de triaje."""

    respuesta: str
    nivel_urgencia: Optional[str]
    prompt_utilizado: str
    modelo_utilizado: str
    tiempo_respuesta: float
    tokens_consumidos: Optional[int] = None
    fuentes: list = field(default_factory=list)


class RAGService:
    """Wrapper del motor RAG para el backend."""

    def __init__(self):
        self._index = None
        self._llm_models = None

    def _inicializar(self):
        """Carga el índice y los modelos de forma perezosa (singleton)."""
        if self._index is None:
            self._index = cargar_o_crear_indice()
        if self._llm_models is None:
            self._llm_models = get_llm_models()

    def analizar(
        self,
        datos_vitales: DatosVitales,
        sintomas: str,
        modelo_nombre: Optional[str] = None,
    ) -> ResultadoTriage:
        """
        Ejecuta el triaje RAG y devuelve un resultado estructurado.

        Args:
            datos_vitales: signos vitales del paciente.
            sintomas: descripción clínica / motivo de consulta.
            modelo_nombre: nombre del modelo a usar (clave de get_llm_models).
                Si es None, usa el primero disponible.
        """
        self._inicializar()

        # Seleccionar modelo
        if modelo_nombre and modelo_nombre in self._llm_models:
            llm = self._llm_models[modelo_nombre]
            modelo_usado = modelo_nombre
        else:
            modelo_usado = next(iter(self._llm_models))
            llm = self._llm_models[modelo_usado]

        # Construir el texto del paciente que irá al prompt (auditoría)
        prompt_utilizado = (
            f"DATOS CLÍNICOS DEL PACIENTE:\n"
            f"- Edad: {datos_vitales.edad} años\n"
            f"- Sexo: {datos_vitales.sexo}\n"
            f"- Temperatura: {datos_vitales.temperatura}°C\n"
            f"- PA: {datos_vitales.presion_sistolica}/{datos_vitales.presion_diastolica} mmHg\n"
            f"- FC: {datos_vitales.frecuencia_cardiaca} bpm\n"
            f"- FR: {datos_vitales.frecuencia_respiratoria} rpm\n"
            f"- SpO2: {datos_vitales.saturacion}%\n"
            f"DESCRIPCIÓN: {sintomas}"
        )

        query_engine = obtener_query_engine_con_vitales(
            self._index, llm, datos_vitales
        )

        start = time.time()
        response = query_engine.query(sintomas)
        elapsed = time.time() - start

        respuesta_texto = str(getattr(response, "response", "") or "").strip()
        nivel = obtener_nivel_urgencia_color(respuesta_texto)

        # Tokens: solo disponible en algunos LLM (Groq). None para local.
        tokens = getattr(response, "metadata", {}).get("total_tokens") if hasattr(
            response, "metadata"
        ) else None

        fuentes = []
        for node in getattr(response, "source_nodes", []) or []:
            meta = getattr(node, "metadata", {}) or {}
            fuentes.append(meta.get("archivo", "Desconocido"))

        return ResultadoTriage(
            respuesta=respuesta_texto,
            nivel_urgencia=nivel,
            prompt_utilizado=prompt_utilizado,
            modelo_utilizado=modelo_usado,
            tiempo_respuesta=round(elapsed, 3),
            tokens_consumidos=tokens,
            fuentes=fuentes,
        )


# Instancia única del servicio (se carga al primer uso).
rag_service = RAGService()