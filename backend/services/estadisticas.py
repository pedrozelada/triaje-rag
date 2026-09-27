"""Agregados del panel de administración.

Aquí vive **una sola** implementación de cada cifra del panel. Los tres
endpoints (`/estadisticas`, `/estadisticas/triaje` y `/estadisticas/llm`) eran
casi el mismo código copiado, con el riesgo de que un arreglo en uno dejara a
los otros dos mintiendo.

Los agregados se devuelven como tuplas y no como los schemas de la API: así el
mismo núcleo sirve para la API, para un script de la tesis o para un test, sin
arrastrar Pydantic.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models import ConsultaTriage, Paciente, Usuario, calcular_edad
from backend.services.demografia import ETIQUETAS_EDAD, rango_de_edad
from backend.services.errores import SolicitudInvalida
from backend.services.palabras_clave import extraer_palabras_clave

#: Días que abarcan las estadísticas cuando no se pide un período.
DIAS_POR_DEFECTO = 30
#: Filas de los rankings del panel.
TOP_ACTIVIDAD = 10
TOP_MOTIVOS = 10


@dataclass(frozen=True)
class Agregados:
    """Cifras de triaje calculadas sobre un mismo conjunto de consultas."""

    total_consultas: int
    por_nivel: list[tuple[str, int]]
    promedio_tiempo: float | None
    modelo_mas_usado: str | None
    por_sexo: list[tuple[str, int]]
    por_rango_edad: list[tuple[str, int]]
    consultas_por_dia: list[tuple[date, int]]
    total_tokens: int
    actividad_usuarios: list[tuple[int, str, int]]
    motivos_frecuentes: list[tuple[str, int]]
    por_modelo: list[tuple[str, int, int]]


@dataclass(frozen=True)
class ResumenLLM:
    """Uso y rendimiento de los modelos, solo sobre consultas con modelo."""

    total_consultas: int
    total_tokens: int
    tiempo_promedio: float | None
    tiempo_minimo: float | None
    tiempo_maximo: float | None
    por_modelo: list[tuple[str, int, int, float | None, float | None, float | None]]


def _redondear(valor: Any) -> float | None:
    """Redondeo homogéneo de los tiempos (o None si no se midió)."""
    return None if valor is None else round(float(valor), 3)


def _filtrar(consulta, criterio):
    """Aplica el criterio solo si existe (None = todas las filas)."""
    return consulta if criterio is None else consulta.filter(criterio)


def filtrar_periodo(desde: datetime, hasta: datetime):
    """Criterio de fecha con ambos extremos incluidos."""
    return (ConsultaTriage.fecha_hora >= desde) & (ConsultaTriage.fecha_hora <= hasta)


def resolver_periodo(
    dias: int | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
) -> tuple[datetime, datetime]:
    """Resuelve el rango [desde, hasta] del período pedido.

    Prioridad: 1) rango explícito (fecha_desde/fecha_hasta), 2) días atrás,
    3) el último mes. El rango devuelto es inclusive en ambos extremos.
    """
    hoy = date.today()

    if fecha_desde or fecha_hasta:
        desde = fecha_desde or hoy
        hasta = fecha_hasta or hoy
        if desde > hasta:
            raise SolicitudInvalida("fecha_desde no puede ser posterior a fecha_hasta.")
        return _dia_completo(desde), _dia_completo(hasta, fin=True)

    if dias is not None:
        if dias < 1:
            raise SolicitudInvalida("dias debe ser mayor o igual a 1.")
        return _dia_completo(hoy - timedelta(days=dias - 1)), _dia_completo(hoy, fin=True)

    return (
        _dia_completo(hoy - timedelta(days=DIAS_POR_DEFECTO - 1)),
        _dia_completo(hoy, fin=True),
    )


def _dia_completo(dia: date, fin: bool = False) -> datetime:
    """Un día entero: su medianoche o su último instante."""
    hora = datetime.max.time() if fin else datetime.min.time()
    return datetime.combine(dia, hora)


def contar(db: Session, modelo) -> int:
    """Cantidad de filas de una tabla."""
    return db.query(func.count(modelo.id)).scalar() or 0


def calcular(
    db: Session,
    *,
    rango: tuple[date, date],
    criterio: Any | None = None,
    demografia_por_consulta: bool = False,
) -> Agregados:
    """Calcula todos los agregados del panel sobre un mismo conjunto.

    Args:
        db: sesión de base de datos.
        rango: (primer día, último día) que se dibuja en la serie por día; los
            días sin consultas aparecen en cero para que la gráfica no mienta.
        criterio: filtro de consultas (None = todas, sin límite de fechas).
        demografia_por_consulta: si es True, la demografía cuenta las consultas
            del período (un paciente que consultó dos veces cuenta dos, que es
            lo que interesa en el panel); si es False, cuenta pacientes únicos
            de todo el sistema.
    """
    desde_dia, hasta_dia = rango

    total_consultas = (
        _filtrar(db.query(func.count(ConsultaTriage.id)), criterio).scalar() or 0
    )

    niveles = (
        _filtrar(
            db.query(ConsultaTriage.nivel_urgencia, func.count(ConsultaTriage.id)),
            criterio,
        )
        .group_by(ConsultaTriage.nivel_urgencia)
        .all()
    )
    por_nivel = [
        (nivel or "sin_clasificar", cantidad) for nivel, cantidad in niveles
    ]

    promedio_tiempo = _redondear(
        _filtrar(db.query(func.avg(ConsultaTriage.tiempo_respuesta)), criterio).scalar()
    )

    modelo_row = (
        _filtrar(
            db.query(ConsultaTriage.modelo_utilizado, func.count(ConsultaTriage.id)),
            criterio,
        )
        .filter(ConsultaTriage.modelo_utilizado.isnot(None))
        .group_by(ConsultaTriage.modelo_utilizado)
        .order_by(func.count(ConsultaTriage.id).desc())
        .first()
    )

    por_sexo, por_rango_edad = (
        _demografia_por_consulta(db, criterio)
        if demografia_por_consulta
        else _demografia_de_pacientes(db)
    )

    por_fecha = Counter(
        fila[0].date()
        for fila in _filtrar(db.query(ConsultaTriage.fecha_hora), criterio).all()
    )
    dias = [
        desde_dia + timedelta(days=offset)
        for offset in range((hasta_dia - desde_dia).days + 1)
    ]
    consultas_por_dia = [(dia, por_fecha.get(dia, 0)) for dia in dias]

    total_tokens = int(
        _filtrar(
            db.query(func.coalesce(func.sum(ConsultaTriage.tokens_consumidos), 0)),
            criterio,
        ).scalar()
    )

    actividad = (
        _filtrar(
            db.query(Usuario.id, Usuario.nombre_completo, func.count(ConsultaTriage.id)),
            criterio,
        )
        .join(ConsultaTriage, ConsultaTriage.usuario_id == Usuario.id)
        .group_by(Usuario.id)
        .order_by(func.count(ConsultaTriage.id).desc())
        .limit(TOP_ACTIVIDAD)
        .all()
    )
    actividad_usuarios = [
        (usuario_id, nombre, consultas) for usuario_id, nombre, consultas in actividad
    ]

    textos = [
        texto
        for fila in _filtrar(
            db.query(ConsultaTriage.motivo_consulta, ConsultaTriage.sintomas), criterio
        ).all()
        for texto in fila
        if texto
    ]
    motivos_frecuentes = extraer_palabras_clave(textos, top_n=TOP_MOTIVOS)

    modelos = (
        _filtrar(
            db.query(
                ConsultaTriage.modelo_utilizado,
                func.count(ConsultaTriage.id),
                func.coalesce(func.sum(ConsultaTriage.tokens_consumidos), 0),
            ),
            criterio,
        )
        .filter(ConsultaTriage.modelo_utilizado.isnot(None))
        .group_by(ConsultaTriage.modelo_utilizado)
        .order_by(func.count(ConsultaTriage.id).desc())
        .all()
    )
    por_modelo = [
        (modelo, consultas, int(tokens)) for modelo, consultas, tokens in modelos
    ]

    return Agregados(
        total_consultas=total_consultas,
        por_nivel=por_nivel,
        promedio_tiempo=promedio_tiempo,
        modelo_mas_usado=modelo_row[0] if modelo_row else None,
        por_sexo=por_sexo,
        por_rango_edad=por_rango_edad,
        consultas_por_dia=consultas_por_dia,
        total_tokens=total_tokens,
        actividad_usuarios=actividad_usuarios,
        motivos_frecuentes=motivos_frecuentes,
        por_modelo=por_modelo,
    )


def _demografia_de_pacientes(db: Session) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Sexo y rango etario de TODOS los pacientes registrados.

    La edad se calcula en Python a partir de la fecha de nacimiento: es
    agnóstico del motor de base de datos.
    """
    por_sexo = [
        (sexo, cantidad)
        for sexo, cantidad in db.query(Paciente.sexo, func.count(Paciente.id))
        .group_by(Paciente.sexo)
        .all()
    ]
    nacimientos = [fila[0] for fila in db.query(Paciente.fecha_nacimiento).all()]
    edades = Counter(rango_de_edad(calcular_edad(fecha)) for fecha in nacimientos)
    return por_sexo, _serie_etaria(edades)


def _demografia_por_consulta(
    db: Session, criterio: Any | None
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Sexo y rango etario de los pacientes que consultaron en el período."""
    filas = _filtrar(
        db.query(Paciente.sexo, Paciente.fecha_nacimiento).join(
            ConsultaTriage, ConsultaTriage.paciente_id == Paciente.id
        ),
        criterio,
    ).all()

    sexos: Counter[str] = Counter()
    edades: Counter[str] = Counter()
    for sexo, nacimiento in filas:
        sexos[sexo] += 1
        edades[rango_de_edad(calcular_edad(nacimiento))] += 1
    return list(sexos.items()), _serie_etaria(edades)


def _serie_etaria(edades: Counter) -> list[tuple[str, int]]:
    """Todos los rangos etarios en orden, con ceros incluidos."""
    return [(etiqueta, edades.get(etiqueta, 0)) for etiqueta in ETIQUETAS_EDAD]


def resumen_llm(db: Session) -> ResumenLLM:
    """Uso y rendimiento de los modelos LLM (solo consultas con modelo)."""
    criterio = ConsultaTriage.modelo_utilizado.isnot(None)

    total_consultas = db.query(func.count(ConsultaTriage.id)).filter(criterio).scalar() or 0
    total_tokens = int(
        db.query(func.coalesce(func.sum(ConsultaTriage.tokens_consumidos), 0))
        .filter(criterio)
        .scalar()
    )

    tiempos = (
        db.query(
            func.avg(ConsultaTriage.tiempo_respuesta),
            func.min(ConsultaTriage.tiempo_respuesta),
            func.max(ConsultaTriage.tiempo_respuesta),
        )
        .filter(criterio, ConsultaTriage.tiempo_respuesta.isnot(None))
        .one()
    )

    modelos = (
        db.query(
            ConsultaTriage.modelo_utilizado,
            func.count(ConsultaTriage.id),
            func.coalesce(func.sum(ConsultaTriage.tokens_consumidos), 0),
            func.avg(ConsultaTriage.tiempo_respuesta),
            func.min(ConsultaTriage.tiempo_respuesta),
            func.max(ConsultaTriage.tiempo_respuesta),
        )
        .filter(criterio)
        .group_by(ConsultaTriage.modelo_utilizado)
        .order_by(func.count(ConsultaTriage.id).desc())
        .all()
    )

    return ResumenLLM(
        total_consultas=total_consultas,
        total_tokens=total_tokens,
        tiempo_promedio=_redondear(tiempos[0]),
        tiempo_minimo=_redondear(tiempos[1]),
        tiempo_maximo=_redondear(tiempos[2]),
        por_modelo=[
            (
                modelo,
                consultas,
                int(tokens),
                _redondear(promedio),
                _redondear(minimo),
                _redondear(maximo),
            )
            for modelo, consultas, tokens, promedio, minimo, maximo in modelos
        ],
    )
