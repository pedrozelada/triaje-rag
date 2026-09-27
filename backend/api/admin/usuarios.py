"""Gestión de usuarios desde el panel de administración.

Las reglas (rol válido, email y cédula únicos, último administrador activo) y
sus mensajes viven en `backend.services.usuarios`; aquí solo está el contrato
HTTP.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.api.deps import require_admin
from backend.db.models import Usuario
from backend.db.session import get_db
from backend.schemas.usuario import UsuarioCreate, UsuarioOut, UsuarioUpdate
from backend.services import usuarios as servicio

router = APIRouter()


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    # El parámetro no se usa en el cuerpo: la dependencia exige el rol admin.
    usuario: Usuario = Depends(require_admin),
):
    """Lista todos los usuarios del sistema."""
    return db.query(Usuario).offset(skip).limit(limit).all()


@router.post("/usuarios", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    datos: UsuarioCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_admin),
):
    """Crea un usuario nuevo desde el panel de administración."""
    return servicio.crear(db, datos)


@router.put("/usuarios/{usuario_id}", response_model=UsuarioOut)
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_admin),
):
    """Actualiza un usuario: rol, estado activo, datos y contraseña."""
    return servicio.actualizar(db, usuario_id, datos)


@router.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_admin),
):
    """Elimina un usuario conservando la auditoría de sus triajes.

    Las consultas asociadas quedan con `usuario_id = NULL`. No pueden
    eliminarse el propio usuario ni el último administrador activo.
    """
    servicio.eliminar(db, usuario_id, usuario)
