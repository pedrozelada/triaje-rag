"""Router de administración: estadísticas, gestión de usuarios, reportes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.db.models import ConsultaTriage, Paciente, Usuario
from backend.db.session import get_db
from backend.schemas.admin import EstadisticasOut, NivelCount
from backend.schemas.usuario import UsuarioOut, UsuarioUpdate

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(usuario: Usuario) -> Usuario:
    """Valida que el usuario autenticado sea admin."""
    if usuario.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador.",
        )
    return usuario


@router.get("/estadisticas", response_model=EstadisticasOut)
def obtener_estadisticas(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Estadísticas generales del sistema (solo admin)."""
    _require_admin(usuario)

    total_consultas = db.query(func.count(ConsultaTriage.id)).scalar() or 0
    total_pacientes = db.query(func.count(Paciente.id)).scalar() or 0
    total_usuarios = db.query(func.count(Usuario.id)).scalar() or 0

    # Conteo por nivel de urgencia
    niveles_raw = (
        db.query(ConsultaTriage.nivel_urgencia, func.count(ConsultaTriage.id))
        .group_by(ConsultaTriage.nivel_urgencia)
        .all()
    )
    por_nivel = [
        NivelCount(nivel=nivel or "sin_clasificar", cantidad=cantidad)
        for nivel, cantidad in niveles_raw
    ]

    # Promedio de tiempo de respuesta
    promedio = db.query(func.avg(ConsultaTriage.tiempo_respuesta)).scalar()
    promedio_tiempo = round(float(promedio), 3) if promedio else None

    # Modelo más usado
    modelo_row = (
        db.query(ConsultaTriage.modelo_utilizado, func.count(ConsultaTriage.id))
        .filter(ConsultaTriage.modelo_utilizado.isnot(None))
        .group_by(ConsultaTriage.modelo_utilizado)
        .order_by(func.count(ConsultaTriage.id).desc())
        .first()
    )
    modelo_mas_usado = modelo_row[0] if modelo_row else None

    return EstadisticasOut(
        total_consultas=total_consultas,
        total_pacientes=total_pacientes,
        total_usuarios=total_usuarios,
        por_nivel=por_nivel,
        promedio_tiempo_respuesta=promedio_tiempo,
        modelo_mas_usado=modelo_mas_usado,
    )


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Lista todos los usuarios del sistema (solo admin)."""
    _require_admin(usuario)
    return db.query(Usuario).offset(skip).limit(limit).all()


@router.put("/usuarios/{usuario_id}", response_model=UsuarioOut)
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Actualiza un usuario: rol, estado activo, datos (solo admin)."""
    _require_admin(usuario)

    target = db.get(Usuario, usuario_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(target, campo, valor)

    db.commit()
    db.refresh(target)
    return target
