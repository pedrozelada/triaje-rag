"""Reindexado manual del índice vectorial de las NNAC.

La aplicación ya reconcilia el índice por su cuenta al arrancar (detecta PDFs
nuevos, modificados y eliminados comparando huellas SHA-256). Este script existe
para los dos casos en los que hace falta una intervención explícita:

  * ``--dry-run``: auditar qué hay indexado y qué cambios están pendientes, sin
    tocar nada y sin cargar modelos de embeddings.
  * ``--forzar``: reconstruir el índice desde cero. Es el remedio indicado
    cuando el arranque aborta porque el índice se construyó con otro modelo de
    embeddings u otra segmentación (sus vectores no son comparables con los de
    las consultas), y también para establecer una línea base limpia tras
    adoptar un índice antiguo que no tenía manifiesto.

Uso:
    python scripts/reindexar.py --dry-run
    python scripts/reindexar.py --forzar
"""

import argparse
import json
import os
import sys

# Asegurar que la raíz del proyecto esté en el path al ejecutar el script directo.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from backend.core.config import settings  # noqa: E402
from ai_service.rag_pipeline import cargar_o_crear_indice, estado_indice  # noqa: E402


def _resumen(estado: dict) -> str:
    """Resumen legible del estado del índice."""
    plan = estado.get("plan") or {}
    lineas = [
        f"Colección      : {estado['coleccion']}",
        f"Documentos     : {estado['data_dir']}",
        f"Índice         : {estado['chroma_path']}",
        f"Chunks         : {estado['chunks']}",
        f"Modelo         : {estado.get('embedding_model') or 'desconocido'}",
        f"Segmentación   : {estado.get('chunk_size')}/{estado.get('chunk_overlap')}",
        f"Indexado en    : {estado.get('indexado_en') or 'desconocido'}",
        f"Manifiesto     : completo={estado['completo']} adoptado={estado['adoptado']}",
        f"Al día         : {'sí' if estado['actualizado'] else 'no'}",
        (
            "Plan           : "
            f"{len(plan.get('nuevos', []))} nuevos, "
            f"{len(plan.get('modificados', []))} modificados, "
            f"{len(plan.get('eliminados', []))} eliminados, "
            f"{len(plan.get('sin_cambios', []))} sin cambios"
        ),
    ]
    if plan.get("motivo_reconstruccion"):
        lineas.append(f"Reconstrucción : {plan['motivo_reconstruccion']}")
    if estado.get("adoptara"):
        lineas.append(
            "Nota           : hay índice pero no manifiesto: al arrancar se ADOPTARÁ "
            "sin re-embeber, registrando la huella actual. Si algún PDF cambió antes "
            "de este cambio, ese cambio no se detectará: usa --forzar para una línea base limpia."
        )
    if estado.get("error"):
        lineas.append(f"Error          : {estado['error']}")
    for nombre in plan.get("nuevos", []):
        lineas.append(f"  + nuevo      : {nombre}")
    for nombre in plan.get("modificados", []):
        lineas.append(f"  ~ modificado : {nombre}")
    for nombre in plan.get("eliminados", []):
        lineas.append(f"  - eliminado  : {nombre}")
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reindexado manual del índice RAG de las NNAC.",
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Reconstruye el índice desde cero aunque el plan diga que está vigente.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra el estado y los cambios pendientes sin modificar el índice.",
    )
    args = parser.parse_args(argv)

    data_dir = settings.data_dir
    chroma_path = settings.chroma_path

    if args.dry_run:
        estado = estado_indice(data_dir, chroma_path)
        print(_resumen(estado))
        print()
        print(json.dumps(estado, indent=2, ensure_ascii=False))
        return 0

    try:
        cargar_o_crear_indice(
            data_dir=data_dir,
            chroma_path=chroma_path,
            forzar_reconstruccion=args.forzar,
        )
    except Exception as e:
        print(f"❌ No se pudo indexar: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    estado = estado_indice(data_dir, chroma_path)
    print(_resumen(estado))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
