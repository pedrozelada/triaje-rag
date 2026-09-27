"""Router de consultas de triaje (integra el motor RAG + auditoría)."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user, get_optional_user
from backend.db.models import ConsultaTriage, Usuario
from backend.db.session import get_db
from backend.rag.service import rag_service
from backend.schemas.triage import TriageCreate, TriageOut
from backend.services import triaje as servicio_triaje

router = APIRouter(prefix="/api/triage", tags=["triage"])


@router.post("", response_model=TriageOut, status_code=status.HTTP_201_CREATED)
def crear_triage(
    datos: TriageCreate,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(get_optional_user),
):
    """
    Crea una consulta de triaje: ejecuta el motor RAG y persiste el resultado
    con auditoría (usuario_id si hay sesión; NULL si es anónimo).
    """
    return servicio_triaje.crear_consulta(db, datos, usuario)


@router.get("", response_model=list[TriageOut])
def listar_triage(
    skip: int = 0,
    limit: int = 100,
    paciente_id: int | None = Query(None, description="Filtrar por paciente"),
    nivel_urgencia: str | None = Query(
        None, description="Filtrar por color: rojo/naranja/amarillo/verde/azul"
    ),
    fecha_desde: datetime | None = Query(None, description="Filtrar desde fecha"),
    fecha_hasta: datetime | None = Query(None, description="Filtrar hasta fecha"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    query = db.query(ConsultaTriage)
    if paciente_id is not None:
        query = query.filter(ConsultaTriage.paciente_id == paciente_id)
    if nivel_urgencia:
        query = query.filter(ConsultaTriage.nivel_urgencia == nivel_urgencia)
    if fecha_desde:
        query = query.filter(ConsultaTriage.fecha_hora >= fecha_desde)
    if fecha_hasta:
        query = query.filter(ConsultaTriage.fecha_hora <= fecha_hasta)
    return query.order_by(ConsultaTriage.fecha_hora.desc()).offset(skip).limit(limit).all()


@router.get("/modelos", response_model=list[str])
def listar_modelos():
    """Lista los nombres de los modelos LLM disponibles para el triaje."""
    try:
        return rag_service.listar_modelos()
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"No hay modelos LLM disponibles: {e}"
        ) from e


@router.get("/{consulta_id}", response_model=TriageOut)
def obtener_triage(
    consulta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    consulta = db.get(ConsultaTriage, consulta_id)
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta no encontrada.")
    return consulta