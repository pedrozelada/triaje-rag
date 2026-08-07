"""Router de consultas de triaje (integra el motor RAG + auditoría)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_optional_user
from backend.db.models import ConsultaTriage, Paciente, Usuario
from backend.db.session import get_db
from backend.rag.service import rag_service
from backend.schemas.triage import TriageCreate, TriageOut
from ai_service.models import DatosVitales

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
    paciente = db.get(Paciente, datos.paciente_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")

    # Construir DatosVitales usando la edad calculada del paciente.
    datos_vitales = DatosVitales(
        edad=paciente.edad,
        sexo=paciente.sexo,
        temperatura=datos.temperatura or 37.0,
        presion_sistolica=datos.presion_sistolica or 120,
        presion_diastolica=datos.presion_diastolica or 80,
        frecuencia_cardiaca=datos.frecuencia_cardiaca or 70,
        frecuencia_respiratoria=datos.frecuencia_respiratoria or 16,
        saturacion=datos.spo2 if datos.spo2 is not None else 98.0,
    )

    descripcion = datos.sintomas or datos.motivo_consulta or ""
    resultado = rag_service.analizar(
        datos_vitales=datos_vitales, sintomas=descripcion
    )

    consulta = ConsultaTriage(
        paciente_id=paciente.id,
        usuario_id=usuario.id if usuario else None,
        temperatura=datos.temperatura,
        presion_sistolica=datos.presion_sistolica,
        presion_diastolica=datos.presion_diastolica,
        frecuencia_cardiaca=datos.frecuencia_cardiaca,
        frecuencia_respiratoria=datos.frecuencia_respiratoria,
        spo2=datos.spo2,
        motivo_consulta=datos.motivo_consulta,
        sintomas=datos.sintomas,
        nivel_urgencia=resultado.nivel_urgencia,
        respuesta_llm=resultado.respuesta,
        prompt_utilizado=resultado.prompt_utilizado,
        modelo_utilizado=resultado.modelo_utilizado,
        tiempo_respuesta=resultado.tiempo_respuesta,
        tokens_consumidos=resultado.tokens_consumidos,
    )
    db.add(consulta)
    db.commit()
    db.refresh(consulta)
    return consulta


@router.get("", response_model=list[TriageOut])
def listar_triage(
    skip: int = 0,
    limit: int = 100,
    paciente_id: Optional[int] = Query(None, description="Filtrar por paciente"),
    nivel_urgencia: Optional[str] = Query(None, description="Filtrar por color: rojo/naranja/amarillo/verde/azul"),
    fecha_desde: Optional[datetime] = Query(None, description="Filtrar desde fecha"),
    fecha_hasta: Optional[datetime] = Query(None, description="Filtrar hasta fecha"),
    db: Session = Depends(get_db),
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


@router.get("/{consulta_id}", response_model=TriageOut)
def obtener_triage(consulta_id: int, db: Session = Depends(get_db)):
    consulta = db.get(ConsultaTriage, consulta_id)
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta no encontrada.")
    return consulta