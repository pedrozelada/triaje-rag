"""Router de administración: estadísticas, gestión de usuarios, reportes."""

import re
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.db.models import ConsultaTriage, Paciente, Usuario, calcular_edad
from backend.db.session import get_db
from backend.schemas.admin import (
    DiaCount,
    EdadRangeCount,
    EstadisticasOut,
    ModeloCount,
    MotivoFrecuente,
    NivelCount,
    SexoCount,
    UsuarioActividad,
)
from backend.schemas.usuario import UsuarioOut, UsuarioUpdate

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
