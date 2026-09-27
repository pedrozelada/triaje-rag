"""Estadísticas del panel de administración.

Las tres rutas comparten el mismo núcleo de agregados
(`backend.services.estadisticas`); aquí solo se elige el período y se traduce
el resultado a los schemas de la API.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import require_admin
from backend.db.models import Paciente, Usuario
from backend.db.session import get_db
from backend.schemas.admin import (
    DiaCount,
    EdadRangeCount,
    EstadisticasLLMOut,
    EstadisticasOut,
    EstadisticasTriajeOut,
    ModeloCount,
    ModeloRendimiento,
    MotivoFrecuente,
    NivelCount,
    SexoCount,
    UsuarioActividad,
)
from backend.services import estadisticas as servicio

router = APIRouter()


@router.get("/estadisticas", response_model=EstadisticasOut)
def obtener_estadisticas(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_admin),
):
    """Estadísticas generales del sistema: totales y últimos 30 días."""
    hoy = date.today()
    agregados = servicio.calcular(
        db,
        rango=(hoy - timedelta(days=servicio.DIAS_POR_DEFECTO - 1), hoy),
    )

    return EstadisticasOut(
        total_consultas=agregados.total_consultas,
        total_pacientes=servicio.contar(db, Paciente),
        total_usuarios=servicio.contar(db, Usuario),
        por_nivel=[
            NivelCount(nivel=nivel, cantidad=cantidad)
            for nivel, cantidad in agregados.por_nivel
        ],
        promedio_tiempo_respuesta=agregados.promedio_tiempo,
        modelo_mas_usado=agregados.modelo_mas_usado,
        por_sexo=[
            SexoCount(sexo=sexo, cantidad=cantidad)
            for sexo, cantidad in agregados.por_sexo
        ],
        por_rango_edad=[
            EdadRangeCount(rango=rango, cantidad=cantidad)
            for rango, cantidad in agregados.por_rango_edad
        ],
        consultas_por_dia=[
            DiaCount(fecha=fecha, cantidad=cantidad)
            for fecha, cantidad in agregados.consultas_por_dia
        ],
        por_modelo=[
            ModeloCount(modelo=modelo, consultas=consultas, tokens=tokens)
            for modelo, consultas, tokens in agregados.por_modelo
        ],
        total_tokens=agregados.total_tokens,
        actividad_usuarios=[
            UsuarioActividad(usuario_id=usuario_id, nombre=nombre, consultas=consultas)
            for usuario_id, nombre, consultas in agregados.actividad_usuarios
        ],
        motivos_frecuentes=[
            MotivoFrecuente(palabra=palabra, cantidad=cantidad)
            for palabra, cantidad in agregados.motivos_frecuentes
        ],
    )


@router.get("/estadisticas/triaje", response_model=EstadisticasTriajeOut)
def obtener_estadisticas_triaje(
    dias: int | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_admin),
):
    """Estadísticas de triaje filtradas por período.

    Si se pasa `fecha_desde`/`fecha_hasta` se usa ese rango; si solo se pasa
    `dias` se filtran los últimos N días; si no se pasa nada, los últimos 30.
    """
    desde, hasta = servicio.resolver_periodo(dias, fecha_desde, fecha_hasta)
    agregados = servicio.calcular(
        db,
        rango=(desde.date(), hasta.date()),
        criterio=servicio.filtrar_periodo(desde, hasta),
        demografia_por_consulta=True,
    )

    return EstadisticasTriajeOut(
        fecha_desde=desde.date(),
        fecha_hasta=hasta.date(),
        total_consultas=agregados.total_consultas,
        por_nivel=[
            NivelCount(nivel=nivel, cantidad=cantidad)
            for nivel, cantidad in agregados.por_nivel
        ],
        promedio_tiempo_respuesta=agregados.promedio_tiempo,
        modelo_mas_usado=agregados.modelo_mas_usado,
        por_sexo=[
            SexoCount(sexo=sexo, cantidad=cantidad)
            for sexo, cantidad in agregados.por_sexo
        ],
        por_rango_edad=[
            EdadRangeCount(rango=rango, cantidad=cantidad)
            for rango, cantidad in agregados.por_rango_edad
        ],
        consultas_por_dia=[
            DiaCount(fecha=fecha, cantidad=cantidad)
            for fecha, cantidad in agregados.consultas_por_dia
        ],
        total_tokens=agregados.total_tokens,
        actividad_usuarios=[
            UsuarioActividad(usuario_id=usuario_id, nombre=nombre, consultas=consultas)
            for usuario_id, nombre, consultas in agregados.actividad_usuarios
        ],
        motivos_frecuentes=[
            MotivoFrecuente(palabra=palabra, cantidad=cantidad)
            for palabra, cantidad in agregados.motivos_frecuentes
        ],
    )


@router.get("/estadisticas/llm", response_model=EstadisticasLLMOut)
def obtener_estadisticas_llm(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_admin),
):
    """Uso y rendimiento de los modelos LLM (todas las consultas con modelo)."""
    resumen = servicio.resumen_llm(db)

    return EstadisticasLLMOut(
        total_consultas=resumen.total_consultas,
        total_tokens=resumen.total_tokens,
        tiempo_promedio=resumen.tiempo_promedio,
        tiempo_minimo=resumen.tiempo_minimo,
        tiempo_maximo=resumen.tiempo_maximo,
        por_modelo=[
            ModeloRendimiento(
                modelo=modelo,
                consultas=consultas,
                tokens=tokens,
                tiempo_promedio=promedio,
                tiempo_minimo=minimo,
                tiempo_maximo=maximo,
            )
            for modelo, consultas, tokens, promedio, minimo, maximo in resumen.por_modelo
        ],
    )
