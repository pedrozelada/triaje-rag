"""Reglas de negocio de los usuarios.

El alta pública (bootstrap del primer administrador) y el alta desde el panel
comparten las mismas validaciones, así que viven juntas: antes estaban copiadas
en `backend/api/auth.py` y en `backend/api/admin.py`.
"""

from sqlalchemy.orm import Session

from backend.core.security import hash_password
from backend.db.models import ROL_ENUM, ConsultaTriage, Usuario
from backend.services.errores import NoEncontrado, Prohibido, SolicitudInvalida

MENSAJE_ROL = "Rol inválido."
MENSAJE_EMAIL = "El email ya está registrado."
MENSAJE_CI = "La cédula ya está registrada."
MENSAJE_ADMIN_EXISTENTE = (
    "Ya existe un administrador. Los administradores solo pueden crearse desde "
    "el panel de administración."
)
MENSAJE_ULTIMO_ADMIN = "No se puede eliminar al último administrador activo."
MENSAJE_PROPIO = "No puedes eliminar tu propio usuario."


def _verificar_rol(rol: str | None) -> None:
    """Un rol fuera del catálogo sería un usuario sin permisos definidos."""
    if rol is not None and rol not in ROL_ENUM:
        raise SolicitudInvalida(MENSAJE_ROL)


def _verificar_no_duplicado(
    db: Session, *, email: str | None, ci: str | None, excluir_id: int | None = None
) -> None:
    """Ni el email ni la cédula pueden repetirse entre usuarios."""
    for campo, valor, mensaje in (
        (Usuario.email, email, MENSAJE_EMAIL),
        (Usuario.ci, ci, MENSAJE_CI),
    ):
        if not valor:
            continue
        consulta = db.query(Usuario).filter(campo == valor)
        if excluir_id is not None:
            consulta = consulta.filter(Usuario.id != excluir_id)
        if consulta.first():
            raise SolicitudInvalida(mensaje)


def _hay_admin_activo(db: Session, excluir_id: int | None = None) -> bool:
    """¿Queda algún administrador activo además del indicado?"""
    consulta = db.query(Usuario).filter(Usuario.rol == "admin", Usuario.activo.is_(True))
    if excluir_id is not None:
        consulta = consulta.filter(Usuario.id != excluir_id)
    return consulta.first() is not None


def _construir(datos) -> Usuario:
    """Instancia el usuario hasheando la contraseña."""
    return Usuario(
        ci=datos.ci,
        nombre_completo=datos.nombre_completo,
        email=datos.email,
        password_hash=hash_password(datos.password),
        rol=datos.rol,
        centro_salud=datos.centro_salud,
    )


def registrar(db: Session, datos) -> Usuario:
    """Alta pública de usuario (endpoint de registro).

    El rol `admin` solo se admite como bootstrap: únicamente mientras no exista
    ningún administrador activo. Después, los administradores se crean desde el
    panel de administración.
    """
    _verificar_rol(datos.rol)
    if datos.rol == "admin" and _hay_admin_activo(db):
        raise Prohibido(MENSAJE_ADMIN_EXISTENTE)
    _verificar_no_duplicado(db, email=datos.email, ci=datos.ci)

    usuario = _construir(datos)
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def crear(db: Session, datos) -> Usuario:
    """Alta de usuario desde el panel de administración."""
    _verificar_rol(datos.rol)
    _verificar_no_duplicado(db, email=datos.email, ci=datos.ci)

    usuario = _construir(datos)
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def actualizar(db: Session, usuario_id: int, datos) -> Usuario:
    """Edita un usuario: datos, rol, estado activo y contraseña (opcional)."""
    _verificar_rol(datos.rol)

    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise NoEncontrado("Usuario no encontrado.")

    cambios = datos.model_dump(exclude_unset=True)
    nueva_password = cambios.pop("password", None)

    if datos.email and datos.email != usuario.email:
        _verificar_no_duplicado(db, email=datos.email, ci=None, excluir_id=usuario_id)

    for campo, valor in cambios.items():
        setattr(usuario, campo, valor)
    if nueva_password:
        usuario.password_hash = hash_password(nueva_password)

    db.commit()
    db.refresh(usuario)
    return usuario


def eliminar(db: Session, usuario_id: int, actor: Usuario) -> None:
    """Elimina un usuario conservando la auditoría de sus triajes.

    Las consultas quedan con `usuario_id = NULL` (SET NULL). No puede
    eliminarse a uno mismo ni al último administrador activo.
    """
    if usuario_id == actor.id:
        raise SolicitudInvalida(MENSAJE_PROPIO)

    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise NoEncontrado("Usuario no encontrado.")

    if usuario.rol == "admin" and usuario.activo and not _hay_admin_activo(
        db, excluir_id=usuario_id
    ):
        raise SolicitudInvalida(MENSAJE_ULTIMO_ADMIN)

    # Conserva la auditoría de triajes: la FK queda en NULL (SET NULL)
    db.query(ConsultaTriage).filter(ConsultaTriage.usuario_id == usuario_id).update(
        {ConsultaTriage.usuario_id: None}, synchronize_session=False
    )
    db.delete(usuario)
    db.commit()
