"""Servicio que envuelve el motor RAG y devuelve un resultado estructurado.

Esto permite que el backend persista la auditoría (prompt, respuesta,
modelo, tiempo, tokens) sin acoplarse a llama-index directamente.
"""

import time
import logging
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

from ai_service.models import DatosVitales
from ai_service.rag_pipeline import (
    cargar_o_crear_indice,
    obtener_query_engine_con_vitales,
)
from ai_service.providers import get_llm_models
from ai_service.red_flags import Alerta, evaluar_reglas, nivel_maximo
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
    reglas_activadas: list[str] = field(default_factory=list)


class RAGService:
    """Wrapper del motor RAG para el backend."""

    def __init__(self):
        self._index = None
        self._llm_models = None
        # El backend atiende requests en varios hilos: sin este lock, dos
        # triajes simultáneos podían inicializar el índice y los modelos a la
        # vez (trabajo duplicado y probes de red redundantes al primer arranque).
        self._lock_inicializacion = Lock()

    def _inicializar(self):
        """Carga el índice y los modelos de forma perezosa (singleton, thread-safe)."""
        if self._index is not None and self._llm_models is not None:
            return
        with self._lock_inicializacion:
            if self._index is None:
                self._index = cargar_o_crear_indice()
            if self._llm_models is None:
                self._llm_models = get_llm_models()

    def listar_modelos(self) -> list[str]:
        """Devuelve los nombres de los modelos LLM disponibles.

        Solo carga los modelos (no el índice vectorial), por lo que es
        liviano y se puede usar para poblar un selector en el frontend.
        """
        if self._llm_models is None:
            self._llm_models = get_llm_models()
        return list(self._llm_models.keys())

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

        # Construir el texto del paciente (auditoría) desde la fuente única
        # de verdad: idéntico al bloque que ve el LLM en el prompt.
        prompt_utilizado = (
            f"DATOS CLÍNICOS DEL PACIENTE:\n"
            f"{datos_vitales.a_texto_prompt()}\n"
            f"DESCRIPCIÓN: {sintomas}"
        )

        # Reglas deterministas de seguridad (evaluadas SIEMPRE, antes del LLM).
        alertas: list[Alerta] = evaluar_reglas(datos_vitales, sintomas)

        query_engine = obtener_query_engine_con_vitales(
            self._index, llm, datos_vitales
        )

        start = time.time()
        response = query_engine.query(sintomas)
        elapsed = time.time() - start

        respuesta_texto = str(getattr(response, "response", "") or "").strip()
        nivel_llm = obtener_nivel_urgencia_color(respuesta_texto)

        # Nivel final = el más urgente entre el LLM y las reglas. Las reglas
        # NUNCA bajan el nivel del LLM; si el LLM no produjo nivel parseable
        # pero hay reglas activas, manda el nivel de la regla.
        nivel_reglas: Optional[str] = None
        for alerta in alertas:
            nivel_reglas = nivel_maximo(nivel_reglas, alerta.nivel)
        nivel = nivel_maximo(nivel_llm, nivel_reglas)

        if nivel_llm is None:
            logger.warning(
                "Respuesta del LLM sin nivel parseable (queda sin_clasificar para revisión manual)."
            )

        # Tokens: el uso real del LLM requiere instrumentar callbacks
        # (TokenCountingHandler); sin eso se registra None, jamás un invento.
        tokens: Optional[int] = None

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
            reglas_activadas=[alerta.descripcion for alerta in alertas],
        )


# Instancia única del servicio (se carga al primer uso).
rag_service = RAGService()