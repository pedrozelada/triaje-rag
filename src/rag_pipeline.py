"""Pipeline RAG: Índice vectorial y Query Engine."""

import os
import logging
from typing import Optional
from threading import Lock
from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    StorageContext,
    PromptTemplate,
    Settings
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

from src.errors import IndexInitializationError, QueryExecutionError
from src.embeddings import get_embedding_model
from src.models import DatosVitales

logger = logging.getLogger(__name__)

# Lock para thread-safety del índice
_index_lock = Lock()
_index_instance: Optional[VectorStoreIndex] = None


def cargar_o_crear_indice(
    data_dir: str = "./data",
    chroma_path: str = "./chroma_db"
) -> VectorStoreIndex:
    """
    Carga los PDFs y crea o carga el índice vectorial.
    
    Thread-safe: usa lock para evitar race conditions.
    
    Args:
        data_dir: Directorio con archivos PDF
        chroma_path: Ruta de la base vectorial Chroma
        
    Returns:
        VectorStoreIndex: Índice vectorial cargado
        
    Raises:
        IndexInitializationError: Si hay error al cargar/crear el índice
    """
    global _index_instance
    
    with _index_lock:
        # Si ya está cargado, devolverlo
        if _index_instance is not None:
            logger.info("Usando índice ya cargado en memoria")
            return _index_instance
        
        try:
            embed_model = get_embedding_model()
            Settings.embed_model = embed_model
            
            # Validar directorio de datos
            if not os.path.exists(data_dir):
                raise IndexInitializationError(
                    f"❌ Directorio de datos no encontrado: {data_dir}"
                )
            
            files = os.listdir(data_dir)
            if not files:
                raise IndexInitializationError(
                    f"❌ No hay archivos PDF en {data_dir}"
                )
            
            logger.info(f"Archivos encontrados: {files}")
            
            # Inicializar Chroma
            chroma_client = chromadb.PersistentClient(path=chroma_path)
            chroma_collection = chroma_client.get_or_create_collection(
                name="nnac_triaje",
                metadata={"description": "Normas Nacionales de Atención Clínica - Triaje"}
            )
            
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            
            # Verificar si hay documentos ya indexados
            doc_count = chroma_collection.count()
            if doc_count > 0:
                logger.info(f"✅ Cargando índice existente ({doc_count} chunks)...")
                index = VectorStoreIndex.from_vector_store(
                    vector_store,
                    embed_model=embed_model
                )
                _index_instance = index
                return index
            
            # Cargar documentos
            logger.info("📂 Cargando documentos...")
            docs = SimpleDirectoryReader(input_dir=data_dir).load_data()
            
            if not docs:
                raise IndexInitializationError(
                    f"❌ No se pudieron cargar documentos de {data_dir}"
                )
            
            logger.info(f"✅ {len(docs)} documentos cargados")
            
            # Enriquecer metadatos con nombre de archivo
            for doc in docs:
                if "file_name" in doc.metadata:
                    doc.metadata["archivo"] = doc.metadata["file_name"]
                else:
                    # Fallback si no existe file_name
                    doc.metadata["archivo"] = "Documento Desconocido"
            
            # Segmentación
            text_splitter = SentenceSplitter(chunk_size=768, chunk_overlap=128)
            nodes = text_splitter.get_nodes_from_documents(docs)
            
            if not nodes:
                raise IndexInitializationError(
                    "❌ No se generaron chunks de los documentos"
                )
            
            logger.info(f"✅ Segmentado en {len(nodes)} chunks")
            
            # Crear índice
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            index = VectorStoreIndex(
                nodes,
                storage_context=storage_context,
                embed_model=embed_model
            )
            
            logger.info("✅ Índice vectorial creado y guardado en ChromaDB")
            _index_instance = index
            return index
            
        except IndexInitializationError:
            raise
        except Exception as e:
            raise IndexInitializationError(f"Error inicializando índice: {str(e)}") from e


def obtener_query_engine(index: VectorStoreIndex, llm_model):
    """
    Configura el Query Engine con el modelo LLM especificado.

    El LLM se pasa de forma local (parámetro `llm=`) para evitar
    condiciones de carrera con el settings global de llama-index.

    Args:
        index: VectorStoreIndex cargado
        llm_model: Instancia del modelo LLM

    Returns:
        QueryEngine: Motor de consultas configurado
    """
    qa_prompt_tmpl = """Eres un asistente de triaje médico para postas rurales de Bolivia.
Usa ÚNICAMENTE la información proporcionada abajo para clasificar el nivel de urgencia.

INFORMACIÓN DE LAS NNAC:
{context_str}

DATOS DEL PACIENTE: {query_str}

Responde en este formato EXACTO:
NIVEL DE URGENCIA: [Emergencia / Urgencia Mayor / Urgencia Menor / No Urgencia]
JUSTIFICACIÓN: [Basada estrictamente en la información de las NNAC proporcionada]
ACCIONES RECOMENDADAS:
- [Acción 1]
- [Acción 2]
FUENTE: [Cita textual breve del documento]
DISCLAIMER: Herramienta de apoyo. No reemplaza evaluación médica profesional.

Si la información no es suficiente, indica: "No hay suficiente información en las NNAC para clasificar este caso."
"""
    qa_template = PromptTemplate(qa_prompt_tmpl)

    return index.as_query_engine(
        llm=llm_model,
        similarity_top_k=5,
        text_qa_template=qa_template,
        response_mode="compact",
    )


def obtener_query_engine_con_vitales(
    index: VectorStoreIndex,
    llm_model,
    datos_vitales: DatosVitales
):
    """
    Configura el Query Engine con datos vitales inyectados en el contexto.

    Los signos vitales se inyectan en el prompt vía `partial_format` para
    que el LLM los tenga en cuenta. El LLM se pasa de forma local
    (parámetro `llm=`) para evitar condiciones de carrera.

    Args:
        index: VectorStoreIndex cargado
        llm_model: Instancia del modelo LLM
        datos_vitales: DatosVitales con información del paciente

    Returns:
        QueryEngine: Motor de consultas configurado con datos vitales
    """
    # Formatar datos vitales para inyectar en el prompt
    datos_str = f"""- Edad: {datos_vitales.edad} años
- Sexo: {datos_vitales.sexo}
- Temperatura: {datos_vitales.temperatura}°C
- Presión Arterial: {datos_vitales.presion_sistolica}/{datos_vitales.presion_diastolica} mmHg
- Frecuencia Cardíaca: {datos_vitales.frecuencia_cardiaca} bpm
- Frecuencia Respiratoria: {datos_vitales.frecuencia_respiratoria} rpm
- SpO2: {datos_vitales.saturacion}%"""

    qa_prompt_tmpl = """Eres un asistente de triaje médico experto para postas rurales (Primer Nivel de Atención) en Bolivia.
Tu tarea es clasificar el nivel de urgencia según el sistema de Triaje Manchester (colores) y dar recomendaciones basándote ÚNICAMENTE en la información de las Normas Nacionales de Atención Clínica (NNAC) proporcionada en el contexto.

INFORMACIÓN DE LAS NNAC (CONTEXTO):
{context_str}

DATOS CLÍNICOS DEL PACIENTE:
{datos_paciente}

DESCRIPCIÓN DE SÍNTOMAS Y PRESENTACIÓN:
{query_str}

Responde en este formato EXACTO y sin añadir texto adicional:

NIVEL DE URGENCIA: [rojo / naranja / amarillo / verde / azul]
Donde:
- rojo = Emergencia (atención inmediata, riesgo de vida)
- naranja = Urgencia Mayor (atención muy prioritaria, ~10 min)
- amarillo = Urgencia Menor (atención en ~60 min)
- verde = Menor / No urgente (atención diferible)
- azul = No urgente / autosanamiento (orientación)

REFERENCIA: [Sí / No].
- Si es "Sí", especifica: "Requiere referencia inmediata a Centro de Salud Nivel II" o "Hospital de Nivel III", justificando brevemente según las NNAC.
- Si es "No", indica: "Manejo y observación en la posta rural".

JUSTIFICACIÓN: [Explica por qué, citando la edad, signos vitales o síntomas específicos y cómo se relacionan con las NNAC].

MEDICACIÓN SUGERIDA (Solo si es amarillo/verde y está en las NNAC):
- [Nombre del fármaco, dosis exacta y vía de administración según el texto].
- Si el contexto no menciona medicación o es rojo/naranja, escribe: "No aplica o requiere evaluación médica presencial para prescripción".

ACCIONES RECOMENDADAS:
- [Acción inmediata 1]
- [Acción de seguimiento 2]

FUENTE: [Nombre del documento NNAC y breve cita textual del chunk recuperado].

DISCLAIMER: Esta es una herramienta de apoyo a la decisión clínica basada en normas. No reemplaza el criterio y la evaluación médica profesional presencial.
"""
    qa_template = PromptTemplate(qa_prompt_tmpl).partial_format(
        datos_paciente=datos_str
    )

    return index.as_query_engine(
        llm=llm_model,
        similarity_top_k=5,
        text_qa_template=qa_template,
        response_mode="compact",
    )
