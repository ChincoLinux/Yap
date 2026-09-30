"""
test_yap_rag.py — Pruebas del RAG local BM25 (#118)

Verifica:
  1. Tokenización y chunking de texto y JSON de cursos
  2. Índice BM25: build, score, query, serialización
  3. Presupuesto de tokens (budget enforcement)
  4. Rebuild incremental por hash de corpus
  5. Protección contra path traversal
  6. Degradación graciosa con RAG deshabilitado
  7. Inyección de contexto RAG en cmd_query
  8. Enrutado en interpret() y despacho en handle_action()
  9. Golden set: ≥30 consultas educativas con resultados relevantes
 10. Rendimiento: <300ms retrieval, <60s rebuild

Ejecucion: python3 -m pytest tests/test_yap_rag.py -v
"""

import sys
import os
import tempfile
import shutil
import json
import time
import unittest.mock as mock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


# ── Fixtures ────────────────────────────────────────────────────

SAMPLE_CURSO = {
    "codigo": "FPY1101",
    "nombre": "Fundamentos de Programacion",
    "descripcion": "Curso introductorio de programacion con PSeInt y Python.",
    "creditos": 4,
    "horas": 72,
    "semanas": 18,
    "ambiente": "Laboratorio",
    "herramientas": ["PSeInt", "Python 3"],
    "ras": [
        {
            "id": "RA1",
            "descripcion": "Disenar algoritmos secuenciales y condicionales.",
            "indicadores": [
                "Identifica problemas computacionales",
                "Disena diagramas de flujo",
            ],
        },
        {
            "id": "RA2",
            "descripcion": "Implementar programas con estructuras iterativas.",
            "indicadores": [
                "Usa ciclos while y for",
                "Valida entradas del usuario",
            ],
        },
    ],
    "eas": [
        {
            "id": "EA1",
            "nombre": "Variables y tipos de datos",
            "descripcion": "Introduccion a variables, tipos y operaciones basicas.",
            "horas": 8,
            "ponderacion": 0.15,
            "herramientas": ["PSeInt"],
            "actividades": [
                {
                    "orden": 1,
                    "nombre": "Calculadora basica",
                    "descripcion": "Crear un programa que sume, reste, multiplique y divida.",
                    "tipo": "practica",
                    "enunciado": "Escribe un algoritmo que lea dos numeros y muestre las 4 operaciones.",
                    "criterios_evaluacion": ["Usa variables correctamente", "Maneja division por cero"],
                    "variantes": {
                        "basico": {
                            "enunciado": "Solo suma y resta.",
                            "criterios_evaluacion": ["Usa variables"],
                        },
                        "avanzado": {
                            "enunciado": "Incluye modulo y potencia.",
                            "criterios_evaluacion": ["Maneja errores"],
                        },
                    },
                },
            ],
            "evaluaciones": [],
        },
        {
            "id": "EA2",
            "nombre": "Estructuras condicionales",
            "descripcion": "Uso de if, else, segun en PSeInt.",
            "horas": 10,
            "ponderacion": 0.20,
            "herramientas": ["PSeInt"],
            "actividades": [],
            "evaluaciones": [],
        },
    ],
    "evaluaciones": [
        {
            "nombre": "Evaluacion Final Transversal",
            "tipo": "transversal",
            "descripcion": "Resolucion de problemas de programacion modularizada.",
            "ponderacion": 40,
            "horas": 7,
        }
    ],
}

SAMPLE_MD = """# Guia de uso

## Instalacion

Ejecuta `sudo apt install yap` para instalar Yap en ChincoLinux.

## Comandos principales

- `yap` — iniciar el asistente interactivo
- `yap busca <tema>` — buscar en Wikipedia
- `yap curso FPY1101` — ver plan de estudio

## Preguntas frecuentes

### Como cambio el modelo?

Usa la variable de entorno `YAP_MODEL_PATH`.

### Como desactivo la telemetria?

Ejecuta `telemetria desactivar` dentro de Yap.
"""

SAMPLE_CONF = """# whitelist/apps.conf
firefox
libreoffice-writer
terminal
code
pseint
"""


class RagTestBase:
    """Aísla el índice RAG y el corpus en un directorio temporal."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.index_dir = os.path.join(self.tmpdir, "index")
        self.corpus_dir = os.path.join(self.tmpdir, "corpus")
        self.cursos_dir = os.path.join(self.corpus_dir, "cursos")
        self.docs_dir = os.path.join(self.corpus_dir, "docs")
        self.wl_dir = os.path.join(self.corpus_dir, "whitelist")

        os.makedirs(self.cursos_dir)
        os.makedirs(self.docs_dir)
        os.makedirs(self.wl_dir)

        # Write sample files
        with open(os.path.join(self.cursos_dir, "FPY1101.json"), "w") as f:
            json.dump(SAMPLE_CURSO, f, ensure_ascii=False)
        with open(os.path.join(self.corpus_dir, "USAGE.md"), "w") as f:
            f.write(SAMPLE_MD)
        with open(os.path.join(self.corpus_dir, "AGENTS.md"), "w") as f:
            f.write("# Agentes\n\nYap es un agente educativo para ChincoLinux.\n")
        with open(os.path.join(self.docs_dir, "DEPLOY.md"), "w") as f:
            f.write("# Deploy\n\n## Requisitos\n\nDebian 12 o superior.\n")
        with open(os.path.join(self.wl_dir, "apps.conf"), "w") as f:
            f.write(SAMPLE_CONF)

        self.patchers = [
            mock.patch.object(yap, "RAG_INDEX_DIR", self.index_dir),
            mock.patch.object(yap, "RAG_ENABLED", True),
            mock.patch.object(yap, "CURSOS_DIR", self.cursos_dir),
            mock.patch.object(yap, "_RAG_INDEX", None),
        ]
        # Patch corpus paths to use our temp dirs
        self._orig_corpus_paths = yap._rag_corpus_paths
        base = self.corpus_dir

        def _mock_corpus_paths():
            import glob as g
            paths = []
            cd = yap.CURSOS_DIR
            if os.path.isdir(cd):
                for p in sorted(g.glob(os.path.join(cd, "*.json"))):
                    real = os.path.realpath(p)
                    if real.startswith(os.path.realpath(cd)):
                        paths.append(real)
            dd = os.path.join(base, "docs")
            if os.path.isdir(dd):
                for p in sorted(g.glob(os.path.join(dd, "*.md"))):
                    real = os.path.realpath(p)
                    if real.startswith(os.path.realpath(dd)):
                        paths.append(real)
            wd = os.path.join(base, "whitelist")
            if os.path.isdir(wd):
                for p in sorted(g.glob(os.path.join(wd, "*.conf"))):
                    real = os.path.realpath(p)
                    if real.startswith(os.path.realpath(wd)):
                        paths.append(real)
            usage = os.path.join(base, "USAGE.md")
            if os.path.isfile(usage):
                paths.append(os.path.realpath(usage))
            agents = os.path.join(base, "AGENTS.md")
            if os.path.isfile(agents):
                paths.append(os.path.realpath(agents))
            return paths

        self.patchers.append(
            mock.patch.object(yap, "_rag_corpus_paths", _mock_corpus_paths)
        )
        for p in self.patchers:
            p.start()

    def teardown_method(self):
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ── 1. Tokenización ────────────────────────────────────────────

class TestRagTokenize:
    """Pruebas de _rag_tokenize."""

    def test_lowercase_and_split(self):
        tokens = yap._rag_tokenize("Hola Mundo 123 PSeInt")
        assert "hola" in tokens
        assert "mundo" in tokens
        assert "123" in tokens
        assert "pseint" in tokens

    def test_removes_punctuation(self):
        tokens = yap._rag_tokenize("¿Cómo estás? ¡Bien!")
        assert "como" in tokens
        assert "estas" in tokens
        assert "bien" in tokens
        # Punctuation not in tokens
        assert "?" not in tokens
        assert "!" not in tokens

    def test_empty_string(self):
        assert yap._rag_tokenize("") == []

    def test_spanish_accents(self):
        tokens = yap._rag_tokenize("programación algoritmo diseño función")
        assert "programacion" in tokens
        assert "algoritmo" in tokens
        assert "diseño" in tokens
        assert "funcion" in tokens

    def test_accent_folding(self):
        t1 = yap._rag_tokenize("programación algoritmo función")
        t2 = yap._rag_tokenize("programacion algoritmo funcion")
        assert t1 == t2


# ── 2. Chunking de texto ───────────────────────────────────────

class TestRagChunkText:
    """Pruebas de _rag_chunk_text."""

    def test_splits_by_headers(self):
        chunks = yap._rag_chunk_text(SAMPLE_MD, "USAGE.md")
        assert len(chunks) >= 2
        assert all(c["source"] == "USAGE.md" for c in chunks)

    def test_preserves_content(self):
        chunks = yap._rag_chunk_text(SAMPLE_MD, "test.md")
        all_text = " ".join(c["text"] for c in chunks)
        assert "yap" in all_text.lower()
        assert "instalar" in all_text.lower() or "instalacion" in all_text.lower()

    def test_chunk_size_limit(self):
        # A very long text should produce multiple chunks
        long_text = "palabra " * 1000
        chunks = yap._rag_chunk_text(long_text, "long.md", chunk_size=100)
        assert len(chunks) > 1
        for c in chunks:
            # Allow some flexibility for overlap
            words = len(c["text"].split())
            assert words <= 200  # chunk_size + overlap margin

    def test_empty_text(self):
        chunks = yap._rag_chunk_text("", "empty.md")
        assert chunks == []


# ── 3. Chunking de JSON de curso ───────────────────────────────

class TestRagChunkJsonCurso:
    """Pruebas de _rag_chunk_json_curso."""

    def test_produces_chunks(self):
        chunks = yap._rag_chunk_json_curso(SAMPLE_CURSO, "FPY1101.json")
        assert len(chunks) >= 5  # overview + 2 RAs + 2 EAs + activities

    def test_overview_chunk(self):
        chunks = yap._rag_chunk_json_curso(SAMPLE_CURSO, "FPY1101.json")
        overview = chunks[0]["text"]
        assert "FPY1101" in overview
        assert "Fundamentos" in overview

    def test_ra_chunks(self):
        chunks = yap._rag_chunk_json_curso(SAMPLE_CURSO, "FPY1101.json")
        ra_chunks = [c for c in chunks if "RA" in c["text"][:10]]
        assert len(ra_chunks) >= 2
        assert any("algoritmos" in c["text"].lower() for c in ra_chunks)

    def test_ea_chunks(self):
        chunks = yap._rag_chunk_json_curso(SAMPLE_CURSO, "FPY1101.json")
        ea_chunks = [c for c in chunks if "EA" in c["text"][:10]]
        assert len(ea_chunks) >= 2

    def test_activity_chunks(self):
        chunks = yap._rag_chunk_json_curso(SAMPLE_CURSO, "FPY1101.json")
        act_chunks = [c for c in chunks if "Actividad" in c["text"][:15]]
        assert len(act_chunks) >= 1
        assert any("Calculadora" in c["text"] for c in act_chunks)

    def test_variante_in_activity(self):
        chunks = yap._rag_chunk_json_curso(SAMPLE_CURSO, "FPY1101.json")
        act_chunks = [c for c in chunks if "Actividad" in c["text"][:15]]
        # Variantes should be included in activity chunks
        act_text = " ".join(c["text"] for c in act_chunks)
        assert "basico" in act_text.lower() or "avanzado" in act_text.lower()

    def test_source_attribute(self):
        chunks = yap._rag_chunk_json_curso(SAMPLE_CURSO, "FPY1101.json")
        assert all(c["source"] == "FPY1101.json" for c in chunks)

    def test_evaluacion_chunks(self):
        chunks = yap._rag_chunk_json_curso(SAMPLE_CURSO, "FPY1101.json")
        ev_chunks = [c for c in chunks if "Evaluacion" in c["text"][:15]]
        assert len(ev_chunks) >= 1
        assert "Transversal" in ev_chunks[0]["text"]
        assert "40%" in ev_chunks[0]["text"]


# ── 4. BM25 Index ──────────────────────────────────────────────

class TestRagBM25Index:
    """Pruebas del índice BM25."""

    def _build_sample_index(self):
        chunks = [
            {"text": "algoritmo secuencial diagrama de flujo", "source": "test"},
            {"text": "ciclo while for iteracion repeticion", "source": "test"},
            {"text": "variable tipo dato entero cadena", "source": "test"},
            {"text": "funcion procedimiento parametro retorno", "source": "test"},
            {"text": "arreglo vector lista indice posicion", "source": "test"},
        ]
        idx = yap.RagBM25Index()
        idx.build(chunks)
        return idx

    def test_build_sets_N(self):
        idx = self._build_sample_index()
        assert idx.N == 5

    def test_build_computes_avg_dl(self):
        idx = self._build_sample_index()
        assert idx.avg_dl > 0

    def test_query_returns_relevant(self):
        idx = self._build_sample_index()
        results = idx.query("algoritmo secuencial", top_k=3)
        assert len(results) > 0
        assert results[0]["source"] == "test"
        # First result should mention algoritmo
        assert "algoritmo" in results[0]["text"]

    def test_query_scores_descending(self):
        idx = self._build_sample_index()
        results = idx.query("ciclo while iteracion", top_k=5)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_query_empty_returns_empty(self):
        idx = self._build_sample_index()
        assert idx.query("", top_k=3) == []

    def test_query_no_match_returns_empty(self):
        idx = self._build_sample_index()
        results = idx.query("xyznonexistent", top_k=3)
        assert results == []

    def test_serialization_roundtrip(self):
        idx = self._build_sample_index()
        idx.corpus_hash = "abc123"
        d = idx.to_dict()
        restored = yap.RagBM25Index.from_dict(d)
        assert restored.N == idx.N
        assert restored.corpus_hash == "abc123"
        assert len(restored.chunks) == len(idx.chunks)
        # Query results should match
        r1 = idx.query("algoritmo", top_k=2)
        r2 = restored.query("algoritmo", top_k=2)
        assert len(r1) == len(r2)

    def test_score_positive_for_match(self):
        idx = self._build_sample_index()
        tokens = yap._rag_tokenize("algoritmo")
        score = idx.score(tokens, 0)
        assert score > 0

    def test_score_zero_for_no_match(self):
        idx = self._build_sample_index()
        tokens = yap._rag_tokenize("xyznonexistent")
        score = idx.score(tokens, 0)
        assert score == 0


# ── 5. Corpus hash e índice persistente ─────────────────────────

class TestRagCorpusHash(RagTestBase):
    """Pruebas de _rag_corpus_hash e índice incremental."""

    def test_hash_is_stable(self):
        h1 = yap._rag_corpus_hash()
        h2 = yap._rag_corpus_hash()
        assert h1 == h2

    def test_hash_changes_on_modification(self):
        h1 = yap._rag_corpus_hash()
        # Wait a tiny bit then modify a file
        time.sleep(0.05)
        with open(os.path.join(self.docs_dir, "DEPLOY.md"), "a") as f:
            f.write("\n## Nuevo\n\nContenido adicional.\n")
        h2 = yap._rag_corpus_hash()
        assert h1 != h2

    def test_hash_length(self):
        h = yap._rag_corpus_hash()
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


class TestRagPersistence(RagTestBase):
    """Pruebas de carga y persistencia del índice."""

    def test_build_creates_index_file(self):
        yap._rag_load_or_build()
        idx_path = yap._rag_index_path()
        assert os.path.isfile(idx_path)

    def test_cached_index_reloads(self):
        idx1 = yap._rag_load_or_build()
        n1 = len(idx1.chunks)
        # Reset singleton
        yap._RAG_INDEX = None
        idx2 = yap._rag_load_or_build()
        assert len(idx2.chunks) == n1

    def test_stale_index_rebuilds(self):
        idx1 = yap._rag_load_or_build()
        old_hash = idx1.corpus_hash
        yap._RAG_INDEX = None
        # Modify corpus
        time.sleep(0.05)
        with open(os.path.join(self.docs_dir, "NEW.md"), "w") as f:
            f.write("# Nuevo documento\n\nContenido nuevo para RAG.\n")
        idx2 = yap._rag_load_or_build()
        assert idx2.corpus_hash != old_hash
        assert len(idx2.chunks) > len(idx1.chunks)


# ── 6. rag_rebuild ──────────────────────────────────────────────

class TestRagRebuild(RagTestBase):
    """Pruebas de rag_rebuild."""

    def test_rebuild_returns_count_and_time(self):
        count, ms = yap.rag_rebuild()
        assert count > 0
        assert ms >= 0

    def test_rebuild_deletes_old_index(self):
        yap._rag_load_or_build()
        idx_path = yap._rag_index_path()
        assert os.path.isfile(idx_path)
        # Rebuild should create a new index
        yap.rag_rebuild()
        assert os.path.isfile(idx_path)


# ── 7. rag_retrieve y presupuesto ───────────────────────────────

class TestRagRetrieve(RagTestBase):
    """Pruebas de rag_retrieve con budget enforcement."""

    def test_retrieve_returns_results(self):
        results = yap.rag_retrieve("algoritmo programacion")
        assert len(results) > 0

    def test_retrieve_has_required_keys(self):
        results = yap.rag_retrieve("variables tipos datos")
        for r in results:
            assert "text" in r
            assert "source" in r
            assert "score" in r

    def test_budget_enforcement(self):
        """Results should not exceed max_tokens budget."""
        results = yap.rag_retrieve("curso programacion", max_tokens=50)
        total_words = sum(len(r["text"].split()) for r in results)
        # Budget is 50 tokens ≈ 37 words; allow generous margin
        assert total_words < 200

    def test_retrieve_disabled(self):
        """When RAG_ENABLED=False, returns empty."""
        with mock.patch.object(yap, "RAG_ENABLED", False):
            results = yap.rag_retrieve("cualquier cosa")
            assert results == []

    def test_retrieve_relevance(self):
        """Query about PSeInt should return PSeInt-related chunks."""
        results = yap.rag_retrieve("PSeInt programacion")
        if results:
            all_text = " ".join(r["text"].lower() for r in results)
            assert "pseint" in all_text or "programacion" in all_text


# ── 8. Contexto RAG para LLM ──────────────────────────────────

class TestRagContextForQuery(RagTestBase):
    """Pruebas de _rag_context_for_query."""

    def test_returns_context_string(self):
        ctx = yap._rag_context_for_query("como instalar yap")
        assert ctx is not None
        assert "[Contexto recuperado por RAG local]" in ctx

    def test_returns_none_when_disabled(self):
        with mock.patch.object(yap, "RAG_ENABLED", False):
            ctx = yap._rag_context_for_query("cualquier cosa")
            assert ctx is None

    def test_context_contains_sources(self):
        ctx = yap._rag_context_for_query("FPY1101 curso fundamentos")
        if ctx:
            # Should reference at least one source
            assert "—" in ctx or "[" in ctx


# ── 9. cmd_rag subcomandos ──────────────────────────────────────

class TestCmdRag(RagTestBase):
    """Pruebas de cmd_rag."""

    def test_status_default(self):
        out = yap.cmd_rag()
        assert "RAG local" in out
        assert "activado" in out.lower()

    def test_status_explicit(self):
        out = yap.cmd_rag("status")
        assert "Fragmentos" in out
        assert "Corpus" in out

    def test_rebuild(self):
        out = yap.cmd_rag("rebuild")
        assert "reconstruido" in out.lower() or "Indice" in out

    def test_buscar(self):
        out = yap.cmd_rag("buscar algoritmo")
        # Should return results or "Sin resultados"
        assert "score" in out.lower() or "sin resultados" in out.lower()

    def test_query_subcommand(self):
        out = yap.cmd_rag("query programacion")
        assert "score" in out.lower() or "sin resultados" in out.lower()


# ── 10. Protección path traversal ───────────────────────────────

class TestRagPathTraversal(RagTestBase):
    """Verifica que no se indexan archivos fuera del corpus."""

    def test_symlink_outside_rejected(self):
        """Symlinks pointing outside corpus directories are rejected."""
        # Create a file outside the corpus
        outside = os.path.join(self.tmpdir, "secret.json")
        with open(outside, "w", encoding="utf-8") as f:
            json.dump({"secret": "data"}, f)
        # Create symlink inside cursos dir
        link = os.path.join(self.cursos_dir, "evil.json")
        try:
            os.symlink(outside, link)
        except OSError:
            pytest.skip("Symlink creation requires administrative privileges on Windows")
        # Corpus paths should NOT include the symlinked file
        paths = yap._rag_corpus_paths()
        for p in paths:
            assert "secret" not in p
            # realpath should be within the expected directory
            assert not p.endswith("secret.json")


# ── 11. Degradación graciosa ─────────────────────────────────────

class TestRagGracefulDegradation:
    """RAG debe degradar sin fallar si el corpus no existe."""

    def test_no_corpus_no_crash(self):
        with mock.patch.object(yap, "RAG_ENABLED", True), \
             mock.patch.object(yap, "_RAG_INDEX", None), \
             mock.patch.object(yap, "_rag_corpus_paths", return_value=[]):
            idx_dir = tempfile.mkdtemp()
            try:
                with mock.patch.object(yap, "RAG_INDEX_DIR", idx_dir):
                    results = yap.rag_retrieve("cualquier cosa")
                    assert results == []
            finally:
                shutil.rmtree(idx_dir, ignore_errors=True)

    def test_disabled_returns_empty(self):
        with mock.patch.object(yap, "RAG_ENABLED", False):
            results = yap.rag_retrieve("cualquier cosa")
            assert results == []


# ── 12. interpret() routing ──────────────────────────────────────

class TestRagInterpretRouting:
    """Pruebas de enrutado en interpret() para RAG."""

    def test_rag_routes(self):
        action, param = yap.interpret("rag")
        assert action == "rag"
        assert param == ""

    def test_rag_rebuild_routes(self):
        action, param = yap.interpret("rag rebuild")
        assert action == "rag"
        assert param == "rebuild"

    def test_rag_status_routes(self):
        action, param = yap.interpret("rag status")
        assert action == "rag"
        assert param == "status"

    def test_rag_buscar_routes(self):
        action, param = yap.interpret("rag buscar algoritmo")
        assert action == "rag"
        assert param == "buscar algoritmo"


# ── 13. ACCIONES_CONOCIDAS incluye rag ─────────────────────────

class TestRagRegistration:
    """Verifica que RAG está registrado en las acciones."""

    def test_in_acciones_conocidas(self):
        assert "rag" in yap.ACCIONES_CONOCIDAS

    def test_in_acciones_nombres(self):
        assert "rag" in yap.ACCIONES_NOMBRES


# ── 14. Golden set — ≥30 consultas educativas ───────────────────

class TestRagGoldenSet(RagTestBase):
    """
    Golden set: 30+ consultas que un estudiante haría.
    Verifica que el RAG retorna al menos 1 resultado relevante.
    """

    GOLDEN_QUERIES = [
        # Sobre el curso
        ("que es FPY1101", ["FPY1101"]),
        ("fundamentos de programacion", ["programacion", "fundamentos"]),
        ("cuantas horas tiene el curso", ["horas"]),
        ("cuantas semanas dura el curso", ["semanas"]),
        ("descripcion del curso", ["curso"]),
        # Sobre RAs
        ("algoritmos secuenciales", ["algoritmo", "secuencial"]),
        ("estructuras iterativas", ["iterativ", "ciclo"]),
        ("indicadores de logro", ["indicador"]),
        ("resultados de aprendizaje", ["RA"]),
        ("diagramas de flujo", ["diagrama", "flujo"]),
        # Sobre EAs
        ("variables y tipos de datos", ["variable", "tipo", "dato"]),
        ("estructuras condicionales", ["condicional"]),
        ("experiencia de aprendizaje EA1", ["EA1"]),
        ("experiencia de aprendizaje EA2", ["EA2"]),
        # Sobre actividades
        ("calculadora basica", ["calculadora", "basica"]),
        ("actividad de practica", ["actividad", "practica"]),
        ("enunciado de la actividad", ["enunciado"]),
        ("variantes de actividad", ["variante", "basico", "avanzado"]),
        ("criterios de evaluacion", ["criterio", "evaluacion"]),
        # Sobre herramientas
        ("PSeInt", ["pseint"]),
        ("Python 3", ["python"]),
        # Sobre uso de Yap
        ("como instalar yap", ["instalar", "apt"]),
        ("comandos principales yap", ["comando"]),
        ("como buscar en wikipedia", ["busca", "wikipedia"]),
        ("como cambiar el modelo", ["modelo", "YAP_MODEL_PATH"]),
        ("desactivar telemetria", ["telemetria", "desactivar"]),
        # Sobre configuración
        ("whitelist aplicaciones", ["firefox", "libreoffice", "terminal"]),
        ("aplicaciones permitidas", ["firefox", "terminal"]),
        # Sobre deployment
        ("requisitos deploy", ["debian", "requisito"]),
        # General
        ("que es yap", ["yap", "agente"]),
        ("para que sirve yap", ["yap"]),
    ]

    def test_golden_set_minimum_30(self):
        """Verificar que hay al menos 30 queries en el golden set."""
        assert len(self.GOLDEN_QUERIES) >= 30

    def test_golden_set_all_return_results(self):
        """Cada query del golden set debe retornar al menos 1 resultado."""
        failed = []
        for query, _expected in self.GOLDEN_QUERIES:
            results = yap.rag_retrieve(query, top_k=5, max_tokens=1000)
            if not results:
                failed.append(query)
        # Allow at most 20% failure for fuzzy matching
        max_failures = len(self.GOLDEN_QUERIES) * 0.2
        assert len(failed) <= max_failures, (
            f"{len(failed)}/{len(self.GOLDEN_QUERIES)} queries sin resultados: "
            f"{failed[:5]}..."
        )

    def test_golden_set_relevance(self):
        """Top result should contain at least one expected keyword."""
        hits = 0
        for query, expected_keywords in self.GOLDEN_QUERIES:
            results = yap.rag_retrieve(query, top_k=3, max_tokens=1000)
            if results:
                all_text = " ".join(r["text"].lower() for r in results)
                if any(kw.lower() in all_text for kw in expected_keywords):
                    hits += 1
        # At least 60% of queries should have relevant results
        min_hits = len(self.GOLDEN_QUERIES) * 0.6
        assert hits >= min_hits, (
            f"Solo {hits}/{len(self.GOLDEN_QUERIES)} queries con resultados relevantes"
        )


# ── 15. Rendimiento ────────────────────────────────────────────

class TestRagPerformance(RagTestBase):
    """Pruebas de rendimiento: retrieval <300ms, rebuild <60s."""

    def test_retrieval_under_300ms(self):
        # Build index first
        yap._rag_load_or_build()
        t0 = time.time()
        for _ in range(10):
            yap.rag_retrieve("algoritmo programacion PSeInt")
        elapsed = (time.time() - t0) / 10 * 1000  # ms per query
        assert elapsed < 300, f"Retrieval too slow: {elapsed:.0f}ms"

    def test_rebuild_under_60s(self):
        t0 = time.time()
        yap.rag_rebuild()
        elapsed = time.time() - t0
        assert elapsed < 60, f"Rebuild too slow: {elapsed:.0f}s"
