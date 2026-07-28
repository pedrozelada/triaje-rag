"""Dependencias compartidas de la API: autenticación opcional/obligatoria."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.core.security import decode_access_token
from backend.db.models import Usuario
from backend.db.session import get_db

# El token se envía como "Bearer <jwt>" en el header Authorization.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Devuelve el usuario autenticado o lanza 401.
    Uso: rutas que REQUIEREN login (p.ej. auditoría).
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado. Inicia sesión.",
        )
    email = decode_access_token(token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
        )
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo.",
        )
    return usuario


def get_optional_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario | None:
    """
    Devuelve el usuario si hay token válido, si no None.
    Uso: triage puede hacerse sin login, pero si hay sesión se registra
    el usuario_id para auditoría.
    """
    if not token:
        return None
    email = decode_access_token(token)
    if not email:
        return None
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or not usuario.activo:
        return None
    return usuario