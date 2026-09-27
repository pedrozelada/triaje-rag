"""Rangos etarios del desglose demográfico.

Vive en un solo lugar porque lo usan dos endpoints (estadísticas globales y
estadísticas por período) y los dos deben agrupar igual: si las etiquetas se
calculan distinto, las dos pantallas del panel muestran cortes incomparables.
"""

#: (inicio, fin inclusivo; None = abierto hacia arriba)
RANGOS_EDAD: tuple[tuple[int, int | None], ...] = (
    (0, 5),
    (6, 12),
    (13, 17),
    (18, 30),
    (31, 50),
    (51, 64),
    (65, None),
)

#: Etiquetas en el mismo orden que RANGOS_EDAD, ya calculadas.
ETIQUETAS_EDAD: tuple[str, ...] = tuple(
    f"{inicio}+" if fin is None else f"{inicio}-{fin}" for inicio, fin in RANGOS_EDAD
)


def etiqueta_de_indice(indice: int) -> str:
    """Etiqueta legible del i-ésimo rango de RANGOS_EDAD."""
    return ETIQUETAS_EDAD[indice]


def rango_de_edad(edad: int) -> str:
    """Etiqueta del rango al que pertenece una edad."""
    for (inicio, fin), etiqueta in zip(RANGOS_EDAD, ETIQUETAS_EDAD, strict=True):
        if fin is None:
            if edad >= inicio:
                return etiqueta
        elif inicio <= edad <= fin:
            return etiqueta
    return "desconocido"
