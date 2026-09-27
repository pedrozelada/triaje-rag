"""Estado del índice vectorial del motor RAG."""

from fastapi import APIRouter, Depends

from backend.api.deps import require_admin
from backend.db.models import Usuario
from backend.schemas.admin import EstadoIndiceOut

router = APIRouter()


@router.get("/indice", response_model=EstadoIndiceOut)
def obtener_estado_indice(usuario: Usuario = Depends(require_admin)):
    """Estado del índice RAG y su vigencia respecto del corpus NNAC.

    Permite comprobar que lo indexado coincide con los PDFs actuales de `data/`
    (qué archivos, con qué huella, cuántos chunks) y ver los cambios pendientes
    si alguien añadió, editó o borró un documento.

    No carga el modelo de embeddings: es una consulta de solo lectura barata.
    """
    # Import local: evita arrastrar llama-index al importar el router completo.
    from backend.rag.service import rag_service

    return rag_service.estado_indice()
