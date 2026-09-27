"""Router de autenticación y gestión de usuarios."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.core.security import create_access_token, verify_password
from backend.db.models import Usuario
from backend.db.session import get_db
from backend.schemas.usuario import LoginRequest, Token, UsuarioCreate, UsuarioOut
from backend.services import usuarios as servicio_usuarios

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/registro", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def registrar(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    """Crea un nuevo usuario con contraseña hasheada.

    Seguridad:
    - El rol debe ser válido (ver ROL_ENUM).
    - El rol 'admin' solo se permite como *bootstrap*: únicamente mientras
      no exista ningún administrador activo en la base de datos. Después,
      los administradores solo pueden crearse desde el panel de administración.
    """
    return servicio_usuarios.registrar(db, usuario)


@router.post("/login", response_model=Token)
def login(credenciales: LoginRequest, db: Session = Depends(get_db)):
    """Autentica al usuario y devuelve un JWT."""
    usuario = db.query(Usuario).filter(Usuario.email == credenciales.email).first()
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")
    if not verify_password(credenciales.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")

    token = create_access_token(subject=usuario.email)
    return Token(access_token=token)


@router.get("/me", response_model=UsuarioOut)
def perfil_actual(usuario: Usuario = Depends(get_current_user)):
    """Devuelve el perfil del usuario autenticado (para el frontend)."""
    return usuario