"""Conteo de palabras frecuentes en textos clínicos libres.

Es una aproximación por palabras clave para el panel administrativo: sirve para
ver de qué se queja la gente, no para contar enfermedades. No se usa ninguna
decisión clínica a partir de esto.
"""

import re
import unicodedata
from collections import Counter

# Stopwords: gramaticales del español + relleno clínico habitual en los formularios
STOPWORDS = frozenset(
    {
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
        "fue", "hubo", "han", "habia", "seria", "dos", "tres", "vez",
    }
)

LARGO_MINIMO_PALABRA = 3


def palabras_de(texto: str) -> list[str]:
    """Palabras significativas de un texto (sin stopwords ni términos cortos).

    La normalización es NFD sin quitar las marcas combinantes, así que una
    palabra con tilde interna se parte en dos ("torácico" -> "tora" + "cico").
    Se conserva ese comportamiento porque las cifras del panel ya se
    publicaron así; corregirlo es un cambio deliberado aparte.
    """
    normalizado = unicodedata.normalize("NFD", texto.lower())
    return [
        palabra
        for palabra in re.findall(r"[a-z]+", normalizado)
        if len(palabra) >= LARGO_MINIMO_PALABRA and palabra not in STOPWORDS
    ]


def extraer_palabras_clave(
    textos: list[str | None], top_n: int = 10
) -> list[tuple[str, int]]:
    """Las `top_n` palabras más frecuentes, de mayor a menor.

    Devuelve pares (palabra, cantidad) para no acoplar el servicio a los
    schemas de la API.
    """
    contador: Counter[str] = Counter()
    for texto in textos:
        if texto:
            contador.update(palabras_de(texto))
    return contador.most_common(top_n)
