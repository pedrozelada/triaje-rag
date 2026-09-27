"""Servicio que envuelve el motor RAG y devuelve un resultado estructurado.

Esto permite que el backend persista la auditoría (prompt, respuesta,
modelo, tiempo, tokens) sin acoplarse a llama-index directamente.

Evidencia de recuperación
-------------------------
`ResultadoTriage.fuentes` conserva su formato histórico (lista de nombres de
archivo) porque lo consumen la API y la UI. Para la evaluación del sistema
(Componente 2 de la tesis) eso no basta: Recall@k, Precision@k y MRR necesitan
el **orden** y el **score** de cada chunk, y la procedencia fina (página del
PDF). Por eso se añade `recuperaciones`, que no reemplaza a `fuentes`: es
información adicional que no altera ninguna decisión del triaje.
"""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from ai_service.indice import ParametrosIndice
from ai_service.models import DatosVitales
from ai_service.providers import get_llm_models
from ai_service.rag_pipeline import (
    cargar_o_crear_indice,
    estado_indice,
    obtener_query_engine_con_vitales,
)
from ai_service.red_flags import Alerta, evaluar_reglas, nivel_maximo
from ai_service.utils import obtener_nivel_urgencia_color
from backend.core.config import settings
from backend.rag.tokens import ContadorTokens

logger = logging.getLogger(__name__)

#: Caracteres de cada chunk que se conservan como vista previa en la evidencia.
#: Suficiente para que un informe cite el fragmento sin inflar la auditoría.
LARGO_PREVIEW = 300


@dataclass
class Recuperacion:
    """Un chunk recuperado por el motor vectorial, con su procedencia y score.

    Es la unidad con la que se calculan las métricas de recuperación: `rank`
    (1 = más similar) y `score` permiten MRR y Recall@k; `archivo` y
    `page_label` permiten comparar contra la fuente esperada de cada caso.
    """

    rank: int
    archivo: str
    page_label: str | None = None
    score: float | None = None
    preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "archivo": self.archivo,
            "page_label": self.page_label,
            "score": self.score,
            "preview": self.preview,
        }


@dataclass
class ResultadoTriage:
    """Resultado estructurado de una consulta de triaje."""

    respuesta: str
    nivel_urgencia: str | None
    prompt_utilizado: str
    modelo_utilizado: str
    tiempo_respuesta: float
    tokens_consumidos: int | None = None
    fuentes: list = field(default_factory=list)
    reglas_activadas: list[str] = field(default_factory=list)
    #: Chunks recuperados, en orden de similitud descendente (evidencia de C2).
    recuperaciones: list[Recuperacion] = field(default_factory=list)
    #: Desglose de tokens cuando el proveedor los reporta (None = no disponible).
    tokens_prompt: int | None = None
    tokens_completacion: int | None = None
    #: "proveedor" si los tokens los reportó la API; None si no se midieron.
    tokens_origen: str | None = None


class RAGService:
    """Wrapper del motor RAG para el backend.

    `analizar()` es el punto de entrada; los pasos del recorrido (elegir el
    modelo, armar el prompt, medir tokens, leer las fuentes, resolver el nivel)
    están separados para poder leerlos y probarlos por partes.
    """

    def __init__(self):
        self._index = None
        self._llm_models = None
        # Forma del índice (modelo de embeddings y segmentación) con la que se
        # construyó lo que hay en disco: si no coincide, el índice se reconstruye.
        self._parametros = ParametrosIndice()
        # El backend atiende requests en varios hilos: sin este lock, dos
        # triajes simultáneos podían inicializar el índice y los modelos a la
        # vez (trabajo duplicado y probes de red redundantes al primer arranque).
        self._lock_inicializacion = Lock()
        # El conteo de tokens engancha un handler al callback manager del LLM,
        # que es un objeto compartido. Este lock serializa SOLO las consultas
        # con conteo activo, para que dos peticiones simultáneas no se atribuyan
        # los tokens de la otra. Con el conteo desactivado (por defecto) no se
        # toma nunca, así que la concurrencia normal no se ve afectada.
        self._lock_conteo = Lock()

    def _inicializar(self):
        """Carga el índice y los modelos de forma perezosa (singleton, thread-safe)."""
        if self._index is not None and self._llm_models is not None:
            return
        with self._lock_inicializacion:
            if self._index is None:
                # Las rutas y la política de reconstrucción vienen de la
                # configuración, para que DATA_DIR / CHROMA_PATH del README
                # funcionen de verdad en lugar de quedar como valores fijos.
                self._index = cargar_o_crear_indice(
                    data_dir=settings.data_dir,
                    chroma_path=settings.chroma_path,
                    parametros=self._parametros,
                    permitir_reconstruccion=settings.rag_reconstruccion_automatica,
                )
            if self._llm_models is None:
                self._llm_models = get_llm_models()

    def precalentar(self) -> None:
        """Deja el índice y los modelos cargados antes del primer triaje.

        Se invoca desde el lifespan de FastAPI: sin esto, el primer paciente
        atendido tras cada reinicio paga la carga del modelo de embeddings.
        """
        self._inicializar()

    def estado_indice(self) -> dict[str, Any]:
        """Estado del índice sin cargar modelos (solo lectura, para el panel admin)."""
        return estado_indice(
            data_dir=settings.data_dir,
            chroma_path=settings.chroma_path,
            parametros=self._parametros,
        )

    def listar_modelos(self) -> list[str]:
        """Devuelve los nombres de los modelos LLM disponibles.

        Solo carga los modelos (no el índice vectorial), por lo que es
        liviano y se puede usar para poblar un selector en el frontend.
        """
        if self._llm_models is None:
            self._llm_models = get_llm_models()
        return list(self._llm_models.keys())

    # ------------------------------------------------------------------
    # Pasos del triaje
    # ------------------------------------------------------------------

    def _elegir_modelo(self, modelo_nombre: str | None) -> tuple[str, Any]:
        """Modelo pedido, o el primero disponible si no se pidió ninguno válido."""
        if modelo_nombre and modelo_nombre in self._llm_models:
            return modelo_nombre, self._llm_models[modelo_nombre]
        modelo_usado = next(iter(self._llm_models))
        return modelo_usado, self._llm_models[modelo_usado]

    @staticmethod
    def _construir_prompt(datos_vitales: DatosVitales, sintomas: str) -> str:
        """Texto de auditoría, idéntico al bloque que ve el LLM en el prompt.

        Se arma desde la fuente única de verdad (`a_texto_prompt`) para que lo
        guardado y lo enviado no puedan divergir.
        """
        return (
            f"DATOS CLÍNICOS DEL PACIENTE:\n"
            f"{datos_vitales.a_texto_prompt()}\n"
            f"DESCRIPCIÓN: {sintomas}"
        )

    @contextmanager
    def _conteo_de_tokens(
        self, llm: Any, activo: bool
    ) -> Iterator[ContadorTokens | None]:
        """Engancha el contador al LLM mientras dura la consulta.

        El handler se añade DESPUÉS de construir el engine, porque
        `as_query_engine` pasa por `resolve_llm`, que reasigna
        `llm.callback_manager`: un handler añadido antes quedaría descartado y
        el conteo nunca llegaría. Se retira al terminar, incluso si la consulta
        falla, y el lock (tomado solo cuando la medición está activa) evita que
        dos consultas medidas se atribuyan los tokens de la otra.
        """
        if not activo:
            yield None
            return

        contador = ContadorTokens()
        self._lock_conteo.acquire()
        try:
            llm.callback_manager.add_handler(contador)
            yield contador
        finally:
            llm.callback_manager.remove_handler(contador)
            self._lock_conteo.release()

    @staticmethod
    def _tokens_publicados(
        contador: ContadorTokens | None,
    ) -> tuple[int | None, int | None, int | None, str | None]:
        """Tokens que se pueden publicar como evidencia.

        Solo si el proveedor reportó el uso en TODOS los eventos de LLM de la
        consulta: un consumo no medido es preferible a un número estimado que
        parezca medido.
        """
        if contador is None or not contador.reportado:
            return None, None, None, None
        return (
            contador.tokens_totales,
            contador.tokens_prompt,
            contador.tokens_completacion,
            "proveedor",
        )

    @staticmethod
    def _extraer_recuperaciones(response: Any) -> tuple[list[str], list[Recuperacion]]:
        """Nombres de archivo (formato histórico) y chunks con su procedencia."""
        fuentes: list[str] = []
        recuperaciones: list[Recuperacion] = []
        for rank, node in enumerate(getattr(response, "source_nodes", []) or [], 1):
            meta = getattr(node, "metadata", {}) or {}
            archivo = meta.get("archivo", "Desconocido")
            fuentes.append(archivo)
            page_label = meta.get("page_label")
            score = getattr(node, "score", None)
            texto = str(getattr(node, "text", "") or "")
            recuperaciones.append(
                Recuperacion(
                    rank=rank,
                    archivo=archivo,
                    page_label=None if page_label is None else str(page_label),
                    score=None if score is None else float(score),
                    preview=" ".join(texto[:LARGO_PREVIEW].split()),
                )
            )
        return fuentes, recuperaciones

    @staticmethod
    def _resolver_nivel(respuesta_texto: str, alertas: list[Alerta]) -> str | None:
        """Nivel final: el más urgente entre el LLM y las reglas.

        Las reglas NUNCA bajan el nivel del LLM; si el LLM no produjo nivel
        parseable pero hay reglas activas, manda el nivel de la regla.
        """
        nivel_llm = obtener_nivel_urgencia_color(respuesta_texto)
        nivel_reglas: str | None = None
        for alerta in alertas:
            nivel_reglas = nivel_maximo(nivel_reglas, alerta.nivel)

        if nivel_llm is None:
            logger.warning(
                "Respuesta del LLM sin nivel parseable (queda sin_clasificar para "
                "revisión manual)."
            )
        return nivel_maximo(nivel_llm, nivel_reglas)

    def analizar(
        self,
        datos_vitales: DatosVitales,
        sintomas: str,
        modelo_nombre: str | None = None,
        medir_tokens: bool | None = None,
    ) -> ResultadoTriage:
        """
        Ejecuta el triaje RAG y devuelve un resultado estructurado.

        Args:
            datos_vitales: signos vitales del paciente.
            sintomas: descripción clínica / motivo de consulta.
            modelo_nombre: nombre del modelo a usar (clave de get_llm_models).
                Si es None, usa el primero disponible.
            medir_tokens: mide el consumo real de tokens del LLM. Si es None se
                usa la configuración (`RAG_MEDIR_TOKENS`). Solo publica un total
                cuando el proveedor reporta el uso; si no, queda en None.
        """
        self._inicializar()

        if medir_tokens is None:
            medir_tokens = settings.rag_medir_tokens

        modelo_usado, llm = self._elegir_modelo(modelo_nombre)
        prompt_utilizado = self._construir_prompt(datos_vitales, sintomas)

        # Reglas deterministas de seguridad (evaluadas SIEMPRE, antes del LLM).
        alertas: list[Alerta] = evaluar_reglas(datos_vitales, sintomas)

        query_engine = obtener_query_engine_con_vitales(
            self._index, llm, datos_vitales
        )

        # El conteo de tokens engancha su handler alrededor de la consulta.
        with self._conteo_de_tokens(llm, medir_tokens) as contador:
            start = time.time()
            response = query_engine.query(sintomas)
            elapsed = time.time() - start

        respuesta_texto = str(getattr(response, "response", "") or "").strip()
        nivel = self._resolver_nivel(respuesta_texto, alertas)
        tokens, tokens_prompt, tokens_completacion, tokens_origen = (
            self._tokens_publicados(contador)
        )
        fuentes, recuperaciones = self._extraer_recuperaciones(response)

        return ResultadoTriage(
            respuesta=respuesta_texto,
            nivel_urgencia=nivel,
            prompt_utilizado=prompt_utilizado,
            modelo_utilizado=modelo_usado,
            tiempo_respuesta=round(elapsed, 3),
            tokens_consumidos=tokens,
            fuentes=fuentes,
            reglas_activadas=[alerta.descripcion for alerta in alertas],
            recuperaciones=recuperaciones,
            tokens_prompt=tokens_prompt,
            tokens_completacion=tokens_completacion,
            tokens_origen=tokens_origen,
        )


# Instancia única del servicio (se carga al primer uso).
rag_service = RAGService()