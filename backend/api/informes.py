"""Router de informes y auditoría.

Los tres formatos comparten la consulta del historial (servicio) y delegan el
formato al paquete `backend.reports`: aquí solo queda el contrato HTTP.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.db.models import Usuario
from backend.db.session import get_db
from backend.reports import pdf as reporte_pdf
from backend.reports import texto as reporte_texto
from backend.schemas.triage import TriageOut
from backend.services import informes as servicio_informes

router = APIRouter(prefix="/api/informes", tags=["informes"])


@router.get("/paciente/{paciente_id}", response_model=list[TriageOut])
def informe_paciente(
    paciente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Historial completo de triaje de un paciente (para auditoría)."""
    _, consultas = servicio_informes.historial_de_paciente(
        db, paciente_id, orden="descendente"
    )
    return consultas


@router.get("/paciente/{paciente_id}/texto")
def informe_paciente_texto(
    paciente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Genera un informe en texto plano del historial del paciente."""
    paciente, consultas = servicio_informes.historial_de_paciente(db, paciente_id)
    return {"informe": reporte_texto.informe_de_paciente(paciente, consultas, usuario)}


@router.get("/paciente/{paciente_id}/pdf")
def informe_paciente_pdf(
    paciente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Genera el informe del historial del paciente como PDF (descarga directa)."""
    paciente, consultas = servicio_informes.historial_de_paciente(db, paciente_id)

    try:
        pdf_bytes = reporte_pdf.generar_pdf_informe_paciente(
            paciente=paciente, consultas=consultas, usuario=usuario
        )
    except RuntimeError as exc:
        # El servidor puede no tener reportlab: se informa del motivo en lugar
        # de romper la API entera.
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    nombre = f"informe_paciente_{paciente_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
