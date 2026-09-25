"""Tests de la instrumentación de métricas del triaje (Componente 2).

Cubren las dos piezas que la evaluación del sistema necesita y que antes no
existían:

1. **Evidencia de recuperación** (`ResultadoTriage.recuperaciones`): orden
   (`rank`), `score`, archivo y página de cada chunk. Sin esto no se pueden
   calcular Recall@k, Precision@k ni MRR. Se verifica además que `fuentes`
   conserve su formato histórico (lo consumen la API y la UI).
2. **Conteo de tokens**: se publica solo el uso que reporta el proveedor, y
   solo si TODOS los eventos de LLM lo reportaron. Un proveedor que no reporta
   uso deja `tokens_consumidos` en None: nunca se estima ni se inventa.

Ningún test toca la red, el corpus real ni la base vectorial real: el índice se
construye en memoria con `MockEmbedding` y el LLM es local.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llama_index.core import Document, VectorStoreIndex
from llama_index.core.embeddings import MockEmbedding
from llama_index.core.llms import CompletionResponse
from llama_index.core.llms.callbacks import llm_completion_callback
from llama_index.core.llms.mock import MockLLM

from ai_service.models import DatosVitales
from backend.rag.service import RAGService

RESPUESTA_VERDE = (
    "NIVEL DE URGENCIA: verde\n"
    "REFERENCIA: No. Manejo y observación en la posta rural\n"
    "JUSTIFICACIÓN: Cuadro leve, sin criterios de gravedad en las NNAC.\n"
    "ACCIONES RECOMENDADAS:\n- Hidratación y reposo\n"
    "FUENTE: NNAC, p. 112\n"
)

DOCUMENTOS = [
    Document(
        text="Manejo del resfriado común y de la fiebre sin signos de alarma.",
        metadata={"archivo": "NNAC-medicina-interna.pdf", "page_label": "112"},
    ),
    Document(
        text="Evaluación pediátrica: frecuencia respiratoria normal del lactante.",
        metadata={"archivo": "NNAC-pediatria.pdf", "page_label": "1047"},
    ),
]


class _LLMConUso(MockLLM):
    """MockLLM que, como un proveedor real, adjunta el uso de tokens.

    `get_tokens_from_response` (llama-index) lee ese bloque para saber cuántos
    tokens se consumieron; aquí se simula el contrato de Groq/Gemini/OpenAI.
    """

    respuesta: str = RESPUESTA_VERDE
    uso_prompt: int = 100
    uso_completacion: int = 20

    @llm_completion_callback()
    def complete(
        self, prompt: str, formatted: bool = False, **kwargs
    ) -> CompletionResponse:
        raw = {}
        if self.uso_prompt or self.uso_completacion:
            raw = {
                "usage": {
                    "prompt_tokens": self.uso_prompt,
                    "completion_tokens": self.uso_completacion,
                }
            }
        return CompletionResponse(text=self.respuesta, raw=raw)


@pytest.fixture()
def servicio():
    """RAGService con índice en memoria y LLM local (sin red ni modelos)."""
    index = VectorStoreIndex.from_documents(
        DOCUMENTOS, embed_model=MockEmbedding(embed_dim=8)
    )
    servicio = RAGService()
    # `_inicializar` retorna temprano si ambos ya están cargados: así el test no
    # depende de data/, chroma_db/ ni de las claves de API.
    servicio._index = index
    servicio._llm_models = {"Mock (local)": _LLMConUso()}
    return servicio


def vitales_leves(**cambios) -> DatosVitales:
    base = dict(
        edad=24,
        sexo="F",
        temperatura=37.6,
        presion_sistolica=112,
        presion_diastolica=72,
        frecuencia_cardiaca=82,
        frecuencia_respiratoria=16,
        saturacion=98.0,
    )
    base.update(cambios)
    return DatosVitales(**base)


class TestEvidenciaDeRecuperacion:
    def test_conserva_orden_score_y_pagina(self, servicio):
        resultado = servicio.analizar(
            vitales_leves(),
            "Dolor de garganta leve, congestión nasal y estornudos.",
        )

        assert len(resultado.recuperaciones) == len(DOCUMENTOS)
        assert [r.rank for r in resultado.recuperaciones] == [1, 2]
        for rec in resultado.recuperaciones:
            assert rec.archivo in {d.metadata["archivo"] for d in DOCUMENTOS}
            assert rec.page_label in {"112", "1047"}
            assert isinstance(rec.score, float)
            assert rec.preview  # vista previa para citar el fragmento

    def test_fuentes_conserva_el_formato_historico(self, servicio):
        """La API y la UI leen `fuentes` como lista de nombres: no debe cambiar."""
        resultado = servicio.analizar(
            vitales_leves(), "Consulta por síntomas leves de vías respiratorias."
        )
        assert resultado.fuentes == [r.archivo for r in resultado.recuperaciones]
        assert all(isinstance(f, str) for f in resultado.fuentes)

    def test_to_dict_es_serializable(self, servicio):
        resultado = servicio.analizar(
            vitales_leves(), "Consulta por síntomas leves de vías respiratorias."
        )
        datos = resultado.recuperaciones[0].to_dict()
        assert set(datos) == {"rank", "archivo", "page_label", "score", "preview"}


class TestConteoDeTokens:
    def test_publica_el_uso_del_proveedor(self, servicio):
        resultado = servicio.analizar(
            vitales_leves(),
            "Consulta por síntomas leves de vías respiratorias.",
            medir_tokens=True,
        )
        assert resultado.tokens_consumidos == 120
        assert resultado.tokens_prompt == 100
        assert resultado.tokens_completacion == 20
        assert resultado.tokens_origen == "proveedor"

    def test_no_hay_tokens_si_el_proveedor_no_reporta(self, servicio):
        """Un proveedor sin bloque de uso deja el token en None, no estimado."""
        # `MockLLM` tiene __init__ propio: se ajustan los campos del contrato
        # de uso sobre la instancia en lugar de pasarlos al constructor.
        llm = _LLMConUso()
        llm.uso_prompt = 0
        llm.uso_completacion = 0
        servicio._llm_models = {"Mock (local)": llm}
        resultado = servicio.analizar(
            vitales_leves(),
            "Consulta por síntomas leves de vías respiratorias.",
            medir_tokens=True,
        )
        assert resultado.tokens_consumidos is None
        assert resultado.tokens_origen is None

    def test_sin_medicion_no_hay_tokens(self, servicio):
        resultado = servicio.analizar(
            vitales_leves(),
            "Consulta por síntomas leves de vías respiratorias.",
            medir_tokens=False,
        )
        assert resultado.tokens_consumidos is None
        assert resultado.tokens_prompt is None
        assert resultado.tokens_completacion is None

    def test_el_handler_se_retira_al_terminar(self, servicio):
        """El handler no debe quedar enganchado tras la consulta (estado limpio)."""
        llm = servicio._llm_models["Mock (local)"]
        servicio.analizar(
            vitales_leves(),
            "Consulta por síntomas leves de vías respiratorias.",
            medir_tokens=True,
        )
        assert llm.callback_manager.handlers == []


class TestComportamientoDelTriajeIntacto:
    def test_las_reglas_siguen_elevando_el_nivel(self, servicio):
        """La instrumentación no altera el resultado clínico del triaje."""
        resultado = servicio.analizar(
            vitales_leves(saturacion=88.0),
            "Refiere cansancio y congestión nasal de dos días de evolución.",
        )
        assert resultado.nivel_urgencia == "rojo"  # SpO2 88% < 90%
        assert any("hipoxemia severa" in a for a in resultado.reglas_activadas)

    def test_negacion_no_dispara_la_regla_naranja(self, servicio):
        """Regresión del bug corregido: 'niega dolor torácico' no eleva el nivel."""
        resultado = servicio.analizar(
            vitales_leves(),
            "Dolor de garganta leve y estornudos. Niega dificultad para respirar, "
            "dolor torácico o vómitos.",
        )
        assert resultado.nivel_urgencia == "verde"
        assert resultado.reglas_activadas == []
