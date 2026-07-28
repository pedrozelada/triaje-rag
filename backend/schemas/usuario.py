"""Schemas de Usuario y autenticación."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UsuarioCreate(BaseModel):
    ci: str = Field(..., min_length=1, max_length=30)
    nombre_completo: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6)
    rol: str = "enfermero_triage"
    centro_salud: str | None = None


class UsuarioUpdate(BaseModel):
    """Schema para que admin actualice usuarios (todos los campos opcionales)."""
    nombre_completo: str | None = None
    email: EmailStr | None = None
    rol: str | None = None
    centro_salud: str | None = None
    activo: bool | None = None


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ci: str
    nombre_completo: str
    email: EmailStr
    rol: str
    centro_salud: str | None = None
    activo: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str