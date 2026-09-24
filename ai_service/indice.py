"""Manifiesto del índice vectorial: frescura y plan de reindexado.

Problema que resuelve
---------------------
La comprobación anterior para decidir si había que indexar era
``chroma_collection.count() > 0``. Eso no mide vigencia: mide *si hay algo*, y
como el índice casi nunca está vacío, quedaba congelado de por vida. Efectos:

  * un PDF nuevo en ``data/`` se ignoraba en silencio (el LLM respondía
    "No hay suficiente información en las NNAC": un fallo silencioso, que es el
    peor tipo de fallo en una herramienta clínica);
  * editar o borrar un PDF no cambiaba nada: sus chunks viejos seguían ahí y se
    citaban como fuente;
  * una indexación interrumpida a mitad quedaba bendecida para siempre, con
    ``count() > 0`` y el corpus mutilado;
  * cambiar el modelo de embeddings corrompía la recuperación sin ningún aviso:
    los vectores guardados y los de la consulta dejarían de ser comparables.

Este módulo guarda un **manifiesto** dentro de la propia colección de Chroma
(como JSON en una clave de su metadata, que es donde Chroma admite metadatos
escalares) y calcula el **plan** de lo que hay que hacer al arrancar:

  nuevo        -> en ``data/`` pero no en el manifiesto: indexar
  modificado   -> el SHA-256 del contenido cambió: borrar sus chunks y reindexar
  eliminado    -> en el manifiesto pero ya no en ``data/``: borrar sus chunks
  sin cambios  -> mismo SHA-256: no se toca (camino rápido, cero embeddings)

Se usa SHA-256 del contenido y no ``mtime`` porque ``mtime`` cambia al copiar o
desplegar un PDF sin que cambie su contenido, y no cambia al restaurar un
backup aunque el contenido sí cambie. Se lee en bloques, así que hashear los
54 MB del corpus cuesta ~0,15 s: despreciable frente a cargar el modelo.

El campo ``completo`` es el seguro contra fallos parciales: se escribe ``False``
antes de empezar a tocar la colección y ``True`` solo al terminar. Si el proceso
muere a mitad, el siguiente arranque lo detecta y reconstruye, en lugar de
servir un corpus incompleto.
"""

import hashlib
import json
import logging
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ai_service.embeddings import MODELO_EMBEDDINGS

logger = logging.getLogger(__name__)

# Versión del formato del manifiesto (permite evolucionarlo en el futuro).
VERSION_MANIFEST = 1

# Clave de la metadata de la colección donde vive el manifiesto serializado.
CLAVE_MANIFEST = "nnac_manifest"

# Parámetros de segmentación (forman parte de la "forma" del índice).
CHUNK_SIZE = 768
CHUNK_OVERLAP = 128

# Motivos por los que hay que reconstruir el índice completo.
MOTIVO_SIN_MANIFIESTO = "no existe manifiesto en la colección"
MOTIVO_INCOMPLETO = "la última indexación no terminó (completo=False)"
MOTIVO_MODELO = "modelo de embeddings distinto"
MOTIVO_CHUNKING = "parámetros de segmentación distintos"

# Motivos que exigen reconstrucción total pero son estados de arranque
# normales (primer uso, o una indexación que murió a mitad): se reconstruye
# automáticamente, porque un sistema que nunca indexó no puede "abortar".
# Los desajustes de configuración sí abortan salvo autorización expresa.
MOTIVOS_BOOTSTRAP = (MOTIVO_SIN_MANIFIESTO, MOTIVO_INCOMPLETO)


@dataclass(frozen=True)
class ParametrosIndice:
    """La "forma" del índice: qué modelo y qué segmentación lo produjeron.

    Si cualquiera de los tres cambia, los vectores guardados dejan de ser
    comparables con los de las consultas y el índice debe reconstruirse.
    """

    modelo_embeddings: str = MODELO_EMBEDDINGS
    chunk_size: int = CHUNK_SIZE
    chunk_overlap: int = CHUNK_OVERLAP


@dataclass
class InfoArchivo:
    """Huella y tamaño de un documento indexado."""

    nombre: str
    sha256: str
    tamano: int = 0
    mtime: float = 0.0
    chunks: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "nombre": self.nombre,
            "sha256": self.sha256,
            "tamano": self.tamano,
            "mtime": self.mtime,
            "chunks": self.chunks,
        }

    @classmethod
    def from_dict(cls, datos: dict[str, Any]) -> "InfoArchivo":
        return cls(
            nombre=str(datos.get("nombre", "")),
            sha256=str(datos.get("sha256", "")),
            tamano=int(datos.get("tamano", 0)),
            mtime=float(datos.get("mtime", 0.0)),
            chunks=int(datos.get("chunks", 0)),
        )


@dataclass
class Manifest:
    """Estado del índice: qué archivos (y con qué contenido) están dentro."""

    version: int = VERSION_MANIFEST
    embedding_model: str = ""
    chunk_size: int = 0
    chunk_overlap: int = 0
    completo: bool = False
    adoptado: bool = False
    indexado_en: str = ""
    archivos: dict[str, InfoArchivo] = field(default_factory=dict)

    @classmethod
    def nuevo(cls, parametros: ParametrosIndice, **kwargs: Any) -> "Manifest":
        """Manifiesto con la forma del índice ya fijada (sin archivos aún)."""
        return cls(
            version=VERSION_MANIFEST,
            embedding_model=parametros.modelo_embeddings,
            chunk_size=parametros.chunk_size,
            chunk_overlap=parametros.chunk_overlap,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "embedding_model": self.embedding_model,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "completo": self.completo,
            "adoptado": self.adoptado,
            "indexado_en": self.indexado_en,
            "archivos": {n: i.to_dict() for n, i in self.archivos.items()},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, datos: dict[str, Any]) -> "Manifest":
        if not isinstance(datos, dict):
            raise ValueError("El manifiesto debe ser un objeto JSON.")
        if not datos.get("archivos"):
            # Un manifiesto sin archivos es indistinguible de "no hay
            # manifiesto" y no debe dar por bueno un índice existente.
            raise ValueError("El manifiesto no contiene archivos.")
        return cls(
            version=int(datos.get("version", VERSION_MANIFEST)),
            embedding_model=str(datos.get("embedding_model", "")),
            chunk_size=int(datos.get("chunk_size", 0)),
            chunk_overlap=int(datos.get("chunk_overlap", 0)),
            completo=bool(datos.get("completo", False)),
            adoptado=bool(datos.get("adoptado", False)),
            indexado_en=str(datos.get("indexado_en", "")),
            archivos={
                str(nombre): InfoArchivo.from_dict(info or {})
                for nombre, info in (datos.get("archivos") or {}).items()
            },
        )

    @classmethod
    def from_json(cls, bruto: str) -> "Manifest":
        """Decodifica un manifiesto. Lanza ValueError si está corrupto."""
        return cls.from_dict(json.loads(bruto))

    def resumen(self) -> str:
        total_chunks = sum(i.chunks for i in self.archivos.values())
        return (
            f"{len(self.archivos)} archivos / {total_chunks} chunks"
            f" · modelo={self.embedding_model}"
            f" · chunk={self.chunk_size}/{self.chunk_overlap}"
            f" · completo={self.completo}"
            f" · adoptado={self.adoptado}"
            f" · indexado_en={self.indexado_en or 'desconocido'}"
        )


@dataclass
class Plan:
    """Qué hay que hacer con el índice para que refleje ``data/``."""

    nuevos: list[str] = field(default_factory=list)
    modificados: list[str] = field(default_factory=list)
    eliminados: list[str] = field(default_factory=list)
    sin_cambios: list[str] = field(default_factory=list)
    motivo_reconstruccion: Optional[str] = None
    # Se marca explícitamente (no se deduce del texto del motivo): si alguien
    # enriqueciera el mensaje de "incompleto", deducirlo de la cadena haría que
    # un estado de arranque normal pasara a abortar el sistema.
    bootstrap: bool = False

    @property
    def requiere_reconstruccion(self) -> bool:
        return self.motivo_reconstruccion is not None

    @property
    def es_bootstrap(self) -> bool:
        """True si la reconstrucción se debe a un estado de arranque normal."""
        return self.bootstrap

    @property
    def requiere_abortar(self) -> bool:
        """True si hay que abortar en lugar de reconstruir.

        Solo para incompatibilidades de configuración (modelo de embeddings o
        segmentación distintos): un índice que nunca se construyó, o cuya
        indexación murió a mitad, siempre se puede reconstruir.
        """
        return self.requiere_reconstruccion and not self.bootstrap

    @property
    def hay_cambios(self) -> bool:
        return bool(self.nuevos or self.modificados or self.eliminados)

    @property
    def a_indexar(self) -> list[str]:
        return sorted(self.nuevos + self.modificados)

    @property
    def a_eliminar(self) -> list[str]:
        return sorted(self.modificados + self.eliminados)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nuevos": sorted(self.nuevos),
            "modificados": sorted(self.modificados),
            "eliminados": sorted(self.eliminados),
            "sin_cambios": sorted(self.sin_cambios),
            "motivo_reconstruccion": self.motivo_reconstruccion,
            "requiere_reconstruccion": self.requiere_reconstruccion,
            "requiere_abortar": self.requiere_abortar,
            "a_indexar": self.a_indexar,
            "a_eliminar": self.a_eliminar,
        }

    def resumen(self) -> str:
        partes = [
            f"nuevos={len(self.nuevos)}",
            f"modificados={len(self.modificados)}",
            f"eliminados={len(self.eliminados)}",
            f"sin_cambios={len(self.sin_cambios)}",
        ]
        texto = " ".join(partes)
        if self.motivo_reconstruccion:
            texto += f" | reconstrucción: {self.motivo_reconstruccion}"
        if self.nuevos:
            texto += f" | nuevos: {', '.join(self.nuevos)}"
        if self.modificados:
            texto += f" | modificados: {', '.join(self.modificados)}"
        if self.eliminados:
            texto += f" | eliminados: {', '.join(self.eliminados)}"
        return texto


def ahora_iso() -> str:
    """Marca temporal UTC en ISO-8601 (para el manifiesto)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def listar_pdfs(data_dir: str) -> list[str]:
    """Nombres de los PDFs de ``data_dir``, ordenados, sin recursión.

    Args:
        data_dir: directorio del corpus.

    Returns:
        Lista de nombres de archivo (no rutas).

    Raises:
        FileNotFoundError: si el directorio no existe.
        IsADirectoryError: si no es un directorio.
    """
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"Directorio de datos no encontrado: {data_dir}")
    if not os.path.isdir(data_dir):
        raise IsADirectoryError(f"La ruta de datos no es un directorio: {data_dir}")
    return sorted(
        nombre
        for nombre in os.listdir(data_dir)
        if nombre.lower().endswith(".pdf")
        and os.path.isfile(os.path.join(data_dir, nombre))
    )


def huella_archivo(ruta: str) -> str:
    """SHA-256 del contenido del archivo, leído por bloques."""
    digest = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def huellas_de_directorio(data_dir: str) -> dict[str, InfoArchivo]:
    """Huella de cada PDF de ``data_dir`` (``chunks`` queda en 0: aún no se sabe)."""
    resultado: dict[str, InfoArchivo] = {}
    for nombre in listar_pdfs(data_dir):
        ruta = os.path.join(data_dir, nombre)
        stats = os.stat(ruta)
        resultado[nombre] = InfoArchivo(
            nombre=nombre,
            sha256=huella_archivo(ruta),
            tamano=stats.st_size,
            mtime=stats.st_mtime,
            chunks=0,
        )
    return resultado


def contar_chunks_por_archivo(collection, lote: int = 1000) -> dict[str, int]:
    """Cuenta los chunks de la colección agrupados por su metadata ``archivo``.

    Se pagina con ``limit``/``offset`` en lugar de pedir todo de golpe: la
    colección tiene miles de chunks y no hace falta materializarlos todos.
    Solo se piden metadatos (nunca los embeddings).
    """
    conteos: Counter[str] = Counter()
    offset = 0
    while True:
        resultado = collection.get(include=["metadatas"], limit=lote, offset=offset)
        metadatos = (resultado or {}).get("metadatas") or []
        if not metadatos:
            break
        for meta in metadatos:
            nombre = (meta or {}).get("archivo")
            if nombre:
                conteos[str(nombre)] += 1
        if len(metadatos) < lote:
            break
        offset += lote
    return dict(conteos)


def es_metadata_valida(metadata: dict[str, Any]) -> dict[str, Any]:
    """Limpia la metadata de la colección: Chroma solo admite escalares.

    ``collection.modify(metadata=...)`` **reemplaza** la metadata entera, así que
    hay que reenviar también las claves que ya existían (p. ej. ``description``);
    las que tengan valor ``None`` se descartan porque Chroma las rechaza.
    """
    return {
        clave: valor
        for clave, valor in dict(metadata or {}).items()
        if valor is not None
    }


def leer_manifest(collection) -> Optional[Manifest]:
    """Lee el manifiesto de la metadata de la colección.

    Returns:
        El manifiesto, o ``None`` si no existe o está corrupto (ambos casos se
        tratan igual: hay que reconstruir o adoptar el índice).
    """
    metadata = getattr(collection, "metadata", None) or {}
    bruto = metadata.get(CLAVE_MANIFEST)
    if not bruto:
        return None
    try:
        return Manifest.from_json(bruto)
    except (ValueError, TypeError) as e:
        logger.warning("Manifiesto del índice ilegible (%s): %s", type(e).__name__, e)
        return None


def escribir_manifest(collection, manifest: Manifest) -> None:
    """Guarda el manifiesto en la metadata de la colección (sin perder claves)."""
    metadata = es_metadata_valida(getattr(collection, "metadata", None) or {})
    metadata[CLAVE_MANIFEST] = manifest.to_json()
    collection.modify(metadata=metadata)


def reconstruir_manifest_desde_coleccion(
    collection,
    data_dir: str,
    parametros: ParametrosIndice,
    adoptado: bool = True,
) -> Manifest:
    """Deduce el manifiesto a partir de lo que ya hay en la colección.

    Se usa en dos escenarios:

    1. **Adopción** (``adoptado=True``): el índice se construyó antes de que
       existiera el manifiesto. No hay nada con lo que comparar, así que se
       registra el hash *actual* de cada PDF. Cuesta cero re-embeddings y a
       partir de ahí cualquier cambio sí se detecta.
    2. **Cierre de una indexación** (``adoptado=False``): tras indexar, se
       registra lo que realmente quedó en la colección.

    Un archivo de ``data/`` que no tenga ningún chunk en la colección **no entra
    al manifiesto**, para que el plan lo marque como ``nuevo`` y se indexe: sería
    justamente el fallo silencioso que se quiere eliminar (declarar vigente un
    documento cuyo contenido no está en el índice).

    Los archivos con chunks en la colección pero ausentes de ``data/`` sí se
    registran (con hash vacío) para que el plan los detecte como ``eliminados``
    y borre sus chunks huérfanos.
    """
    conteos = contar_chunks_por_archivo(collection)
    archivos: dict[str, InfoArchivo] = {}
    sin_chunks: list[str] = []

    for nombre, info in huellas_de_directorio(data_dir).items():
        chunks = conteos.get(nombre, 0)
        if chunks == 0:
            sin_chunks.append(nombre)
            continue
        info.chunks = chunks
        archivos[nombre] = info

    if sin_chunks:
        logger.warning(
            "Archivos en %s sin ningún chunk en el índice (se indexarán): %s",
            data_dir,
            ", ".join(sorted(sin_chunks)),
        )

    for nombre, chunks in conteos.items():
        if nombre not in archivos and nombre not in sin_chunks:
            archivos[nombre] = InfoArchivo(
                nombre=nombre, sha256="", tamano=0, mtime=0.0, chunks=chunks
            )

    return Manifest.nuevo(
        parametros,
        completo=True,
        adoptado=adoptado,
        indexado_en=ahora_iso(),
        archivos=archivos,
    )


def calcular_plan(
    data_dir: str,
    manifest: Optional[Manifest],
    parametros: ParametrosIndice,
) -> Plan:
    """Decide qué hay que hacer con el índice para que refleje ``data/``.

    Función pura (salvo leer los PDFs del disco): no toca Chroma ni embeddings,
    por lo que es testeable sin red.

    La lista de archivos se calcula **siempre**, incluso cuando hay que
    reconstruir todo, para que el plan se pueda mostrar en un ``--dry-run``.
    """
    archivos = huellas_de_directorio(data_dir)
    previos = manifest.archivos if manifest is not None else {}

    nuevos: list[str] = []
    modificados: list[str] = []
    sin_cambios: list[str] = []

    for nombre, info in archivos.items():
        anterior = previos.get(nombre)
        if anterior is None:
            nuevos.append(nombre)
        elif anterior.sha256 != info.sha256:
            modificados.append(nombre)
        else:
            sin_cambios.append(nombre)

    eliminados = sorted(nombre for nombre in previos if nombre not in archivos)

    motivo: Optional[str] = None
    if manifest is None:
        motivo = MOTIVO_SIN_MANIFIESTO
    elif not manifest.completo:
        motivo = MOTIVO_INCOMPLETO
    elif manifest.embedding_model != parametros.modelo_embeddings:
        motivo = (
            f"{MOTIVO_MODELO}: índice={manifest.embedding_model!r} "
            f"actual={parametros.modelo_embeddings!r}"
        )
    elif (
        manifest.chunk_size != parametros.chunk_size
        or manifest.chunk_overlap != parametros.chunk_overlap
    ):
        motivo = (
            f"{MOTIVO_CHUNKING}: índice={manifest.chunk_size}/{manifest.chunk_overlap} "
            f"actual={parametros.chunk_size}/{parametros.chunk_overlap}"
        )

    return Plan(
        nuevos=nuevos,
        modificados=modificados,
        eliminados=eliminados,
        sin_cambios=sin_cambios,
        motivo_reconstruccion=motivo,
        bootstrap=motivo in MOTIVOS_BOOTSTRAP,
    )
