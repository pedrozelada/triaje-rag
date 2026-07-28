"""Router de autenticación y gestión de usuarios."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from backend.api.deps import get_current_user
from backend.db.models import Usuario
from backend.db.session import get_db
from backend.schemas.usuario import LoginRequest, Token, UsuarioCreate, UsuarioOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/registro", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def registrar(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    """Crea un nuevo usuario (médico/enfermero/admin) con contraseña hasheada."""
    if db.query(Usuario).filter(Usuario.email == usuario.email).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado.")
    if db.query(Usuario).filter(Usuario.ci == usuario.ci).first():
        raise HTTPException(status_code=400, detail="La cédula ya está registrada.")

    nuevo = Usuario(
        ci=usuario.ci,
        nombre_completo=usuario.nombre_completo,
        email=usuario.email,
        password_hash=hash_password(usuario.password),
        rol=usuario.rol,
        centro_salud=usuario.centro_salud,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


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