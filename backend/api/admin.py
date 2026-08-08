"""Router de administración: estadísticas, gestión de usuarios, reportes."""

import re
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.core.security import hash_password
from backend.db.models import ConsultaTriage, Paciente, Usuario, calcular_edad
from backend.db.session import get_db
from backend.schemas.admin import (
    DiaCount,
    EdadRangeCount,
    EstadisticasOut,
    EstadisticasTriajeOut,
    ModeloCount,
    MotivoFrecuente,
    NivelCount,
    SexoCount,
    UsuarioActividad,
)
from backend.schemas.usuario import UsuarioCreate, UsuarioOut, UsuarioUpdate

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Rangos etarios para el desglose demográfico (inicio, fin inclusivo; None = abierto)
RANGOS_EDAD = [(0, 5), (6, 12), (13, 17), (18, 30), (31, 50), (51, 64), (65, None)]

# Stopwords: gramaticales del español + relleno clínico habitual en los formularios
STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
    "al", "en", "con", "por", "para", "sin", "sobre", "entre", "hasta",
    "desde", "durante", "que", "como", "pero", "porque", "cuando",
    "donde", "cual", "quien", "quienes", "cuyo", "cuya", "este", "esta",
    "estos", "estas", "ese", "esa", "esos", "esas", "aquel", "aquella",
    "esto", "eso", "ello", "ellos", "ellas", "nosotros", "usted", "ustedes",
    "sus", "suyo", "suya", "nuestro", "nuestra", "muy", "mas", "menos",
    "tambien", "tampoco", "solo", "solamente", "ya", "aun", "cada",
    "todo", "toda", "todos", "todas", "otro", "otra", "otros", "otras",
    "mismo", "misma", "mucho", "mucha", "poco", "poca", "hay", "hace",
    "hacer", "ser", "estar", "tiene", "tienen", "tener", "presento",
    "presenta", "presentan", "refiere", "refieren", "manifiesta",
    "sintomas", "sintoma", "signos", "cuadro", "consulta", "motivo",
    "paciente", "persona", "caso", "dia", "dias", "semana", "semanas",
    "mes", "meses", "horas", "hora", "momento", "actual", "actualmente",
    "fue", "hubo", "han", "habia", "seria", "esta", "dos", "tres", "vez",
}


def _require_admin(usuario: Usuario) -> Usuario:
    """Valida que el usuario autenticado sea admin."""
    if usuario.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador.",
        )
    return usuario


def _rango_edad(edad: int) -> str:
    """Convierte una edad en su etiqueta de rango etario."""
    for inicio, fin in RANGOS_EDAD:
        if fin is None:
            if edad >= inicio:
                return f"{inicio}+"
        elif inicio <= edad <= fin:
            return f"{inicio}-{fin}"
    return "desconocido"


def _etiqueta_rango(indice: int) -> str:
    """Etiqueta legible para el i-ésimo rango de RANGOS_EDAD."""
    inicio, fin = RANGOS_EDAD[indice]
    return f"{inicio}+" if fin is None else f"{inicio}-{fin}"


def _extraer_palabras_clave(textos: list[str], top_n: int = 10) -> list[MotivoFrecuente]:
    """Extrae las palabras más frecuentes de textos libres (motivos/síntomas).

    Normaliza (minúsculas, sin tildes), filtra stopwords y tokens cortos.
    Es una aproximación por keywords, no un conteo clínico de enfermedades.
    """
    contador: Counter[str] = Counter()
    for texto in textos:
        if not texto:
            continue
        normalizado = unicodedata.normalize("NFD", texto.lower())
        palabras = re.findall(r"[a-z]+", normalizado)
        contador.update(
            palabra
            for palabra in palabras
            if len(palabra) >= 3 and palabra not in STOPWORDS
        )
    return [
        MotivoFrecuente(palabra=palabra, cantidad=cantidad)
        for palabra, cantidad in contador.most_common(top_n)
    ]


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

    # Pacientes por sexo
    sexo_raw = (
        db.query(Paciente.sexo, func.count(Paciente.id)).group_by(Paciente.sexo).all()
    )
    por_sexo = [SexoCount(sexo=sexo, cantidad=cantidad) for sexo, cantidad in sexo_raw]

    # Pacientes por rango etario (la edad se calcula de fecha_nacimiento,
    # por eso se agrupa en Python: es agnóstico del motor de BD)
    nacimientos = [fila[0] for fila in db.query(Paciente.fecha_nacimiento).all()]
    edades = Counter(_rango_edad(calcular_edad(fn)) for fn in nacimientos)
    por_rango_edad = [
        EdadRangeCount(rango=_etiqueta_rango(i), cantidad=edades.get(_etiqueta_rango(i), 0))
        for i in range(len(RANGOS_EDAD))
    ]

    # Consultas por día (últimos 30 días, con días sin datos en cero)
    desde = datetime.now() - timedelta(days=29)
    fechas_raw = (
        db.query(ConsultaTriage.fecha_hora)
        .filter(ConsultaTriage.fecha_hora >= desde)
        .all()
    )
    por_fecha = Counter(fila[0].date() for fila in fechas_raw)
    hoy = date.today()
    consultas_por_dia = [
        DiaCount(fecha=dia, cantidad=por_fecha.get(dia, 0))
        for dia in (hoy - timedelta(days=offset) for offset in range(29, -1, -1))
    ]

    # Uso por modelo LLM (consultas + tokens)
    modelo_raw = (
        db.query(
            ConsultaTriage.modelo_utilizado,
            func.count(ConsultaTriage.id),
            func.coalesce(func.sum(ConsultaTriage.tokens_consumidos), 0),
        )
        .filter(ConsultaTriage.modelo_utilizado.isnot(None))
        .group_by(ConsultaTriage.modelo_utilizado)
        .order_by(func.count(ConsultaTriage.id).desc())
        .all()
    )
    por_modelo = [
        ModeloCount(modelo=modelo, consultas=consultas, tokens=int(tokens))
        for modelo, consultas, tokens in modelo_raw
    ]
    total_tokens = int(
        db.query(func.coalesce(func.sum(ConsultaTriage.tokens_consumidos), 0)).scalar()
    )

    # Actividad por usuario (top 10, sin contar consultas anónimas)
    actividad_raw = (
        db.query(Usuario.id, Usuario.nombre_completo, func.count(ConsultaTriage.id))
        .join(ConsultaTriage, ConsultaTriage.usuario_id == Usuario.id)
        .group_by(Usuario.id)
        .order_by(func.count(ConsultaTriage.id).desc())
        .limit(10)
        .all()
    )
    actividad_usuarios = [
        UsuarioActividad(usuario_id=uid, nombre=nombre, consultas=consultas)
        for uid, nombre, consultas in actividad_raw
    ]

    # Palabras clave frecuentes en motivos de consulta y síntomas
    textos = [
        texto
        for fila in db.query(ConsultaTriage.motivo_consulta, ConsultaTriage.sintomas).all()
        for texto in fila
        if texto
    ]
    motivos_frecuentes = _extraer_palabras_clave(textos, top_n=10)

    return EstadisticasOut(
        total_consultas=total_consultas,
        total_pacientes=total_pacientes,
        total_usuarios=total_usuarios,
        por_nivel=por_nivel,
        promedio_tiempo_respuesta=promedio_tiempo,
        modelo_mas_usado=modelo_mas_usado,
        por_sexo=por_sexo,
        por_rango_edad=por_rango_edad,
        consultas_por_dia=consultas_por_dia,
        por_modelo=por_modelo,
        total_tokens=total_tokens,
        actividad_usuarios=actividad_usuarios,
        motivos_frecuentes=motivos_frecuentes,
    )


def _validar_rango(
    dias: int | None, fecha_desde: date | None, fecha_hasta: date | None
) -> tuple[datetime, datetime]:
    """Resuelve el rango [desde, hasta] del período solicitado.

    Prioridad: 1) rango explícito (fecha_desde/fecha_hasta), 2) días atrás,
    3) último mes (30 días). Devuelve datetime inclusive para el filtro.
    """
    hoy = date.today()

    if fecha_desde or fecha_hasta:
        desde = fecha_desde or hoy
        hasta = fecha_hasta or hoy
        if desde > hasta:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="fecha_desde no puede ser posterior a fecha_hasta.",
            )
        return datetime.combine(desde, datetime.min.time()), datetime.combine(
            hasta, datetime.max.time()
        )

    if dias is not None:
        if dias < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="dias debe ser mayor o igual a 1.",
            )
        return (
            datetime.combine(hoy - timedelta(days=dias - 1), datetime.min.time()),
            datetime.combine(hoy, datetime.max.time()),
        )

    return (
        datetime.combine(hoy - timedelta(days=29), datetime.min.time()),
        datetime.combine(hoy, datetime.max.time()),
    )


@router.get("/estadisticas/triaje", response_model=EstadisticasTriajeOut)
def obtener_estadisticas_triaje(
    dias: int | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Estadísticas de triaje filtradas por período (solo admin).

    Si se pasa `fecha_desde`/`fecha_hasta` se usa ese rango; si solo se pasa
    `dias` se filtran los últimos N días; si no se pasa nada, se devuelven
    los últimos 30 días (equivalente al comportamiento por defecto).
    """
    _require_admin(usuario)
    desde, hasta = _validar_rango(dias, fecha_desde, fecha_hasta)

    # Rango temporal de consultas (inclusive)
    filtro = ConsultaTriage.fecha_hora >= desde
    filtro = filtro & (ConsultaTriage.fecha_hora <= hasta)

    # Total de consultas en el período
    total_consultas = (
        db.query(func.count(ConsultaTriage.id)).filter(filtro).scalar() or 0
    )

    # Conteo por nivel de urgencia
    niveles_raw = (
        db.query(ConsultaTriage.nivel_urgencia, func.count(ConsultaTriage.id))
        .filter(filtro)
        .group_by(ConsultaTriage.nivel_urgencia)
        .all()
    )
    por_nivel = [
        NivelCount(nivel=nivel or "sin_clasificar", cantidad=cantidad)
        for nivel, cantidad in niveles_raw
    ]

    # Promedio de tiempo de respuesta en el período
    promedio = (
        db.query(func.avg(ConsultaTriage.tiempo_respuesta)).filter(filtro).scalar()
    )
    promedio_tiempo = round(float(promedio), 3) if promedio else None

    # Modelo más usado en el período
    modelo_row = (
        db.query(ConsultaTriage.modelo_utilizado, func.count(ConsultaTriage.id))
        .filter(filtro, ConsultaTriage.modelo_utilizado.isnot(None))
        .group_by(ConsultaTriage.modelo_utilizado)
        .order_by(func.count(ConsultaTriage.id).desc())
        .first()
    )
    modelo_mas_usado = modelo_row[0] if modelo_row else None

    # Demografía de los pacientes que consultaron en el período
    demografia_raw = (
        db.query(Paciente.sexo, Paciente.fecha_nacimiento)
        .join(ConsultaTriage, ConsultaTriage.paciente_id == Paciente.id)
        .filter(filtro)
        .all()
    )
    por_sexo_counter: Counter[str] = Counter()
    por_edad_counter: Counter[str] = Counter()
    for sexo, nacimiento in demografia_raw:
        por_sexo_counter[sexo] += 1
        por_edad_counter[_rango_edad(calcular_edad(nacimiento))] += 1
    por_sexo = [
        SexoCount(sexo=sexo, cantidad=cantidad)
        for sexo, cantidad in por_sexo_counter.items()
    ]
    por_rango_edad = [
        EdadRangeCount(rango=_etiqueta_rango(i), cantidad=por_edad_counter.get(_etiqueta_rango(i), 0))
        for i in range(len(RANGOS_EDAD))
    ]

    # Consultas por día dentro del rango (días sin datos en cero)
    fechas_raw = (
        db.query(ConsultaTriage.fecha_hora).filter(filtro).all()
    )
    por_fecha = Counter(fila[0].date() for fila in fechas_raw)
    num_dias = (hasta.date() - desde.date()).days + 1
    consultas_por_dia = [
        DiaCount(fecha=desde.date() + timedelta(days=offset), cantidad=por_fecha.get(desde.date() + timedelta(days=offset), 0))
        for offset in range(num_dias)
    ]

    # Tokens consumidos en el período
    total_tokens = int(
        db.query(func.coalesce(func.sum(ConsultaTriage.tokens_consumidos), 0))
        .filter(filtro)
        .scalar()
    )

    # Actividad por usuario (top 10, sin consultas anónimas) en el período
    actividad_raw = (
        db.query(Usuario.id, Usuario.nombre_completo, func.count(ConsultaTriage.id))
        .join(ConsultaTriage, ConsultaTriage.usuario_id == Usuario.id)
        .filter(filtro)
        .group_by(Usuario.id)
        .order_by(func.count(ConsultaTriage.id).desc())
        .limit(10)
        .all()
    )
    actividad_usuarios = [
        UsuarioActividad(usuario_id=uid, nombre=nombre, consultas=consultas)
        for uid, nombre, consultas in actividad_raw
    ]

    # Palabras clave frecuentes en motivos y síntomas del período
    textos = [
        texto
        for fila in db.query(ConsultaTriage.motivo_consulta, ConsultaTriage.sintomas)
        .filter(filtro)
        .all()
        for texto in fila
        if texto
    ]
    motivos_frecuentes = _extraer_palabras_clave(textos, top_n=10)

    return EstadisticasTriajeOut(
        fecha_desde=desde.date(),
        fecha_hasta=hasta.date(),
        total_consultas=total_consultas,
        por_nivel=por_nivel,
        promedio_tiempo_respuesta=promedio_tiempo,
        modelo_mas_usado=modelo_mas_usado,
        por_sexo=por_sexo,
        por_rango_edad=por_rango_edad,
        consultas_por_dia=consultas_por_dia,
        total_tokens=total_tokens,
        actividad_usuarios=actividad_usuarios,
        motivos_frecuentes=motivos_frecuentes,
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


@router.post("/usuarios", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    datos: UsuarioCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Crea un usuario nuevo desde el panel admin (solo admin)."""
    _require_admin(usuario)

    if db.query(Usuario).filter(Usuario.email == datos.email).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado.")
    if db.query(Usuario).filter(Usuario.ci == datos.ci).first():
        raise HTTPException(status_code=400, detail="La cédula ya está registrada.")

    nuevo = Usuario(
        ci=datos.ci,
        nombre_completo=datos.nombre_completo,
        email=datos.email,
        password_hash=hash_password(datos.password),
        rol=datos.rol,
        centro_salud=datos.centro_salud,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@router.put("/usuarios/{usuario_id}", response_model=UsuarioOut)
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Actualiza un usuario: rol, estado activo, datos, contraseña (solo admin)."""
    _require_admin(usuario)

    target = db.get(Usuario, usuario_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    cambios = datos.model_dump(exclude_unset=True)
    nueva_password = cambios.pop("password", None)

    if datos.email and datos.email != target.email:
        duplicado = (
            db.query(Usuario)
            .filter(Usuario.email == datos.email, Usuario.id != usuario_id)
            .first()
        )
        if duplicado:
            raise HTTPException(status_code=400, detail="El email ya está registrado.")

    for campo, valor in cambios.items():
        setattr(target, campo, valor)
    if nueva_password:
        target.password_hash = hash_password(nueva_password)

    db.commit()
    db.refresh(target)
    return target


@router.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Elimina un usuario (solo admin).

    Las consultas de triaje asociadas se conservan con auditoría anónima
    (usuario_id = NULL). Protecciones: no puede eliminarse a sí mismo ni
    al último admin activo del sistema.
    """
    _require_admin(usuario)

    if usuario_id == usuario.id:
        raise HTTPException(
            status_code=400, detail="No puedes eliminar tu propio usuario."
        )

    target = db.get(Usuario, usuario_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if target.rol == "admin" and target.activo:
        otros_admins = (
            db.query(Usuario)
            .filter(Usuario.rol == "admin", Usuario.activo.is_(True), Usuario.id != usuario_id)
            .count()
        )
        if otros_admins == 0:
            raise HTTPException(
                status_code=400,
                detail="No se puede eliminar al último administrador activo.",
            )

    # Conserva la auditoría de triajes: la FK queda en NULL (SET NULL)
    db.query(ConsultaTriage).filter(ConsultaTriage.usuario_id == usuario_id).update(
        {ConsultaTriage.usuario_id: None}, synchronize_session=False
    )
    db.delete(target)
    db.commit()
