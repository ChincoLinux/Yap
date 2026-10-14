"""Filtro de relevancia del RAG (#263)."""

import os
import subprocess
import sys

import yap


def _frag(texto):
    return {"text": texto, "source": "x"}


def test_consulta_solo_de_stopwords_no_recupera_nada():
    assert yap._rag_filtrar_relevantes("que es la", [_frag("que es la vida")]) == []


def test_fragmento_sin_terminos_de_contenido_se_descarta():
    r = [_frag("como se usa la terminal")]
    assert yap._rag_filtrar_relevantes("capital de francia", r, min_cobertura=0.2) == []


def test_fragmento_con_terminos_de_contenido_se_conserva():
    r = [_frag("Estructuras de decision: if, elif, else")]
    assert (
        yap._rag_filtrar_relevantes("como funciona if elif else", r, min_cobertura=0.2)
        == r
    )


def test_las_tildes_no_cuentan():
    r = [_frag("Evaluacion Final Transversal")]
    assert (
        yap._rag_filtrar_relevantes("evaluación transversal", r, min_cobertura=0.5) == r
    )


def test_cobertura_cero_no_filtra_por_contenido():
    r = [_frag("nada que ver")]
    assert yap._rag_filtrar_relevantes("capital de francia", r, min_cobertura=0.0) == r


def test_default_y_variable_de_entorno():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def valor(env):
        r = subprocess.run(
            [sys.executable, "-c", "import yap; print(yap.RAG_MIN_COBERTURA)"],
            cwd=raiz,
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            env=env,
        )
        assert r.returncode == 0, r.stderr
        return float(r.stdout.strip().splitlines()[-1])

    base = {k: v for k, v in os.environ.items() if k != "YAP_RAG_MIN_COBERTURA"}
    assert valor(base) == 0.2
    assert valor({**base, "YAP_RAG_MIN_COBERTURA": "0.5"}) == 0.5


def test_rag_retrieve_aplica_el_filtro(monkeypatch):
    class Indice:
        def query(self, q, top_k=5):
            return [
                _frag("Estructuras de decision: if, elif, else"),
                _frag("instalar paquetes"),
            ]

    monkeypatch.setattr(yap, "RAG_ENABLED", True)
    monkeypatch.setattr(yap, "_rag_load_or_build", lambda: Indice())
    textos = [r["text"] for r in yap.rag_retrieve("como funciona if elif else")]
    assert textos == ["Estructuras de decision: if, elif, else"]
