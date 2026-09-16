"""Router de consultas de triaje (integra el motor RAG + auditoría)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user, get_optional_user
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

    # Los vitales ausentes llegan como None (= no medido) y se muestran como
    # "No registrado" en el prompt. NUNCA se sustituyen por valores normales.
    datos_vitales = DatosVitales(
        edad=paciente.edad,
        sexo=paciente.sexo,
        temperatura=datos.temperatura,
        presion_sistolica=datos.presion_sistolica,
        presion_diastolica=datos.presion_diastolica,
        frecuencia_cardiaca=datos.frecuencia_cardiaca,
        frecuencia_respiratoria=datos.frecuencia_respiratoria,
        saturacion=datos.spo2,
    )

    # Defensa en profundidad: Pydantic ya validó los rangos, pero se revalida
    # la coherencia clínica (p.ej. sistólica > diastólica) antes del RAG.
    if not datos_vitales.es_valido():
        raise HTTPException(
            status_code=422,
            detail="Signos vitales fuera de rango fisiológicamente posible. Verifica los valores.",
        )

    descripcion = "\n".join(
        parte for parte in (datos.motivo_consulta, datos.sintomas) if parte
    )
    resultado = rag_service.analizar(
        datos_vitales=datos_vitales, sintomas=descripcion, modelo_nombre=datos.modelo
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
        reglas_activadas=resultado.reglas_activadas,
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
        )


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