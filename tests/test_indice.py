"""Tests del manifiesto del índice y del reindexado incremental.

Cubren las tres capas:

1. **Plan puro** (`calcular_plan`): qué hacer ante archivos nuevos, modificados,
   eliminados, sin cambios, o ante un manifiesto incompleto/incompatible.
2. **Contrato con Chroma**: que el manifiesto sobreviva el viaje de ida y vuelta
   por la metadata de la colección, que `escribir_manifest` no borre otras
   claves, y que borrar chunks por `archivo` funcione de verdad.
3. **End-to-end**: indexar, añadir, modificar y eliminar PDFs reales usando
   `MockEmbedding` (sin red ni descargas) para comprobar que los chunks viejos se
   borran y los nuevos entran, y que el índice incompatible aborta.

Los PDFs se generan con reportlab (ya es dependencia del proyecto) en
directorios temporales, así que ningún test toca el `data/` ni el `chroma_db/`
reales.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_service import rag_pipeline
from ai_service.errors import ConfigurationError
from ai_service.indice import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CLAVE_MANIFEST,
    InfoArchivo,
    Manifest,
    ParametrosIndice,
    calcular_plan,
    contar_chunks_por_archivo,
    escribir_manifest,
    huella_archivo,
    huellas_de_directorio,
    leer_manifest,
    listar_pdfs,
    reconstruir_manifest_desde_coleccion,
)

# ============================================================================
# Utilidades
# ============================================================================


def escribir_pdf(ruta, texto: str) -> None:
    """Genera un PDF con texto extraíble (para indexarlo de verdad)."""
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(ruta))
    pdf.setFont("Helvetica", 10)
    y = 800
    for linea in texto.split(". "):
        if not linea.strip():
            continue
        pdf.drawString(50, y, linea.strip()[:110])
        y -= 14
        if y < 60:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = 800
    pdf.save()


def texto_largo(marca: str, frases: int = 40) -> str:
    """Texto de varias frases (para producir varios chunks)."""
    return ". ".join(f"{marca} frase clinica numero {i} de prueba" for i in range(frases))


def manifest_con(
    archivos: dict,
    parametros: ParametrosIndice,
    completo: bool = True,
    chunks: int = 1,
) -> Manifest:
    """Manifiesto de prueba con archivos dados (nombre -> sha256)."""
    return Manifest.nuevo(
        parametros,
        completo=completo,
        adoptado=False,
        indexado_en="2026-01-01T00:00:00+00:00",
        archivos={
            nombre: InfoArchivo(nombre=nombre, sha256=sha, chunks=chunks)
            for nombre, sha in archivos.items()
        },
    )


def abrir_coleccion(chroma_path: str):
    """Abre la colección de Chroma para inspeccionarla en los asserts."""
    import chromadb

    cliente = chromadb.PersistentClient(path=chroma_path)
    return cliente.get_collection(rag_pipeline.NOMBRE_COLECCION)


def chunks_de(coleccion, nombre: str) -> list[str]:
    """Ids de los chunks cuyo metadata `archivo` es el indicado."""
    return list(coleccion.get(where={"archivo": nombre}).get("ids") or [])


def manifest_en(chroma_path: str) -> Manifest | None:
    """Manifiesto leído desde una colección recién abierta.

    Chroma cachea la metadata de la colección en el objeto `Collection` del lado
    del cliente, y `modify` solo refresca el objeto que escribe: leer desde un
    objeto abierto antes de una reindexación devolvería un valor viejo. El código
    de producción siempre abre la colección fresca (en cada carga del índice y en
    `estado_indice`), así que el test debe hacer lo mismo.
    """
    return leer_manifest(abrir_coleccion(chroma_path))


def conteo(chroma_path: str) -> int:
    """Chunks de la colección, leyendo una colección recién abierta."""
    return abrir_coleccion(chroma_path).count()


def indexar_en_fresco(entorno, sufijo: str) -> int:
    """Indexa el mismo corpus en una base vectorial nueva y devuelve sus chunks.

    Es el oráculo del reindexado incremental: si al actualizar el índice no se
    hubieran borrado los chunks viejos, quedarían de más y el total no
    coincidiría con el de un índice construido desde cero sobre el mismo corpus.
    """
    data_dir, chroma_path, parametros = entorno
    chroma_fresco = os.path.join(os.path.dirname(chroma_path), sufijo)
    rag_pipeline.cargar_o_crear_indice(
        data_dir=data_dir, chroma_path=chroma_fresco, parametros=parametros
    )
    return abrir_coleccion(chroma_fresco).count()


# ============================================================================
# 1. Plan puro
# ============================================================================


class TestListarPdfs:
    def test_solo_pdfs_y_ordenados(self, tmp_path):
        (tmp_path / "b.pdf").write_bytes(b"b")
        (tmp_path / "a.pdf").write_bytes(b"a")
        (tmp_path / "notas.txt").write_text("no es un pdf")
        (tmp_path / "README.md").write_text("x")
        assert listar_pdfs(str(tmp_path)) == ["a.pdf", "b.pdf"]

    def test_directorio_inexistente(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            listar_pdfs(str(tmp_path / "no-existe"))


class TestHuellas:
    def test_huella_cambia_con_el_contenido(self, tmp_path):
        a = tmp_path / "a.pdf"
        a.write_bytes(b"contenido uno")
        h1 = huella_archivo(str(a))
        a.write_bytes(b"contenido dos")
        assert huella_archivo(str(a)) != h1

    def test_huella_estable_si_no_cambia(self, tmp_path):
        a = tmp_path / "a.pdf"
        a.write_bytes(b"igual")
        assert huella_archivo(str(a)) == huella_archivo(str(a))

    def test_huellas_de_directorio_registra_tamano(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"12345")
        info = huellas_de_directorio(str(tmp_path))["a.pdf"]
        assert info.tamano == 5
        assert info.nombre == "a.pdf"
        assert len(info.sha256) == 64


class TestManifestSerializacion:
    def test_round_trip_json(self):
        parametros = ParametrosIndice()
        original = manifest_con({"a.pdf": "abc"}, parametros)
        recuperado = Manifest.from_json(original.to_json())
        assert recuperado.archivos["a.pdf"].sha256 == "abc"
        assert recuperado.embedding_model == parametros.modelo_embeddings
        assert recuperado.chunk_size == parametros.chunk_size
        assert recuperado.completo is True

    def test_json_corrupto_falla(self):
        with pytest.raises(Exception):
            Manifest.from_json("no es json")

    def test_manifest_vacio_no_es_valido(self):
        """Un manifiesto sin archivos no debe dar por bueno un índice existente."""
        with pytest.raises(ValueError):
            Manifest.from_dict({"archivos": {}})


class TestCalcularPlan:
    @pytest.fixture()
    def parametros(self):
        return ParametrosIndice()

    def test_sin_manifiesto_todo_es_nuevo(self, tmp_path, parametros):
        (tmp_path / "a.pdf").write_bytes(b"a")
        plan = calcular_plan(str(tmp_path), None, parametros)
        assert plan.nuevos == ["a.pdf"]
        assert plan.motivo_reconstruccion is not None
        assert plan.es_bootstrap is True  # primer arranque: se reconstruye solo
        assert plan.to_dict()["requiere_abortar"] is False

    def test_sin_cambios(self, tmp_path, parametros):
        (tmp_path / "a.pdf").write_bytes(b"a")
        manifest = manifest_con(
            {"a.pdf": huella_archivo(str(tmp_path / "a.pdf"))}, parametros
        )
        plan = calcular_plan(str(tmp_path), manifest, parametros)
        assert plan.sin_cambios == ["a.pdf"]
        assert plan.hay_cambios is False
        assert plan.requiere_reconstruccion is False

    def test_detecta_modificado(self, tmp_path, parametros):
        archivo = tmp_path / "a.pdf"
        archivo.write_bytes(b"version 1")
        manifest = manifest_con({"a.pdf": huella_archivo(str(archivo))}, parametros)
        archivo.write_bytes(b"version 2")
        plan = calcular_plan(str(tmp_path), manifest, parametros)
        assert plan.modificados == ["a.pdf"]
        assert plan.a_indexar == ["a.pdf"]
        assert plan.a_eliminar == ["a.pdf"]  # hay que borrar los chunks viejos

    def test_detecta_nuevo(self, tmp_path, parametros):
        (tmp_path / "a.pdf").write_bytes(b"a")
        manifest = manifest_con(
            {"a.pdf": huella_archivo(str(tmp_path / "a.pdf"))}, parametros
        )
        (tmp_path / "nuevo.pdf").write_bytes(b"n")
        plan = calcular_plan(str(tmp_path), manifest, parametros)
        assert plan.nuevos == ["nuevo.pdf"]
        assert plan.a_indexar == ["nuevo.pdf"]
        assert plan.a_eliminar == []  # un archivo nuevo no borra nada

    def test_detecta_eliminado(self, tmp_path, parametros):
        (tmp_path / "a.pdf").write_bytes(b"a")
        manifest = manifest_con(
            {
                "a.pdf": huella_archivo(str(tmp_path / "a.pdf")),
                "borrado.pdf": "hash-viejo",
            },
            parametros,
        )
        plan = calcular_plan(str(tmp_path), manifest, parametros)
        assert plan.eliminados == ["borrado.pdf"]
        assert plan.a_eliminar == ["borrado.pdf"]

    def test_manifiesto_incompleto_fuerza_reconstruccion(self, tmp_path, parametros):
        (tmp_path / "a.pdf").write_bytes(b"a")
        manifest = manifest_con(
            {"a.pdf": huella_archivo(str(tmp_path / "a.pdf"))},
            parametros,
            completo=False,
        )
        plan = calcular_plan(str(tmp_path), manifest, parametros)
        assert plan.requiere_reconstruccion is True
        assert plan.es_bootstrap is True

    def test_modelo_distinto_exige_reconstruccion(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"a")
        viejo = ParametrosIndice(modelo_embeddings="otro-modelo")
        manifest = manifest_con(
            {"a.pdf": huella_archivo(str(tmp_path / "a.pdf"))}, viejo
        )
        plan = calcular_plan(str(tmp_path), manifest, ParametrosIndice())
        assert plan.requiere_reconstruccion is True
        assert plan.es_bootstrap is False  # no es un estado de arranque normal
        assert plan.requiere_abortar is True

    def test_chunking_distinto_exige_reconstruccion(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"a")
        viejo = ParametrosIndice(chunk_size=CHUNK_SIZE + 1, chunk_overlap=CHUNK_OVERLAP)
        manifest = manifest_con(
            {"a.pdf": huella_archivo(str(tmp_path / "a.pdf"))}, viejo
        )
        plan = calcular_plan(str(tmp_path), manifest, ParametrosIndice())
        assert plan.requiere_reconstruccion is True
        assert plan.es_bootstrap is False


# ============================================================================
# 2. Contrato con Chroma
# ============================================================================


@pytest.fixture()
def chroma_temporal(tmp_path):
    """Colección de Chroma vacía en un directorio temporal."""
    import chromadb

    cliente = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    return cliente.get_or_create_collection(
        name=rag_pipeline.NOMBRE_COLECCION, metadata={"description": "prueba"}
    )


class TestManifiestoEnChroma:
    def test_round_trip_en_metadata(self, chroma_temporal):
        parametros = ParametrosIndice()
        escribir_manifest(chroma_temporal, manifest_con({"a.pdf": "abc"}, parametros))
        leido = leer_manifest(chroma_temporal)
        assert leido is not None
        assert leido.archivos["a.pdf"].sha256 == "abc"

    def test_escribir_no_pierde_la_descripcion(self, chroma_temporal):
        """`modify` reemplaza la metadata entera: no debe borrar otras claves."""
        escribir_manifest(chroma_temporal, manifest_con({"a.pdf": "abc"}, ParametrosIndice()))
        assert (chroma_temporal.metadata or {}).get("description") == "prueba"

    def test_sin_manifiesto_devuelve_none(self, chroma_temporal):
        assert leer_manifest(chroma_temporal) is None

    def test_manifiesto_corrupto_devuelve_none(self, chroma_temporal):
        chroma_temporal.modify(metadata={"description": "prueba", CLAVE_MANIFEST: "{roto"})
        assert leer_manifest(chroma_temporal) is None

    def test_borrar_por_archivo(self, chroma_temporal):
        chroma_temporal.add(
            ids=["1", "2", "3"],
            embeddings=[[0.1, 0.1], [0.2, 0.2], [0.3, 0.3]],
            documents=["a", "b", "c"],
            metadatas=[
                {"archivo": "a.pdf"},
                {"archivo": "a.pdf"},
                {"archivo": "b.pdf"},
            ],
        )
        assert contar_chunks_por_archivo(chroma_temporal) == {"a.pdf": 2, "b.pdf": 1}
        chroma_temporal.delete(where={"archivo": "a.pdf"})
        assert contar_chunks_por_archivo(chroma_temporal) == {"b.pdf": 1}
        assert chroma_temporal.count() == 1

    def test_adopcion_registra_huella_actual(self, chroma_temporal, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"a")
        chroma_temporal.add(
            ids=["1"],
            embeddings=[[0.1, 0.1]],
            documents=["texto"],
            metadatas=[{"archivo": "a.pdf"}],
        )
        manifest = reconstruir_manifest_desde_coleccion(
            chroma_temporal, str(tmp_path), ParametrosIndice(), adoptado=True
        )
        assert manifest.adoptado is True
        assert manifest.completo is True
        assert manifest.archivos["a.pdf"].sha256 == huella_archivo(str(tmp_path / "a.pdf"))
        assert manifest.archivos["a.pdf"].chunks == 1

    def test_adopcion_no_bendice_archivo_sin_chunks(self, chroma_temporal, tmp_path):
        """Un PDF presente en disco pero ausente del índice debe quedar pendiente."""
        (tmp_path / "indexado.pdf").write_bytes(b"a")
        (tmp_path / "no-indexado.pdf").write_bytes(b"b")
        chroma_temporal.add(
            ids=["1"],
            embeddings=[[0.1, 0.1]],
            documents=["texto"],
            metadatas=[{"archivo": "indexado.pdf"}],
        )
        manifest = reconstruir_manifest_desde_coleccion(
            chroma_temporal, str(tmp_path), ParametrosIndice(), adoptado=True
        )
        assert "indexado.pdf" in manifest.archivos
        assert "no-indexado.pdf" not in manifest.archivos
        plan = calcular_plan(str(tmp_path), manifest, ParametrosIndice())
        assert plan.nuevos == ["no-indexado.pdf"]

    def test_adopcion_conserva_huerfanos_para_borrarlos(self, chroma_temporal, tmp_path):
        """Chunks de un PDF ya borrado de data/ se registran para poder limpiarlos."""
        chroma_temporal.add(
            ids=["1"],
            embeddings=[[0.1, 0.1]],
            documents=["texto"],
            metadatas=[{"archivo": "fantasma.pdf"}],
        )
        manifest = reconstruir_manifest_desde_coleccion(
            chroma_temporal, str(tmp_path), ParametrosIndice(), adoptado=True
        )
        assert "fantasma.pdf" in manifest.archivos
        plan = calcular_plan(str(tmp_path), manifest, ParametrosIndice())
        assert plan.eliminados == ["fantasma.pdf"]


# ============================================================================
# 3. End-to-end con PDFs reales y embeddings simulados
# ============================================================================


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    """Corpus temporal, Chroma temporal y embeddings falsos (sin red).

    Se usa MockEmbedding en lugar del modelo real: el test verifica la
    *mecánica* del reindexado (qué se borra, qué se inserta, qué queda en el
    manifiesto), no la calidad semántica de los vectores.
    """
    from llama_index.core.embeddings import MockEmbedding

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    chroma_path = str(tmp_path / "chroma")
    parametros = ParametrosIndice(chunk_size=200, chunk_overlap=0)

    monkeypatch.setattr(
        rag_pipeline, "get_embedding_model", lambda: MockEmbedding(embed_dim=8)
    )
    rag_pipeline.limpiar_cache_indices()
    yield str(data_dir), chroma_path, parametros
    rag_pipeline.limpiar_cache_indices()


def cargar(entorno, **kwargs):
    """Carga el índice con el entorno de prueba."""
    data_dir, chroma_path, parametros = entorno
    return rag_pipeline.cargar_o_crear_indice(
        data_dir=data_dir, chroma_path=chroma_path, parametros=parametros, **kwargs
    )


class TestReindexadoEndToEnd:
    def test_primera_indexacion_crea_manifiesto_completo(self, entorno):
        data_dir, chroma_path, parametros = entorno
        escribir_pdf(os.path.join(data_dir, "a.pdf"), texto_largo("alpha"))

        cargar(entorno)

        coleccion = abrir_coleccion(chroma_path)
        assert coleccion.count() > 0
        manifest = leer_manifest(coleccion)
        assert manifest is not None
        assert manifest.completo is True
        assert manifest.adoptado is False
        assert list(manifest.archivos) == ["a.pdf"]
        assert manifest.archivos["a.pdf"].chunks == coleccion.count()

    def test_sin_cambios_no_reindexa(self, entorno, monkeypatch):
        data_dir, chroma_path, _ = entorno
        escribir_pdf(os.path.join(data_dir, "a.pdf"), texto_largo("alpha"))
        cargar(entorno)

        # Si el camino rápido se toma, no debe ni tocarse la segmentación.
        def prohibido(*args, **kwargs):
            raise AssertionError("No debía reindexar: no hay cambios pendientes")

        monkeypatch.setattr(rag_pipeline, "_nodos_de_archivos", prohibido)
        rag_pipeline.limpiar_cache_indices()  # fuerza a replantear el plan

        cargar(entorno)
        assert abrir_coleccion(chroma_path).count() > 0

    def test_archivo_nuevo_se_indexa(self, entorno):
        data_dir, chroma_path, _ = entorno
        escribir_pdf(os.path.join(data_dir, "a.pdf"), texto_largo("alpha"))
        cargar(entorno)

        escribir_pdf(os.path.join(data_dir, "b.pdf"), texto_largo("beta"))
        rag_pipeline.limpiar_cache_indices()
        cargar(entorno)

        coleccion = abrir_coleccion(chroma_path)
        assert chunks_de(coleccion, "b.pdf")
        assert chunks_de(coleccion, "a.pdf")  # lo anterior se conserva
        assert set(leer_manifest(coleccion).archivos) == {"a.pdf", "b.pdf"}

    def test_archivo_modificado_reemplaza_sus_chunks(self, entorno):
        data_dir, chroma_path, _ = entorno
        escribir_pdf(os.path.join(data_dir, "a.pdf"), texto_largo("alpha", frases=40))
        cargar(entorno)

        coleccion = abrir_coleccion(chroma_path)
        chunks_viejos = chunks_de(coleccion, "a.pdf")
        assert len(chunks_viejos) > 1

        # Se reescribe con mucho menos texto.
        escribir_pdf(os.path.join(data_dir, "a.pdf"), "alpha unico")
        rag_pipeline.limpiar_cache_indices()
        cargar(entorno)

        chunks_nuevos = chunks_de(coleccion, "a.pdf")
        assert 0 < len(chunks_nuevos) < len(chunks_viejos)
        manifest = manifest_en(chroma_path)
        assert manifest.archivos["a.pdf"].sha256 == huella_archivo(
            os.path.join(data_dir, "a.pdf")
        )
        assert manifest.archivos["a.pdf"].chunks == len(chunks_nuevos)
        # El contenido del índice debe ser idéntico a uno reconstruido desde
        # cero: así se detecta cualquier chunk viejo que hubiera sobrevivido.
        assert conteo(chroma_path) == indexar_en_fresco(entorno, "chroma_fresco_mod")

    def test_archivo_eliminado_borra_sus_chunks(self, entorno):
        data_dir, chroma_path, _ = entorno
        escribir_pdf(os.path.join(data_dir, "a.pdf"), texto_largo("alpha"))
        escribir_pdf(os.path.join(data_dir, "b.pdf"), texto_largo("beta"))
        cargar(entorno)

        coleccion = abrir_coleccion(chroma_path)
        assert chunks_de(coleccion, "b.pdf")

        os.remove(os.path.join(data_dir, "b.pdf"))
        rag_pipeline.limpiar_cache_indices()
        cargar(entorno)

        assert chunks_de(coleccion, "b.pdf") == []
        assert chunks_de(coleccion, "a.pdf")
        assert set(manifest_en(chroma_path).archivos) == {"a.pdf"}
        assert conteo(chroma_path) == indexar_en_fresco(entorno, "chroma_fresco_del")

    def test_adopcion_de_indice_sin_manifiesto(self, entorno):
        """Índice heredado: se adopta sin reindexar y luego vuelve el camino rápido."""
        data_dir, chroma_path, parametros = entorno
        escribir_pdf(os.path.join(data_dir, "a.pdf"), texto_largo("alpha"))
        cargar(entorno)

        coleccion = abrir_coleccion(chroma_path)
        chunks_antes = coleccion.count()
        # Simula un índice construido antes de que existiera el manifiesto.
        coleccion.modify(metadata={"description": "heredado"})
        rag_pipeline.limpiar_cache_indices()

        # El estado debe avisar de la adopción en lugar de alarmar con
        # "todos los archivos son nuevos" (al adoptar no se re-embebe nada).
        estado = rag_pipeline.estado_indice(data_dir, chroma_path, parametros)
        assert estado["adoptara"] is True
        assert estado["actualizado"] is False

        cargar(entorno)

        manifest = manifest_en(chroma_path)
        assert manifest is not None
        assert manifest.adoptado is True
        assert manifest.completo is True
        assert conteo(chroma_path) == chunks_antes  # no se re-embebió nada

    def test_indice_incompatible_aborta(self, entorno):
        data_dir, chroma_path, parametros = entorno
        escribir_pdf(os.path.join(data_dir, "a.pdf"), texto_largo("alpha"))
        cargar(entorno)

        incompatible = ParametrosIndice(
            modelo_embeddings="modelo-incompatible",
            chunk_size=parametros.chunk_size,
            chunk_overlap=parametros.chunk_overlap,
        )
        rag_pipeline.limpiar_cache_indices()
        with pytest.raises(ConfigurationError) as exc:
            rag_pipeline.cargar_o_crear_indice(
                data_dir=data_dir, chroma_path=chroma_path, parametros=incompatible
            )
        assert "reindexar.py --forzar" in str(exc.value)

    def test_indice_incompatible_se_reconstruye_si_se_autoriza(self, entorno):
        data_dir, chroma_path, parametros = entorno
        escribir_pdf(os.path.join(data_dir, "a.pdf"), texto_largo("alpha"))
        cargar(entorno)

        incompatible = ParametrosIndice(
            modelo_embeddings="modelo-incompatible",
            chunk_size=parametros.chunk_size,
            chunk_overlap=parametros.chunk_overlap,
        )
        rag_pipeline.limpiar_cache_indices()
        rag_pipeline.cargar_o_crear_indice(
            data_dir=data_dir,
            chroma_path=chroma_path,
            parametros=incompatible,
            permitir_reconstruccion=True,
        )

        coleccion = abrir_coleccion(chroma_path)
        manifest = leer_manifest(coleccion)
        assert manifest.embedding_model == "modelo-incompatible"
        assert coleccion.count() > 0

    def test_forzar_reconstruccion(self, entorno):
        data_dir, chroma_path, _ = entorno
        escribir_pdf(os.path.join(data_dir, "a.pdf"), texto_largo("alpha"))
        cargar(entorno)

        coleccion = abrir_coleccion(chroma_path)
        assert leer_manifest(coleccion) is not None

        cargar(entorno, forzar_reconstruccion=True)

        coleccion = abrir_coleccion(chroma_path)
        assert coleccion.count() > 0
        assert leer_manifest(coleccion).completo is True

    def test_estado_indice_detecta_desviacion(self, entorno):
        data_dir, chroma_path, parametros = entorno
        escribir_pdf(os.path.join(data_dir, "a.pdf"), texto_largo("alpha"))
        cargar(entorno)

        estado = rag_pipeline.estado_indice(data_dir, chroma_path, parametros)
        assert estado["existe_indice"] is True
        assert estado["actualizado"] is True
        assert estado["plan"]["sin_cambios"] == ["a.pdf"]
        assert estado["chunks"] > 0

        # Un cambio en disco que aún no se ha indexado debe verse reflejado.
        escribir_pdf(os.path.join(data_dir, "a.pdf"), texto_largo("alpha cambiado"))
        estado = rag_pipeline.estado_indice(data_dir, chroma_path, parametros)
        assert estado["actualizado"] is False
        assert estado["plan"]["modificados"] == ["a.pdf"]

    def test_cache_respeta_rutas_distintas(self, entorno, tmp_path):
        """La firma promete data_dir/chroma_path: no se puede devolver otro índice."""
        data_dir, chroma_path, parametros = entorno
        escribir_pdf(os.path.join(data_dir, "a.pdf"), texto_largo("alpha"))
        cargar(entorno)

        otra_data = tmp_path / "data2"
        otra_data.mkdir()
        escribir_pdf(str(otra_data / "z.pdf"), texto_largo("zeta"))
        otro_chroma = str(tmp_path / "chroma2")

        rag_pipeline.cargar_o_crear_indice(
            data_dir=str(otra_data), chroma_path=otro_chroma, parametros=parametros
        )

        assert list(leer_manifest(abrir_coleccion(otro_chroma)).archivos) == ["z.pdf"]
        # El primero sigue intacto.
        assert list(leer_manifest(abrir_coleccion(chroma_path)).archivos) == ["a.pdf"]


# ============================================================================
# 4. Endpoint de administración
# ============================================================================


class TestEndpointEstadoIndice:
    def _headers(self, client, datos):
        r = client.post("/api/auth/registro", json=datos)
        assert r.status_code == 201, r.text
        r = client.post(
            "/api/auth/login",
            json={"email": datos["email"], "password": datos["password"]},
        )
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_requiere_autenticacion(self, client):
        assert client.get("/api/admin/indice").status_code == 401

    def test_admin_obtiene_estado(self, client):
        headers = self._headers(
            client,
            {
                "ci": "9700001",
                "nombre_completo": "Admin Indice",
                "email": "indice@admin.bo",
                "password": "admin123",
                "rol": "admin",
            },
        )
        r = client.get("/api/admin/indice", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "data_dir" in data and "chroma_path" in data
        assert isinstance(data["archivos"], list)
        assert "existe_indice" in data and "actualizado" in data

    def test_no_admin_recibe_403(self, client):
        headers = self._headers(
            client,
            {
                "ci": "9700002",
                "nombre_completo": "Enfermero Indice",
                "email": "indice@enfermero.bo",
                "password": "enfermero123",
                "rol": "enfermero_triage",
            },
        )
        assert client.get("/api/admin/indice", headers=headers).status_code == 403
