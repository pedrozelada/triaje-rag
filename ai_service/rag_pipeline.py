"""Pipeline RAG: Índice vectorial y Query Engine.

Frescura del índice
-------------------
Antes, la decisión de indexar era ``collection.count() > 0``: eso no mide
vigencia, mide *si hay algo*. Como el índice casi nunca está vacío, quedaba
congelado: un PDF nuevo se ignoraba en silencio, editar o borrar un PDF no
cambiaba nada, y una indexación interrumpida a mitad quedaba bendecida.

Ahora, en cada arranque, el pipeline lee el **manifiesto** de la colección
(ver ``ai_service.indice``), calcula el plan comparando las huellas SHA-256 de
``data/`` con lo registrado, y aplica solo lo necesario:

  * sin cambios -> carga el índice existente (cero embeddings, camino rápido);
  * nuevos/modificados -> borra los chunks de esos archivos y los reindexa;
  * eliminados -> borra sus chunks huérfanos.

Si el modelo de embeddings o los parámetros de segmentación cambiaron, los
vectores guardados dejan de ser comparables con los de las consultas: en ese
caso se **aborta** con ``ConfigurationError`` (salvo autorización expresa) en
lugar de servir recuperaciones inválidas en silencio.
"""

import os
import logging
from typing import Any, Optional
from threading import Lock

from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    StorageContext,
    PromptTemplate,
    Settings,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

from ai_service.errors import ConfigurationError, IndexInitializationError
from ai_service.embeddings import get_embedding_model
from ai_service.indice import (
    Manifest,
    ParametrosIndice,
    Plan,
    calcular_plan,
    escribir_manifest,
    leer_manifest,
    listar_pdfs,
    reconstruir_manifest_desde_coleccion,
)
from ai_service.models import DatosVitales

logger = logging.getLogger(__name__)

NOMBRE_COLECCION = "nnac_triaje"
DESCRIPCION_COLECCION = "Normas Nacionales de Atención Clínica - Triaje"

# Lock para thread-safety del índice
_index_lock = Lock()

# El índice se cachea por (data_dir, chroma_path, forma del índice): la firma
# promete esos parámetros, así que dos rutas distintas deben dar dos índices
# distintos. Antes había una única variable global y los argumentos se
# ignoraban en silencio cuando ya había algo cacheado.
_indices: dict[tuple, VectorStoreIndex] = {}


def _mensaje_aborto(plan: Plan) -> str:
    """Mensaje accionable para el aborto por incompatibilidad del índice."""
    return (
        "El índice existente no es compatible con la configuración actual "
        f"({plan.motivo_reconstruccion}). Los vectores guardados no son "
        "comparables con los de las consultas, así que la recuperación sería "
        "inválida. Se aborta a propósito en lugar de servir resultados "
        "silenciosamente incorrectos. Remedios: reconstruir el índice con "
        "`python scripts/reindexar.py --forzar`, o activar "
        "RAG_RECONSTRUCCION_AUTOMATICA=true para que se reconstruya solo."
    )


def _nodos_de_archivos(
    data_dir: str, nombres: list[str], parametros: ParametrosIndice
) -> list:
    """Carga y segmenta solo los archivos indicados.

    Args:
        data_dir: directorio del corpus.
        nombres: nombres de archivo (no rutas) a cargar.
        parametros: chunk_size/chunk_overlap con los que segmentar.

    Returns:
        Lista de nodos (chunks) listos para insertar en el índice.
    """
    if not nombres:
        return []

    rutas = [os.path.join(data_dir, nombre) for nombre in nombres]
    docs = SimpleDirectoryReader(input_files=rutas).load_data()
    if not docs:
        raise IndexInitializationError(
            f"❌ No se pudieron cargar documentos de {data_dir}: {', '.join(nombres)}"
        )

    # Enriquecer metadatos con el nombre de archivo. Esta clave ('archivo') es
    # la que permite borrar los chunks de un documento concreto más adelante,
    # y coincide con la que usaban los índices anteriores (viene de
    # `file_name`, que SimpleDirectoryReader fija al basename).
    for doc in docs:
        doc.metadata["archivo"] = doc.metadata.get("file_name") or "Documento Desconocido"

    splitter = SentenceSplitter(
        chunk_size=parametros.chunk_size, chunk_overlap=parametros.chunk_overlap
    )
    return splitter.get_nodes_from_documents(docs)


def _abrir_coleccion(chroma_path: str):
    """Abre (o crea) la colección de Chroma. Devuelve (cliente, colección)."""
    cliente = chromadb.PersistentClient(path=chroma_path)
    coleccion = cliente.get_or_create_collection(
        name=NOMBRE_COLECCION, metadata={"description": DESCRIPCION_COLECCION}
    )
    return cliente, coleccion


def _reconstruir_indice_completo(
    cliente,
    data_dir: str,
    parametros: ParametrosIndice,
    embed_model,
) -> VectorStoreIndex:
    """Reindexa todo desde cero eliminando la colección anterior.

    Se borra la colección entera en lugar de limpiarla archivo por archivo: así
    no puede quedar ningún chunk huérfano (de un documento que ya no está, o de
    una indexación fallida), ni siquiera si su metadata es inesperada.
    """
    logger.warning("Reconstruyendo el índice completo desde %s ...", data_dir)
    try:
        cliente.delete_collection(NOMBRE_COLECCION)
    except Exception as e:  # colección inexistente: nada que borrar
        logger.debug("No había colección previa que borrar: %s", e)

    coleccion = cliente.get_or_create_collection(
        name=NOMBRE_COLECCION, metadata={"description": DESCRIPCION_COLECCION}
    )
    vector_store = ChromaVectorStore(chroma_collection=coleccion)

    nombres = listar_pdfs(data_dir)
    nodos = _nodos_de_archivos(data_dir, nombres, parametros)
    if not nodos:
        raise IndexInitializationError(
            f"❌ No se generaron chunks de los documentos de {data_dir}"
        )

    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(
        nodos, storage_context=storage_context, embed_model=embed_model
    )

    escribir_manifest(
        coleccion,
        reconstruir_manifest_desde_coleccion(
            coleccion, data_dir, parametros, adoptado=False
        ),
    )
    logger.info("✅ Índice reconstruido con %d chunks", len(nodos))
    return index


def _actualizar_indice_incremental(
    coleccion,
    vector_store,
    data_dir: str,
    parametros: ParametrosIndice,
    embed_model,
    manifest: Optional[Manifest],
    plan: Plan,
) -> VectorStoreIndex:
    """Aplica solo los cambios detectados por el plan."""
    logger.info(
        "Actualizando índice: %d a indexar, %d a eliminar",
        len(plan.a_indexar),
        len(plan.a_eliminar),
    )

    # Seguro ante fallo parcial: si el proceso muere a mitad de la
    # actualización, el manifiesto queda marcado como incompleto y el siguiente
    # arranque reconstruye en lugar de servir un corpus mutilado.
    if manifest is not None:
        manifest.completo = False
        escribir_manifest(coleccion, manifest)

    for nombre in plan.a_eliminar:
        coleccion.delete(where={"archivo": nombre})

    index = VectorStoreIndex.from_vector_store(
        vector_store, embed_model=embed_model
    )

    nodos = _nodos_de_archivos(data_dir, plan.a_indexar, parametros)
    if nodos:
        index.insert_nodes(nodos)

    # El manifiesto se recalcula desde la colección (no desde la intención): así
    # los conteos de chunks reflejan lo que realmente quedó indexado.
    escribir_manifest(
        coleccion,
        reconstruir_manifest_desde_coleccion(
            coleccion, data_dir, parametros, adoptado=False
        ),
    )
    logger.info("✅ Índice actualizado (%d chunks)", coleccion.count())
    return index


def _construir_indice(
    data_dir: str,
    chroma_path: str,
    parametros: ParametrosIndice,
    permitir_reconstruccion: bool,
    forzar_reconstruccion: bool,
) -> VectorStoreIndex:
    """Lógica interna de carga/creación del índice (ya con el lock tomado)."""
    if not os.path.isdir(data_dir):
        raise IndexInitializationError(
            f"❌ Directorio de datos no encontrado: {data_dir}"
        )

    nombres = listar_pdfs(data_dir)
    if not nombres:
        raise IndexInitializationError(f"❌ No hay archivos PDF en {data_dir}")
    logger.info("Archivos encontrados (%d): %s", len(nombres), ", ".join(nombres))

    embed_model = get_embedding_model()
    Settings.embed_model = embed_model

    cliente, coleccion = _abrir_coleccion(chroma_path)
    vector_store = ChromaVectorStore(chroma_collection=coleccion)

    # Índice heredado (construido antes de que existiera el manifiesto): se
    # adopta registrando la huella ACTUAL de cada documento. Cuesta cero
    # re-embeddings y a partir de aquí cualquier cambio sí se detecta.
    manifest = leer_manifest(coleccion)
    if manifest is None and coleccion.count() > 0:
        logger.warning(
            "Índice sin manifiesto (%d chunks): adoptándolo y registrando la "
            "huella actual de los documentos de %s. ATENCIÓN: si algún PDF cambió "
            "antes de este arranque, ese cambio no se detectará. Usa "
            "`python scripts/reindexar.py --forzar` para una línea base limpia.",
            coleccion.count(),
            data_dir,
        )
        manifest = reconstruir_manifest_desde_coleccion(
            coleccion, data_dir, parametros, adoptado=True
        )
        escribir_manifest(coleccion, manifest)

    plan = calcular_plan(data_dir, manifest, parametros)
    logger.info("Plan de indexado: %s", plan.resumen())

    # Un desajuste de modelo/segmentación no es un estado de arranque normal:
    # implica que el índice guardado no sirve y hay que reconstruirlo. Se aborta
    # por defecto para no degradar la recuperación en silencio.
    if (
        plan.requiere_reconstruccion
        and not plan.es_bootstrap
        and not permitir_reconstruccion
        and not forzar_reconstruccion
    ):
        raise ConfigurationError(_mensaje_aborto(plan))

    if forzar_reconstruccion or plan.requiere_reconstruccion:
        return _reconstruir_indice_completo(cliente, data_dir, parametros, embed_model)

    if not plan.hay_cambios:
        logger.info(
            "Índice vigente (%d chunks): cargando sin reindexar.", coleccion.count()
        )
        return VectorStoreIndex.from_vector_store(
            vector_store, embed_model=embed_model
        )

    return _actualizar_indice_incremental(
        coleccion, vector_store, data_dir, parametros, embed_model, manifest, plan
    )


def cargar_o_crear_indice(
    data_dir: str = "./data",
    chroma_path: str = "./chroma_db",
    parametros: Optional[ParametrosIndice] = None,
    permitir_reconstruccion: bool = False,
    forzar_reconstruccion: bool = False,
) -> VectorStoreIndex:
    """Carga el índice vectorial, reconciliándolo antes con ``data_dir``.

    Thread-safe: usa lock para evitar que dos hilos construyan el índice a la vez.

    Args:
        data_dir: Directorio con los PDFs del corpus.
        chroma_path: Ruta de la base vectorial Chroma.
        parametros: Forma del índice (modelo de embeddings y segmentación).
        permitir_reconstruccion: Si es True, ante un índice incompatible con la
            configuración actual se reconstruye en lugar de abortar.
        forzar_reconstruccion: Reconstruye el índice desde cero aunque el plan
            diga que está vigente.

    Returns:
        VectorStoreIndex: Índice vectorial listo para consultar.

    Raises:
        IndexInitializationError: Si hay error al cargar/crear el índice.
        ConfigurationError: Si el índice existente es incompatible con la
            configuración actual y no se autorizó la reconstrucción.
    """
    parametros = parametros or ParametrosIndice()
    data_dir_abs = os.path.abspath(data_dir)
    chroma_path_abs = os.path.abspath(chroma_path)
    clave = (data_dir_abs, chroma_path_abs, parametros)

    with _index_lock:
        if not forzar_reconstruccion and clave in _indices:
            logger.info("Usando índice ya cargado en memoria (%s)", data_dir_abs)
            return _indices[clave]

        try:
            index = _construir_indice(
                data_dir_abs,
                chroma_path_abs,
                parametros,
                permitir_reconstruccion,
                forzar_reconstruccion,
            )
        except (IndexInitializationError, ConfigurationError):
            raise
        except Exception as e:
            raise IndexInitializationError(f"Error inicializando índice: {str(e)}") from e

        _indices[clave] = index
        return index


def limpiar_cache_indices() -> None:
    """Vacía la caché de índices en memoria (útil en tests y tras reindexar)."""
    with _index_lock:
        _indices.clear()


def estado_indice(
    data_dir: str = "./data",
    chroma_path: str = "./chroma_db",
    parametros: Optional[ParametrosIndice] = None,
) -> dict[str, Any]:
    """Estado del índice y su vigencia respecto de ``data_dir``.

    Es de solo lectura y **no carga el modelo de embeddings**: sirve para que un
    administrador compruebe que el corpus indexado está al día (y para detectar
    desviaciones) sin pagar el coste de inicializar el índice.
    """
    parametros = parametros or ParametrosIndice()
    data_dir_abs = os.path.abspath(data_dir)
    chroma_path_abs = os.path.abspath(chroma_path)

    estado: dict[str, Any] = {
        "coleccion": NOMBRE_COLECCION,
        "data_dir": data_dir_abs,
        "chroma_path": chroma_path_abs,
        "existe_indice": False,
        "chunks": 0,
        "archivos": [],
        "completo": False,
        "adoptado": False,
        "adoptara": False,
        "indexado_en": None,
        "embedding_model": parametros.modelo_embeddings,
        "chunk_size": parametros.chunk_size,
        "chunk_overlap": parametros.chunk_overlap,
        "plan": None,
        "actualizado": False,
        "error": None,
    }

    if not os.path.isdir(data_dir_abs):
        estado["error"] = f"Directorio de datos no encontrado: {data_dir_abs}"
        return estado

    if not os.path.exists(chroma_path_abs):
        # Todavía no se ha creado la base vectorial: no hay nada indexado.
        estado["plan"] = calcular_plan(data_dir_abs, None, parametros).to_dict()
        return estado

    try:
        cliente = chromadb.PersistentClient(path=chroma_path_abs)
        try:
            coleccion = cliente.get_collection(NOMBRE_COLECCION)
        except Exception:
            coleccion = None
    except Exception as e:
        estado["error"] = f"No se pudo abrir la base vectorial: {e}"
        return estado

    if coleccion is None:
        estado["plan"] = calcular_plan(data_dir_abs, None, parametros).to_dict()
        return estado

    manifest = leer_manifest(coleccion)
    plan = calcular_plan(data_dir_abs, manifest, parametros)
    chunks = coleccion.count()

    # Sin manifiesto pero con chunks: la carga adoptará el índice tal cual
    # (registrando la huella ACTUAL, sin re-embeber nada), así que los archivos
    # que el plan lista como "nuevos" no se reindexarán en ese arranque.
    adoptara = manifest is None and chunks > 0

    estado.update(
        {
            "existe_indice": chunks > 0,
            "chunks": chunks,
            "adoptara": adoptara,
            "archivos": (
                sorted(
                    (
                        {
                            "nombre": info.nombre,
                            "sha256": info.sha256,
                            "tamano": info.tamano,
                            "chunks": info.chunks,
                        }
                        for info in manifest.archivos.values()
                    ),
                    key=lambda a: a["nombre"],
                )
                if manifest is not None
                else []
            ),
            "completo": manifest.completo if manifest is not None else False,
            "adoptado": manifest.adoptado if manifest is not None else False,
            "indexado_en": manifest.indexado_en if manifest is not None else None,
            "embedding_model": (
                manifest.embedding_model if manifest is not None else None
            ),
            "plan": plan.to_dict(),
            # "al día" = hay índice, no hay cambios pendientes y su forma
            # coincide con la configuración actual.
            "actualizado": bool(
                chunks > 0
                and not plan.hay_cambios
                and not plan.requiere_reconstruccion
                and not adoptara
            ),
        }
    )
    return estado


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


#: Plantilla del prompt de triaje con signos vitales.
#:
#: Es una constante de módulo —y no una cadena dentro de la función— porque la
#: evaluación del sistema (Componente 2) necesita construir el MISMO prompt sin
#: bloque de contexto para medir el desempeño del modelo sin recuperación
#: (línea base del benchmark). Si la plantilla viviera duplicada, el benchmark
#: compararía dos prompts distintos y la comparación no valdría nada.
#:
#: Marcadores: {context_str} (fragmentos recuperados), {datos_paciente} (signos
#: vitales) y {query_str} (motivo de consulta).
PROMPT_TRIAGE_NNAC = """Eres un asistente de triaje médico experto para postas rurales (Primer Nivel de Atención) en Bolivia.
Tu tarea es clasificar el nivel de urgencia según el sistema de Triaje Manchester (colores) y dar recomendaciones basándote ÚNICAMENTE en la información de las Normas Nacionales de Atención Clínica (NNAC) proporcionada en el contexto.

INFORMACIÓN DE LAS NNAC (CONTEXTO):
{context_str}

DATOS CLÍNICOS DEL PACIENTE:
{datos_paciente}

DESCRIPCIÓN DE SÍNTOMAS Y PRESENTACIÓN:
{query_str}

IMPORTANTE: si algún signo vital figura como "No registrado", NO lo asumas ni
inventes su valor: menciónalo como limitación en la justificación y clasifica
con la información disponible.

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


def obtener_query_engine_con_vitales(
    index: VectorStoreIndex,
    llm_model,
    datos_vitales: DatosVitales
):
    """
    Configura el Query Engine con datos vitales inyectados en el contexto.

    Los signos vitales se inyectan en el prompt vía `partial_format` para
    que el LLM los tenga en cuenta. Los valores no medidos se muestran como
    "No registrado" (NUNCA se sustituyen por valores normales). El LLM se
    pasa de forma local (parámetro `llm=`) para evitar condiciones de carrera.

    Args:
        index: VectorStoreIndex cargado
        llm_model: Instancia del modelo LLM
        datos_vitales: DatosVitales con información del paciente (None = no medido)

    Returns:
        QueryEngine: Motor de consultas configurado con datos vitales
    """
    # Bloque de datos del paciente desde la fuente única de verdad
    # (idéntico al texto de auditoría persistido en la BD).
    datos_str = datos_vitales.a_texto_prompt()

    qa_template = PromptTemplate(PROMPT_TRIAGE_NNAC).partial_format(
        datos_paciente=datos_str
    )

    return index.as_query_engine(
        llm=llm_model,
        similarity_top_k=5,
        text_qa_template=qa_template,
        response_mode="compact",
    )
