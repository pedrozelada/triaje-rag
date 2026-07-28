"""Router de informes y auditoría."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.models import ConsultaTriage, Paciente
from backend.db.session import get_db
from backend.schemas.triage import TriageOut

router = APIRouter(prefix="/api/informes", tags=["informes"])


@router.get("/paciente/{paciente_id}", response_model=list[TriageOut])
def informe_paciente(paciente_id: int, db: Session = Depends(get_db)):
    """Historial completo de triaje de un paciente (para auditoría)."""
    if not db.get(Paciente, paciente_id):
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")
    return (
        db.query(ConsultaTriage)
        .filter(ConsultaTriage.paciente_id == paciente_id)
        .order_by(ConsultaTriage.fecha_hora.desc())
        .all()
    )


@router.get("/paciente/{paciente_id}/texto")
def informe_paciente_texto(paciente_id: int, db: Session = Depends(get_db)):
    """Genera un informe en texto plano del historial del paciente."""
    paciente = db.get(Paciente, paciente_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")

    consultas = (
        db.query(ConsultaTriage)
        .filter(ConsultaTriage.paciente_id == paciente_id)
        .order_by(ConsultaTriage.fecha_hora.asc())
        .all()
    )

    lineas = [
        "INFORME DE TRIAJE - HISTORIAL DEL PACIENTE",
        "=" * 50,
        f"Paciente: {paciente.nombre} {paciente.apellido}",
        f"C.I.: {paciente.ci}",
        f"Edad: {paciente.edad} años   Sexo: {paciente.sexo}",
        f"Total de consultas: {len(consultas)}",
        "",
    ]
    for i, c in enumerate(consultas, 1):
        fecha = c.fecha_hora.strftime("%Y-%m-%d %H:%M") if c.fecha_hora else "?"
        lineas.append(f"--- Consulta {i} ({fecha}) ---")
        lineas.append(f"Nivel de urgencia: {c.nivel_urgencia or 'N/D'}")
        lineas.append(f"Modelo: {c.modelo_utilizado or 'N/D'}")
        lineas.append(f"Tiempo: {c.tiempo_respuesta}s  Tokens: {c.tokens_consumidos}")
        if c.respuesta_llm:
            lineas.append("Resultado:")
            lineas.append(c.respuesta_llm)
        lineas.append("")

    return {"informe": "\n".join(lineas)}