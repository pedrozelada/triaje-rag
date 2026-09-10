"""Router de CRUD de pacientes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.db.models import Paciente, Usuario
from backend.db.session import get_db
from backend.schemas.paciente import (
    PacienteCreate,
    PacienteOut,
    PacienteUpdate,
)

router = APIRouter(prefix="/api/pacientes", tags=["pacientes"])


@router.post("", response_model=PacienteOut, status_code=status.HTTP_201_CREATED)
def crear_paciente(
    datos: PacienteCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if db.query(Paciente).filter(Paciente.ci == datos.ci).first():
        raise HTTPException(status_code=400, detail="La cédula ya está registrada.")
    paciente = Paciente(**datos.model_dump())
    db.add(paciente)
    db.commit()
    db.refresh(paciente)
    return paciente


@router.get("", response_model=list[PacienteOut])
def listar_pacientes(
    q: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Lista pacientes con filtro opcional por CI, nombre o apellido (`q`)."""
    query = db.query(Paciente)
    if q and q.strip():
        termino = f"%{q.strip()}%"
        query = query.filter(
            Paciente.ci.ilike(termino)
            | Paciente.nombre.ilike(termino)
            | Paciente.apellido.ilike(termino)
        )
    return query.order_by(Paciente.nombre, Paciente.apellido).offset(skip).limit(limit).all()


@router.get("/{paciente_id}", response_model=PacienteOut)
def obtener_paciente(
    paciente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    paciente = db.get(Paciente, paciente_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")
    return paciente


@router.put("/{paciente_id}", response_model=PacienteOut)
def actualizar_paciente(
    paciente_id: int,
    datos: PacienteUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    paciente = db.get(Paciente, paciente_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(paciente, campo, valor)
    db.commit()
    db.refresh(paciente)
    return paciente


@router.delete("/{paciente_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_paciente(
    paciente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Elimina un paciente y todas sus consultas asociadas."""
    paciente = db.get(Paciente, paciente_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")
    db.delete(paciente)
    db.commit()