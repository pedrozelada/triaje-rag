"""Router de informes y auditoría."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.api.informe_pdf import generar_pdf_informe_paciente
from backend.db.models import ConsultaTriage, Paciente, Usuario
from backend.db.session import get_db
from backend.schemas.triage import TriageOut

router = APIRouter(prefix="/api/informes", tags=["informes"])


@router.get("/paciente/{paciente_id}", response_model=list[TriageOut])
def informe_paciente(
    paciente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
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
def informe_paciente_texto(
    paciente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
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
        f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        f"Generado por: {usuario.nombre_completo}",
        f"Filtro: Paciente #{paciente.id}",
        "",
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
        if c.prompt_utilizado:
            lineas.append("Prompt utilizado (auditoría):")
            lineas.append(c.prompt_utilizado)
        lineas.append("")

    return {"informe": "\n".join(lineas)}


@router.get("/paciente/{paciente_id}/pdf")
def informe_paciente_pdf(
    paciente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Genera el informe del historial del paciente como PDF (descarga directa)."""
    paciente = db.get(Paciente, paciente_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")

    consultas = (
        db.query(ConsultaTriage)
        .filter(ConsultaTriage.paciente_id == paciente_id)
        .order_by(ConsultaTriage.fecha_hora.asc())
        .all()
    )

    try:
        pdf_bytes = generar_pdf_informe_paciente(
            paciente=paciente, consultas=consultas, usuario=usuario
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    nombre = (
        f"informe_paciente_{paciente_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )