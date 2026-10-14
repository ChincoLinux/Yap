"""Que entra al corpus del RAG, en cada entorno (#262)."""

import os
from pathlib import Path

import pytest

import yap

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def rutas(tmp_path, monkeypatch):
    """Ninguna ruta real: cada test monta solo lo que necesita."""
    nada = str(tmp_path / "no-existe")
    for k in (
        "RAIZ_INSTALACION",
        "DOC_DIR",
        "WHITELIST_APPS",
        "WHITELIST_WEB",
        "CURSOS_DIR",
    ):
        monkeypatch.setattr(yap, k, nada)
    return tmp_path


def _nombres():
    return sorted(os.path.basename(p) for p in yap._rag_corpus_paths())


def test_checkout_sin_docs_de_desarrollo(monkeypatch, rutas):
    monkeypatch.setattr(yap, "RAIZ_INSTALACION", str(RAIZ))
    monkeypatch.setattr(yap, "CURSOS_DIR", str(RAIZ / "cursos"))
    nombres = _nombres()
    assert "USAGE.md" in nombres and "apps.conf" in nombres and "web.conf" in nombres
    assert not any(
        n in nombres for n in ("AGENTS.md", "DEPLOY.md", "ROADMAP.md", "RAG.md")
    )


def test_usage_desde_la_doc_del_paquete(monkeypatch, rutas):
    doc = rutas / "doc"
    doc.mkdir()
    (doc / "USAGE.md").write_text("# guia", encoding="utf-8")
    monkeypatch.setattr(yap, "DOC_DIR", str(doc))
    assert _nombres() == ["USAGE.md"]


def test_usage_junto_al_codigo_tiene_prioridad(monkeypatch, rutas):
    raiz, doc = rutas / "raiz", rutas / "doc"
    raiz.mkdir()
    doc.mkdir()
    (raiz / "USAGE.md").write_text("junto", encoding="utf-8")
    (doc / "USAGE.md").write_text("doc", encoding="utf-8")
    monkeypatch.setattr(yap, "RAIZ_INSTALACION", str(raiz))
    monkeypatch.setattr(yap, "DOC_DIR", str(doc))
    (ruta,) = yap._rag_corpus_paths()
    assert Path(ruta).read_text(encoding="utf-8") == "junto"


def test_whitelist_efectiva_antes_que_la_del_repo(monkeypatch, rutas):
    etc, raiz = rutas / "etc", rutas / "raiz"
    (raiz / "whitelist").mkdir(parents=True)
    etc.mkdir()
    (etc / "apps.conf").write_text("Instalada:x", encoding="utf-8")
    (raiz / "whitelist" / "apps.conf").write_text("Repo:y", encoding="utf-8")
    monkeypatch.setattr(yap, "WHITELIST_APPS", str(etc / "apps.conf"))
    monkeypatch.setattr(yap, "RAIZ_INSTALACION", str(raiz))
    (ruta,) = yap._rag_corpus_paths()
    assert Path(ruta).read_text(encoding="utf-8") == "Instalada:x"


def test_los_fragmentos_de_whitelist_llevan_contexto(monkeypatch, rutas):
    """Sin cabecera, 'que paginas puedo visitar' no comparte ni un token con web.conf."""
    monkeypatch.setattr(yap, "WHITELIST_WEB", str(RAIZ / "whitelist" / "web.conf"))
    chunks = yap._rag_build_chunks()
    assert chunks
    assert all(
        c["text"].startswith(yap._RAG_CABECERA_WHITELIST["web.conf"]) for c in chunks
    )
