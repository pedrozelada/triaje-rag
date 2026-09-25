"""Harness de evaluación del sistema de triaje (Componente 2 de la tesis).

Qué hace
--------
Ejecuta los casos de ``evaluacion/casos/`` contra el sistema real, guarda la
evidencia cruda (respuesta completa, chunks recuperados con score y página,
tiempos y tokens) y calcula las métricas del Componente 2: exactitud del nivel
de urgencia, under/over-triage, Recall@k, Precision@k, MRR, latencia, tokens,
estabilidad y tasa de alucinaciones.

Subcomandos
-----------
    validar       Revisa los casos: esquema, cobertura, vitales válidos, regex
                  compilables y gold verificado contra el corpus. No llama a
                  ningún modelo.
    correr        Ejecuta los casos y guarda el JSON/CSV crudo de la corrida.
                  Variantes: ``rag`` (sistema completo) y ``sin-contexto``
                  (mismo prompt y mismas reglas, pero sin recuperación: la
                  línea base del benchmark).
    informe       Recalcula TODAS las métricas desde uno o varios JSON de
                  resultados y escribe el informe Markdown. No gasta llamadas a
                  modelos, así que las definiciones se pueden corregir sin
                  repetir la corrida.
    instrumentos  Genera la rúbrica clínica y la encuesta SUS listas para que
                  las complete el médico colaborador (C2.A4 y C2.A5).
    rubrica       Calcula el porcentaje de casos Bueno/Muy bueno, el puntaje
                  SUS y la concordancia con el veredicto automático.

Principios de diseño
--------------------
* **Nada se escribe en la base de datos real ni en el índice**: la evaluación
  vive en ``evaluacion/`` y no contamina los datos de la demo.
* **El gold no depende del sistema**: las fuentes esperadas se eligieron
  leyendo la norma (búsqueda literal en el corpus), no al revés, para que
  Recall@k mida al sistema y no a sí mismo.
* **Lo no medido queda None**: los tokens solo se publican si el proveedor los
  reporta y la RAM no se estima (se declara como no medida en el informe).
* **La negación cuenta**: los criterios automáticos reutilizan el manejo de
  negación del motor de reglas, para no marcar como hallazgo aquello que la
  respuesta enuncia como ausente.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import sqlite3
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

DIR_CASOS = RAIZ / "evaluacion" / "casos"
DIR_RESULTADOS = RAIZ / "evaluacion" / "resultados"
DIR_INFORMES = RAIZ / "evaluacion" / "informes"
DIR_INSTRUMENTOS = RAIZ / "evaluacion" / "instrumentos"
CHROMA_SQLITE = RAIZ / "chroma_db" / "chroma.sqlite3"

ARCHIVOS_CASOS = ("casos_clinicos.json", "casos_antialucinacion.json")

#: Orden Manchester, de menor a mayor urgencia (igual que ai_service.red_flags).
NIVELES = ("azul", "verde", "amarillo", "naranja", "rojo")
POSICION = {nivel: i for i, nivel in enumerate(NIVELES)}

#: K del protocolo de evaluación. Recall@5 es Recall@k con k = similarity_top_k.
K_RECALL = (3, 5)
K_PRECISION = 5

#: Detectores de alucinación reconocidos (ver README de los casos).
DETECTORES_VALIDOS = {
    "dosis_inventada",
    "entidad_inventada",
    "cita_no_anclada",
    "contradiccion_no_reconocida",
}

#: Dosis: cifras con unidad farmacológica. NO incluye mmHg (es un signo vital,
#: no una dosis) para no marcar como invento una presión arterial enunciada.
RE_DOSIS = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:mg/kg|mg|mcg|µg|ug|g|ml|ui|gotas|comprimidos)\b"
)

#: Citas entrecomilladas (comillas latinas, inglesas, tipográficas y simples).
RE_CITA = re.compile(r"[«\"“'‘]([^«»\"”'’]{25,400})[»\"”'’]")

#: Referencias de página en la respuesta, con o sin abreviatura.
RE_PAGINA = re.compile(r"\bp(?:ág|ag|ág\.|ag\.|\.)?\.?\s*(\d{1,4})\b", re.IGNORECASE)

#: Cues de negación que NO están en el motor de reglas y que sí aparecen en las
#: respuestas explicativas ("no corresponde a taquicardia", "no existe la
#: página 4321", "no hay información", "no se describe en las NNAC").
RE_CUES_NEGACION_EXTRA = re.compile(
    r"\bno\s+(?:corresponde|corresponden|es|son|constituye|constituyen|sugiere|"
    r"sugieren|indica|indican|existe|existen|consta|figura|figuran|aparece|"
    r"aparecen|cuenta|hay|describe|describen|menciona|mencionan|se\s+describe|"
    r"se\s+menciona|se\s+encontraba|se\s+encuentra|aplica|aplican|amerita|"
    r"requiere|requieren|evidencia|presenta|presentan|recomienda|recomiendan)\b"
    r"|\bsin\s+(?:signos|datos|evidencia|presencia|incremento|alteraciones|"
    r"compromiso|criterios)\b"
)

#: Enunciado obligatorio de ausencia (para los casos de entidad inventada).
#:
#: Se comprobó en una corrida real que un modelo puede declarar la ausencia con
#: verbos que no estaban en la primera versión ("las NNAC no INCLUYEN...", "no
#: se ENCONTRÓ descripción de..."): sin ampliarlos, el detector acusaba de
#: inventar a una respuesta que en realidad sí había admitido el límite.
RE_AUSENCIA = re.compile(
    r"no\s+(?:figura|figuran|consta|constan|aparece|aparecen|existe|existen|"
    r"se\s+encuentra|se\s+encuentran|hay|se\s+describe|se\s+describen|"
    r"se\s+menciona|se\s+mencionan|está|están|especifica|especifican|"
    r"menciona|mencionan|corresponde|incluye|incluyen|contiene|contienen|"
    r"contempla|contemplan|define|definen|aborda|abordan|reporta|reportan)\b"
    r"|no\s+se\s+(?:encontr[oóó]|describe|describen|menciona|mencionan|"
    r"especifica|especifican|encontraron|hall[oó])\w*"
    r"|informaci[oó]n\s+(?:insuficiente|no\s+disponible|limitada)"
    r"|no\s+(?:está|están|se\s+encuentra|se\s+encuentran)\s+(?:en|dentro)"
)


# ---------------------------------------------------------------------------
# Texto y negación
# ---------------------------------------------------------------------------


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes (mismo criterio que el motor de reglas).

    Se reutiliza la normalización del proyecto en lugar de escribir otra: si el
    motor de reglas y el evaluador normalizaran distinto, una negación detectada
    por las reglas podría no serlo para los criterios automáticos. Conserva los
    saltos de línea porque delimitan el alcance de la negación.
    """
    from ai_service.red_flags import _normalizar

    return _normalizar(texto)


def normalizar_ws(texto: str) -> str:
    """Igual que `normalizar`, colapsando además el espaciado.

    Hace falta porque el texto extraído de los PDF del corpus conserva los
    TABS del extractor ("muñón\tumbilical"): sin colapsar, cualquier
    comprobación de frase con espacios —palabras clave del gold, anclaje de
    citas, dosis— fallaría por un carácter invisible y no por contenido. Es un
    hallazgo de calidad de datos que se reporta en el informe.
    """
    return re.sub(r"\s+", " ", normalizar(texto))


def _clausulas(texto_normalizado: str) -> list[str]:
    """Divide en cláusulas por . ; ! ? y salto de línea (como las reglas)."""
    return [c for c in re.split(r"[^.!?;\n]+", texto_normalizado) if c.strip()]


def hallazgo_afirmado(texto: str, patron: str) -> Optional[str]:
    """Devuelve la cláusula donde el patrón aparece AFIRMADO, o None.

    Reutiliza el criterio del motor de reglas: un hallazgo está negado si antes
    de su aparición hay un cue de negación sin un cue afirmativo en medio. Se
    añaden cues de negación propios de las respuestas narrativas ("no
    corresponde a", "no existe", ...), que el motor no necesita para el relato
    del paciente pero sí la evaluación para leer la respuesta del modelo.
    """
    from ai_service.red_flags import _CUES_AFIRMACION, _CUES_NEGACION

    for clausula in _clausulas(normalizar(texto)):
        # El espaciado se colapsa DENTRO de la cláusula (no antes de separarlas)
        # para que los patrones con espacios coincidan sin perder el alcance de
        # la negación que fijan los saltos de línea.
        fragmento = re.sub(r"\s+", " ", clausula).strip()
        for coincidencia in re.finditer(patron, fragmento):
            negado = False
            for cue in list(_CUES_NEGACION.finditer(fragmento)) + list(
                RE_CUES_NEGACION_EXTRA.finditer(fragmento)
            ):
                if cue.end() > coincidencia.start():
                    continue
                if not _CUES_AFIRMACION.search(
                    fragmento, cue.end(), coincidencia.start()
                ):
                    negado = True
                    break
            if not negado:
                return fragmento
    return None


def hash_archivo(ruta: Path) -> str:
    """SHA-256 del contenido de un archivo (trazabilidad de los casos)."""
    digest = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Casos
# ---------------------------------------------------------------------------


def _relativa(ruta: Path) -> str:
    """Ruta relativa al repositorio; si está fuera (--salida, pruebas), la absoluta."""
    try:
        return str(ruta.relative_to(RAIZ))
    except ValueError:
        return str(ruta)


def cargar_casos() -> list[dict[str, Any]]:
    """Carga los 30 casos de los dos archivos, en orden estable."""
    casos: list[dict[str, Any]] = []
    for nombre in ARCHIVOS_CASOS:
        ruta = DIR_CASOS / nombre
        if not ruta.exists():
            raise SystemExit(f"❌ No se encontró el archivo de casos: {ruta}")
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        for caso in datos.get("casos", []):
            caso["_archivo"] = nombre
            caso["_grupo_archivo"] = datos.get("grupo")
            casos.append(caso)
    return casos


def hashes_casos() -> dict[str, str]:
    """Hash de cada archivo de casos (para la trazabilidad de la corrida)."""
    return {
        nombre: hash_archivo(DIR_CASOS / nombre)
        for nombre in ARCHIVOS_CASOS
        if (DIR_CASOS / nombre).exists()
    }


def vitales_de(caso: dict[str, Any]):
    """Construye DatosVitales desde el JSON del caso (None = no medido)."""
    from ai_service.models import DatosVitales

    v = caso.get("vitales") or {}
    return DatosVitales(
        edad=int(caso.get("edad", 0)),
        sexo=caso.get("sexo", "M"),
        temperatura=v.get("temperatura"),
        presion_sistolica=v.get("presion_sistolica"),
        presion_diastolica=v.get("presion_diastolica"),
        frecuencia_cardiaca=v.get("frecuencia_cardiaca"),
        frecuencia_respiratoria=v.get("frecuencia_respiratoria"),
        saturacion=v.get("saturacion"),
        edad_meses=caso.get("edad_meses"),
    )


# ---------------------------------------------------------------------------
# Corpus (solo lectura)
# ---------------------------------------------------------------------------


def _conexion_chroma() -> Optional[sqlite3.Connection]:
    """Abre la base de Chroma en modo ESTRICTAMENTE de solo lectura."""
    if not CHROMA_SQLITE.exists():
        return None
    try:
        return sqlite3.connect(f"file:{CHROMA_SQLITE}?mode=ro", uri=True)
    except sqlite3.Error:
        return None


def universo_paginas() -> dict[str, set[str]]:
    """Páginas indexadas por archivo, leídas del índice (read-only).

    Sirve para dos cosas: comprobar que la página de una fuente esperada exista
    de verdad y detectar citas de páginas que no existen (alucinación de cita).
    """
    con = _conexion_chroma()
    if con is None:
        return {}
    try:
        filas = con.execute(
            "SELECT mf.string_value AS archivo, ml.string_value AS pagina "
            "FROM embedding_metadata ml "
            "JOIN embedding_metadata mf ON mf.id = ml.id AND mf.key = 'archivo' "
            "WHERE ml.key = 'page_label'"
        ).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        con.close()

    universo: dict[str, set[str]] = {}
    for archivo, pagina in filas:
        if archivo and pagina:
            universo.setdefault(str(archivo), set()).add(str(pagina))
    return universo


def _chunks_de_pagina(archivo: str, pagina: str, limite: int = 40) -> list[str]:
    """Chunks de una página concreta del índice (solo lectura).

    Se devuelven por separado, sin concatenar: una frase partida entre dos
    chunks no debe hacer creer que la página no contiene esa información.
    """
    con = _conexion_chroma()
    if con is None:
        return []
    try:
        filas = con.execute(
            "SELECT md.string_value FROM embedding_metadata md "
            "JOIN embedding_metadata ml ON ml.id = md.id AND ml.key = 'page_label' "
            "JOIN embedding_metadata mf ON mf.id = md.id AND mf.key = 'archivo' "
            "WHERE md.key = 'chroma:document' AND mf.string_value = ? "
            "AND ml.string_value = ? LIMIT ?",
            (archivo, str(pagina), limite),
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()
    return [str(f[0]) for f in filas]


def pagina_contiene(archivo: str, pagina: str, palabra: str) -> bool:
    """True si algún chunk de esa página contiene la palabra clave."""
    aguja = normalizar_ws(palabra)
    return any(
        aguja in normalizar_ws(chunk) for chunk in _chunks_de_pagina(archivo, pagina)
    )


def texto_de_pagina(archivo: str, pagina: str, limite: int = 60000) -> str:
    """Texto indexado de una página concreta (contexto para citas y dosis)."""
    return " ".join(_chunks_de_pagina(archivo, pagina))[:limite]


# ---------------------------------------------------------------------------
# Entorno y trazabilidad
# ---------------------------------------------------------------------------


def _git(*args: str) -> str:
    """Ejecuta git en modo consulta (nunca escribe nada en el repositorio)."""
    try:
        salida = subprocess.run(
            ["git", *args], cwd=RAIZ, capture_output=True, text=True, timeout=20
        )
        return salida.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def entorno() -> dict[str, Any]:
    """Metadatos de reproducibilidad de la corrida.

    Sin esto, un resultado no es verificable: el mismo corpus en distinto commit
    o con otro modelo de embeddings no es el mismo experimento.
    """
    from ai_service.indice import ParametrosIndice
    from ai_service.rag_pipeline import estado_indice
    from backend.core.config import settings

    parametros = ParametrosIndice()
    try:
        corpus = estado_indice(settings.data_dir, settings.chroma_path, parametros)
    except Exception as e:  # el índice no es obligatorio para el baseline
        corpus = {"error": str(e)}

    commit = _git("rev-parse", "HEAD")
    sucio = bool(_git("status", "--porcelain"))
    universo = universo_paginas()

    return {
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": commit or None,
        "commit_corto": commit[:8] if commit else None,
        "arbol_con_cambios_sin_commitear": sucio,
        "python": sys.version.split()[0],
        "so": platform.platform(),
        "embedding_model": parametros.modelo_embeddings,
        "chunk_size": parametros.chunk_size,
        "chunk_overlap": parametros.chunk_overlap,
        "data_dir": settings.data_dir,
        "chroma_path": settings.chroma_path,
        "corpus": corpus,
        "paginas_indexadas_por_archivo": {k: len(v) for k, v in sorted(universo.items())},
        "pagina_maxima_por_archivo": {
            k: max((int(p) for p in v if p.isdigit()), default=0)
            for k, v in sorted(universo.items())
        },
        "hashes_casos": hashes_casos(),
    }


# ---------------------------------------------------------------------------
# Ejecución de casos
# ---------------------------------------------------------------------------


def seleccionar_modelo(patron: Optional[str]):
    """Elige el modelo LLM por coincidencia parcial del nombre del proveedor."""
    from ai_service.providers import get_llm_models

    modelos = get_llm_models()
    if not modelos:
        raise SystemExit("❌ No hay modelos LLM disponibles (revisa las API keys).")
    if not patron:
        clave = next(iter(modelos))
        return clave, modelos[clave]
    candidatos = [(k, v) for k, v in modelos.items() if patron.lower() in k.lower()]
    if not candidatos:
        disponibles = ", ".join(modelos)
        raise SystemExit(f"❌ Ningún modelo coincide con '{patron}'. Disponibles: {disponibles}")
    return candidatos[0]


def temperatura_del_proveedor(clave: str) -> Optional[float]:
    """Temperatura configurada del proveedor (0.1 por defecto), para el informe."""
    prefijo = {
        "Groq": "GROQ_TEMPERATURE",
        "Gemini": "GEMINI_TEMPERATURE",
        "OpenAI": "OPENAI_TEMPERATURE",
    }
    for inicio, variable in prefijo.items():
        if clave.lower().startswith(inicio.lower()):
            return float(os.getenv(variable, "0.1"))
    return None


def _registro_desde_resultado(resultado, repeticion: int) -> dict[str, Any]:
    """Convierte el ResultadoTriage en el registro de evidencia de la corrida."""
    return {
        "repeticion": repeticion,
        "error": None,
        "nivel_llm": None,  # el servicio solo publica el nivel final
        "nivel_reglas": None,
        "nivel_final": resultado.nivel_urgencia,
        "reglas_activadas": list(resultado.reglas_activadas),
        "tiempo_respuesta": resultado.tiempo_respuesta,
        "tokens_consumidos": resultado.tokens_consumidos,
        "tokens_prompt": resultado.tokens_prompt,
        "tokens_completacion": resultado.tokens_completacion,
        "tokens_origen": resultado.tokens_origen,
        "modelo_utilizado": resultado.modelo_utilizado,
        "prompt_utilizado": resultado.prompt_utilizado,
        "respuesta": resultado.respuesta,
        "recuperaciones": [r.to_dict() for r in resultado.recuperaciones],
    }


def ejecutar_caso_rag(caso, servicio, modelo_nombre: str, repeticion: int) -> dict[str, Any]:
    """Ejecuta un caso contra el sistema completo (RAG + reglas)."""
    datos = vitales_de(caso)
    resultado = servicio.analizar(
        datos_vitales=datos,
        sintomas=caso["descripcion"],
        modelo_nombre=modelo_nombre,
        medir_tokens=True,
    )
    registro = _registro_desde_resultado(resultado, repeticion)

    # El servicio publica el nivel final (el más urgente entre LLM y reglas) y no
    # los dos por separado. Para poder atribuir cada acierto y cada error, el
    # evaluador los recalcula aquí con las MISMAS funciones puras del sistema
    # (sin volver a llamar al modelo): el nivel del LLM extraído de su respuesta
    # y el nivel que exigen las reglas de seguridad.
    from ai_service.red_flags import evaluar_reglas, nivel_maximo
    from ai_service.utils import obtener_nivel_urgencia_color

    registro["nivel_llm"] = obtener_nivel_urgencia_color(resultado.respuesta)
    alertas = evaluar_reglas(datos, caso["descripcion"])
    nivel_reglas = None
    for alerta in alertas:
        nivel_reglas = nivel_maximo(nivel_reglas, alerta.nivel)
    registro["nivel_reglas"] = nivel_reglas
    # Control de coherencia: si el recálculo no coincidiera con lo que devolvió
    # el servicio, el evaluador estaría midiendo otra cosa. Se registra para que
    # aparezca en el informe en lugar de quedar oculto.
    registro["nivel_final_coincide_con_servicio"] = (
        nivel_maximo(registro["nivel_llm"], nivel_reglas) == resultado.nivel_urgencia
    )
    return registro


def ejecutar_caso_sin_contexto(caso, llm, modelo_nombre: str, repeticion: int) -> dict[str, Any]:
    """Ejecuta el caso con el MISMO prompt pero sin recuperación (línea base).

    Se aplican también las reglas deterministas y se toma el nivel más urgente,
    igual que en producción: así la comparación aísla el efecto del contexto
    recuperado y no el de la capa de seguridad.
    """
    from ai_service.rag_pipeline import PROMPT_TRIAGE_NNAC
    from ai_service.red_flags import evaluar_reglas, nivel_maximo
    from ai_service.utils import obtener_nivel_urgencia_color

    datos = vitales_de(caso)
    prompt = PROMPT_TRIAGE_NNAC.format(
        context_str=(
            "(Sin contexto recuperado: no se dispone de fragmentos de las NNAC "
            "para este caso. Responde con tu conocimiento general e indica "
            "explícitamente los límites de tu respuesta.)"
        ),
        datos_paciente=datos.a_texto_prompt(),
        query_str=caso["descripcion"],
    )

    inicio = time.time()
    respuesta = llm.complete(prompt)
    elapsed = time.time() - inicio
    texto = str(getattr(respuesta, "text", "") or "").strip()

    prompt_tokens = completacion_tokens = 0
    try:
        from llama_index.core.callbacks.token_counting import get_tokens_from_response

        prompt_tokens, completacion_tokens = get_tokens_from_response(respuesta)
    except Exception:
        pass
    total = prompt_tokens + completacion_tokens if (prompt_tokens or completacion_tokens) else None

    alertas = evaluar_reglas(datos, caso["descripcion"])
    nivel_reglas = None
    for alerta in alertas:
        nivel_reglas = nivel_maximo(nivel_reglas, alerta.nivel)
    nivel_llm = obtener_nivel_urgencia_color(texto)

    return {
        "repeticion": repeticion,
        "error": None,
        "nivel_llm": nivel_llm,
        "nivel_reglas": nivel_reglas,
        "nivel_final": nivel_maximo(nivel_llm, nivel_reglas),
        "reglas_activadas": [a.descripcion for a in alertas],
        "tiempo_respuesta": round(elapsed, 3),
        "tokens_consumidos": total,
        "tokens_prompt": prompt_tokens or None,
        "tokens_completacion": completacion_tokens or None,
        "tokens_origen": "proveedor" if total else None,
        "modelo_utilizado": modelo_nombre,
        "prompt_utilizado": prompt,
        "respuesta": texto,
        "recuperaciones": [],
    }


def _con_reintentos(fn, intentos: int = 2, espera: float = 6.0):
    """Ejecuta fn con reintentos ante fallos de red o límites de tasa.

    La corrida nunca se pierde por un caso: si tras los reintentos sigue
    fallando, el error se registra en el JSON y se continúa con el siguiente.
    """
    ultimo_error: Optional[Exception] = None
    for intento in range(1, intentos + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - se registra para el informe
            ultimo_error = e
            if intento < intentos:
                time.sleep(espera * intento)
    raise ultimo_error  # type: ignore[misc]


def _registro_error(mensaje: str, repeticion: int) -> dict[str, Any]:
    return {
        "repeticion": repeticion,
        "error": mensaje,
        "nivel_llm": None,
        "nivel_reglas": None,
        "nivel_final": None,
        "reglas_activadas": [],
        "tiempo_respuesta": None,
        "tokens_consumidos": None,
        "tokens_prompt": None,
        "tokens_completacion": None,
        "tokens_origen": None,
        "modelo_utilizado": None,
        "prompt_utilizado": None,
        "respuesta": "",
        "recuperaciones": [],
    }


# ---------------------------------------------------------------------------
# Subcomando: validar
# ---------------------------------------------------------------------------


CAMPOS_OBLIGATORIOS = (
    "id",
    "titulo",
    "grupo",
    "categoria",
    "edad",
    "sexo",
    "descripcion",
    "nivel_permitido",
    "fuentes_esperadas",
    "justificacion_esperada",
    "criterios",
    "validacion_gold",
)


def comando_validar(args) -> int:
    """Revisa el corpus de casos antes de gastar una sola llamada a un modelo."""
    from ai_service.red_flags import evaluar_reglas, nivel_maximo

    casos = cargar_casos()
    universo = universo_paginas()
    problemas: list[str] = []
    avisos: list[str] = []

    if len(casos) != 30:
        problemas.append(f"Se esperaban 30 casos y hay {len(casos)}.")
    clinicos = [c for c in casos if c.get("_grupo_archivo") == "clinico"]
    anti = [c for c in casos if c.get("_grupo_archivo") == "anti_alucinacion"]
    if len(clinicos) != 20:
        problemas.append(f"Se esperaban 20 casos clínicos y hay {len(clinicos)}.")
    if len(anti) != 10:
        problemas.append(f"Se esperaban 10 casos anti-alucinación y hay {len(anti)}.")

    ids = [c.get("id") for c in casos]
    if len(set(ids)) != len(ids):
        problemas.append("Hay identificadores de caso repetidos.")

    print("=" * 78)
    print("VALIDACIÓN DE LOS CASOS")
    print("=" * 78)

    for caso in casos:
        cid = caso.get("id", "¿?")
        etiqueta = f"{cid} ({caso.get('_grupo_archivo')})"
        faltantes = [c for c in CAMPOS_OBLIGATORIOS if c not in caso]
        if faltantes:
            problemas.append(f"{etiqueta}: faltan campos {faltantes}.")
            continue

        # --- Vitales y grupo etario ---
        try:
            datos = vitales_de(caso)
            if not datos.es_valido():
                problemas.append(
                    f"{etiqueta}: signos vitales inválidos (revisa rangos o "
                    "edad_meses para menores de 1 año)."
                )
            grupo = datos.grupo_etario
        except Exception as e:  # noqa: BLE001
            problemas.append(f"{etiqueta}: no se pudieron construir los vitales: {e}")
            continue

        # --- Nivel esperado ---
        esperado = caso.get("nivel_esperado")
        permitido = caso.get("nivel_permitido") or []
        if esperado is not None and esperado not in NIVELES:
            problemas.append(f"{etiqueta}: nivel_esperado inválido ({esperado}).")
        for nivel in permitido:
            if nivel not in NIVELES:
                problemas.append(f"{etiqueta}: nivel_permitido inválido ({nivel}).")
        if esperado is not None and permitido and esperado not in permitido:
            problemas.append(
                f"{etiqueta}: el nivel esperado ({esperado}) no está entre los "
                f"permitidos ({permitido})."
            )
        if caso.get("_grupo_archivo") == "clinico" and esperado is None:
            problemas.append(f"{etiqueta}: un caso clínico debe tener nivel esperado.")

        # --- Criterios automáticos ---
        criterios = caso.get("criterios") or {}
        for clave in ("debe_incluir", "no_debe_incluir"):
            for patron in criterios.get(clave) or []:
                try:
                    re.compile(patron)
                except re.error as e:
                    problemas.append(f"{etiqueta}: regex inválida en {clave} ({patron}): {e}")
        for detector in caso.get("detectores") or []:
            if detector not in DETECTORES_VALIDOS:
                problemas.append(f"{etiqueta}: detector desconocido ({detector}).")
        if caso.get("categoria") in {"capciosa", "inexistente", "cita_falsa"} and not caso.get(
            "detectores"
        ):
            avisos.append(f"{etiqueta}: caso de alucinación sin detectores declarados.")

        # --- Gold contra el corpus ---
        for fuente in caso.get("fuentes_esperadas") or []:
            archivo = fuente.get("archivo")
            pagina = str(fuente.get("page_label"))
            if archivo not in universo:
                problemas.append(f"{etiqueta}: el archivo {archivo} no está en el índice.")
                continue
            if pagina not in universo[archivo]:
                problemas.append(
                    f"{etiqueta}: la página {pagina} de {archivo} no existe en el índice."
                )
                continue
            for palabra in fuente.get("palabras_clave") or []:
                if not pagina_contiene(archivo, pagina, palabra):
                    avisos.append(
                        f"{etiqueta}: '{palabra}' no aparece en {archivo} p.{pagina} "
                        "(revisar el gold)."
                    )

        # --- Qué harían las reglas deterministas en este caso ---
        alertas = evaluar_reglas(datos, caso["descripcion"])
        nivel_reglas = None
        for alerta in alertas:
            nivel_reglas = nivel_maximo(nivel_reglas, alerta.nivel)
        marca_reglas = nivel_reglas or "—"
        if (
            esperado is not None
            and nivel_reglas is not None
            and POSICION[nivel_reglas] > POSICION[esperado]
            and caso.get("categoria") not in {"contradictoria"}
        ):
            avisos.append(
                f"{etiqueta}: las reglas exigen {nivel_reglas} y el esperado es "
                f"{esperado} — revisar si es una elevación deseada ({alertas[0].descripcion})."
            )
        print(
            f"  {cid:<5} {grupo:<12} esperado={str(esperado):<9} "
            f"reglas={marca_reglas:<9} fuentes={len(caso.get('fuentes_esperadas') or [])} "
            f"alertas={len(alertas)}"
        )

    print()
    print(f"Casos validados: {len(casos)} (clínicos={len(clinicos)}, anti={len(anti)})")
    if avisos:
        print(f"\n⚠️  Avisos ({len(avisos)}):")
        for aviso in avisos:
            print(f"  - {aviso}")
    if problemas:
        print(f"\n❌ Problemas ({len(problemas)}):")
        for problema in problemas:
            print(f"  - {problema}")
        return 1
    print("\n✅ Casos válidos.")
    return 0


# ---------------------------------------------------------------------------
# Subcomando: correr
# ---------------------------------------------------------------------------


COLUMNAS_CSV = (
    "caso_id",
    "grupo",
    "categoria",
    "repeticion",
    "nivel_esperado",
    "nivel_permitido",
    "nivel_llm",
    "nivel_reglas",
    "nivel_final",
    "coincide",
    "desvio",
    "tiempo_respuesta",
    "tokens_consumidos",
    "n_recuperaciones",
    "top1_archivo",
    "top1_pagina",
    "top1_score",
    "error",
)


def _fila_csv(caso: dict[str, Any], registro: dict[str, Any]) -> dict[str, Any]:
    esperado = caso.get("nivel_esperado")
    final = registro.get("nivel_final")
    recs = registro.get("recuperaciones") or []
    top1 = recs[0] if recs else {}
    if esperado and final:
        coincide = final == esperado
        desvio = POSICION.get(final, 0) - POSICION.get(esperado, 0)
    else:
        coincide = ""
        desvio = ""
    return {
        "caso_id": caso.get("id"),
        "grupo": caso.get("_grupo_archivo"),
        "categoria": caso.get("categoria"),
        "repeticion": registro.get("repeticion"),
        "nivel_esperado": esperado or "",
        "nivel_permitido": "|".join(caso.get("nivel_permitido") or []),
        "nivel_llm": registro.get("nivel_llm") or "",
        "nivel_reglas": registro.get("nivel_reglas") or "",
        "nivel_final": final or "",
        "coincide": coincide,
        "desvio": desvio,
        "tiempo_respuesta": registro.get("tiempo_respuesta") or "",
        "tokens_consumidos": registro.get("tokens_consumidos") or "",
        "n_recuperaciones": len(recs),
        "top1_archivo": top1.get("archivo", ""),
        "top1_pagina": top1.get("page_label", ""),
        "top1_score": top1.get("score", ""),
        "error": registro.get("error") or "",
    }


def comando_correr(args) -> int:
    casos = cargar_casos()
    if args.ids:
        pedidos = {i.strip() for i in args.ids.split(",") if i.strip()}
        casos = [c for c in casos if c["id"] in pedidos]
    if args.solo_estabilidad:
        casos = [c for c in casos if c.get("estabilidad")]
    if args.limite:
        casos = casos[: args.limite]
    if not casos:
        raise SystemExit("❌ No hay casos que cumplan los filtros indicados.")

    entorno_info = entorno()
    corpus = entorno_info.get("corpus") or {}
    if args.variante == "rag" and not corpus.get("actualizado", False):
        print(
            "⚠️  El índice no está vigente respecto de data/ (o no se pudo leer)."
            " La corrida usaría un corpus distinto del declarado en el informe."
        )

    clave, llm = seleccionar_modelo(args.modelo)
    temperatura = temperatura_del_proveedor(clave)

    if args.variante == "rag":
        from backend.rag.service import RAGService

        servicio = RAGService()

        def ejecutar(caso, repeticion):
            return ejecutar_caso_rag(caso, servicio, clave, repeticion)

    else:

        def ejecutar(caso, repeticion):
            return ejecutar_caso_sin_contexto(caso, llm, clave, repeticion)

    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug_modelo = re.sub(r"[^a-z0-9]+", "-", clave.lower()).strip("-")[:24]
    run_id = args.salida or f"{args.variante}_{slug_modelo}_{marca}"

    print("=" * 78)
    print(f"CORRIDA {run_id}")
    print(f"  variante={args.variante}  modelo={clave}  casos={len(casos)}  "
          f"repeticiones={args.repeticiones}")
    print(f"  commit={entorno_info.get('commit_corto')}  chunks={corpus.get('chunks')}")
    print("=" * 78)

    iniciado = datetime.now(timezone.utc)
    resultados: list[dict[str, Any]] = []
    DIR_RESULTADOS.mkdir(parents=True, exist_ok=True)
    ruta_json = DIR_RESULTADOS / f"{run_id}.json"
    ruta_csv = DIR_RESULTADOS / f"{run_id}.csv"

    def guardar(terminado: Optional[datetime] = None) -> None:
        """Escribe la evidencia tal como está en este momento.

        Se llama después de CADA caso, no solo al final: una corrida larga
        (decenas de llamadas a la nube) puede interrumpirse —cierre de la
        terminal, límite de tiempo, corte de red— y perder todo el trabajo
        hecho. Con el guardado incremental, lo ejecutado queda en disco.
        """
        fin = terminado or datetime.now(timezone.utc)
        documento = {
            "run_id": run_id,
            "variante": args.variante,
            "iniciado_en": iniciado.isoformat(timespec="seconds"),
            "terminado_en": None if terminado is None else fin.isoformat(timespec="seconds"),
            "parcial": terminado is None,
            "duracion_s": round((fin - iniciado).total_seconds(), 1),
            "config": {
                "modelo_solicitado": args.modelo or "(prioridad por defecto)",
                "modelo_usado": clave,
                "temperature": temperatura,
                "repeticiones": args.repeticiones,
                "solo_estabilidad": bool(args.solo_estabilidad),
                "pausa_s": args.pausa,
                "medir_tokens": args.variante == "rag",
                "ids": args.ids,
                "limite": args.limite,
            },
            "entorno": entorno_info,
            "casos": resultados,
        }
        ruta_json.write_text(
            json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with open(ruta_csv, "w", newline="", encoding="utf-8") as fh:
            escritor = csv.DictWriter(fh, fieldnames=COLUMNAS_CSV)
            escritor.writeheader()
            for caso in resultados:
                for registro in caso["repeticiones"]:
                    escritor.writerow(_fila_csv(caso, registro))

    for i, caso in enumerate(casos, 1):
        repeticiones = 1
        if args.repeticiones > 1:
            repeticiones = args.repeticiones if (not args.solo_estabilidad or caso.get("estabilidad")) else 1
        registros: list[dict[str, Any]] = []
        for rep in range(1, repeticiones + 1):
            try:
                registro = _con_reintentos(
                    lambda: ejecutar(caso, rep), intentos=args.reintentos
                )
            except Exception as e:  # noqa: BLE001
                registro = _registro_error(f"{type(e).__name__}: {e}", rep)
                print(f"  ✖ {caso['id']} rep {rep}: {registro['error']}")
            registros.append(registro)

        nivel = registros[0].get("nivel_final") if registros else None
        esperado = caso.get("nivel_esperado")
        marca_acierto = ""
        if esperado and nivel:
            marca_acierto = "✔" if nivel == esperado else "✖"
        print(
            f"  [{i:>2}/{len(casos)}] {caso['id']:<5} final={str(nivel):<9} "
            f"esperado={str(esperado):<9} {marca_acierto} "
            f"t={registros[0].get('tiempo_respuesta')}s"
        )

        resultados.append(
            {
                "id": caso["id"],
                "titulo": caso["titulo"],
                "grupo": caso.get("_grupo_archivo"),
                "categoria": caso.get("categoria"),
                "edad": caso.get("edad"),
                "edad_meses": caso.get("edad_meses"),
                "sexo": caso.get("sexo"),
                "vitales": caso.get("vitales"),
                "descripcion": caso["descripcion"],
                "nivel_esperado": esperado,
                "nivel_permitido": caso.get("nivel_permitido") or [],
                "fuentes_esperadas": caso.get("fuentes_esperadas") or [],
                "detectores": caso.get("detectores") or [],
                "criterios": caso.get("criterios") or {},
                "repeticiones": registros,
            }
        )
        # Guardado incremental tras cada caso (ver docstring de `guardar`).
        guardar()
        if args.pausa and i < len(casos):
            time.sleep(args.pausa)

    terminado = datetime.now(timezone.utc)
    guardar(terminado)
    documento = json.loads(ruta_json.read_text(encoding="utf-8"))

    errores = sum(
        1 for c in resultados for r in c["repeticiones"] if r.get("error")
    )
    print()
    print(f"Evidencia cruda: {_relativa(ruta_json)}")
    print(f"Tabla por caso : {_relativa(ruta_csv)}")
    print(f"Errores        : {errores}")
    print(f"Duración       : {documento['duracion_s']} s")
    print(f"\nPara calcular las métricas: python scripts/evaluar.py informe {ruta_json.name}")
    return 0


# ---------------------------------------------------------------------------
# Veredictos y métricas (se calculan en `informe`: no gastan llamadas)
# ---------------------------------------------------------------------------


def _contexto_recuperado(registro: dict[str, Any]) -> str:
    """Texto de referencia para comprobar dosis y citas.

    Se usan las PÁGINAS completas de los chunks recuperados (no solo los 300
    caracteres de vista previa del registro): comprobar una cita contra más
    texto es más permisivo, así que un fallo indica de verdad que el contenido
    no estaba en el material recuperado. Es la opción conservadora: nunca acusa
    de inventar algo que sí estaba en la norma.
    """
    partes: list[str] = []
    vistas: set[tuple[str, str]] = set()
    for rec in registro.get("recuperaciones") or []:
        partes.append(rec.get("preview") or "")
        archivo, pagina = rec.get("archivo"), rec.get("page_label")
        if archivo and pagina and (archivo, pagina) not in vistas:
            vistas.add((archivo, pagina))
            partes.append(texto_de_pagina(archivo, pagina))
    return normalizar_ws(" ".join(partes))


def _material_entregado(registro: dict[str, Any]) -> str:
    """Todo el texto que el modelo tuvo delante: su prompt y las páginas recuperadas.

    El detector comparaba las citas solo contra los fragmentos recuperados, y eso
    produjo falsos positivos comprobados en una corrida real: los modelos
    entrecomillan los datos del propio paciente ("se le hunden las costillas",
    "SpO₂: 92.0 %") y la línea de plantilla de la respuesta ("Manejo y
    observación en la posta rural"). Nada de eso es inventar: estaba en el
    prompt. Anclar contra el material entregado sigue detectando contenido
    inventado (páginas inexistentes, dosis o párrafos que nunca se entregaron)
    sin acusar a la forma de citar.
    """
    partes = [registro.get("prompt_utilizado") or "", _contexto_recuperado(registro)]
    return normalizar_ws(" ".join(partes))


def _cita_anclada(cita: str, contexto_normalizado: str) -> bool:
    """Comprueba si una cita entre comillas se apoya en el material recuperado.

    Se comprobó con respuestas reales que exigir una ventana textual exacta
    produce falsos positivos: los modelos citan contenido recuperado con
    elipsis ("Intubación oral… Administrar oxígeno…") o lo parafrasean entre
    comillas, y también entrecomillan los datos del propio paciente. Una cita se
    considera anclada si CUALQUIERA de sus fragmentos (separados por elipsis)
    cumple alguna de estas dos condiciones:

    1. contiene una ventana textual exacta de 5 palabras del contexto; o
    2. al menos el 80 % de sus palabras significativas (>= 5 letras) aparecen en
       el contexto, lo que tolera paráfrasis sin aceptar contenido nuevo.

    Es una comprobación conservadora a propósito: su objetivo es detectar
    contenido que NO está en la norma (páginas inexistentes, dosis o párrafos
    inventados), no castigar la forma de citar.
    """
    fragmentos = [f for f in re.split(r"[.…]{2,}|\s\.\.\.\s", cita) if f.strip()]
    evaluables = 0
    for fragmento in fragmentos:
        # Las palabras se extraen sin puntuación: una cita como "Intubación,
        # cricotiroidotomía, administrar oxígeno" dejaría las comas pegadas al
        # token y ninguna palabra coincidiría con el contexto por un signo de
        # puntuación (falso positivo comprobado en una corrida real).
        palabras = re.findall(r"[a-z0-9]+", normalizar_ws(fragmento))
        if len(palabras) < 5:
            continue
        evaluables += 1
        for i in range(len(palabras) - 4):
            if " ".join(palabras[i : i + 5]) in contexto_normalizado:
                return True
        significativas = [p for p in palabras if len(p) >= 5]
        if not significativas:
            continue
        presentes = sum(1 for p in significativas if p in contexto_normalizado)
        if presentes / len(significativas) >= 0.8:
            return True
    # Sin fragmentos evaluables (cita muy corta) no hay señal suficiente: no se
    # acusa de no estar anclada.
    return evaluables == 0


def _paginas_no_recuperadas(
    texto: str, registro: dict[str, Any], universo: dict[str, set[str]]
) -> list[str]:
    """Páginas citadas que existe en el corpus pero NO se recuperaron.

    Señal de anclaje (no de invención): una cita a una página que el modelo
    nunca recibió no está respaldada por el material que tuvo delante. Se
    informa aparte y NO cuenta para el veredicto de alucinación, porque un chunk
    recuperado puede mencionar otras páginas de la propia norma.
    """
    todas: set[str] = set()
    for archivo in universo.values():
        todas |= archivo
    recuperadas = {
        str(rec.get("page_label"))
        for rec in registro.get("recuperaciones") or []
        if rec.get("page_label")
    }
    sospechosas: list[str] = []
    for coincidencia in RE_PAGINA.finditer(texto):
        pagina = coincidencia.group(1)
        if pagina in todas and pagina not in recuperadas:
            sospechosas.append(pagina)
    return sorted(set(sospechosas), key=int)


def _dosis_inventadas(texto: str, contexto_normalizado: str) -> list[str]:
    """Dosis enunciadas en la respuesta que no figuran en el contexto."""
    inventadas: list[str] = []
    for coincidencia in RE_DOSIS.finditer(normalizar_ws(texto)):
        # La dosis encontrada también se colapsa: si el extractor dejó un tab
        # entre la cifra y la unidad, compararla sin colapsar la declararía
        # inventada aunque estuviera en la norma.
        dosis = re.sub(r"\s+", " ", coincidencia.group()).strip()
        if dosis not in contexto_normalizado:
            inventadas.append(dosis)
    return inventadas


def _paginas_inexistentes(texto: str, universo: dict[str, set[str]]) -> list[str]:
    """Números de página citados que no existen en ningún documento del corpus."""
    todas: set[str] = set()
    for paginas in universo.values():
        todas |= paginas
    if not todas:
        return []
    citadas = set()
    for coincidencia in RE_PAGINA.finditer(texto):
        numero = coincidencia.group(1)
        if numero not in todas:
            citadas.add(numero)
    return sorted(citadas, key=int)


def evaluar_registro(caso: dict[str, Any], registro: dict[str, Any], universo) -> dict[str, Any]:
    """Veredictos automáticos de un registro: nivel, recuperación y alucinación."""
    veredicto: dict[str, Any] = {}
    esperado = caso.get("nivel_esperado")
    permitido = caso.get("nivel_permitido") or []
    final = registro.get("nivel_final")
    llm = registro.get("nivel_llm")
    reglas = registro.get("nivel_reglas")

    # --- Nivel de urgencia ---
    veredicto["evaluable_nivel"] = bool(esperado)
    if esperado and final:
        desvio = POSICION[final] - POSICION[esperado]
        veredicto.update(
            {
                "coincide_exacto": desvio == 0,
                "coincide_permitido": final in permitido if permitido else desvio == 0,
                "desvio": desvio,
                "desvio_abs_1": abs(desvio) <= 1,
                "sub_triaje": desvio < 0,
                "supra_triaje": desvio > 0,
            }
        )
    elif esperado and final is None:
        veredicto.update(
            {
                "coincide_exacto": False,
                "coincide_permitido": False,
                "desvio": None,
                "desvio_abs_1": False,
                "sub_triaje": False,
                "supra_triaje": False,
                "sin_clasificar": True,
            }
        )

    # --- Atribución: ¿decidió el LLM o las reglas? ---
    if llm and reglas:
        veredicto["reglas_elevaron"] = POSICION[reglas] > POSICION[llm]
        if esperado:
            veredicto["elevacion_correcta"] = (
                POSICION[reglas] > POSICION[llm] and reglas == esperado
            )
            veredicto["elevacion_espuria"] = (
                POSICION[reglas] > POSICION[llm] and POSICION[reglas] > POSICION[esperado]
            )

    # --- Recuperación ---
    fuentes = caso.get("fuentes_esperadas") or []
    recuperaciones = registro.get("recuperaciones") or []
    if fuentes and recuperaciones:
        paginas_gold = {(f.get("archivo"), str(f.get("page_label"))) for f in fuentes}
        docs_gold = {f.get("archivo") for f in fuentes}
        for k in K_RECALL:
            top = recuperaciones[:k]
            veredicto[f"recall_{k}_pagina"] = any(
                (r.get("archivo"), str(r.get("page_label"))) in paginas_gold for r in top
            )
            veredicto[f"recall_{k}_documento"] = any(
                r.get("archivo") in docs_gold for r in top
            )
        top5 = recuperaciones[:K_PRECISION]
        veredicto["precision_5_pagina"] = sum(
            1 for r in top5 if (r.get("archivo"), str(r.get("page_label"))) in paginas_gold
        ) / max(len(top5), 1)
        veredicto["precision_5_documento"] = sum(
            1 for r in top5 if r.get("archivo") in docs_gold
        ) / max(len(top5), 1)
        rango = next(
            (
                r["rank"]
                for r in recuperaciones
                if (r.get("archivo"), str(r.get("page_label"))) in paginas_gold
                or r.get("archivo") in docs_gold
            ),
            None,
        )
        veredicto["mrr"] = 0.0 if rango is None else 1.0 / rango

    # --- Criterios automáticos ---
    texto = registro.get("respuesta") or ""
    contexto = _material_entregado(registro)
    criterios = caso.get("criterios") or {}
    faltantes = [
        patron
        for patron in criterios.get("debe_incluir") or []
        if not re.search(patron, normalizar_ws(texto))
    ]
    violaciones = []
    for patron in criterios.get("no_debe_incluir") or []:
        clausula = hallazgo_afirmado(texto, patron)
        if clausula:
            violaciones.append({"patron": patron, "clausula": clausula[:200]})
    veredicto["criterios_faltantes"] = faltantes
    veredicto["criterios_violados"] = violaciones

    # --- Detectores de alucinación ---
    detectores = caso.get("detectores") or []
    dosis = _dosis_inventadas(texto, contexto) if "dosis_inventada" in detectores else []
    citas = [
        cita.strip()
        for cita in RE_CITA.findall(texto)
        if not _cita_anclada(cita, contexto)
    ]
    paginas = _paginas_inexistentes(texto, universo) if "cita_no_anclada" in detectores else []
    veredicto["dosis_inventadas"] = dosis
    veredicto["citas_no_ancladas"] = citas
    veredicto["paginas_inexistentes"] = paginas
    veredicto["paginas_no_recuperadas"] = _paginas_no_recuperadas(texto, registro, universo)

    falta_ausencia = False
    if "entidad_inventada" in detectores:
        falta_ausencia = not RE_AUSENCIA.search(normalizar_ws(texto))
    veredicto["no_declara_ausencia"] = falta_ausencia

    contradiccion_no_reconocida = False
    if "contradiccion_no_reconocida" in detectores:
        contradiccion_no_reconocida = bool(faltantes)
    veredicto["contradiccion_no_reconocida"] = contradiccion_no_reconocida

    # ¿Declaró que el material no cubre lo que se le pide? Se informa aparte del
    # veredicto de alucinación: callar el límite es un fallo de COMPLETITUD
    # (comprobado en A-02, donde el fármaco preguntado nunca se menciona), no una
    # invención.
    veredicto["declara_limite"] = bool(RE_AUSENCIA.search(normalizar_ws(texto)))

    #: Veredicto global de alucinación: contenido inventado o afirmado en contra
    #: de los criterios del caso, citas que no existen o contradicción no
    #: reconocida. Es una señal automática y conservadora; no sustituye la
    #: lectura clínica (se informa caso por caso).
    veredicto["alucinacion"] = bool(
        violaciones or dosis or citas or paginas or falta_ausencia or contradiccion_no_reconocida
    )
    veredicto["sin_clasificar"] = veredicto.get("sin_clasificar", final is None)
    return veredicto


def _percentil(valores: list[float], p: float) -> Optional[float]:
    """Percentil simple (interpolación por rango), sin dependencias externas."""
    if not valores:
        return None
    ordenados = sorted(valores)
    indice = max(0, min(len(ordenados) - 1, math.ceil(p * len(ordenados)) - 1))
    return ordenados[indice]


def agregar(documentos: list[dict[str, Any]]) -> dict[str, Any]:
    """Calcula todas las métricas del Componente 2 a partir de las corridas.

    Es una función pura sobre la evidencia guardada: si mañana se corrige la
    definición de una métrica, basta con volver a ejecutar `informe` sin gastar
    una sola llamada a los modelos.
    """
    universo = universo_paginas()
    resultado: dict[str, Any] = {"variantes": [], "universo_paginas": {k: len(v) for k, v in universo.items()}}

    for documento in documentos:
        variante = {
            "run_id": documento.get("run_id"),
            "variante": documento.get("variante"),
            "config": documento.get("config"),
            "entorno": documento.get("entorno"),
            "duracion_s": documento.get("duracion_s"),
            "parcial": bool(documento.get("parcial")),
            "casos": [],
        }

        for caso in documento.get("casos", []):
            evaluables = [
                {**evaluar_registro(caso, registro, universo), "_registro": registro}
                for registro in caso.get("repeticiones", [])
                if not registro.get("error")
            ]
            errores = [r for r in caso.get("repeticiones", []) if r.get("error")]
            variante["casos"].append(
                {
                    "id": caso.get("id"),
                    "titulo": caso.get("titulo"),
                    "grupo": caso.get("grupo"),
                    "categoria": caso.get("categoria"),
                    "nivel_esperado": caso.get("nivel_esperado"),
                    "nivel_permitido": caso.get("nivel_permitido") or [],
                    "niveles_finales": [
                        v["_registro"].get("nivel_final") for v in evaluables
                    ],
                    # Los tiempos y tokens viven en el registro crudo: el veredicto
                    # los envuelve bajo `_registro`.
                    "tiempos": [
                        v["_registro"].get("tiempo_respuesta")
                        for v in evaluables
                        if v["_registro"].get("tiempo_respuesta")
                    ],
                    "tokens": [
                        v["_registro"].get("tokens_consumidos")
                        for v in evaluables
                        if v["_registro"].get("tokens_consumidos")
                    ],
                    "veredictos": evaluables,
                    "errores": errores,
                    # Recuento explícito: la comparación entre variantes necesita
                    # saber qué casos respondió cada una sin volver a mirar la
                    # evidencia cruda.
                    "n_exitosos": len(evaluables),
                    "n_errores": len(errores),
                }
            )
        resultado["variantes"].append(variante)
    return resultado


def resumen_variante(variante: dict[str, Any]) -> dict[str, Any]:
    """Agrega los veredictos de una variante en los indicadores del informe."""
    casos = variante["casos"]
    regs = [v for c in casos for v in c["veredictos"]]
    niveles = [r for r in regs if r.get("evaluable_nivel")]

    resumen: dict[str, Any] = {
        "n_casos": len(casos),
        "n_registros": len(regs),
        "n_errores": sum(len(c["errores"]) for c in casos),
        "nivel_evaluables": len(niveles),
        "exactos": sum(1 for r in niveles if r.get("coincide_exacto")),
        "en_permitido": sum(1 for r in niveles if r.get("coincide_permitido")),
        "desvio_abs_1": sum(1 for r in niveles if r.get("desvio_abs_1")),
        "sub_triaje": sum(1 for r in niveles if r.get("sub_triaje")),
        "supra_triaje": sum(1 for r in niveles if r.get("supra_triaje")),
        "sin_clasificar": sum(1 for r in niveles if r.get("sin_clasificar")),
        "reglas_elevaron": sum(1 for r in regs if r.get("reglas_elevaron")),
        "elevacion_correcta": sum(1 for r in regs if r.get("elevacion_correcta")),
        "elevacion_espuria": sum(1 for r in regs if r.get("elevacion_espuria")),
        "alucinaciones": sum(1 for r in regs if r.get("alucinacion")),
        "alucinaciones_anti": sum(
            1
            for c in casos
            if c["grupo"] == "anti_alucinacion"
            for v in c["veredictos"]
            if v.get("alucinacion")
        ),
        "n_anti": sum(1 for c in casos if c["grupo"] == "anti_alucinacion"),
    }

    # Recuperación: solo sobre casos con fuente esperada y recuperaciones.
    for clave in (
        "recall_3_pagina",
        "recall_5_pagina",
        "recall_3_documento",
        "recall_5_documento",
    ):
        valores = [r[clave] for r in regs if clave in r]
        resumen[f"{clave}_n"] = len(valores)
        resumen[clave] = (sum(1 for v in valores if v) / len(valores)) if valores else None
    for clave in ("precision_5_pagina", "precision_5_documento", "mrr"):
        valores = [r[clave] for r in regs if clave in r]
        resumen[f"{clave}_media"] = (sum(valores) / len(valores)) if valores else None
        resumen[f"{clave}_n"] = len(valores)

    tiempos = [t for c in casos for t in c["tiempos"]]
    resumen["latencia_media"] = (sum(tiempos) / len(tiempos)) if tiempos else None
    resumen["latencia_mediana"] = _percentil(tiempos, 0.5)
    resumen["latencia_p95"] = _percentil(tiempos, 0.95)
    resumen["latencia_min"] = min(tiempos) if tiempos else None
    resumen["latencia_max"] = max(tiempos) if tiempos else None

    tokens = [t for c in casos for t in c["tokens"]]
    resumen["tokens_medidos"] = len(tokens)
    resumen["tokens_media"] = (sum(tokens) / len(tokens)) if tokens else None
    resumen["tokens_total"] = sum(tokens) if tokens else None

    # Estabilidad: casos con más de una repetición ejecutada con éxito.
    estables = inestables = 0
    detalle_inestables = []
    for caso in casos:
        niveles_rep = [n for n in caso["niveles_finales"] if n]
        if len(niveles_rep) < 2:
            continue
        if len(set(niveles_rep)) == 1:
            estables += 1
        else:
            inestables += 1
            detalle_inestables.append({"id": caso["id"], "niveles": niveles_rep})
    resumen["estables"] = estables
    resumen["inestables"] = inestables
    resumen["detalle_inestables"] = detalle_inestables
    return resumen


# ---------------------------------------------------------------------------
# Subcomando: informe
# ---------------------------------------------------------------------------


def _pct(valor: Optional[float]) -> str:
    return "—" if valor is None else f"{100 * valor:.1f} %"


def _num(valor: Optional[float], dec: int = 2) -> str:
    return "—" if valor is None else f"{valor:.{dec}f}"


def _tasa(numerador: Optional[int], denominador: Optional[int]) -> str:
    if not denominador:
        return "—"
    return f"{100 * (numerador or 0) / denominador:.1f} %"


def _matriz_confusion(casos: list[dict[str, Any]]) -> list[str]:
    """Matriz de confusión 5×5 (nivel esperado × nivel final)."""
    filas = [f"| Esperado \\ Final | {' | '.join(NIVELES)} | Total |", "|---|---|---|---|---|---|---|"]
    for esperado in reversed(NIVELES):
        conteo = {n: 0 for n in NIVELES}
        total = 0
        for caso in casos:
            if caso.get("nivel_esperado") != esperado:
                continue
            for v in caso["veredictos"]:
                final = v["_registro"].get("nivel_final")
                if final in conteo:
                    conteo[final] += 1
                total += 1
        filas.append(
            f"| **{esperado}** | "
            + " | ".join(str(conteo[n]) for n in NIVELES)
            + f" | {total} |"
        )
    return filas


def _tabla_por_categoria(casos: list[dict[str, Any]]) -> list[str]:
    categorias: dict[str, dict[str, int]] = {}
    for caso in casos:
        cat = caso.get("categoria") or "sin categoría"
        datos = categorias.setdefault(cat, {"n": 0, "exactos": 0, "tolerantes": 0, "alucinaciones": 0})
        for v in caso["veredictos"]:
            if v.get("evaluable_nivel"):
                datos["n"] += 1
                datos["exactos"] += 1 if v.get("coincide_exacto") else 0
                datos["tolerantes"] += 1 if v.get("coincide_permitido") else 0
            datos["alucinaciones"] += 1 if v.get("alucinacion") else 0
    filas = [
        "| Categoría | Casos evaluables | Exactos | En rango permitido | Alucinaciones |",
        "|---|---|---|---|---|",
    ]
    for cat, datos in sorted(categorias.items()):
        filas.append(
            f"| {cat} | {datos['n']} | {_tasa(datos['exactos'], datos['n'])} | "
            f"{_tasa(datos['tolerantes'], datos['n'])} | {datos['alucinaciones']} |"
        )
    return filas


def _tabla_casos(caso: dict[str, Any], resumen_v: dict[str, Any]) -> list[str]:
    """Anexo: una fila por caso con lo observado y los criterios incumplidos."""
    filas = [
        "| Caso | Esperado | Final | Veredicto | t (s) | Recuperación | Criterios |",
        "|---|---|---|---|---|---|---|",
    ]
    for caso in resumen_v["casos"]:
        for i, v in enumerate(caso["veredictos"], 1):
            reg = v["_registro"]
            esperado = caso["nivel_esperado"] or "—"
            final = reg.get("nivel_final") or "sin clasificar"
            if v.get("evaluable_nivel"):
                if v.get("coincide_exacto"):
                    marca = "✔"
                elif v.get("coincide_permitido"):
                    marca = "≈ (en rango)"
                elif v.get("sub_triaje"):
                    marca = "✖ sub-triage"
                elif v.get("supra_triaje"):
                    marca = "✖ supra-triage"
                else:
                    marca = "✖"
            else:
                marca = "—"
            recs = reg.get("recuperaciones") or []
            recuperacion = ""
            if recs:
                top = recs[0]
                paginas_gold = {
                    (f.get("archivo"), str(f.get("page_label"))) for f in (caso.get("fuentes_esperadas") or [])
                }
                aciertos = sum(
                    1
                    for r in recs[:K_RECALL[-1]]
                    if (r.get("archivo"), str(r.get("page_label"))) in paginas_gold
                )
                recuperacion = f"{top.get('archivo')} p.{top.get('page_label')} ({_num(top.get('score'), 3)}); gold en top5={aciertos}"
            incidencias = []
            if v.get("criterios_faltantes"):
                incidencias.append(f"falta: {', '.join(v['criterios_faltantes'])}")
            for viol in v.get("criterios_violados") or []:
                incidencias.append(f"prohibido: /{viol['patron']}/")
            if v.get("dosis_inventadas"):
                incidencias.append(f"dosis sin respaldo: {', '.join(v['dosis_inventadas'])}")
            if v.get("citas_no_ancladas"):
                incidencias.append(f"cita no anclada: \"{v['citas_no_ancladas'][0][:60]}…\"")
            if v.get("paginas_inexistentes"):
                incidencias.append(f"página inexistente: {', '.join(v['paginas_inexistentes'])}")
            if v.get("paginas_no_recuperadas"):
                incidencias.append(
                    f"página citada no recuperada: {', '.join(v['paginas_no_recuperadas'])}"
                )
            if v.get("no_declara_ausencia"):
                incidencias.append("no declara la ausencia")
            if v.get("contradiccion_no_reconocida"):
                incidencias.append("no reconoce la contradicción")
            if reg.get("reglas_activadas"):
                incidencias.append("reglas: " + "; ".join(reg["reglas_activadas"])[:80])
            if reg.get("error"):
                incidencias.append(f"ERROR: {reg['error'][:60]}")
            sufijo = f" (rep {i})" if len(caso["veredictos"]) > 1 else ""
            filas.append(
                f"| {caso['id']}{sufijo} | {esperado} | {final} | {marca} | "
                f"{_num(reg.get('tiempo_respuesta'), 2)} | {recuperacion or '—'} | "
                f"{'; '.join(incidencias) or '—'} |"
            )
    return filas


def _bloque_indicadores(resumenes: list[tuple[str, dict[str, Any]]]) -> list[str]:
    """Cumplimiento explícito de los indicadores de aceptación del C2."""
    lineas = [
        "| Indicador | Criterio | Resultado | Cumple |",
        "|---|---|---|---|",
    ]
    for nombre, r in resumenes:
        total_anti = r.get("n_anti") or 0
        tasa_aluc = (r.get("alucinaciones_anti", 0) / total_anti) if total_anti else None
        cumple = "✔" if (tasa_aluc is not None and tasa_aluc < 0.15) else "✖"
        lineas.append(
            f"| Tasa de alucinaciones ({nombre}) | < 15 % sobre los {total_anti} casos anti-alucinación | "
            f"{_pct(tasa_aluc)} | {cumple} |"
        )
    lineas.append(
        "| Casos en Bueno/Muy bueno (C2.A4) | ≥ 80 % | pendiente: requiere el médico colaborador "
        "(ver `evaluacion/instrumentos/`) | ⏳ |"
    )
    return lineas


def fusionar_corridas(documentos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Une en un solo experimento las corridas del mismo variante y modelo.

    Una corrida de 30 casos con latencias de decenas de segundos no cabe en una
    sola ejecución de terminal, así que se hace por lotes con `--ids`. Para el
    informe, los lotes del mismo experimento son UNA variante: si no se
    fusionaran, la tabla comparativa mostraría tres columnas del mismo sistema.

    Si un caso aparece en dos lotes, se conserva el registro exitoso (el error
    de un lote anterior se descarta cuando el siguiente lote sí respondió).
    """
    grupos: dict[tuple, dict[str, Any]] = {}
    orden: list[tuple] = []

    for documento in documentos:
        clave = (
            documento.get("variante"),
            (documento.get("config") or {}).get("modelo_usado"),
        )
        if clave not in grupos:
            grupos[clave] = {
                "run_id": [],
                "variante": documento.get("variante"),
                "config": documento.get("config"),
                "entorno": documento.get("entorno"),
                "duracion_s": 0.0,
                "parcial": False,
                "casos": [],
                "_por_id": {},
            }
            orden.append(clave)
        grupo = grupos[clave]
        grupo["run_id"].append(documento.get("run_id"))
        grupo["duracion_s"] = round(
            grupo["duracion_s"] + (documento.get("duracion_s") or 0), 1
        )
        if documento.get("parcial"):
            grupo["parcial"] = True

        for caso in documento.get("casos") or []:
            exitosos = [r for r in caso.get("repeticiones", []) if not r.get("error")]
            previo = grupo["_por_id"].get(caso["id"])
            if previo is None:
                grupo["casos"].append(caso)
                grupo["_por_id"][caso["id"]] = caso
            elif exitosos:
                # El lote nuevo respondió: reemplaza los errores del anterior.
                previo["repeticiones"] = exitosos

    salida = []
    for clave in orden:
        grupo = grupos[clave]
        grupo["run_id"] = " + ".join(grupo["run_id"])
        grupo.pop("_por_id")
        salida.append(grupo)
    return salida


def _resolver_ruta_resultado(nombre: str) -> Path:
    """Resuelve un nombre de corrida al archivo JSON, con o sin extensión.

    Acepta la ruta completa, el nombre del archivo o solo el identificador de la
    corrida (`rag_groq_20260924-1530`), que es como lo imprime `correr`.
    """
    candidatos = [Path(nombre)]
    if not Path(nombre).is_absolute():
        candidatos.append(DIR_RESULTADOS / nombre)
        candidatos.append(DIR_RESULTADOS / f"{nombre}.json")
    for candidato in candidatos:
        if candidato.exists() and candidato.suffix == ".json":
            return candidato
    raise SystemExit(f"❌ No se encontró el resultado: {nombre}")


def comando_informe(args) -> int:
    rutas = [_resolver_ruta_resultado(nombre) for nombre in args.runs]
    _ = args.fusionar

    documentos = [json.loads(r.read_text(encoding="utf-8")) for r in rutas]
    if args.fusionar and len(documentos) > 1:
        # Los lotes del mismo experimento se presentan como una sola variante.
        documentos = fusionar_corridas(documentos)
    limpio = agregar(documentos)
    resumenes = [
        (v["run_id"], resumen_variante(v)) for v in limpio["variantes"]
    ]

    lineas: list[str] = []
    primero = documentos[0]
    entorno_info = primero.get("entorno") or {}
    corpus = entorno_info.get("corpus") or {}

    lineas.append(f"# Evaluación del sistema de triaje (Componente 2){' — ' + args.titulo if args.titulo else ''}")
    lineas.append("")
    lineas.append(
        "Informe generado automáticamente por `scripts/evaluar.py informe` a partir de las "
        "corridas registradas. Todas las cifras provienen de la evidencia cruda guardada en "
        "`evaluacion/resultados/`: se pueden auditar caso por caso."
    )
    lineas.append("")

    # --- 1. Resumen ejecutivo ---
    lineas.append("## 1. Resumen ejecutivo")
    lineas.append("")
    lineas.append(
        "| Variante | Casos | Exactitud del nivel | En rango permitido | Sub-triage | "
        "Supra-triage | Alucinaciones (anti) | Latencia media |"
    )
    lineas.append("|---|---|---|---|---|---|---|---|")
    for nombre, r in resumenes:
        lineas.append(
            f"| {nombre} | {r['n_casos']} | {_tasa(r['exactos'], r['nivel_evaluables'])} | "
            f"{_tasa(r['en_permitido'], r['nivel_evaluables'])} | {r['sub_triaje']} | "
            f"{r['supra_triaje']} | {r['alucinaciones_anti']}/{r['n_anti']} | "
            f"{_num(r['latencia_media'], 2)} s |"
        )
    lineas.append("")
    lineas.append("**Cumplimiento de los indicadores del Componente 2**")
    lineas.append("")
    lineas += _bloque_indicadores([(n, r) for n, r in resumenes])
    lineas.append("")

    # --- 2. Metodología ---
    lineas.append("## 2. Metodología")
    lineas.append("")
    lineas.append(
        "Se ejecutan los mismos 30 casos (20 clínicos y 10 anti-alucinación) contra cada "
        "variante del sistema. En **rag**, el caso pasa por el sistema completo: reglas "
        "deterministas de seguridad + recuperación vectorial de las NNAC + LLM. En "
        "**sin-contexto**, el MISMO prompt y las MISMAS reglas se aplican sin fragmentos "
        "recuperados: es la línea base que mide cuánto aporta el componente RAG."
    )
    lineas.append("")
    lineas.append("Definición operativa de cada métrica:")
    lineas.append("")
    lineas.append(
        "- **Exactitud del nivel**: proporción de casos en que el nivel final (el más urgente "
        "entre LLM y reglas) coincide con el nivel esperado del caso."
    )
    lineas.append(
        "- **En rango permitido**: el nivel final cae dentro del rango clínicamente aceptable "
        "declarado en el caso, que reconoce las zonas grises de la clasificación Manchester."
    )
    lineas.append(
        "- **Sub-triage**: el sistema clasificó con MENOS urgencia que la esperada. Es el error "
        "clínicamente grave (paciente que no recibe atención a tiempo)."
    )
    lineas.append(
        "- **Supra-triage**: clasificó con MÁS urgencia que la esperada. No pone en riesgo al "
        "paciente, pero consume recursos y genera alarmas falsas."
    )
    lineas.append(
        "- **Recall@3 y Recall@5**: al menos un chunk de la fuente esperada aparece entre los "
        "3 o 5 chunks mejor puntuados. **Precision@5**: fracción de los 5 chunks recuperados "
        "que provienen de la fuente esperada. **MRR**: recíproco de la posición del primer "
        "chunk relevante. Se calculan a nivel de página (principal) y de documento (secundario)."
    )
    lineas.append(
        "- **Tasa de alucinación**: proporción de casos anti-alucinación en que la respuesta "
        "inventa contenido: afirma algo prohibido por el caso, enuncia una dosis que no está "
        "en el **material entregado al modelo** (contexto recuperado, datos del paciente del "
        "caso y plantilla del prompt), entrecomilla texto que no se le entregó, no declara la "
        "ausencia de una entidad inexistente, cita una página que no existe o no reconoce una "
        "contradicción clínica. Comparar contra todo lo entregado —y no solo contra los "
        "fragmentos recuperados— evita acusar de inventar a quien repite los datos del propio "
        "paciente o la plantilla de su respuesta."
    )
    lineas.append(
        "- **Latencia**: tiempo alrededor de la consulta (recuperación + generación), medido "
        "en la máquina de la corrida; los tokens son los que reporta el proveedor del LLM."
    )
    lineas.append(
        "- **Estabilidad**: proporción de casos repetidos que conservan el mismo nivel en todas "
        "las repeticiones (mide determinismo, no acierto)."
    )
    lineas.append("")

    # --- 3. Configuración y trazabilidad ---
    lineas.append("## 3. Configuración del experimento y trazabilidad")
    lineas.append("")
    lineas.append("| Elemento | Valor |")
    lineas.append("|---|---|")
    lineas.append(f"| Commit evaluado | `{entorno_info.get('commit') or 'desconocido'}` |")
    lineas.append(
        f"| Árbol con cambios sin commitear | {'sí' if entorno_info.get('arbol_con_cambios_sin_commitear') else 'no'} |"
    )
    lineas.append(f"| Python / SO | {entorno_info.get('python')} · {entorno_info.get('so')} |")
    lineas.append(
        f"| Modelo de embeddings | `{entorno_info.get('embedding_model')}` |"
    )
    lineas.append(
        f"| Segmentación | chunk_size={entorno_info.get('chunk_size')} · chunk_overlap={entorno_info.get('chunk_overlap')} |"
    )
    lineas.append(
        f"| Corpus | {len(corpus.get('archivos') or [])} PDFs · {corpus.get('chunks')} chunks · "
        f"índice vigente: {'sí' if corpus.get('actualizado') else 'no'} |"
    )
    for archivo in corpus.get("archivos") or []:
        lineas.append(
            f"| · {archivo.get('nombre')} | {archivo.get('chunks')} chunks · sha256 `{str(archivo.get('sha256'))[:16]}…` |"
        )
    lineas.append(
        f"| Huellas de los casos | "
        + " · ".join(
            f"{n}={h[:12]}…" for n, h in (entorno_info.get("hashes_casos") or {}).items()
        )
        + " |"
    )
    for variante in limpio["variantes"]:
        cfg = variante.get("config") or {}
        # Una corrida interrumpida queda marcada: el informe no debe presentar
        # un lote incompleto como si fuera el experimento completo.
        parcial = " · **PARCIAL (interrumpida)**" if variante.get("parcial") else ""
        lineas.append(
            f"| Corrida `{variante['run_id']}` | modelo={cfg.get('modelo_usado')} · "
            f"temperature={cfg.get('temperature')} · repeticiones={cfg.get('repeticiones')} · "
            f"variante={variante.get('variante')} · casos={len(variante.get('casos') or [])} · "
            f"duración={variante.get('duracion_s')} s{parcial} |"
        )
    lineas.append("")
    li = entorno_info.get("pagina_maxima_por_archivo") or {}
    if li:
        lineas.append(
            "La verificación de citas usa el universo real del índice: páginas máximas "
            + ", ".join(f"{k}={v}" for k, v in li.items())
            + "."
        )
        lineas.append("")

    # --- 4. Resultados por variante ---
    seccion = 4
    for (nombre, r), variante in zip(resumenes, limpio["variantes"]):
        lineas.append(f"## {seccion}. Resultados de la variante `{nombre}`")
        lineas.append("")
        lineas.append(
            f"Casos ejecutados: {r['n_casos']} · registros: {r['n_registros']} · "
            f"errores de ejecución: {r['n_errores']}"
        )
        lineas.append("")
        lineas.append("### Nivel de urgencia")
        lineas.append("")
        lineas.append(
            f"- Exactitud (estricta): {_tasa(r['exactos'], r['nivel_evaluables'])} "
            f"({r['exactos']}/{r['nivel_evaluables']})"
        )
        lineas.append(
            f"- En rango clínicamente permitido: {_tasa(r['en_permitido'], r['nivel_evaluables'])} "
            f"({r['en_permitido']}/{r['nivel_evaluables']})"
        )
        lineas.append(
            f"- Desvío de a lo sumo un nivel: {_tasa(r['desvio_abs_1'], r['nivel_evaluables'])}"
        )
        lineas.append(
            f"- **Sub-triage (error grave): {r['sub_triaje']}** · "
            f"Supra-triage: {r['supra_triaje']} · Sin clasificar: {r['sin_clasificar']}"
        )
        lineas.append("")
        lineas.append("**Matriz de confusión (esperado × final)**")
        lineas.append("")
        lineas += _matriz_confusion(variante["casos"])
        lineas.append("")
        lineas.append("### Qué aporta la capa de reglas deterministas")
        lineas.append("")
        lineas.append(
            f"- Casos en que las reglas elevaron el nivel del LLM: {r['reglas_elevaron']}"
        )
        lineas.append(f"- De ésas, correctas: {r['elevacion_correcta']}")
        lineas.append(
            f"- De ésas, espurias (elevaron por encima del nivel esperado): {r['elevacion_espuria']}"
        )
        lineas.append("")
        lineas.append("### Recuperación")
        lineas.append("")
        if r.get("recall_5_pagina_n"):
            lineas.append(
                f"Sobre los {r['recall_5_pagina_n']} registros con fuente esperada declarada:"
            )
            lineas.append("")
            lineas.append("| Métrica | Nivel de página | Nivel de documento |")
            lineas.append("|---|---|---|")
            lineas.append(
                f"| Recall@3 | {_pct(r.get('recall_3_pagina'))} | {_pct(r.get('recall_3_documento'))} |"
            )
            lineas.append(
                f"| Recall@5 | {_pct(r.get('recall_5_pagina'))} | {_pct(r.get('recall_5_documento'))} |"
            )
            lineas.append(
                f"| Precision@5 | {_num(r.get('precision_5_pagina_media'), 3)} | "
                f"{_num(r.get('precision_5_documento_media'), 3)} |"
            )
            lineas.append(f"| MRR | {_num(r.get('mrr_media'), 3)} | (idem) |")
            lineas.append("")
            lineas.append(
                "Los casos clínicos sin fuente esperada (el corpus no cubre su condición) no "
                "participan de estas métricas y se informan aparte: son un hueco del corpus, "
                "no un error de recuperación."
            )
        else:
            lineas.append(
                "Esta variante no tiene recuperaciones: es la línea base sin contexto, por lo "
                "que las métricas de recuperación no aplican."
            )
        lineas.append("")
        lineas.append("### Latencia y tokens")
        lineas.append("")
        lineas.append(
            f"- Latencia: media {_num(r['latencia_media'], 2)} s · mediana "
            f"{_num(r['latencia_mediana'], 2)} s · p95 {_num(r['latencia_p95'], 2)} s · "
            f"mín {_num(r['latencia_min'], 2)} s · máx {_num(r['latencia_max'], 2)} s"
        )
        lineas.append(
            f"- Tokens: {r['tokens_medidos']} registros con medición del proveedor · "
            f"media {_num(r['tokens_media'], 1)} · total {_num(r['tokens_total'], 0)}"
        )
        if not r["tokens_medidos"]:
            lineas.append(
                "  (Ningún registro reportó tokens: el proveedor no expuso el bloque de uso en "
                "esta corrida. La cifra queda como no medida y no se estima.)"
            )
        lineas.append("")
        lineas.append("### Alucinaciones e invento de contenido")
        lineas.append("")
        lineas.append(
            f"Tasa global sobre los 30 casos: {r['alucinaciones']}/{r['n_registros']} "
            f"({_tasa(r['alucinaciones'], r['n_registros'])})"
        )
        lineas.append(
            f"Tasa sobre los casos anti-alucinación: {r['alucinaciones_anti']}/{r['n_anti']} "
            f"({_tasa(r['alucinaciones_anti'], r['n_anti'])})"
        )
        lineas.append("")
        lineas.append("**Desglose por categoría de caso**")
        lineas.append("")
        lineas += _tabla_por_categoria(variante["casos"])
        lineas.append("")
        lineas.append("### Estabilidad")
        lineas.append("")
        if r["estables"] or r["inestables"]:
            lineas.append(
                f"Casos con repeticiones: {r['estables'] + r['inestables']} · estables "
                f"(mismo nivel en todas las repeticiones): {r['estables']} · inestables: "
                f"{r['inestables']}"
            )
            for detalle in r["detalle_inestables"]:
                lineas.append(
                    f"  - {detalle['id']}: niveles observados {detalle['niveles']}"
                )
        else:
            lineas.append(
                "La corrida se hizo con una sola repetición por caso: para medir estabilidad hay "
                "que repetir con `--repeticiones 3 --solo-estabilidad`."
            )
        lineas.append("")
        seccion += 1

    # --- Comparación en el subconjunto comparable ---
    sistema = next(
        (v for v in limpio["variantes"] if v.get("variante") == "rag"), None
    )
    otros = [v for v in limpio["variantes"] if v is not sistema]
    if sistema is not None and otros:
        exitosos_sistema = {c["id"] for c in sistema["casos"] if c.get("n_exitosos")}
        lineas.append(f"## {seccion}. Comparación en el subconjunto comparable")
        lineas.append("")
        lineas.append(
            "Las líneas base no pudieron ejecutar los 30 casos (límites de cuota de los "
            "planes gratuitos de los proveedores). Para que la comparación siga siendo "
            "válida, se restringe a los casos que AMBAS variantes respondieron con éxito: "
            "comparar el 100 % de una contra el 60 % de la otra no mediría nada."
        )
        lineas.append("")
        lineas.append(
            "| Sistema | Casos en común | Sistema | Línea base | Δ exactitud | "
            "Alucinaciones (anti): sistema / base |"
        )
        lineas.append("|---|---|---|---|---|---|")
        for otro in otros:
            exitosos_otro = {c["id"] for c in otro["casos"] if c.get("n_exitosos")}
            comunes = exitosos_sistema & exitosos_otro
            if len(comunes) < 5:
                lineas.append(
                    f"| {otro['run_id']} | {len(comunes)} | — | — | — | "
                    "pocos casos en común: no se compara |"
                )
                continue
            r_sis = resumen_variante(
                {"casos": [c for c in sistema["casos"] if c["id"] in comunes]}
            )
            r_base = resumen_variante(
                {"casos": [c for c in otro["casos"] if c["id"] in comunes]}
            )
            ex_sis = (r_sis["exactos"] / r_sis["nivel_evaluables"]) if r_sis["nivel_evaluables"] else None
            ex_base = (r_base["exactos"] / r_base["nivel_evaluables"]) if r_base["nivel_evaluables"] else None
            delta = (
                f"{100 * (ex_sis - ex_base):+.1f} puntos"
                if (ex_sis is not None and ex_base is not None)
                else "—"
            )
            lineas.append(
                f"| {otro['run_id']} | {len(comunes)} | {_tasa(r_sis['exactos'], r_sis['nivel_evaluables'])} "
                f"({r_sis['exactos']}/{r_sis['nivel_evaluables']}) | "
                f"{_tasa(r_base['exactos'], r_base['nivel_evaluables'])} "
                f"({r_base['exactos']}/{r_base['nivel_evaluables']}) | {delta} | "
                f"{r_sis['alucinaciones_anti']}/{r_sis['n_anti']} vs "
                f"{r_base['alucinaciones_anti']}/{r_base['n_anti']} |"
            )
        lineas.append("")
        lineas.append(
            "La columna de alucinaciones se calcula solo sobre los casos anti-alucinación "
            "presentes en el subconjunto, así que puede apoyarse en pocos casos: se informa "
            "como indicio, no como tasa establecida."
        )
        lineas.append("")
        seccion += 1

    # --- Comparación entre variantes ---
    if len(resumenes) > 1:
        lineas.append(f"## {seccion}. Comparación entre variantes (benchmark)")
        lineas.append("")
        lineas.append(
            "| Métrica | " + " | ".join(n for n, _ in resumenes) + " |"
        )
        lineas.append("|---" * (len(resumenes) + 1) + "|")
        filas = [
            ("Exactitud del nivel", lambda r: _tasa(r["exactos"], r["nivel_evaluables"])),
            ("En rango permitido", lambda r: _tasa(r["en_permitido"], r["nivel_evaluables"])),
            ("Sub-triage", lambda r: str(r["sub_triaje"])),
            ("Supra-triage", lambda r: str(r["supra_triaje"])),
            ("Sin clasificar", lambda r: str(r["sin_clasificar"])),
            ("Alucinaciones (anti)", lambda r: _tasa(r["alucinaciones_anti"], r["n_anti"])),
            ("Alucinaciones (global)", lambda r: _tasa(r["alucinaciones"], r["n_registros"])),
            ("Recall@5 (página)", lambda r: _pct(r.get("recall_5_pagina"))),
            ("MRR", lambda r: _num(r.get("mrr_media"), 3)),
            ("Latencia media (s)", lambda r: _num(r["latencia_media"], 2)),
            ("Tokens por consulta", lambda r: _num(r["tokens_media"], 1)),
        ]
        for etiqueta, obtener in filas:
            lineas.append(
                f"| {etiqueta} | " + " | ".join(obtener(r) for _, r in resumenes) + " |"
            )
        lineas.append("")
        lineas.append(
            "Lectura: la comparación relevante es la variante `rag` frente a la que comparte "
            "modelo pero no tiene contexto (`sin-contexto`). Si ambos usan el mismo LLM y las "
            "mismas reglas, la diferencia mide el aporte del corpus normativo recuperado."
        )
        lineas.append("")
        seccion += 1

    # --- Hallazgos y limitaciones ---
    lineas.append(f"## {seccion}. Hallazgos, límites y amenazas a la validez")
    lineas.append("")
    lineas.append("**Hallazgos que se pueden sostener con esta evidencia**")
    lineas.append("")
    huecos = [
        c["id"]
        for v in limpio["variantes"]
        for c in v["casos"]
        if c["grupo"] == "clinico" and not c["nivel_esperado"]
    ]
    lineas.append(
        "- El corpus de NNAC no contiene una norma de clasificación de urgencias tipo "
        "Manchester: el mapeo de colores vive en el prompt del sistema. Los casos sin fuente "
        "esperada (el corpus no cubre su condición) se listan en el anexo por caso."
    )
    lineas.append(
        "- Los huecos de reglas deterministas aparecen en los casos de quemaduras, "
        "hipertensión severa, sangrado obstétrico y mordedura de serpiente: no existe red flag "
        "y el nivel depende por completo del LLM."
    )
    lineas.append(
        "- La medición de memoria RAM no se incluyó en este alcance y se declara como no "
        "medida (trabajo futuro concreto: muestreo de RSS del proceso con `psutil` o la API de "
        "memoria de Windows, antes, durante y después de cada consulta)."
    )
    anti_por_variante = [
        (
            nombre,
            [
                (c["id"], c["veredictos"][0].get("declara_limite") if c["veredictos"] else None)
                for c in variante["casos"]
                if c["grupo"] == "anti_alucinacion"
            ],
        )
        for (nombre, _), variante in zip(resumenes, limpio["variantes"])
    ]
    for nombre, anti in anti_por_variante:
        evaluados = [cid for cid, declara in anti if declara is not None]
        if not evaluados:
            continue
        declaran = [cid for cid, declara in anti if declara]
        callan = [cid for cid, declara in anti if declara is False]
        lineas.append(
            f"- **Declaración del límite ({nombre})**: de los {len(evaluados)} casos "
            f"anti-alucinación que respondieron, la respuesta declara que el contenido no está "
            f"en el material en {len(declaran)} "
            + (f"({', '.join(declaran)})" if declaran else "(ninguno)")
            + (
                f" y la omite en {len(callan)} ({', '.join(callan)}). Callar el límite no es "
                "una invención, pero quien lee la respuesta no recibe la advertencia de que ese "
                "dato no está respaldado por la norma: es un fallo de completitud que la "
                "medición de alucinación no captura."
                if callan
                else "."
            )
        )
    lineas.append(
        "- **Los planes gratuitos de los proveedores de nube limitan el experimento**: se "
        "registraron errores 429 por cuota agotada (Groq: techo diario de tokens del plan "
        "gratuito; Gemini: límite de peticiones por día y por minuto del modelo usado). Por eso "
        "las líneas base quedaron parciales y la comparación se restringe al subconjunto común. "
        "Es una limitación real de un prototipo para postas rurales: la disponibilidad del "
        "servicio de inferencia es un supuesto de operación, y refuerza la conveniencia de la "
        "opción local (el proyecto ya contempla Ollama) para un despliegue sin cuotas externas."
    )
    lineas.append("")
    lineas.append("**Amenazas a la validez**")
    lineas.append("")
    lineas.append(
        "1. El nivel esperado de cada caso es una propuesta del tesista derivada de la norma y "
        "del sistema Manchester: está pendiente de validación por el médico colaborador "
        "(C2.A4), que también puede ajustar los rangos permitidos."
    )
    lineas.append(
        "2. Los criterios automáticos de contenido (expresiones obligatorias y prohibidas) son "
        "señales heurísticas, sensibles a la paráfrasis; se informan caso por caso y nunca "
        "sustituyen la lectura clínica."
    )
    lineas.append(
        "3. Los detectores de alucinación son deliberadamente conservadores: comprueban la cita "
        "contra TODO el material entregado al modelo (el prompt completo y el texto íntegro de "
        "las páginas recuperadas), no solo contra el fragmento, de modo que un fallo indica que "
        "el contenido no estaba en nada de lo que el modelo tuvo delante. La primera versión "
        "del detector comprobaba solo los fragmentos recuperados y marcaba como cita no anclada "
        "a los datos del propio paciente y a la plantilla de la respuesta; el veredicto que se "
        "informa aquí ya está corregido."
    )
    lineas.append(
        "4. La latencia depende de la máquina, de la red y del proveedor: es comparable entre "
        "variantes de una misma corrida, no contra valores absolutos de la literatura."
    )
    lineas.append(
        "5. Con una sola repetición por caso, la estabilidad no es medible; y con temperatura "
        "distinta de cero el nivel puede variar entre corridas idénticas."
    )
    lineas.append("")

    # --- Anexo ---
    lineas.append(f"## {seccion + 1}. Anexo: resultado por caso")
    lineas.append("")
    for (nombre, _), variante in zip(resumenes, limpio["variantes"]):
        lineas.append(f"### Variante `{nombre}`")
        lineas.append("")
        lineas += _tabla_casos(variante, variante)
        lineas.append("")

    DIR_INFORMES.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    ruta = DIR_INFORMES / f"informe_{marca}.md"
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    print(f"Informe escrito en: {_relativa(ruta)}")
    for nombre, r in resumenes:
        print(
            f"  {nombre}: exactitud {_tasa(r['exactos'], r['nivel_evaluables'])} · "
            f"en rango {_tasa(r['en_permitido'], r['nivel_evaluables'])} · "
            f"sub-triage {r['sub_triaje']} · alucinaciones anti "
            f"{r['alucinaciones_anti']}/{r['n_anti']}"
        )
    return 0


# ---------------------------------------------------------------------------
# Subcomando: instrumentos (C2.A4 y C2.A5)
# ---------------------------------------------------------------------------


NIVELES_RUBRICA = ("Muy bueno", "Bueno", "Regular", "Malo")

ITEMS_SUS = (
    "Creo que me gustaría usar este sistema con frecuencia.",
    "Encontré el sistema innecesariamente complejo.",
    "Pensé que el sistema era fácil de usar.",
    "Creo que necesitaría apoyo técnico para poder usar este sistema.",
    "Encontré que las distintas funciones del sistema estaban bien integradas.",
    "Pensé que había demasiada inconsistencia en el sistema.",
    "Imagino que la mayoría de la gente aprendería a usar este sistema muy rápidamente.",
    "Encontré el sistema muy engorroso de usar.",
    "Me sentí muy confiado al usar el sistema.",
    "Necesité aprender muchas cosas antes de poder empezar a usar el sistema.",
)


def _cargar_runs(nombres: Optional[list[str]]) -> Optional[dict[str, Any]]:
    """Carga una o varias corridas y las fusiona en un solo experimento.

    Las corridas reales se hacen por lotes (`--ids`) para no exceder el tiempo
    de una terminal, así que la rúbrica debe poder tomar los lotes del mismo
    experimento y tratarlos como el sistema completo; si no, los casos que
    quedaron en otro lote aparecen sin nivel del sistema.
    """
    if not nombres:
        return None
    documentos = [
        json.loads(_resolver_ruta_resultado(nombre).read_text(encoding="utf-8"))
        for nombre in nombres
    ]
    if len(documentos) == 1:
        return documentos[0]

    fusionados = fusionar_corridas(documentos)
    if len(fusionados) == 1:
        return fusionados[0]
    # Variantes distintas en una misma llamada: un solo documento con todos los
    # casos, indexado por identificador (el nivel más reciente gana).
    combinado: dict[str, Any] = {
        "run_id": [d.get("run_id") for d in documentos],
        "variante": " + ".join(sorted({d.get("variante") or "?" for d in documentos})),
        "config": documentos[0].get("config"),
        "entorno": documentos[0].get("entorno"),
        "duracion_s": round(sum(d.get("duracion_s") or 0 for d in documentos), 1),
        "casos": [],
    }
    por_id: dict[str, dict[str, Any]] = {}
    for documento in fusionados:
        for caso in documento.get("casos") or []:
            por_id[caso["id"]] = caso
    combinado["casos"] = list(por_id.values())
    return combinado


def comando_instrumentos(args) -> int:
    """Genera la rúbrica clínica y la encuesta SUS listas para el médico."""
    DIR_INSTRUMENTOS.mkdir(parents=True, exist_ok=True)
    run = _cargar_runs(args.run)

    niveles_sistema: dict[str, str] = {}
    if run:
        for caso in run.get("casos", []):
            registros = [r for r in caso.get("repeticiones", []) if not r.get("error")]
            if registros:
                niveles_sistema[caso["id"]] = registros[0].get("nivel_final") or "sin clasificar"

    casos = [c for c in cargar_casos() if c.get("_grupo_archivo") == "clinico"]
    ruta_rubrica = DIR_INSTRUMENTOS / "rubrica_clinica.csv"
    with open(ruta_rubrica, "w", newline="", encoding="utf-8") as fh:
        escritor = csv.DictWriter(
            fh,
            fieldnames=(
                "caso_id",
                "titulo",
                "nivel_esperado",
                "nivel_sistema",
                "calificacion",
                "comentario",
            ),
        )
        escritor.writeheader()
        for caso in casos:
            escritor.writerow(
                {
                    "caso_id": caso["id"],
                    "titulo": caso["titulo"],
                    "nivel_esperado": caso.get("nivel_esperado") or "",
                    "nivel_sistema": niveles_sistema.get(caso["id"], ""),
                    "calificacion": "",
                    "comentario": "",
                }
            )

    ruta_sus = DIR_INSTRUMENTOS / "encuesta_sus.csv"
    with open(ruta_sus, "w", newline="", encoding="utf-8") as fh:
        escritor = csv.writer(fh)
        escritor.writerow(["item", "enunciado", "respuesta_1_a_5"])
        for i, enunciado in enumerate(ITEMS_SUS, 1):
            escritor.writerow([i, enunciado, ""])

    ruta_lee = DIR_INSTRUMENTOS / "README.md"
    ruta_lee.write_text(
        "# Instrumentos de evaluación clínica (C2.A4 y C2.A5)\n\n"
        "Estos archivos los completa el médico colaborador. No hace falta que \n"
        "ejecute nada: solo llenar los CSV y devolverlos. El cálculo lo hace \n"
        "`python scripts/evaluar.py rubrica`.\n\n"
        "## 1. `rubrica_clinica.csv` — calidad clínica de cada respuesta (C2.A4)\n\n"
        "Para cada uno de los 20 casos clínicos, califique la respuesta del sistema \n"
        "en la columna `calificacion` con uno de estos cuatro valores:\n\n"
        "| Valor | Significado |\n"
        "|---|---|\n"
        "| Muy bueno | El nivel de urgencia es correcto y las acciones recomendadas son \n"
        "adecuadas y seguras para una posta rural. |\n"
        "| Bueno | El nivel es correcto, con recomendaciones incompletas o poco \n"
        "específicas que no comprometen la seguridad. |\n"
        "| Regular | El nivel es discutible (sub o sobrevaloración leve) o faltan \n"
        "elementos importantes de manejo. |\n"
        "| Malo | El nivel es incorrecto o la respuesta contiene indicaciones \n"
        "peligrosas. |\n\n"
        "La columna `nivel_sistema` muestra lo que respondió el sistema y \n"
        "`nivel_esperado` lo que se considera correcto según las NNAC; el médico \n"
        "puede corregir el nivel esperado en `comentario` si no está de acuerdo.\n\n"
        "Criterio de aceptación del Componente 2: **al menos 80 % de los casos en \n"
        "Bueno o Muy bueno**.\n\n"
        "## 2. `encuesta_sus.csv` — usabilidad percibida (C2.A5)\n\n"
        "Responder los 10 ítems con la escala de 1 (muy en desacuerdo) a 5 (muy de \n"
        "acuerdo). El puntaje se calcula en la escala estándar 0-100 y el criterio \n"
        "de aceptación es **70 puntos o más**.\n\n"
        "## 3. Cómo devolverlo\n\n"
        "Copiar los dos CSV en `evaluacion/instrumentos/` del repositorio y ejecutar:\n\n"
        "```\npython scripts/evaluar.py rubrica --run <archivo-de-corrida.json>\n```\n\n"
        "Eso genera `evaluacion/informes/informe_clinico.md` con el porcentaje de \n"
        "casos aceptables, el puntaje SUS y la concordancia con el veredicto \n"
        "automático del sistema.\n",
        encoding="utf-8",
    )

    print(f"Rúbrica clínica : {_relativa(ruta_rubrica)}")
    print(f"Encuesta SUS    : {_relativa(ruta_sus)}")
    print(f"Instrucciones   : {_relativa(ruta_lee)}")
    if niveles_sistema:
        corridas = run.get("run_id")
        etiqueta = " + ".join(corridas) if isinstance(corridas, list) else corridas
        print(f"Niveles del sistema incorporados desde la corrida: {etiqueta}")
    else:
        print(
            "Sin corrida asociada: la columna nivel_sistema quedó vacía. "
            "Vuelve a ejecutarlo con --run <corrida.json> para incluirla."
        )
    return 0


# ---------------------------------------------------------------------------
# Subcomando: rubrica (calcula C2.A4 y C2.A5 cuando el médico los devuelve)
# ---------------------------------------------------------------------------


def _leer_csv(ruta: Path) -> list[dict[str, str]]:
    if not ruta.exists():
        raise SystemExit(f"❌ No se encontró el archivo: {ruta}")
    with open(ruta, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _kappa(a: list[bool], b: list[bool]) -> Optional[float]:
    """Kappa de Cohen entre dos jueces binarios (sin dependencias externas)."""
    n = len(a)
    if n == 0:
        return None
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa_si = sum(1 for x in a if x) / n
    pb_si = sum(1 for y in b if y) / n
    pe = pa_si * pb_si + (1 - pa_si) * (1 - pb_si)
    if pe == 1:
        return 1.0 if po == 1 else 0.0
    return (po - pe) / (1 - pe)


def comando_rubrica(args) -> int:
    filas = _leer_csv(Path(args.rubrica))
    validas = [f for f in filas if (f.get("calificacion") or "").strip()]
    aceptables = [
        f for f in validas if (f.get("calificacion") or "").strip() in {"Muy bueno", "Bueno"}
    ]
    desconocidas = {
        (f.get("calificacion") or "").strip()
        for f in validas
        if (f.get("calificacion") or "").strip() not in NIVELES_RUBRICA
    }

    print("=" * 78)
    print("EVALUACIÓN CLÍNICA (C2.A4) y USABILIDAD (C2.A5)")
    print("=" * 78)
    print(f"Casos calificados: {len(validas)} de {len(filas)}")
    if desconocidas:
        print(
            "⚠️  Valores de calificación no reconocidos: "
            + ", ".join(sorted(desconocidas))
            + " (usa Muy bueno / Bueno / Regular / Malo)."
        )
    porcentaje = (len(aceptables) / len(validas)) if validas else None
    print(
        f"Casos en Bueno o Muy bueno: {len(aceptables)}/{len(validas)} "
        f"({_pct(porcentaje)}) — criterio ≥ 80 %: "
        f"{'✔' if (porcentaje or 0) >= 0.8 else '✖'}"
    )

    sus_filas = _leer_csv(Path(args.sus))
    respuestas: list[int] = []
    for fila in sus_filas:
        valor = (fila.get("respuesta_1_a_5") or "").strip()
        if valor.isdigit() and 1 <= int(valor) <= 5:
            respuestas.append(int(valor))
    sus = None
    if len(respuestas) == len(ITEMS_SUS):
        sus = sum(
            (v - 1) if i % 2 == 0 else (5 - v) for i, v in enumerate(respuestas)
        ) * 2.5
        print(f"Puntaje SUS: {sus:.1f} / 100 — criterio ≥ 70: {'✔' if sus >= 70 else '✖'}")
    else:
        print(
            f"Puntaje SUS: no calculable aún ({len(respuestas)} de {len(ITEMS_SUS)} "
            "respuestas válidas de 1 a 5)."
        )

    kappa = None
    run = _cargar_runs(args.run)
    if run and validas:
        acuerdos_medico: list[bool] = []
        acuerdos_auto: list[bool] = []
        niveles_por_caso = {
            c["id"]: (
                [r for r in c.get("repeticiones", []) if not r.get("error")][0].get("nivel_final")
                if [r for r in c.get("repeticiones", []) if not r.get("error")]
                else None
            )
            for c in run.get("casos", [])
        }
        permitidos_por_caso = {
            c["id"]: c.get("nivel_permitido") or [] for c in run.get("casos", [])
        }
        for fila in validas:
            cid = fila.get("caso_id")
            nivel = niveles_por_caso.get(cid)
            permitido = permitidos_por_caso.get(cid) or []
            if nivel is None:
                continue
            acuerdos_medico.append(
                (fila.get("calificacion") or "").strip() in {"Muy bueno", "Bueno"}
            )
            acuerdos_auto.append(nivel in permitido if permitido else False)
        kappa = _kappa(acuerdos_medico, acuerdos_auto) if acuerdos_medico else None
        print(
            f"Concordancia con el veredicto automático (kappa de Cohen): "
            f"{_num(kappa, 2)} sobre {len(acuerdos_auto)} casos con corrida asociada."
        )

    lineas = [
        "# Informe de la evaluación clínica (C2.A4) y de usabilidad (C2.A5)",
        "",
        "## Rúbrica clínica",
        "",
        f"- Casos calificados: {len(validas)} de {len(filas)}",
        f"- Casos en Bueno o Muy bueno: {len(aceptables)}/{len(validas)} ({_pct(porcentaje)})",
        f"- Criterio de aceptación (≥ 80 %): {'cumple' if (porcentaje or 0) >= 0.8 else 'no cumple'}",
        "",
        "| Caso | Nivel esperado | Nivel del sistema | Calificación | Comentario |",
        "|---|---|---|---|---|",
    ]
    for fila in filas:
        lineas.append(
            f"| {fila.get('caso_id')} | {fila.get('nivel_esperado')} | "
            f"{fila.get('nivel_sistema')} | {fila.get('calificacion') or '—'} | "
            f"{(fila.get('comentario') or '').replace('|', '/') or '—'} |"
        )
    lineas += [
        "",
        "## Encuesta SUS",
        "",
        f"- Respuestas válidas: {len(respuestas)} de {len(ITEMS_SUS)}",
        f"- Puntaje SUS: {'—' if sus is None else f'{sus:.1f} / 100'}",
        f"- Criterio de aceptación (≥ 70): {'cumple' if (sus or 0) >= 70 else 'no cumple o no calculable'}",
        "",
    ]
    if kappa is not None:
        lineas += [
            "## Concordancia con el veredicto automático",
            "",
            f"- Kappa de Cohen: {_num(kappa, 2)} (sobre {len(acuerdos_auto)} casos)",
            "",
            "El kappa compara dos cosas distintas —el juicio clínico global y el "
            "cumplimiento del rango de nivel esperado— así que se informa como "
            "indicador de consistencia, no como medida de acierto.",
            "",
        ]

    DIR_INFORMES.mkdir(parents=True, exist_ok=True)
    ruta = DIR_INFORMES / "informe_clinico.md"
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"\nInforme clínico escrito en: {_relativa(ruta)}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evaluar.py",
        description="Evaluación del sistema de triaje (Componente 2 de la tesis).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python scripts/evaluar.py validar\n"
            "  python scripts/evaluar.py correr --variante rag --modelo groq --repeticiones 3 --solo-estabilidad\n"
            "  python scripts/evaluar.py correr --variante sin-contexto --modelo groq\n"
            "  python scripts/evaluar.py informe rag_groq_20260101-1200 sin-contexto_groq_20260101-1300\n"
            "  python scripts/evaluar.py instrumentos --run rag_groq_20260101-1200\n"
        ),
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("validar", help="Revisa los casos sin llamar a ningún modelo.")

    p_correr = sub.add_parser("correr", help="Ejecuta los casos y guarda la evidencia cruda.")
    p_correr.add_argument(
        "--variante",
        choices=("rag", "sin-contexto"),
        default="rag",
        help="rag = sistema completo; sin-contexto = misma plantilla sin recuperación.",
    )
    p_correr.add_argument("--modelo", help="Parte del nombre del proveedor (groq, gemini, ollama...).")
    p_correr.add_argument("--limite", type=int, help="Ejecuta solo los primeros N casos (piloto).")
    p_correr.add_argument("--ids", help="Lista de identificadores separados por coma (ej. C-11,A-01).")
    p_correr.add_argument("--repeticiones", type=int, default=1, help="Repeticiones por caso (estabilidad).")
    p_correr.add_argument(
        "--solo-estabilidad",
        action="store_true",
        help="Con repeticiones > 1, repite solo los casos marcados como de estabilidad.",
    )
    p_correr.add_argument("--pausa", type=float, default=0.0, help="Segundos entre casos (límites de tasa).")
    p_correr.add_argument("--reintentos", type=int, default=2, help="Reintentos por caso ante fallo de red.")
    p_correr.add_argument("--salida", help="Nombre de la corrida (por defecto se arma solo).")

    p_informe = sub.add_parser("informe", help="Recalcula las métricas y escribe el informe.")
    p_informe.add_argument("runs", nargs="+", help="Archivos o nombres de corrida en evaluacion/resultados/.")
    p_informe.add_argument("--titulo", help="Subtítulo opcional del informe.")
    p_informe.add_argument(
        "--no-fusionar",
        dest="fusionar",
        action="store_false",
        help="No unir los lotes del mismo variante y modelo (cada lote como columna).",
    )

    p_instr = sub.add_parser("instrumentos", help="Genera la rúbrica y la encuesta SUS.")
    p_instr.add_argument(
        "--run",
        nargs="+",
        help="Corrida(s) cuyos niveles se incorporan a la rúbrica (los lotes se fusionan).",
    )

    p_rub = sub.add_parser("rubrica", help="Calcula C2.A4 y C2.A5 desde los CSV del médico.")
    p_rub.add_argument(
        "--rubrica",
        default=str(DIR_INSTRUMENTOS / "rubrica_clinica.csv"),
        help="CSV de la rúbrica clínica.",
    )
    p_rub.add_argument(
        "--sus",
        default=str(DIR_INSTRUMENTOS / "encuesta_sus.csv"),
        help="CSV de la encuesta SUS.",
    )
    p_rub.add_argument(
        "--run",
        nargs="+",
        help="Corrida(s) para calcular la concordancia con el veredicto automático.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = construir_parser().parse_args(argv)
    comandos = {
        "validar": comando_validar,
        "correr": comando_correr,
        "informe": comando_informe,
        "instrumentos": comando_instrumentos,
        "rubrica": comando_rubrica,
    }
    return comandos[args.comando](args)


if __name__ == "__main__":
    raise SystemExit(main())
