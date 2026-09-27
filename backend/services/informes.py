"""Consulta del historial de triaje de un paciente.

Los tres formatos de informe (JSON, texto y PDF) necesitan lo mismo: el
paciente y sus consultas en un orden concreto. Vivía repetido en cada endpoint,
con el riesgo de que uno olvidara comprobar que el paciente existe.
"""

from sqlalchemy.orm import Session

from backend.db.models import ConsultaTriage, Paciente
from backend.services.errores import NoEncontrado

MENSAJE_PACIENTE = "Paciente no encontrado."


def historial_de_paciente(
    db: Session, paciente_id: int, *, orden: str = "ascendente"
) -> tuple[Paciente, list[ConsultaTriage]]:
    """Paciente y sus consultas, de la más antigua a la más reciente.

    Args:
        orden: "ascendente" (para leer el informe de corrido) o "descendente"
            (para la tabla del historial, donde interesa lo más reciente).

    Raises:
        NoEncontrado: si el paciente no existe.
    """
    paciente = db.get(Paciente, paciente_id)
    if not paciente:
        raise NoEncontrado(MENSAJE_PACIENTE)

    columna = ConsultaTriage.fecha_hora
    consultas = (
        db.query(ConsultaTriage)
        .filter(ConsultaTriage.paciente_id == paciente_id)
        .order_by(columna.desc() if orden == "descendente" else columna.asc())
        .all()
    )
    return paciente, consultas
