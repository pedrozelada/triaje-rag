"""Errores de dominio del backend.

Los servicios no conocen FastAPI: cuando una operación no puede completarse
lanzan uno de estos errores, y un manejador global (en `backend.app.main`) los
traduce al contrato HTTP de siempre: el código del error y el cuerpo
`{"detail": <mensaje>}`, idéntico al de `HTTPException` para no cambiar lo que
ya consume el frontend.
"""


class ErrorDeNegocio(Exception):
    """Operación rechazada por una regla del dominio."""

    #: Código HTTP que le corresponde.
    codigo: int = 400

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class SolicitudInvalida(ErrorDeNegocio):
    """Datos que no cumplen una regla (rol inexistente, duplicados, fechas)."""

    codigo = 400


class DatosInvalidos(ErrorDeNegocio):
    """Datos que no pasan una validación semántica (422).

    Es el caso de unos signos vitales que no son imposibles de escribir pero sí
    de tener (una sistólica menor que la diastólica, por ejemplo).
    """

    codigo = 422


class NoEncontrado(ErrorDeNegocio):
    """El recurso pedido no existe."""

    codigo = 404


class Prohibido(ErrorDeNegocio):
    """El usuario está autenticado pero no puede hacer esta operación."""

    codigo = 403


class NoDisponible(ErrorDeNegocio):
    """Una dependencia externa (el modelo de lenguaje, por ejemplo) no responde."""

    codigo = 503
