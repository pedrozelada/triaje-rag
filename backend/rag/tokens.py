"""Conteo de los tokens que reporta el proveedor del modelo.

Vive aparte del servicio para que `backend/rag/service.py` se lea como el
recorrido del triaje y no como una mezcla de recorrido y plumbing de
llama-index.
"""

import logging
from typing import Any

from llama_index.core.callbacks import CBEventType
from llama_index.core.callbacks.base_handler import BaseCallbackHandler
from llama_index.core.callbacks.token_counting import get_tokens_from_response

logger = logging.getLogger(__name__)


class ContadorTokens(BaseCallbackHandler):
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
    def start_trace(self, trace_id: str | None = None) -> None:
        return None

    def end_trace(
        self, trace_id: str | None = None, trace_map: dict | None = None
    ) -> None:
        return None

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: dict[str, Any] | None = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: dict[str, Any] | None = None,
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
        return bool(self._eventos) and all(evento[2] for evento in self._eventos)

    @property
    def tokens_prompt(self) -> int:
        return sum(evento[0] for evento in self._eventos)

    @property
    def tokens_completacion(self) -> int:
        return sum(evento[1] for evento in self._eventos)

    @property
    def tokens_totales(self) -> int:
        return self.tokens_prompt + self.tokens_completacion
