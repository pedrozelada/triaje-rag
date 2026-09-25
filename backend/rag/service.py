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

import time
import logging
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Optional

from llama_index.core.callbacks import CBEventType, CallbackManager
from llama_index.core.callbacks.base_handler import BaseCallbackHandler
from llama_index.core.callbacks.token_counting import get_tokens_from_response

from ai_service.models import DatosVitales
from ai_service.indice import ParametrosIndice
from ai_service.rag_pipeline import (
    cargar_o_crear_indice,
    estado_indice,
    obtener_query_engine_con_vitales,
)
from ai_service.providers import get_llm_models
from ai_service.red_flags import Alerta, evaluar_reglas, nivel_maximo
from ai_service.utils import obtener_nivel_urgencia_color
from backend.core.config import settings

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
    page_label: Optional[str] = None
    score: Optional[float] = None
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
    nivel_urgencia: Optional[str]
    prompt_utilizado: str
    modelo_utilizado: str
    tiempo_respuesta: float
    tokens_consumidos: Optional[int] = None
    fuentes: list = field(default_factory=list)
    reglas_activadas: list[str] = field(default_factory=list)
    #: Chunks recuperados, en orden de similitud descendente (evidencia de C2).
    recuperaciones: list[Recuperacion] = field(default_factory=list)
    #: Desglose de tokens cuando el proveedor los reporta (None = no disponible).
    tokens_prompt: Optional[int] = None
    tokens_completacion: Optional[int] = None
    #: "proveedor" si los tokens los reportó la API; None si no se midieron.
    tokens_origen: Optional[str] = None


class _ContadorTokens(BaseCallbackHandler):
    """Handler de llama-index que suma los tokens reportados por el PROVEEDOR.

    No estima: usa `get_tokens_from_response`, que lee el bloque de uso de la
    respuesta cruda (`usage` / `usage_metadata`) con las claves de OpenAI, Groq,
    Gemini y compatibles. Si un evento no trae uso, el token queda **no
    disponible** en lugar de inventarse con un tokenizador aproximado, porque el
    consumo se cita en la tesis como evidencia y debe ser reproducible.

    Se registra además `reportado`: solo si TODOS los eventos de LLM trajeron
    uso se publica un total; con uno solo sin reportar, el total sería una cota
    inferior y se descarta (mejor None que un número que miente).
    """

    def __init__(self) -> None:
        super().__init__(event_starts_to_ignore=[], event_ends_to_ignore=[])
        self._eventos: list[tuple[int, int, bool]] = []

    # --- Interfaz de BaseCallbackHandler ---
    def start_trace(self, trace_id: Optional[str] = None) -> None:
        return None

    def end_trace(
        self, trace_id: Optional[str] = None, trace_map: Optional[dict] = None
    ) -> None:
        return None

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: Optional[dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: Optional[dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> None:
        if event_type != CBEventType.LLM or not payload:
            return
        prompt_tokens, completacion_tokens = self._uso_de(payload)
        reportado = bool(prompt_tokens or completacion_tokens)
        self._eventos.append((prompt_tokens, completacion_tokens, reportado))

    @staticmethod
    def _uso_de(payload: dict[str, Any]) -> tuple[int, int]:
        """Tokens (prompt, completación) del payload del evento, o (0, 0)."""
        respuesta = payload.get("response") or payload.get("completion")
        if respuesta is None:
            return 0, 0
        try:
            return get_tokens_from_response(respuesta)
        except Exception as e:  # proveedor con un formato de uso inesperado
            logger.debug("No se pudo leer el uso de tokens: %s", e)
            return 0, 0

    # --- Resultados ---
    @property
    def reportado(self) -> bool:
        """True solo si hubo eventos y todos trajeron tokens del proveedor."""
        return bool(self._eventos) and all(e[2] for e in self._eventos)

    @property
    def tokens_prompt(self) -> int:
        return sum(e[0] for e in self._eventos)

    @property
    def tokens_completacion(self) -> int:
        return sum(e[1] for e in self._eventos)

    @property
    def tokens_totales(self) -> int:
        return self.tokens_prompt + self.tokens_completacion


class RAGService:
    """Wrapper del motor RAG para el backend."""

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

    def analizar(
        self,
        datos_vitales: DatosVitales,
        sintomas: str,
        modelo_nombre: Optional[str] = None,
        medir_tokens: Optional[bool] = None,
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

        # Conteo de tokens: el handler se engancha a `llm.callback_manager`
        # DESPUÉS de construir el engine, porque `as_query_engine` pasa por
        # `resolve_llm`, que reasigna ese atributo del LLM (un handler añadido
        # antes quedaría descartado y el conteo nunca llegaría). Se retira al
        # terminar, incluso si la consulta falla, para no dejar estado
        # compartido; el lock evita que dos consultas medidas se atribuyan los
        # tokens de la otra.
        contador: Optional[_ContadorTokens] = None
        if medir_tokens:
            contador = _ContadorTokens()
            self._lock_conteo.acquire()
            try:
                llm.callback_manager.add_handler(contador)
            except Exception:
                self._lock_conteo.release()
                raise

        try:
            start = time.time()
            response = query_engine.query(sintomas)
            elapsed = time.time() - start
        finally:
            if contador is not None:
                llm.callback_manager.remove_handler(contador)
                self._lock_conteo.release()

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

        # Tokens: se publican solo si el proveedor reportó el uso en TODOS los
        # eventos de LLM de esta consulta. Si no, queda None: un consumo no
        # medido es preferible a un número estimado que parezca medido.
        tokens: Optional[int] = None
        tokens_prompt: Optional[int] = None
        tokens_completacion: Optional[int] = None
        tokens_origen: Optional[str] = None
        if contador is not None and contador.reportado:
            tokens = contador.tokens_totales
            tokens_prompt = contador.tokens_prompt
            tokens_completacion = contador.tokens_completacion
            tokens_origen = "proveedor"

        fuentes = []
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