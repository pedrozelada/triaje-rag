"""Ejecución de un triaje: vitales, motor RAG, reglas y auditoría.

El router solo valida el formato de la petición y devuelve la respuesta; el
recorrido clínico (armar los vitales del paciente, pasar por el motor, guardar
la auditoría) vive aquí y se puede probar sin HTTP.
"""

from sqlalchemy.orm import Session

from ai_service.models import DatosVitales
from backend.db.models import ConsultaTriage, Paciente, Usuario
from backend.rag.service import rag_service
from backend.services.errores import DatosInvalidos, NoEncontrado

MENSAJE_PACIENTE = "Paciente no encontrado."
MENSAJE_VITALES = (
    "Signos vitales fuera de rango fisiológicamente posible. Verifica los valores."
)


def datos_vitales_del_paciente(paciente: Paciente, datos) -> DatosVitales:
    """Arma los vitales del motor con los datos del paciente y de la consulta.

    Los signos ausentes llegan como None (= no medido) y se muestran como
    "No registrado" en el prompt: NUNCA se sustituyen por valores normales.
    La edad en meses permite triar lactantes; sin ella, con 0 años se perdería
    el grupo etario y se aplicarían umbrales de adulto.
    """
    return DatosVitales(
        edad=paciente.edad,
        edad_meses=paciente.edad_meses,
        sexo=paciente.sexo,
        temperatura=datos.temperatura,
        presion_sistolica=datos.presion_sistolica,
        presion_diastolica=datos.presion_diastolica,
        frecuencia_cardiaca=datos.frecuencia_cardiaca,
        frecuencia_respiratoria=datos.frecuencia_respiratoria,
        saturacion=datos.spo2,
    )


def descripcion_clinica(datos) -> str:
    """Texto que ve el modelo: motivo de consulta y síntomas, en ese orden."""
    return "\n".join(
        parte for parte in (datos.motivo_consulta, datos.sintomas) if parte
    )


def crear_consulta(db: Session, datos, usuario: Usuario | None = None, motor=None):
    """Ejecuta el triaje de una petición y persiste la auditoría.

    Args:
        db: sesión de base de datos.
        datos: `TriageCreate` con el paciente y los signos vitales.
        usuario: usuario autenticado o None si el triaje es anónimo.
        motor: servicio RAG a usar (por defecto el del sistema). Se puede
            inyectar otro en los tests para no llamar a ningún modelo.

    Raises:
        NoEncontrado: si el paciente no existe.
        DatosInvalidos: si los vitales son incoherentes entre sí.
    """
    motor = motor or rag_service

    paciente = db.get(Paciente, datos.paciente_id)
    if not paciente:
        raise NoEncontrado(MENSAJE_PACIENTE)

    vitales = datos_vitales_del_paciente(paciente, datos)

    # Defensa en profundidad: Pydantic ya validó los rangos campo por campo,
    # aquí se comprueba la coherencia clínica (p. ej. sistólica > diastólica).
    if not vitales.es_valido():
        raise DatosInvalidos(MENSAJE_VITALES)

    resultado = motor.analizar(
        datos_vitales=vitales,
        sintomas=descripcion_clinica(datos),
        modelo_nombre=datos.modelo,
    )

    consulta = ConsultaTriage(
        paciente_id=paciente.id,
        usuario_id=usuario.id if usuario else None,
        temperatura=datos.temperatura,
        presion_sistolica=datos.presion_sistolica,
        presion_diastolica=datos.presion_diastolica,
        frecuencia_cardiaca=datos.frecuencia_cardiaca,
        frecuencia_respiratoria=datos.frecuencia_respiratoria,
        spo2=datos.spo2,
        motivo_consulta=datos.motivo_consulta,
        sintomas=datos.sintomas,
        nivel_urgencia=resultado.nivel_urgencia,
        respuesta_llm=resultado.respuesta,
        prompt_utilizado=resultado.prompt_utilizado,
        modelo_utilizado=resultado.modelo_utilizado,
        tiempo_respuesta=resultado.tiempo_respuesta,
        tokens_consumidos=resultado.tokens_consumidos,
        reglas_activadas=resultado.reglas_activadas,
    )
    db.add(consulta)
    db.commit()
    db.refresh(consulta)
    return consulta
