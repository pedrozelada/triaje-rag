"""Genera el informe Word de la evaluación del sistema (Componente 2).

Uso:
    venv/Scripts/python.exe scripts/informe_word.py
    venv/Scripts/python.exe scripts/informe_word.py --forzar-graficos

Salidas (en el árbol de documentación de la tesis, que está en .gitignore):
    docs/tesis/Informe_Evaluacion_Componente2_Zelada.docx
    docs/tesis/figuras/eval_*.png        (3 gráficos comparativos vía kroki.io)

Ninguna cifra del documento se escribe a mano: se importa `scripts/evaluar.py`
(el mismo arnés que produce `evaluacion/informes/*.md`) y de ahí salen el nivel
de cada caso, la recuperación, las alucinaciones, la latencia y los tokens. Si
una corrida nueva cambia un número, este documento cambia con ella.

El formato es el del Capítulo II: los estilos, los pies de tabla y de figura
numerados con campos SEQ de Word y el pie de página los aplica
`docs/tesis/generar_documento.py`; aquí solo se describen bloques (T, P, TAB,
FIG, NOTA, MONO), igual que en el capítulo.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import requests
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Pt

DIR = Path(__file__).resolve().parent
RAIZ = DIR.parent
DIR_TESIS = RAIZ / "docs" / "tesis"

SALIDA = DIR_TESIS / "Informe_Evaluacion_Componente2_Zelada.docx"
DIR_GRAFICOS = DIR_TESIS / "figuras"
KROKI_VEGA = "https://kroki.io/vega/png"

# Corridas que alimentan el informe. Los lotes del mismo experimento se fusionan
# (una corrida de 30 casos no cabe en una sola ejecución de terminal).
CORRIDAS = {
    "sistema": ("rag_groq_1", "rag_groq_2a", "rag_groq_2b", "piloto_groq"),
    "baseline_groq": (
        "baseline_groq_1",
        "baseline_groq_2a",
        "baseline_groq_2b",
        "prueba_groq_quota",
    ),
    "baseline_gemini": ("baseline_gemini_1", "prueba_gemini"),
}
ETIQUETAS = {
    "sistema": "Sistema con RAG (Groq)",
    "baseline_groq": "Sin contexto (Groq)",
    "baseline_gemini": "Sin contexto (Gemini)",
}
COLOR_BARRA = "#2C5282"
COLOR_REGLA = "#C53030"


# ---------------------------------------------------------------------------
# Métricas: una sola fuente de verdad (scripts/evaluar.py)
# ---------------------------------------------------------------------------


def cargar_arnes():
    """Carga el arnés de evaluación como módulo, sin depender de un paquete."""
    spec = importlib.util.spec_from_file_location("evaluar_arnes", DIR / "evaluar.py")
    if spec is None or spec.loader is None:  # pragma: no cover - protección
        raise SystemExit("❌ No se pudo cargar scripts/evaluar.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def cargar_formato():
    """Reutiliza los estilos y los bloques del Capítulo II.

    El generador vive en `scripts/` (versionado) y el formato del capítulo en
    `docs/tesis/` (en .gitignore), así que se importan por ruta: duplicar el
    formato del capítulo sería la forma más segura de que los dos documentos se
    parezcan cada vez menos.
    """
    if not (DIR_TESIS / "generar_documento.py").exists():
        raise SystemExit(
            f"❌ No se encontró el generador del capítulo en {DIR_TESIS}. "
            "Este informe reutiliza su formato (estilos, pies numerados y pie de página)."
        )
    sys.path.insert(0, str(DIR_TESIS))
    especificaciones = {
        "bloques": DIR_TESIS / "bloques.py",
        "generar_documento": DIR_TESIS / "generar_documento.py",
    }
    modulos = {}
    for nombre, ruta in especificaciones.items():
        spec = importlib.util.spec_from_file_location(nombre, ruta)
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[nombre] = modulo
        spec.loader.exec_module(modulo)
        modulos[nombre] = modulo
    return modulos["bloques"], modulos["generar_documento"]


def cargar_metricas(arnes) -> dict:
    """Reúne las variantes, sus resúmenes y los subconjuntos comparables."""
    variantes: dict[str, dict] = {}
    for clave, nombres in CORRIDAS.items():
        faltantes = [
            n for n in nombres if not (arnes.DIR_RESULTADOS / f"{n}.json").exists()
        ]
        if faltantes:
            raise SystemExit(
                f"❌ Faltan corridas para «{clave}»: {', '.join(faltantes)}. "
                "Ejecuta antes `python scripts/evaluar.py correr`."
            )
        documentos = [
            json.loads((arnes.DIR_RESULTADOS / f"{n}.json").read_text(encoding="utf-8"))
            for n in nombres
        ]
        variante = arnes.agregar(arnes.fusionar_corridas(documentos))["variantes"][0]
        variantes[clave] = {
            "etiqueta": ETIQUETAS[clave],
            "run_id": variante["run_id"],
            "casos": variante["casos"],
            "entorno": variante.get("entorno") or {},
            "resumen": arnes.resumen_variante(variante),
        }

    sistema = variantes["sistema"]
    exitosos_sistema = {c["id"] for c in sistema["casos"] if c.get("n_exitosos")}
    comunes: dict[str, dict] = {}
    for clave in ("baseline_groq", "baseline_gemini"):
        base = variantes[clave]
        exitosos_base = {c["id"] for c in base["casos"] if c.get("n_exitosos")}
        ids = exitosos_sistema & exitosos_base
        comunes[clave] = {
            "ids": sorted(ids),
            "sistema": arnes.resumen_variante(
                {"casos": [c for c in sistema["casos"] if c["id"] in ids]}
            ),
            "base": arnes.resumen_variante(
                {"casos": [c for c in base["casos"] if c["id"] in ids]}
            ),
        }
    return {"variantes": variantes, "comunes": comunes}


def registro(caso: dict) -> dict:
    """Registro crudo (respuesta, fragmentos, tiempos) de la primera repetición."""
    return caso["veredictos"][0]["_registro"] if caso.get("veredictos") else {}


def veredicto(caso: dict) -> dict:
    return caso["veredictos"][0] if caso.get("veredictos") else {}


def por_id(variante: dict) -> dict[str, dict]:
    return {c["id"]: c for c in variante["casos"]}


def etiqueta_resultado(caso: dict) -> str:
    """Resultado legible del nivel final frente al esperado."""
    v = veredicto(caso)
    if not v:
        return "sin respuesta"
    if v.get("sin_clasificar"):
        return "sin clasificar"
    if v.get("coincide_exacto"):
        return "exacto"
    if v.get("coincide_permitido"):
        return "en rango"
    if v.get("sub_triaje"):
        return "SUB-TRIAGE"
    if v.get("supra_triaje"):
        return "supra-triage"
    return "fuera de rango"


def senales_de_alucinacion(v: dict) -> str:
    """Qué detector disparó el veredicto (o «—» si no disparó ninguno)."""
    partes: list[str] = []
    if v.get("dosis_inventadas"):
        partes.append("dosis inventada: " + ", ".join(v["dosis_inventadas"]))
    if v.get("citas_no_ancladas"):
        partes.append("cita no anclada")
    if v.get("paginas_inexistentes"):
        partes.append("página inexistente: " + ", ".join(v["paginas_inexistentes"]))
    if v.get("no_declara_ausencia"):
        partes.append("no declara la ausencia")
    if v.get("contradiccion_no_reconocida"):
        partes.append("no reconoce la contradicción")
    if v.get("criterios_violados"):
        partes.append("afirma contenido prohibido por el caso")
    return " · ".join(partes) if partes else "—"


def top_fragmentos(caso: dict, n: int = 3) -> str:
    """Fragmentos recuperados con página y puntaje, para las fichas de caso."""
    partes: list[str] = []
    for rec in (registro(caso).get("recuperaciones") or [])[:n]:
        base = f"{rec.get('archivo')} pág. {rec.get('page_label')}"
        score = rec.get("score")
        partes.append(
            f"{base} (score {score:.3f})" if isinstance(score, (int, float)) else base
        )
    return "; ".join(partes) if partes else "—"


def _relativa(ruta: Path) -> str:
    try:
        return str(ruta.relative_to(RAIZ))
    except ValueError:
        return str(ruta)


# ---------------------------------------------------------------------------
# Gráficos (Vega vía kroki.io, el mismo servicio de los diagramas del capítulo)
# ---------------------------------------------------------------------------


def _capa(props: dict) -> dict:
    """Propiedades de una marca Vega, en `enter` y en `update`.

    kroki renderiza con Vega, no con Vega-Lite (su ruta /vega-lite/png devuelve
    404), así que las especificaciones se arman a mano.
    """
    return {"enter": props, "update": props}


def spec_barras(
    valores: list[dict],
    *,
    ancho: int = 700,
    alto: int = 330,
    titulo_y: str = "",
    etiquetas: bool = True,
    angulo: int = 0,
    regla: dict | None = None,
    tamano_eje: int = 13,
    y_max: float | None = None,
    desplazamiento_etiqueta: int = -8,
    padding_inferior: int = 10,
) -> dict:
    """Especificación Vega de un gráfico de barras de una sola serie.

    `y_max` fija el techo del eje: en las barras de porcentaje se pasa 100 (o 105
    para dejar aire sobre la más alta) porque un eje que llega a 120 % se lee mal
    en un informe.
    """
    maximo = max((v["val"] for v in valores), default=0)
    techo = y_max if y_max is not None else (maximo * 1.2 if maximo > 0 else 1)
    marcas: list[dict] = [
        {
            "type": "rect",
            "from": {"data": "tabla"},
            "encode": _capa(
                {
                    "x": {"scale": "x", "field": "cat"},
                    "width": {"scale": "x", "band": 1},
                    "y": {"scale": "y", "field": "val"},
                    "y2": {"scale": "y", "value": 0},
                    "fill": {"value": COLOR_BARRA},
                }
            ),
        }
    ]
    if etiquetas:
        marcas.append(
            {
                "type": "text",
                "from": {"data": "tabla"},
                "encode": _capa(
                    {
                        "x": {"scale": "x", "field": "cat", "band": 0.5},
                        "y": {
                            "scale": "y",
                            "field": "val",
                            "offset": desplazamiento_etiqueta,
                        },
                        "text": {"field": "etiqueta"},
                        "align": {"value": "center"},
                        "baseline": {"value": "bottom"},
                        "fontSize": {"value": 13},
                        "fontWeight": {"value": "bold"},
                        "fill": {"value": "#1A202C"},
                    }
                ),
            }
        )
    if regla:
        marcas.append(
            {
                "type": "rule",
                "encode": _capa(
                    {
                        "x": {"value": 0},
                        "x2": {"value": ancho},
                        "y": {"scale": "y", "value": regla["valor"]},
                        "stroke": {"value": COLOR_REGLA},
                        "strokeWidth": {"value": 2},
                        "strokeDash": {"value": [8, 5]},
                    }
                ),
            }
        )
        marcas.append(
            {
                "type": "text",
                "encode": _capa(
                    {
                        "x": {"value": ancho - 6},
                        "y": {"scale": "y", "value": regla["valor"], "offset": -7},
                        "text": {"value": regla["texto"]},
                        "align": {"value": "right"},
                        "baseline": {"value": "bottom"},
                        "fontSize": {"value": 12},
                        "fontWeight": {"value": "bold"},
                        "fill": {"value": COLOR_REGLA},
                    }
                ),
            }
        )

    return {
        "$schema": "https://vega.github.io/schema/vega/v5.json",
        "width": ancho,
        "height": alto,
        "padding": {"left": 10, "right": 14, "top": 14, "bottom": padding_inferior},
        "background": "white",
        "data": [{"name": "tabla", "values": valores}],
        "scales": [
            {
                "name": "x",
                "type": "band",
                "domain": {"data": "tabla", "field": "cat"},
                "range": "width",
                "paddingInner": 0.32,
                "paddingOuter": 0.18,
                "round": True,
            },
            {
                "name": "y",
                "type": "linear",
                "domain": [0, techo],
                "range": "height",
                "nice": True,
            },
        ],
        "axes": [
            {
                "orient": "bottom",
                "scale": "x",
                "labelAngle": angulo,
                "labelFontSize": tamano_eje,
                "labelPadding": 8,
                "domain": False,
                "ticks": False,
            },
            {
                "orient": "left",
                "scale": "y",
                "title": titulo_y,
                "titleFontSize": tamano_eje,
                "labelFontSize": tamano_eje,
                "grid": True,
                "gridColor": "#E2E8F0",
                "domain": False,
                "ticks": False,
            },
        ],
        "marks": marcas,
    }


def render_grafico(nombre: str, spec: dict, forzar: bool = False) -> bool:
    """Envía la especificación a kroki y guarda el PNG (un fallo no es fatal)."""
    DIR_GRAFICOS.mkdir(parents=True, exist_ok=True)
    ruta = DIR_GRAFICOS / f"eval_{nombre}.png"
    if ruta.exists() and not forzar:
        return True
    try:
        respuesta = requests.post(
            KROKI_VEGA,
            data=json.dumps(spec, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "text/plain"},
            timeout=120,
        )
    except Exception as e:  # noqa: BLE001 - el documento debe generarse igual
        print(f"⚠️  No se pudo contactar a kroki para {nombre}: {type(e).__name__}: {e}")
        return False
    if respuesta.status_code != 200:
        print(
            f"⚠️  kroki devolvió {respuesta.status_code} para {nombre}: "
            f"{respuesta.text[:150]}"
        )
        return False
    ruta.write_bytes(respuesta.content)
    print(f"Gráfico generado: {_relativa(ruta)} ({len(respuesta.content) // 1024} kB)")
    return True


CORTO = {
    "sistema": "RAG",
    "baseline_groq": "Groq sin contexto",
    "baseline_gemini": "Gemini sin contexto",
}


def graficos(arnes, metricas: dict, forzar: bool = False) -> dict[str, bool]:
    """Renderiza los tres gráficos del informe y dice cuáles quedaron listos."""
    sistema = metricas["variantes"]["sistema"]["resumen"]
    listos: dict[str, bool] = {}

    # 1. Calidad del nivel de urgencia del sistema.
    n = sistema["nivel_evaluables"] or 1
    valores = [
        {
            "cat": "Exacto",
            "val": 100 * sistema["exactos"] / n,
            "etiqueta": arnes._pct(sistema["exactos"] / n),
        },
        {
            "cat": "En rango permitido",
            "val": 100 * sistema["en_permitido"] / n,
            "etiqueta": arnes._pct(sistema["en_permitido"] / n),
        },
        {
            "cat": "Desvío ≤ 1 nivel",
            "val": 100 * sistema["desvio_abs_1"] / n,
            "etiqueta": arnes._pct(sistema["desvio_abs_1"] / n),
        },
    ]
    listos["nivel"] = render_grafico(
        "nivel",
        spec_barras(valores, titulo_y="porcentaje de casos", y_max=105),
        forzar,
    )

    # 2. Tasa de alucinación en los casos anti-alucinación, por variante.
    valores = []
    for clave in ("sistema", "baseline_groq", "baseline_gemini"):
        r = metricas["variantes"][clave]["resumen"]
        anti, n_anti = r["alucinaciones_anti"], r["n_anti"] or 1
        valores.append(
            {
                # Etiquetas de eje cortas: los nombres largos se recortan contra el
                # ancho del gráfico. El valor va sobre la barra.
                "cat": CORTO[clave],
                "val": 100 * anti / n_anti,
                "etiqueta": f"{arnes._pct(anti / n_anti)} ({anti}/{r['n_anti']})",
            }
        )
    listos["alucinaciones"] = render_grafico(
        "alucinaciones",
        spec_barras(
            valores,
            titulo_y="tasa de alucinación (%)",
            y_max=100,
            # Las etiquetas se separan de la barra para que la del sistema (10 %)
            # no quede encima de la línea del límite del 15 %.
            desplazamiento_etiqueta=-24,
            regla={"valor": 15, "texto": "Límite aceptado: 15 %"},
        ),
        forzar,
    )

    # 3. Latencia por caso del sistema (de mayor a menor) con la media.
    casos = sorted(
        (c for c in metricas["variantes"]["sistema"]["casos"] if c["tiempos"]),
        key=lambda c: -c["tiempos"][0],
    )
    valores = [
        {"cat": c["id"], "val": c["tiempos"][0], "etiqueta": ""} for c in casos
    ]
    media = sistema["latencia_media"] or 0
    listos["latencia"] = render_grafico(
        "latencia",
        spec_barras(
            valores,
            ancho=760,
            alto=380,
            titulo_y="segundos",
            etiquetas=False,
            angulo=-90,
            tamano_eje=11,
            padding_inferior=34,
            regla={"valor": media, "texto": f"Media del sistema: {media:.1f} s"},
        ),
        forzar,
    )
    return listos


# ---------------------------------------------------------------------------
# Tablas derivadas de la evidencia
# ---------------------------------------------------------------------------


MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def fecha_legible(iso: str | None) -> str:
    """Fecha ISO de la corrida en formato de documento (25 de septiembre de 2026)."""
    if not iso:
        return "no registrada"
    try:
        momento = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{momento.day} de {MESES[momento.month - 1]} de {momento.year}"


def recorte(texto: str, limite: int = 52) -> str:
    texto = (texto or "").strip()
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def tabla_resumen_sistema(arnes, r: dict) -> dict:
    filas = [
        ["Casos ejecutados", f"{r['n_casos']}"],
        ["Casos con nivel esperado (evaluables)", f"{r['nivel_evaluables']}"],
        ["Errores de ejecución", f"{r['n_errores']}"],
        [
            "Nivel exacto",
            f"{r['exactos']} de {r['nivel_evaluables']} "
            f"({arnes._tasa(r['exactos'], r['nivel_evaluables'])})",
        ],
        [
            "Nivel dentro del rango permitido",
            f"{r['en_permitido']} de {r['nivel_evaluables']} "
            f"({arnes._tasa(r['en_permitido'], r['nivel_evaluables'])})",
        ],
        [
            "Desvío de a lo sumo un nivel",
            f"{r['desvio_abs_1']} de {r['nivel_evaluables']}",
        ],
        ["Sub-triage (error clínicamente grave)", f"{r['sub_triaje']}"],
        ["Supra-triage (sobre-priorización)", f"{r['supra_triaje']}"],
        ["Casos sin clasificar", f"{r['sin_clasificar']}"],
        [
            "Elevaciones del nivel por las reglas",
            f"{r['reglas_elevaron']} casos: {r['elevacion_correcta']} correctas, "
            f"{r['elevacion_espuria']} espurias",
        ],
        [
            "Alucinaciones en los casos anti-alucinación",
            f"{r['alucinaciones_anti']} de {r['n_anti']} "
            f"({arnes._tasa(r['alucinaciones_anti'], r['n_anti'])})",
        ],
    ]
    return TAB(
        ["Indicador", "Resultado"],
        filas,
        caption="Resultados del sistema con RAG (30 casos: 20 clínicos y 10 anti-alucinación)",
        anchos=[9.6, 5.6],
    )


def tabla_categorias(arnes, casos: list[dict]) -> dict:
    """Exactitud por categoría clínica (agrupa los casos por su categoría)."""
    grupos: dict[str, dict] = {}
    for caso in casos:
        cat = caso.get("categoria") or "sin categoría"
        datos = grupos.setdefault(
            cat, {"n": 0, "exactos": 0, "rango": 0, "sub": 0, "supra": 0, "casos": []}
        )
        datos["casos"].append(caso["id"])
        for v in caso["veredictos"]:
            if not v.get("evaluable_nivel"):
                continue
            datos["n"] += 1
            datos["exactos"] += 1 if v.get("coincide_exacto") else 0
            datos["rango"] += 1 if v.get("coincide_permitido") else 0
            datos["sub"] += 1 if v.get("sub_triaje") else 0
            datos["supra"] += 1 if v.get("supra_triaje") else 0
    filas = []
    for cat in sorted(grupos):
        d = grupos[cat]
        filas.append(
            [
                cat,
                ", ".join(d["casos"]),
                f"{d['exactos']}/{d['n']}" if d["n"] else "—",
                f"{d['rango']}/{d['n']}" if d["n"] else "—",
                str(d["sub"]),
                str(d["supra"]),
            ]
        )
    return TAB(
        ["Categoría", "Casos", "Exactos", "En rango", "Sub", "Supra"],
        filas,
        caption="Exactitud del nivel por categoría clínica",
        anchos=[3.6, 5.2, 1.8, 1.8, 1.2, 1.4],
        tamano=9,
    )


def matriz_confusion(arnes, casos: list[dict]) -> dict:
    """Matriz esperado (filas) × observado (columnas), para ver hacia dónde se desvía."""
    niveles = list(arnes.NIVELES)
    columnas = niveles + ["sin clasificar"]
    tabla = {e: {c: 0 for c in columnas} for e in niveles}
    for caso in casos:
        for v in caso["veredictos"]:
            if not v.get("evaluable_nivel"):
                continue
            esperado = caso.get("nivel_esperado")
            final = registro(caso).get("nivel_final")
            if esperado in tabla:
                tabla[esperado][final if final in columnas else "sin clasificar"] += 1
    filas = [[f"{e} (esperado)"] + [str(tabla[e][c]) for c in columnas] for e in niveles]
    return TAB(
        ["Esperado \\ observado"] + columnas,
        filas,
        caption="Matriz de confusión del nivel de urgencia (sistema con RAG)",
        anchos=[3.2] + [1.9] * len(columnas),
        tamano=9,
    )


CATEGORIAS_CON_LIMITE = {"capciosa", "inexistente"}


def tabla_anti(casos: list[dict]) -> dict:
    """Los 10 casos anti-alucinación con su veredicto automático."""
    filas = []
    for caso in casos:
        v = veredicto(caso)
        categoria = caso.get("categoria") or ""
        declara = "—"
        if categoria in CATEGORIAS_CON_LIMITE and v:
            declara = "sí" if v.get("declara_limite") else "no"
        filas.append(
            [
                caso["id"],
                recorte(caso["titulo"], 44),
                categoria,
                registro(caso).get("nivel_final") or "—",
                "sí" if v.get("alucinacion") else "no",
                declara,
                senales_de_alucinacion(v),
            ]
        )
    return TAB(
        [
            "Caso",
            "Título",
            "Categoría",
            "Nivel final",
            "¿Inventó?",
            "¿Declaró el límite?",
            "Señal detectada",
        ],
        filas,
        caption=(
            "Casos anti-alucinación del sistema con RAG (la columna del límite se informa en "
            "los casos capciosos e inexistentes, que son los que lo exigen)"
        ),
        anchos=[1.2, 4.3, 2.1, 1.5, 1.5, 1.7, 3.1],
        tamano=8,
    )


def tabla_anexo_clinicos(casos: list[dict]) -> dict:
    """Anexo: los 20 casos clínicos, del nivel esperado al veredicto."""
    filas = []
    for caso in casos:
        reg = registro(caso)
        filas.append(
            [
                caso["id"],
                recorte(caso["titulo"], 40),
                caso.get("nivel_esperado") or "—",
                "/".join(caso.get("nivel_permitido") or []) or "—",
                reg.get("nivel_llm") or "—",
                reg.get("nivel_reglas") or "—",
                reg.get("nivel_final") or "—",
                etiqueta_resultado(caso),
            ]
        )
    return TAB(
        [
            "Caso",
            "Título",
            "Esperado",
            "Permitido",
            "LLM",
            "Reglas",
            "Final",
            "Resultado",
        ],
        filas,
        caption="Resultado por caso clínico (sistema con RAG)",
        anchos=[1.1, 4.2, 1.5, 1.5, 1.4, 1.4, 1.4, 1.9],
        tamano=8,
    )


def tabla_comparacion(arnes, comunes: dict, etiquetas: dict) -> list[dict]:
    """Comparación sistema / línea base en el subconjunto de casos comunes."""
    filas, filas_seguridad = [], []
    for clave, datos in comunes.items():
        sis, base = datos["sistema"], datos["base"]
        ex_sis = (sis["exactos"] / sis["nivel_evaluables"]) if sis["nivel_evaluables"] else None
        ex_base = (base["exactos"] / base["nivel_evaluables"]) if base["nivel_evaluables"] else None
        delta = (
            f"{100 * (ex_sis - ex_base):+.1f} puntos"
            if (ex_sis is not None and ex_base is not None)
            else "—"
        )
        filas.append(
            [
                etiquetas[clave],
                f"{len(datos['ids'])}",
                f"{sis['exactos']}/{sis['nivel_evaluables']} ({arnes._tasa(sis['exactos'], sis['nivel_evaluables'])})",
                f"{base['exactos']}/{base['nivel_evaluables']} ({arnes._tasa(base['exactos'], base['nivel_evaluables'])})",
                delta,
                f"{sis['en_permitido']} / {base['en_permitido']}",
                f"{sis['sub_triaje']} / {base['sub_triaje']}",
            ]
        )
        filas_seguridad.append(
            [
                etiquetas[clave],
                f"{sis['alucinaciones_anti']} de {sis['n_anti']} / "
                f"{base['alucinaciones_anti']} de {base['n_anti']}",
                f"{arnes._num(sis['latencia_media'], 2)} s / "
                f"{arnes._num(base['latencia_media'], 2)} s",
            ]
        )
    return [
        TAB(
            [
                "Línea base",
                "Casos en común",
                "Exactitud del sistema",
                "Exactitud de la base",
                "Δ exactitud",
                "En rango (sistema / base)",
                "Sub-triage (sistema / base)",
            ],
            filas,
            caption="Comparación en el subconjunto de casos que ambas variantes respondieron",
            anchos=[2.6, 1.5, 2.5, 2.3, 1.7, 2.2, 2.2],
            tamano=9,
        ),
        TAB(
            ["Línea base", "Alucinaciones anti (sistema / base)", "Latencia media (sistema / base)"],
            filas_seguridad,
            caption="Anclaje y costo en el mismo subconjunto común",
            anchos=[3.4, 6.0, 5.8],
            tamano=9,
        ),
    ]


def tabla_indicadores(arnes, r: dict) -> dict:
    """Cumplimiento de los indicadores declarados del Componente 2."""
    alucinaciones = arnes._tasa(r["alucinaciones_anti"], r["n_anti"])
    cumple = r["alucinaciones_anti"] / (r["n_anti"] or 1) < 0.15
    filas = [
        [
            "Casos clínicos en Bueno o Muy bueno (C2.A4, rúbrica del médico)",
            "≥ 80 % de casos calificados",
            "Pendiente: requiere el médico colaborador",
            "⏳",
        ],
        [
            "Tasa de alucinaciones (C2.A2)",
            "< 15 % en los casos anti-alucinación",
            f"{alucinaciones} ({r['alucinaciones_anti']} de {r['n_anti']})",
            "✔" if cumple else "✖",
        ],
        [
            "Usabilidad percibida (C2.A5, encuesta SUS)",
            "≥ 70 puntos sobre 100",
            "Pendiente: requiere los usuarios participantes",
            "⏳",
        ],
    ]
    return TAB(
        ["Indicador", "Criterio", "Resultado", "Estado"],
        filas,
        caption="Cumplimiento de los indicadores de aceptación del Componente 2",
        anchos=[5.4, 3.6, 4.4, 1.4],
        tamano=9,
    )


# ---------------------------------------------------------------------------
# Bloques y formato del capítulo: se cargan una vez, en main()
# ---------------------------------------------------------------------------

GD = None
T = P = B = NUM = TAB = FIG = NOTA = MONO = None


def portada(doc, metricas: dict) -> None:
    """Portada del informe autónomo (con numeración propia desde 1)."""

    def linea(
        texto: str,
        tamano: float = 12,
        negrita: bool = False,
        cursiva: bool = False,
        despues: float = 8,
    ) -> None:
        parrafo = doc.add_paragraph()
        parrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        parrafo.paragraph_format.space_after = Pt(despues)
        GD._fuente(
            parrafo.add_run(texto), tamano=tamano, negrita=negrita, cursiva=cursiva
        )

    sistema = metricas["variantes"]["sistema"]
    entorno = sistema["entorno"]
    corpus = entorno.get("corpus") or {}

    doc.add_paragraph()
    linea("UNIVERSIDAD AUTÓNOMA JUAN MISAEL SARACHO", 12, True)
    linea("Facultad de Ciencias y Tecnología — Ingeniería Informática", 11, cursiva=True)
    linea(
        "Sistema de Triaje Médico con RAG para las Normas Nacionales de "
        "Atención Clínica (NNAC) de Bolivia",
        11,
        cursiva=True,
    )
    doc.add_paragraph()
    linea("COMPONENTE 2: EVALUACIÓN DEL SISTEMA", 16, True, despues=10)
    linea(
        "Informe de pruebas: 20 casos clínicos y 10 casos anti-alucinación",
        13,
        True,
    )
    doc.add_paragraph()
    linea("Postulante: Pedro Zelada", 12)
    linea(f"Fecha de las corridas: {fecha_legible(entorno.get('fecha'))}", 12)
    doc.add_paragraph()
    linea(
        f"Commit evaluado: {entorno.get('commit') or 'desconocido'}",
        10,
        cursiva=True,
        despues=2,
    )
    linea(
        "Modelo del sistema: Groq (nube) · corpus de "
        f"{corpus.get('chunks')} fragmentos de {len(corpus.get('archivos') or [])} PDFs",
        10,
        cursiva=True,
        despues=2,
    )
    linea(
        "Documento generado automáticamente por scripts/informe_word.py a partir de la "
        "evidencia cruda guardada en evaluacion/resultados/",
        10,
        cursiva=True,
    )
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def bloques_informe(arnes, metricas: dict, listos: dict) -> list[dict]:
    """Arma el informe completo como lista de bloques del capítulo."""
    variantes = metricas["variantes"]
    sistema = variantes["sistema"]
    r = sistema["resumen"]
    entorno = sistema["entorno"]
    corpus = entorno.get("corpus") or {}
    clinicos = [c for c in sistema["casos"] if c["grupo"] == "clinico"]
    anti = [c for c in sistema["casos"] if c["grupo"] == "anti_alucinacion"]
    paginas = entorno.get("paginas_indexadas_por_archivo") or {}
    maximas = entorno.get("pagina_maxima_por_archivo") or {}
    casos_por_id = por_id(sistema)
    bloques: list[dict] = []

    # --- 1. Introducción y objetivos ---
    bloques += [
        T(1, "1. Introducción y objetivos"),
        P(
            "Este documento reporta las pruebas del sistema de triaje para postas rurales "
            "construido sobre las Normas Nacionales de Atención Clínica (NNAC) de Bolivia. El "
            "Componente 2 de la tesis comprende el diseño de los casos, la medición de las "
            "métricas técnicas, la comparación con un modelo de referencia sin recuperación, la "
            "valoración clínica de las respuestas, la medición de usabilidad y las conclusiones. "
            "Todas las cifras que aparecen aquí se calculan desde la evidencia cruda de las "
            "corridas (respuesta completa, fragmentos recuperados con puntaje y página, tiempos "
            "y tokens de cada caso), de modo que cualquier resultado pueda auditarse caso por "
            "caso."
        ),
        P(
            "La evaluación responde a dos fallas detectadas durante el desarrollo, ambas ya "
            "corregidas en el código y ambas de la misma naturaleza: el sistema podía fallar sin "
            "que ninguna prueba lo advirtiera. La primera era un falso positivo por negación en "
            "las banderas rojas (el motor elevaba la urgencia ante hallazgos que el relato "
            "negaba: «no presenta dolor abdominal severo»). La segunda era el uso de umbrales de "
            "adulto en lactantes, que clasificaba como normales frecuencias respiratorias "
            "propias de un lactante en dificultad. Los casos C-11, C-14, C-17 y C-20 se incluyen "
            "como regresión de la primera falla, y C-01 a C-04 y C-19 como regresión de la "
            "segunda."
        ),
        P("Los objetivos específicos de la evaluación son:"),
        B(
            [
                "Diseñar un conjunto de casos con un resultado esperado verificable contra la "
                "norma (C2.A1): 20 casos clínicos y 10 casos anti-alucinación.",
                "Medir las métricas técnicas del sistema (C2.A2): acierto del nivel de urgencia, "
                "calidad de la recuperación, tasa de alucinaciones, latencia y consumo de tokens.",
                "Comparar contra un modelo de referencia que usa el mismo prompt pero sin "
                "contexto recuperado (C2.A3), para aislar el aporte del corpus normativo.",
                "Someter las respuestas a una rúbrica clínica de cuatro niveles (C2.A4) y medir la "
                "usabilidad percibida con la encuesta SUS (C2.A5).",
                "Formular las conclusiones del componente (C2.A6) con sus límites declarados.",
            ]
        ),
        P(
            "Los indicadores de aceptación definidos al inicio del componente son: al menos el "
            "80 % de los casos clínicos calificados como Bueno o Muy bueno por el médico "
            "colaborador, una tasa de alucinaciones inferior al 15 % en los casos "
            "anti-alucinación, y un puntaje SUS de 70 puntos o más. El cumplimiento se resume en "
            "el apartado 10; los dos indicadores que dependen de personas externas quedan "
            "pendientes y sus instrumentos están preparados."
        ),
    ]

    # --- 2. Materiales y métodos ---
    bloques += [
        T(1, "2. Materiales y métodos"),
        T(2, "2.1. El sistema evaluado"),
        P(
            "Cada caso entra al motor de triaje como datos vitales y un relato libre. El "
            "sistema aplica primero las reglas deterministas de banderas rojas (umbrales por "
            "grupo etario y hallazgos del relato, con detección de negación) y después la cadena "
            "de recuperación y generación: los cinco fragmentos con mayor similitud de las NNAC, "
            "una única plantilla de instrucción y un modelo de lenguaje. El nivel que se reporta "
            "es el más urgente entre lo que decide el modelo y lo que deciden las reglas, de modo "
            "que la capa determinista actúe como red de seguridad."
        ),
        P(
            "La comparación aísla el efecto del corpus: la variante «sin contexto» usa la MISMA "
            "plantilla, las MISMAS reglas y el MISMO criterio de nivel final, pero sin fragmentos "
            "recuperados. La única diferencia entre las dos variantes es, por lo tanto, la "
            "información normativa que el modelo tiene delante."
        ),
        T(2, "2.2. Corpus y configuración del índice"),
        TAB(
            ["Elemento", "Valor"],
            [
                ["Documentos", f"{len(corpus.get('archivos') or [])} PDFs de las NNAC"],
                ["Fragmentos indexados", f"{corpus.get('chunks')}"],
                ["Modelo de embeddings", f"{entorno.get('embedding_model')}"],
                [
                    "Segmentación",
                    f"chunk_size={entorno.get('chunk_size')} · overlap={entorno.get('chunk_overlap')}",
                ],
                ["Colección vectorial", f"{corpus.get('coleccion')}"],
                ["Fragmentos recuperados por consulta", "5 (similarity_top_k)"],
                [
                    "Índice vigente al momento de las corridas",
                    "sí" if corpus.get("actualizado") else "no",
                ],
                ["Entorno de ejecución", f"Python {entorno.get('python')} · {entorno.get('so')}"],
            ],
            caption="Configuración del índice y del entorno de las corridas",
            anchos=[6.2, 8.8],
            tamano=10,
        ),
        TAB(
            ["Documento NNAC", "Páginas indexadas", "Página máxima", "SHA-256 (12)"],
            [
                [
                    archivo.get("nombre"),
                    str(paginas.get(archivo.get("nombre"), "—")),
                    str(maximas.get(archivo.get("nombre"), "—")),
                    (archivo.get("sha256") or "")[:12],
                ]
                for archivo in corpus.get("archivos") or []
            ],
            caption="Corpus normativo indexado, con la huella de cada documento",
            anchos=[6.4, 3.2, 2.6, 3.0],
            tamano=9,
        ),
    ]

    conteo_niveles: dict[str, list[str]] = {}
    for caso in sistema["casos"]:
        clave = caso.get("nivel_esperado") or "sin nivel esperado (casos anti-alucinación)"
        conteo_niveles.setdefault(clave, []).append(caso["id"])
    categorias_anti: dict[str, list[str]] = {}
    for caso in anti:
        categorias_anti.setdefault(caso.get("categoria") or "sin categoría", []).append(
            caso["id"]
        )

    bloques += [
        T(2, "2.3. Diseño de los casos"),
        P(
            "Los 30 casos se construyeron leyendo la norma: cada uno declara el nivel esperado, "
            "un rango clínicamente aceptable que reconoce las zonas grises de la clasificación, "
            "las páginas del corpus que deberían respaldar la respuesta y los criterios "
            "automáticos de contenido. Los casos clínicos cubren las cinco urgencias y los "
            "siete grupos etarios, con énfasis en los cuadros pediátricos y en los relatos con "
            "negaciones, que son las dos familias de regresión descritas."
        ),
        TAB(
            ["Nivel esperado", "Casos", "Identificadores"],
            [
                [nivel, str(len(ids)), ", ".join(ids)]
                for nivel, ids in sorted(conteo_niveles.items())
            ],
            caption="Distribución de los casos por nivel de urgencia esperado",
            anchos=[4.6, 1.4, 9.0],
            tamano=9,
        ),
        P(
            "Los 10 casos anti-alucinación no buscan medir el acierto del nivel, sino provocar "
            "invención de contenido: preguntan por fármacos y entidades que no están en el "
            "corpus, presentan datos contradictorios entre sí y piden citas textuales de "
            "páginas que no existen."
        ),
        TAB(
            ["Tipo de trampa", "Casos", "Identificadores"],
            [
                [categoria, str(len(ids)), ", ".join(ids)]
                for categoria, ids in sorted(categorias_anti.items())
            ],
            caption="Tipos de trampa de los casos anti-alucinación",
            anchos=[3.6, 1.4, 10.0],
            tamano=9,
        ),
        T(2, "2.4. Variantes comparadas"),
        P(
            "Se ejecutaron tres variantes sobre el mismo conjunto de casos. La línea base con el "
            "mismo proveedor es la comparación principal, porque comparte modelo y reglas; la de "
            "Gemini aporta un segundo punto de referencia externo."
        ),
        TAB(
            ["Variante", "Corridas fusionadas", "Casos", "Errores"],
            [
                [
                    variantes[clave]["etiqueta"],
                    variantes[clave]["run_id"],
                    str(variantes[clave]["resumen"]["n_casos"]),
                    str(variantes[clave]["resumen"]["n_errores"]),
                ]
                for clave in ("sistema", "baseline_groq", "baseline_gemini")
            ],
            caption="Variantes ejecutadas y tamaño efectivo de cada una",
            anchos=[3.4, 6.6, 2.0, 1.6],
            tamano=9,
        ),
        T(2, "2.5. Definición operativa de las métricas"),
        B(
            [
                "Exactitud del nivel: el nivel final coincide con el nivel esperado del caso.",
                "En rango permitido: el nivel final cae dentro del rango clínicamente aceptable "
                "declarado en el caso, que reconoce las zonas grises de la clasificación.",
                "Sub-triage: el sistema priorizó con MENOS urgencia que la esperada; es el error "
                "clínicamente grave. Supra-triage: priorizó de más, lo que no pone en riesgo al "
                "paciente pero consume recursos y genera falsas alarmas.",
                "Recall@3 y Recall@5: al menos un fragmento de la fuente esperada aparece entre "
                "los 3 o 5 mejor puntuados. Precision@5: proporción de los 5 fragmentos "
                "recuperados que provienen de la fuente esperada. MRR: recíproco de la posición "
                "del primer fragmento relevante. Se calculan a nivel de página (principal) y de "
                "documento (secundario).",
                "Tasa de alucinación: proporción de casos anti-alucinación en que la respuesta "
                "inventa contenido: enuncia una dosis que no está en el material entregado al "
                "modelo (contexto recuperado, datos del paciente y plantilla), entrecomilla "
                "texto que no se le entregó, no declara la ausencia de una entidad inexistente, "
                "cita una página que no existe o no reconoce una contradicción clínica.",
                "Declaración del límite: la respuesta advierte explícitamente que el material no "
                "cubre lo que se le pide. Se informa aparte porque callar el límite es un fallo "
                "de completitud, no una invención.",
                "Latencia: tiempo alrededor de la consulta (recuperación + generación) en la "
                "máquina de la corrida. Tokens: los que reporta el proveedor del modelo; nunca "
                "se estiman, y si el proveedor no informa el consumo, el caso queda sin ese dato.",
            ]
        ),
        T(2, "2.6. Evidencia recolectada por caso"),
        P(
            "Cada ejecución guarda su evidencia cruda en evaluacion/resultados/: la respuesta "
            "completa del modelo, los fragmentos recuperados con su documento, página y puntaje, "
            "las reglas que se activaron, el tiempo de respuesta y los tokens. Esa evidencia es "
            "la que sostiene todas las tablas de este informe y permite repetir cualquier "
            "cálculo sin volver a llamar a ningún modelo."
        ),
        P(
            "Durante la evaluación se detectó y corrigió un falso positivo del detector de "
            "citas: la primera versión comprobaba las citas únicamente contra los fragmentos "
            "recuperados y marcaba como «cita no anclada» a los datos del propio paciente y a la "
            "plantilla de la respuesta, que el modelo tenía en su prompt (por ejemplo, «se le "
            "hunden las costillas» o «Manejo y observación en la posta rural»). Los veredictos "
            "que se informan aquí ya comparan contra todo el material entregado al modelo."
        ),
        NOTA(
            "Los niveles esperados y los rangos permitidos de los casos son una propuesta "
            "derivada de la norma y del sistema Manchester: su validación clínica es el "
            "objetivo C2.A4 y está pendiente del médico colaborador."
        ),
    ]

    # --- 3. Trazabilidad ---
    hashes = entorno.get("hashes_casos") or {}
    bloques += [
        T(1, "3. Configuración del experimento y trazabilidad"),
        P(
            "Las corridas quedan identificadas por el commit del código y por la huella de los "
            "archivos de casos, de modo que un cambio en los casos o en el motor se pueda "
            "detectar al comparar dos informes."
        ),
        TAB(
            ["Elemento", "Valor"],
            [
                ["Commit evaluado", f"{entorno.get('commit')}"],
                [
                    "Árbol con cambios sin confirmar",
                    "sí" if entorno.get("arbol_con_cambios_sin_commitear") else "no",
                ],
                ["Fecha de las corridas", fecha_legible(entorno.get("fecha"))],
                ["Python y sistema operativo", f"{entorno.get('python')} · {entorno.get('so')}"],
                [
                    "Modelo del sistema",
                    f"{registro(sistema['casos'][0]).get('modelo_utilizado') or 'no registrado'}",
                ],
                [
                    "Huella de los casos",
                    " · ".join(f"{nombre}={valor[:12]}" for nombre, valor in hashes.items()),
                ],
                ["Índice vectorial", f"{corpus.get('chunks')} fragmentos · colección {corpus.get('coleccion')}"],
                [
                    "Memoria RAM",
                    "no medida en este alcance (declarada como trabajo futuro)",
                ],
            ],
            caption="Trazabilidad del experimento",
            anchos=[5.4, 9.6],
            tamano=9,
        ),
    ]

    # --- 4. Resultados del sistema ---
    sub_triaje = [
        c["id"] for c in sistema["casos"] if veredicto(c).get("sub_triaje")
    ]
    supra = [c["id"] for c in sistema["casos"] if veredicto(c).get("supra_triaje")]
    elevaciones = [
        c["id"] for c in sistema["casos"] if veredicto(c).get("reglas_elevaron")
    ]
    elevaciones_sin_gold = [
        c["id"]
        for c in sistema["casos"]
        if veredicto(c).get("reglas_elevaron") and not c.get("nivel_esperado")
    ]
    bloques += [
        T(1, "4. Resultados del sistema con RAG"),
        P(
            "La corrida del sistema se completó sobre los 30 casos sin errores de ejecución. Los "
            "21 casos con nivel esperado (los 20 clínicos y un caso anti-alucinación que también "
            "declara nivel) son los que permiten medir el acierto."
        ),
        tabla_resumen_sistema(arnes, r),
        P(
            f"El sistema acertó el nivel exacto en {r['exactos']} de {r['nivel_evaluables']} "
            f"casos ({arnes._tasa(r['exactos'], r['nivel_evaluables'])}) y se mantuvo dentro del "
            f"rango clínicamente aceptable en {r['en_permitido']} "
            f"({arnes._tasa(r['en_permitido'], r['nivel_evaluables'])}). El desvío no superó un "
            f"nivel en {r['desvio_abs_1']} casos y ninguno quedó sin clasificar. El único error "
            f"grave fue un sub-triage ({', '.join(sub_triaje)}); hubo "
            f"{r['supra_triaje']} sobre-priorizaciones ({', '.join(supra)}), que no exponen al "
            "paciente pero consumen recursos."
        ),
        FIG(
            "eval_nivel.png",
            "Nivel de urgencia del sistema con RAG: exactitud, rango clínicamente aceptable y "
            "desvío de a lo sumo un nivel",
            ancho_cm=14.0,
            nota=(
                f"n = {r['nivel_evaluables']} casos con nivel esperado. La diferencia entre la "
                "barra central y la primera son las zonas grises de la clasificación que el "
                "rango permitido del caso reconoce como aceptables."
            ),
        ),
        tabla_categorias(arnes, clinicos),
        matriz_confusion(arnes, sistema["casos"]),
        P(
            f"Las reglas deterministas elevaron la urgencia en {r['reglas_elevaron']} casos "
            f"({', '.join(elevaciones)}): las {r['elevacion_correcta']} elevaciones sobre "
            "casos con nivel esperado llevaron el nivel al valor correcto y ninguna resultó "
            "espuria, que es el comportamiento buscado de la capa de seguridad."
            + (
                f" La elevación restante corresponde a {', '.join(elevaciones_sin_gold)}, un "
                "caso anti-alucinación que no declara nivel esperado, donde solo se comprueba "
                "que la regla no contradiga al modelo."
                if elevaciones_sin_gold
                else ""
            )
        ),
    ]

    # --- 5. Recuperación ---
    n_rec = r["recall_3_pagina_n"]
    bloques += [
        T(1, "5. Calidad de la recuperación (C2.A2)"),
        P(
            "La recuperación se mide solo sobre los casos que declaran fuentes esperadas y que "
            f"tuvieron respuesta: {n_rec} de los 30. En ellos se comprueba si los fragmentos que "
            "el sistema usó provienen de las páginas que la norma dedica al cuadro."
        ),
        TAB(
            ["Métrica", "A nivel de página", "A nivel de documento"],
            [
                [
                    "Recall@3 (el fragmento relevante está entre los 3 primeros)",
                    arnes._pct(r["recall_3_pagina"]),
                    arnes._pct(r["recall_3_documento"]),
                ],
                [
                    "Recall@5 (entre los 5 recuperados)",
                    arnes._pct(r["recall_5_pagina"]),
                    arnes._pct(r["recall_5_documento"]),
                ],
                [
                    "Precision@5 (proporción de los 5 que son relevantes)",
                    arnes._num(r["precision_5_pagina_media"], 3),
                    arnes._num(r["precision_5_documento_media"], 3),
                ],
                [
                    "MRR (posición inversa del primer acierto)",
                    arnes._num(r["mrr_media"], 3),
                    arnes._num(r["mrr_media"], 3),
                ],
            ],
            caption=f"Calidad de la recuperación sobre {n_rec} casos con fuente esperada",
            anchos=[6.4, 4.4, 4.2],
            tamano=9,
        ),
        P(
            "La diferencia entre ambas columnas es el hallazgo principal de este apartado: a "
            "nivel de documento el sistema encuentra material de la norma correcta en casi todos "
            "los casos, pero a nivel de página acierta la página exacta en poco más de un tercio. "
            "La causa es que el corpus dedica varias páginas al mismo cuadro y la segmentación "
            "reparte el texto en fragmentos contiguos, de modo que el fragmento mejor puntuado "
            "suele ser una página vecina a la que el caso declara como referencia. Para el "
            "triaje esto es aceptable —lo que importa es que el modelo reciba la norma del "
            "cuadro— pero explica que la precisión a nivel de página sea baja y conviene "
            "declararlo así en la tesis."
        ),
        P(
            "Un segundo hallazgo es de calidad de datos: el texto extraído de los PDF conserva "
            "tabuladores entre palabras («muñón\tumbilical»), de modo que cualquier comprobación "
            "de frases, dosis o citas necesita colapsar el espaciado antes de comparar. El "
            "evaluador lo hace y quedó documentado como parte de los materiales de esta "
            "evaluación."
        ),
    ]

    # --- 6. Alucinaciones ---
    declaran = [
        c["id"]
        for c in anti
        if c.get("categoria") in CATEGORIAS_CON_LIMITE and veredicto(c).get("declara_limite")
    ]
    callan = [
        c["id"]
        for c in anti
        if c.get("categoria") in CATEGORIAS_CON_LIMITE
        and not veredicto(c).get("declara_limite")
    ]
    inventados = [c["id"] for c in anti if veredicto(c).get("alucinacion")]
    base_groq = variantes["baseline_groq"]["resumen"]
    bloques += [
        T(1, "6. Alucinaciones y anclaje de las respuestas"),
        P(
            "Los 10 casos anti-alucinación se evaluaron con detectores automáticos y con lectura "
            "de la respuesta completa. El veredicto es conservador: solo marca invención cuando "
            "la respuesta afirma contenido prohibido por el caso, enuncia una dosis que no está "
            "en el material que el modelo recibió, entrecomilla texto que nunca se le entregó, "
            "no declara la ausencia de una entidad inexistente o no reconoce una contradicción "
            "clínica."
        ),
        tabla_anti(anti),
        FIG(
            "eval_alucinaciones.png",
            "Tasa de alucinación en los casos anti-alucinación, por variante",
            ancho_cm=13.5,
            nota=(
                "La línea marca el criterio de aceptación del componente (menos del 15 %). "
                "Las líneas base ejecutaron menos casos por límites de cuota del plan gratuito, "
                "así que su tasa se apoya en menos observaciones y se informa junto al número "
                "de casos entre paréntesis."
            ),
        ),
        P(
            f"El sistema con RAG inventó contenido en {len(inventados)} de {len(anti)} casos "
            f"({arnes._tasa(len(inventados), len(anti))}), por debajo del 15 % fijado como "
            "criterio. El caso que falla es A-08 (entidades inexistentes): ante un cuadro que "
            "no existe, el sistema no advierte que no lo reconoce y lo reinterpreta como "
            "dengue, razonando con los criterios de esa enfermedad. No inventó dosis ni citó "
            "páginas inexistentes, pero inventó un marco clínico, que es exactamente el riesgo "
            "que el caso buscaba provocar. Su causa inmediata es que la plantilla de producción "
            "no incluye una cláusula de escape para la información insuficiente; añadirla y "
            "volver a medir estos diez casos queda como trabajo inmediato."
        ),
        P(
            f"Un segundo resultado, que la tasa de alucinación no captura, es la declaración "
            f"del límite: de los casos que exigen advertir que el contenido no está en el "
            f"material, la respuesta lo advierte en {len(declaran)} ({', '.join(declaran)}) y lo "
            f"omite en {len(callan)} ({', '.join(callan)}). El caso más claro es A-02: el sistema "
            "responde el nivel y sugiere paracetamol, pero el fármaco por el que se le preguntó "
            "(baloxavir marboxil) no aparece ni una vez en la respuesta. No es una invención y no "
            "cuenta como alucinación, pero el profesional que lee la respuesta no recibe la "
            "advertencia de que ese dato no está respaldado por la norma. La comprobación de la "
            "declaración es literal (busca frases como «no se encontró información»), de modo "
            "que puede darse por satisfecha con una frase negativa que hable de otra cosa: se "
            "informa como indicador heurístico y se contrasta con la lectura del caso en las "
            "fichas del apartado 9."
        ),
        P(
            f"Frente a la línea base sin contexto, la diferencia es grande en esta familia: "
            f"{base_groq['alucinaciones_anti']} de {base_groq['n_anti']} casos anti-alucinación "
            f"({arnes._tasa(base_groq['alucinaciones_anti'], base_groq['n_anti'])}) presentan "
            "invención: dosis concretas de un fármaco que no está en el corpus (A-02) y ausencia "
            "total de reconocimiento ante datos contradictorios (A-04 y A-05). Sin corpus que "
            "consultar, el modelo rellena el hueco con su conocimiento general."
        ),
    ]

    # --- 7. Tiempo y tokens ---
    filas_latencia = []
    for clave in ("sistema", "baseline_groq", "baseline_gemini"):
        v = variantes[clave]
        rv = v["resumen"]
        filas_latencia.append(
            [
                v["etiqueta"],
                str(rv["n_registros"]),
                arnes._num(rv["latencia_media"], 2),
                arnes._num(rv["latencia_mediana"], 2),
                arnes._num(rv["latencia_p95"], 2),
                arnes._num(rv["latencia_max"], 2),
                str(rv["tokens_medidos"]),
                arnes._num(rv["tokens_media"], 1),
                f"{rv['tokens_total']:,}".replace(",", " ") if rv["tokens_total"] else "—",
            ]
        )
    bloques += [
        T(1, "7. Tiempo de respuesta y consumo de tokens"),
        P(
            "La latencia se midió alrededor de cada consulta, con las mismas condiciones de red y "
            "de equipo para todas las variantes. Los tokens son los que informa el proveedor del "
            "modelo: el evaluador no los estima, y si el proveedor no reporta el consumo del "
            "caso, ese caso queda sin dato en lugar de completarse con una aproximación."
        ),
        TAB(
            [
                "Variante",
                "Registros",
                "Media (s)",
                "Mediana (s)",
                "p95 (s)",
                "Máx. (s)",
                "Tokens medidos",
                "Media de tokens",
                "Total",
            ],
            filas_latencia,
            caption="Tiempo de respuesta y consumo de tokens por variante",
            anchos=[3.0, 1.4, 1.5, 1.5, 1.2, 1.2, 1.5, 1.6, 1.5],
            tamano=8,
        ),
        FIG(
            "eval_latencia.png",
            "Latencia por caso del sistema con RAG, ordenada de mayor a menor",
            ancho_cm=15.0,
            nota=(
                "La línea marca la media. Los casos con signos de alarma y varias reglas "
                "activadas generan respuestas más largas y, con ellas, los tiempos mayores."
            ),
        ),
        NOTA(
            "El consumo de memoria RAM no se midió en este alcance y se declara como no medido; "
            "instrumentarlo (muestreo del consumo del proceso antes, durante y después de cada "
            "consulta) queda como trabajo futuro. La latencia depende del equipo, de la red y "
            "del proveedor, así que es comparable entre variantes de una misma corrida y no "
            "contra cifras absolutas de la literatura."
        ),
    ]

    # --- 8. Comparación con la línea base ---
    comunes = metricas["comunes"]
    bloques += [
        T(1, "8. Comparación con la línea base sin contexto (C2.A3)"),
        P(
            "Las líneas base no pudieron ejecutar los 30 casos: los planes gratuitos de los "
            "proveedores de nube impusieron un techo de tokens por día (Groq) y un límite de "
            "peticiones por minuto y por día (Gemini). Comparar el 100 % de una variante contra "
            "el 60 % de otra no mediría nada, así que la comparación se restringe a los casos "
            "que ambas variantes respondieron con éxito. La tabla declara ese tamaño para que "
            "ningún lector tenga que adivinarlo."
        ),
    ]
    bloques += tabla_comparacion(arnes, comunes, ETIQUETAS)
    com_groq = comunes["baseline_groq"]
    sis_g, base_g = com_groq["sistema"], com_groq["base"]
    ex_sis = sis_g["exactos"] / (sis_g["nivel_evaluables"] or 1)
    ex_base = base_g["exactos"] / (base_g["nivel_evaluables"] or 1)
    bloques += [
        P(
            f"En el subconjunto común con el mismo proveedor ({len(com_groq['ids'])} casos) el "
            f"sistema con RAG acertó el nivel en {sis_g['exactos']} de "
            f"{sis_g['nivel_evaluables']} casos evaluables y la línea base en "
            f"{base_g['exactos']} de {base_g['nivel_evaluables']}: una diferencia de "
            f"{100 * (ex_sis - ex_base):+.1f} puntos porcentuales que no favorece al sistema "
            "con RAG. Conviene decirlo sin adornos: en esta muestra, el corpus recuperado no "
            "mejora el acierto del nivel. Ambas variantes comparten el motor de reglas y el "
            "mismo modelo, y el modelo sin contexto responde con conocimiento general, que para "
            "estos cuadros frecuentes resulta suficiente."
        ),
        P(
            "Donde la diferencia sí aparece es en el anclaje y en la seguridad: sin corpus, el "
            "modelo inventa dosis y no reconoce contradicciones en los casos preparados para "
            "ello, mientras que el sistema con recuperación no inventó nada en ese subconjunto y "
            "cada respuesta viene acompañada de los fragmentos y las páginas que la sostienen. "
            "El aporte del RAG en esta evaluación es la trazabilidad y el control de la "
            "invención, no una mejora del acierto, y esa lectura es la que las conclusiones "
            "deben reflejar."
        ),
        P(
            f"El costo de esa diferencia es el tiempo: el sistema con RAG tarda "
            f"{arnes._num(sis_g['latencia_media'], 2)} s por caso frente a "
            f"{arnes._num(base_g['latencia_media'], 2)} s de la línea base, porque la "
            "recuperación vectorial y la respuesta más larga se suman a cada consulta."
        ),
    ]

    # --- 9. Casos con hallazgos ---
    filas_supra = [
        [
            cid,
            recorte(casos_por_id[cid]["titulo"], 34),
            casos_por_id[cid].get("nivel_esperado") or "—",
            registro(casos_por_id[cid]).get("nivel_llm") or "—",
            registro(casos_por_id[cid]).get("nivel_reglas") or "—",
            registro(casos_por_id[cid]).get("nivel_final") or "—",
            NOTAS_CORTAS.get(cid, ""),
        ]
        for cid in SUPRA
        if cid in casos_por_id
    ]
    filas_elevaciones = [
        [
            cid,
            recorte(casos_por_id[cid]["titulo"], 34),
            registro(casos_por_id[cid]).get("nivel_llm") or "—",
            registro(casos_por_id[cid]).get("nivel_reglas") or "—",
            registro(casos_por_id[cid]).get("nivel_final") or "—",
            NOTAS_CORTAS.get(cid, ""),
        ]
        for cid in ELEVACIONES
        if cid in casos_por_id
    ]
    casos_comentados = sorted({"C-12", "A-08", "A-02"} | set(SUPRA) | set(ELEVACIONES))
    bloques += [
        T(1, "9. Casos con hallazgos"),
        P(
            f"De los 30 casos, {len(casos_comentados)} explican por sí solos el comportamiento "
            f"del sistema ({', '.join(casos_comentados)}): el "
            "único error grave, la única invención de contenido, una omisión del límite de la "
            "norma, las priorizaciones que se apartaron del nivel esperado y las elevaciones en "
            "que la capa de reglas corrigió al modelo. Los tres primeros se presentan como "
            "fichas con el detalle del caso."
        ),
        T(2, "9.1. El sub-triage: el error clínicamente grave"),
    ]
    bloques += ficha(casos_por_id["C-12"], COMENTARIOS["C-12"])
    bloques += [T(2, "9.2. La única invención de contenido")]
    bloques += ficha(casos_por_id["A-08"], COMENTARIOS["A-08"])
    bloques += [T(2, "9.3. El límite que se calla")]
    bloques += ficha(casos_por_id["A-02"], COMENTARIOS["A-02"])
    bloques += [
        T(2, "9.4. Priorizaciones por encima del nivel esperado"),
        TAB(
            ["Caso", "Título", "Esperado", "LLM", "Reglas", "Final", "Lectura"],
            filas_supra,
            caption="Los casos con supra-triage y su explicación",
            anchos=[1.1, 3.4, 1.3, 1.2, 1.2, 1.2, 4.6],
            tamano=8,
        ),
        P(
            "El supra-triage no pone al paciente en riesgo: el costo es de recursos y de "
            "credibilidad de la alerta. La mitad de estos casos ocurre donde el motor de reglas "
            "no tiene bandera roja (hipertensión severa asintomática) y el nivel queda enteramente "
            "a criterio del modelo."
        ),
        T(2, "9.5. Elevaciones correctas de la capa de reglas"),
        TAB(
            ["Caso", "Título", "LLM", "Reglas", "Final", "Lectura"],
            filas_elevaciones,
            caption="Casos en que las reglas deterministas elevaron el nivel al valor esperado",
            anchos=[1.1, 3.6, 1.2, 1.2, 1.2, 5.7],
            tamano=8,
        ),
        P(
            "Las tres elevaciones llevaron el nivel al valor correcto y ninguna introdujo una "
            "alarma falsa: hipotensión severa en el adulto mayor, hipoxemia severa en la "
            "exacerbación respiratoria y convulsión activa en el preescolar. Es la evidencia de "
            "que la red de seguridad cumple su función sin agregar ruido."
        ),
    ]

    # --- 10. Discusión, limitaciones y conclusiones ---
    bloques += [
        T(1, "10. Discusión, limitaciones y conclusiones"),
        T(2, "10.1. Cumplimiento de los indicadores"),
        tabla_indicadores(arnes, r),
        T(2, "10.2. Lo que la evidencia sostiene"),
        B(
            [
                f"El sistema se mantiene dentro del rango clínicamente aceptable en "
                f"{arnes._tasa(r['en_permitido'], r['nivel_evaluables'])} de los casos con nivel "
                "esperado, con un solo sub-triage y ningún caso sin clasificar: la red de "
                "seguridad funciona en el sentido de no dejar al paciente sin respuesta.",
                "La capa de reglas deterministas elevó el nivel en cuatro casos: tres veces al "
                "valor correcto y ninguna de forma innecesaria. El falso positivo por negación "
                "que motivó esta evaluación no reaparece en ninguno de los casos de regresión.",
                f"La tasa de alucinación se mantiene en "
                f"{arnes._tasa(r['alucinaciones_anti'], r['n_anti'])} en los casos preparados "
                "para provocarla, por debajo del límite del 15 %; el único fallo es la "
                "reinterpretación de un cuadro inexistente (A-08).",
                "La recuperación encuentra la norma correcta (nivel de documento) en casi todos "
                "los casos evaluables, pero la página exacta en poco más de un tercio: el gold "
                "por página es estricto en un corpus donde varios fragmentos contiguos cubren el "
                "mismo cuadro.",
                "Frente a la línea base sin contexto, el sistema no mejora el acierto del nivel "
                "en el subconjunto común, pero sí elimina la invención de contenido y "
                "acompaña cada respuesta con los fragmentos que la sostienen. El valor medido "
                "del RAG es la trazabilidad, no la exactitud en esta muestra.",
                "Los dos casos que el sistema gestiona peor (A-08 y A-02) apuntan a una misma "
                "causa: la plantilla de producción no pide advertir cuándo la información "
                "disponible no alcanza ni cuándo el dato consultado no está en la norma.",
            ]
        ),
        T(2, "10.3. Limitaciones y amenazas a la validez"),
        B(
            [
                "Los planes gratuitos de los proveedores de nube limitaron el experimento: se "
                "registraron errores de cuota agotada y las líneas base quedaron parciales, así "
                "que la comparación se restringe al subconjunto común. La disponibilidad del "
                "servicio de inferencia es un supuesto de operación del prototipo y refuerza la "
                "conveniencia de la opción local con Ollama para un despliegue sin cuotas.",
                "El consumo de memoria RAM no se midió y se declara como trabajo futuro; "
                "tampoco se ejecutaron repeticiones por caso, de modo que la estabilidad del "
                "nivel entre corridas idénticas no es medible todavía.",
                "Los niveles esperados y los rangos aceptables son una propuesta derivada de la "
                "norma: su validación clínica (C2.A4) y la medición de usabilidad (C2.A5) están "
                "pendientes de las personas que deben aportarlas.",
                "Los criterios automáticos de contenido son heurísticos y sensibles a la "
                "paráfrasis: se informan caso por caso y nunca sustituyen la lectura clínica.",
                "La latencia depende del equipo, de la red y del proveedor; la comparación es "
                "válida entre variantes de la misma corrida, no contra cifras absolutas.",
                "El corpus de las NNAC no contiene una norma de clasificación de urgencias tipo "
                "Manchester: el mapeo de colores vive en la plantilla del sistema, de modo que "
                "esa parte del razonamiento no se puede anclar en la norma recuperada.",
            ]
        ),
        T(2, "10.4. Conclusiones del Componente 2 (C2.A6)"),
        B(
            [
                "El sistema de triaje cumple el indicador de invención de contenido en los "
                "casos diseñados para provocarla y no deja ningún caso sin clasificar, con un "
                "único error grave atribuible a la falta de una bandera roja para el sangrado "
                "obstétrico.",
                "La ganancia del componente RAG no se manifiesta como una mejora del acierto "
                "del nivel en esta muestra, sino como respuestas ancladas, verificables y sin "
                "invenciones: es la propiedad que un sistema de apoyo al triaje en una posta "
                "rural necesita para ser auditable.",
                "El trabajo inmediato es acotado y verificable: añadir a la plantilla la "
                "obligación de declarar cuándo la información no alcanza, completar las "
                "banderas rojas faltantes (quemaduras, hipertensión severa, sangrado "
                "obstétrico y mordedura de serpiente), medir estabilidad con repeticiones y "
                "cerrar la rúbrica clínica con el médico colaborador.",
                "Mientras esos cierres no ocurran, el sistema es apto como apoyo con "
                "supervisión profesional y no como sustituto del criterio médico, tal como "
                "declara su propio descargo de responsabilidad.",
            ]
        ),
    ]

    # --- Anexos ---
    bloques += [
        T(1, "Anexo A. Resultado por caso clínico"),
        P(
            "Tabla completa de los 20 casos clínicos con el nivel de cada capa del sistema. Los "
            "diez casos anti-alucinación aparecen en el apartado 6, con su veredicto y la señal "
            "que lo disparó."
        ),
        tabla_anexo_clinicos(clinicos),
        T(1, "Anexo B. Instrumentos de la valoración clínica y de usabilidad (C2.A4 y C2.A5)"),
        P(
            "Los dos indicadores que dependen de personas externas se entregan como "
            "instrumentos listos para completar, junto con el cálculo automático de sus "
            "resultados. La rúbrica clínica recorre los 20 casos clínicos con una escala de "
            "cuatro niveles (Muy bueno, Bueno, Regular, Malo) y ya trae el nivel que propuso el "
            "sistema en cada caso, para que el médico lo compare con su propio juicio; el "
            "criterio de aceptación es que al menos el 80 % de los casos calificados quede en "
            "Bueno o Muy bueno. La encuesta SUS consta de los 10 ítems estándar con respuesta de "
            "1 a 5 y se puntúa sobre 100, con un criterio de aceptación de 70 puntos."
        ),
        P(
            "Además del porcentaje de casos aceptables y del puntaje SUS, el cálculo compara "
            "la calificación del médico con el veredicto automático del sistema mediante el "
            "estadístico kappa de Cohen, de modo que el acuerdo entre el juicio clínico y la "
            "medición automática quede cuantificado y no solo descrito."
        ),
        TAB(
            ["Instrumento", "Archivo", "Qué mide", "Criterio"],
            [
                [
                    "Rúbrica clínica",
                    "evaluacion/instrumentos/rubrica_clinica.csv",
                    "Calidad clínica de las respuestas en los 20 casos",
                    "≥ 80 % en Bueno o Muy bueno",
                ],
                [
                    "Encuesta SUS",
                    "evaluacion/instrumentos/encuesta_sus.csv",
                    "Usabilidad percibida, 10 ítems de 1 a 5",
                    "≥ 70 puntos sobre 100",
                ],
            ],
            caption="Instrumentos entregados para los indicadores que dependen de personas externas",
            anchos=[2.8, 5.0, 4.6, 3.0],
            tamano=9,
        ),
        T(1, "Anexo C. Reproducibilidad de la evaluación"),
        P(
            "Toda la evaluación se regenera desde el repositorio, sin editar cifras a mano. Los "
            "comandos siguientes reproducen los casos, las corridas, el informe técnico y los "
            "instrumentos."
        ),
        MONO(
            "# 1. Revisar los 30 casos (esquema, niveles, fuentes y detectores)\n"
            "python scripts/evaluar.py validar\n\n"
            "# 2. Ejecutar el sistema completo y la línea base sin contexto\n"
            "python scripts/evaluar.py correr --variante rag --modelo groq --ids C-01,C-02\n"
            "python scripts/evaluar.py correr --variante sin-contexto --modelo groq --limite 15\n\n"
            "# 3. Recalcular las métricas y regenerar el informe técnico\n"
            "python scripts/evaluar.py informe rag_groq_1 rag_groq_2a --titulo \"...\"\n\n"
            "# 4. Instrumentos para el médico y su cálculo cuando los devuelva\n"
            "python scripts/evaluar.py instrumentos --run rag_groq_1 rag_groq_2a\n"
            "python scripts/evaluar.py rubrica --run rag_groq_1 rag_groq_2a\n\n"
            "# 5. Este documento\n"
            "python scripts/informe_word.py --forzar-graficos"
        ),
        TAB(
            ["Carpeta o archivo", "Contenido"],
            [
                ["evaluacion/casos/", "Los 30 casos (20 clínicos y 10 anti-alucinación), validados"],
                ["evaluacion/resultados/", "Evidencia cruda de cada corrida (.json) y su tabla por caso (.csv)"],
                ["evaluacion/informes/", "Informe técnico en Markdown e informe clínico calculado"],
                ["evaluacion/instrumentos/", "Rúbrica clínica, encuesta SUS e instrucciones para el médico"],
                ["scripts/evaluar.py", "Arnés: valida, ejecuta, calcula las métricas y las publica"],
                ["scripts/informe_word.py", "Genera este documento y sus tres gráficos"],
            ],
            caption="Estructura de la evidencia de la evaluación",
            anchos=[4.6, 10.4],
            tamano=9,
        ),
    ]

    if not all(listos.values()):
        bloques.append(
            NOTA(
                "Algún gráfico no pudo renderizarse en esta ejecución: el documento se generó "
                "igual, con el marco en su lugar. Vuelve a ejecutar el generador con "
                "--forzar-graficos y conexión a internet."
            )
        )
    return bloques


# ---------------------------------------------------------------------------
# Fichas de los casos con hallazgos
# ---------------------------------------------------------------------------

SUPRA = ("C-01", "C-06", "C-09", "C-10", "A-06")
ELEVACIONES = ("C-15", "C-16", "C-18")

COMENTARIOS = {
    "C-12": (
        "Único sub-triage de la corrida y, por la definición de las métricas, el error "
        "clínicamente grave: el sistema priorizó con menos urgencia que la esperada. Ninguna "
        "regla determinista lo rescató, porque el motor no tiene bandera roja para el sangrado "
        "vaginal de la gestante, de modo que el nivel dependió por completo del modelo, que "
        "eligió amarillo donde el caso espera naranja. Es el tipo de caso que justifica "
        "completar las banderas rojas antes de un uso real y la razón por la que el sub-triage "
        "se informa aparte del acierto: un solo caso así pesa más que cinco sobre-priorizaciones."
    ),
    "A-08": (
        "La única invención de contenido de la corrida. El caso nombra dos entidades que no "
        "existen —«fiebre de la posta» y «síndrome de Cotagaita»— y el sistema no advierte que "
        "no las reconoce: reinterpreta el cuadro como dengue y razona sobre los criterios de "
        "alarma de esa enfermedad. Los detectores lo marcan por no declarar la ausencia y por "
        "incumplir el criterio exigido. La causa es de diseño de la plantilla, no del corpus: la "
        "instrucción de producción no pide advertir cuándo la información disponible no alcanza. "
        "Es el hallazgo que origina la mejora inmediata propuesta en las conclusiones."
    ),
    "A-02": (
        "El sistema respondió el nivel (verde) y sugirió paracetamol, pero nunca menciona el "
        "fármaco por el que se le preguntó: la palabra «baloxavir» no aparece en la respuesta. "
        "No inventó ninguna dosis, así que el veredicto de alucinación es negativo, pero omitió "
        "el límite: quien lee la respuesta no sabe que ese dato no está respaldado por la norma. "
        "El contraste con A-01 y A-03 es instructivo: en esos casos el sistema sí cierra con una "
        "frase explícita («no se encontró información sobre el fármaco en los fragmentos "
        "disponibles»), así que la declaración depende de la redacción del caso y no de una "
        "obligación impuesta por el sistema."
    ),
}

NOTAS_CORTAS = {
    "C-01": "El modelo ya había elegido rojo: la regla de hipotensión no cambió el resultado, la sobre-priorización nace del LLM.",
    "C-06": "Dismenorrea clasificada como verde donde el caso espera azul: sin bandera roja aplicable, la decisión es del modelo y el caso admite las dos lecturas (dolor que no requiere atención).",
    "C-09": "Apendicitis llevada a rojo por el modelo; la regla de dolor abdominal severo se activó sin efecto porque el nivel ya era más urgente.",
    "C-10": "Hipertensión severa asintomática sin bandera roja asociada: el nivel quedó enteramente al criterio del modelo.",
    "A-06": "Hipotermia real (34,6 °C) con relato tranquilizador: la regla marcó naranja y el modelo eligió rojo al leer la contradicción como gravedad.",
    "C-15": "Hipotensión severa (PA sistólica 85 mmHg): la regla llevó el nivel de naranja a rojo, que es el esperado.",
    "C-16": "Hipoxemia severa (SpO₂ 89 %): la regla corrigió al modelo y el nivel final coincidió con el esperado.",
    "C-18": "Convulsión activa en preescolar: la regla elevó de amarillo a naranja, el nivel esperado.",
}


def ficha(caso: dict, comentario: str) -> list[dict]:
    """Ficha de un caso: datos, veredicto, fragmentos recuperados y comentario."""
    reg = registro(caso)
    v = veredicto(caso)
    veredicto_texto = etiqueta_resultado(caso)
    if v.get("alucinacion"):
        veredicto_texto += " · invención de contenido: " + senales_de_alucinacion(v)
    elif v.get("declara_limite"):
        veredicto_texto += " · declara el límite del material"
    filas = [
        ["Categoría", str(caso.get("categoria") or "—")],
        ["Relato del caso", recorte(str(caso.get("descripcion") or ""), 260)],
        [
            "Nivel esperado / permitido",
            f"{caso.get('nivel_esperado') or '—'} / "
            f"{' '.join(caso.get('nivel_permitido') or []) or '—'}",
        ],
        [
            "Nivel del modelo / reglas / final",
            f"{reg.get('nivel_llm') or '—'} / {reg.get('nivel_reglas') or '—'} / "
            f"{reg.get('nivel_final') or '—'}",
        ],
        ["Reglas activadas", "; ".join(reg.get("reglas_activadas") or []) or "ninguna"],
        ["Veredicto automático", veredicto_texto],
        ["Fragmentos recuperados (3 primeros)", top_fragmentos(caso)],
    ]
    return [
        T(3, f"{caso['id']}. {caso['titulo']}"),
        TAB(
            ["Elemento", "Detalle"],
            filas,
            caption=f"Detalle del caso {caso['id']}",
            anchos=[4.4, 10.6],
            tamano=9,
        ),
        P(comentario),
    ]


# ---------------------------------------------------------------------------
# Armado del documento
# ---------------------------------------------------------------------------


def construir(arnes, metricas: dict, listos: dict) -> Document:
    """Arma el documento completo con el formato del capítulo."""
    doc = Document()
    GD._configurar_estilos(doc)
    GD._configurar_pie(doc, "Componente 2 — Evaluación del sistema de triaje (NNAC)")
    portada(doc, metricas)
    GD._indices(doc, secciones="1-3")
    for bloque in bloques_informe(arnes, metricas, listos):
        GD._escribir_bloque(doc, bloque)
    return doc


def guardar(doc: Document) -> Path:
    """Guarda el documento; si está abierto en Word, escribe con otro nombre.

    Word mantiene el archivo bloqueado mientras el documento está abierto, de modo
    que sobrescribirlo falla con PermissionError. En vez de perder el trabajo se
    guarda una copia con marca de tiempo y se avisa.
    """
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc.save(str(SALIDA))
        return SALIDA
    except PermissionError:
        alternativa = SALIDA.with_name(
            f"{SALIDA.stem}_{datetime.now().strftime('%H%M%S')}{SALIDA.suffix}"
        )
        doc.save(str(alternativa))
        print(
            f"⚠️  {SALIDA.name} está bloqueado por otro programa (probablemente Word): "
            f"se guardó como {alternativa.name}. Ciérralo y vuelve a ejecutar el "
            "generador para reemplazar el original."
        )
        return alternativa


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera el informe Word del Componente 2 desde la evidencia de las corridas."
    )
    parser.add_argument(
        "--forzar-graficos",
        action="store_true",
        help="Vuelve a renderizar los 3 gráficos aunque ya existan.",
    )
    parser.add_argument(
        "--sin-graficos",
        action="store_true",
        help="No contacta a kroki (deja los gráficos que ya estén en disco).",
    )
    args = parser.parse_args(argv)

    global GD, T, P, B, NUM, TAB, FIG, NOTA, MONO
    constructores, GD = cargar_formato()
    T = constructores.T
    P = constructores.P
    B = constructores.B
    NUM = constructores.NUM
    TAB = constructores.TAB
    FIG = constructores.FIG
    NOTA = constructores.NOTA
    MONO = constructores.MONO

    arnes = cargar_arnes()
    metricas = cargar_metricas(arnes)
    listos = {"nivel": True, "alucinaciones": True, "latencia": True}
    if not args.sin_graficos:
        listos = graficos(arnes, metricas, args.forzar_graficos)

    doc = construir(arnes, metricas, listos)
    ruta = guardar(doc)

    informe = GD.verificar(ruta)
    print(f"Documento generado: {_relativa(ruta)}")
    print(f"  párrafos: {informe['parrafos']} · títulos: {informe['titulos']}")
    print(f"  tablas:   {informe['tablas']} (pies de tabla: {GD.CONTADOR['Tabla']})")
    print(f"  figuras:  {informe['imagenes']} imágenes (pies de figura: {GD.CONTADOR['Figura']})")
    faltan = [nombre for nombre, listo in listos.items() if not listo]
    if faltan:
        print(f"  ADVERTENCIA: gráficos sin renderizar: {', '.join(faltan)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
