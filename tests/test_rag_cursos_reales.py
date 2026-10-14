"""El RAG indexa los cursos que de verdad se distribuyen (#260).

Los tests de test_yap_rag.py usan un curso escrito a mano con indicadores
como strings. El curso real los trae como objetos {id, descripcion}, y eso
hacia que toda consulta terminara en TypeError en un equipo instalado.
Estos tests usan cursos/*.json tal cual.
"""

import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest

import yap

RAIZ = Path(__file__).resolve().parent.parent
CURSOS = sorted((RAIZ / "cursos").glob("*.json"))


@pytest.fixture
def instalado(tmp_path, monkeypatch):
    """Como en un .deb: los cursos reales en CURSOS_DIR, indice en tmp."""
    monkeypatch.setattr(yap, "CURSOS_DIR", str(RAIZ / "cursos"))
    monkeypatch.setattr(yap, "RAG_INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setattr(yap, "RAG_ENABLED", True)
    monkeypatch.setattr(yap, "_RAG_INDEX", None)
    yield
    yap._RAG_INDEX = None


def test_hay_cursos_que_probar():
    assert CURSOS, "no hay cursos/*.json: el test ya no mide nada"


@pytest.mark.parametrize("curso", CURSOS, ids=lambda p: p.name)
def test_cada_curso_real_se_trocea_sin_error(curso):
    data = json.loads(curso.read_text(encoding="utf-8"))
    chunks = yap._rag_chunk_json_curso(data, str(curso))
    assert len(chunks) > 5
    assert all(isinstance(c["text"], str) and c["text"] for c in chunks)


@pytest.mark.parametrize("curso", CURSOS, ids=lambda p: p.name)
def test_los_indicadores_llegan_como_texto_legible(curso):
    """Ni 'dict' ni llaves de Python en el indice: el texto real del indicador."""
    data = json.loads(curso.read_text(encoding="utf-8"))
    textos = " ".join(c["text"] for c in yap._rag_chunk_json_curso(data, str(curso)))
    assert "{'" not in textos and "'id':" not in textos
    for ra in data.get("ras", []):
        for ind in ra.get("indicadores", []):
            if isinstance(ind, dict) and ind.get("descripcion"):
                assert ind["descripcion"][:40] in textos


def test_cmd_query_con_el_curso_instalado_no_revienta(instalado):
    ok = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="respuesta", stderr=""
    )
    with mock.patch.object(yap.subprocess, "run", return_value=ok) as run:
        yap.cmd_query("que es un algoritmo", store_history=False)
    prompt = run.call_args[0][0][run.call_args[0][0].index("-p") + 1]
    assert "Contexto recuperado por RAG" in prompt
    assert "FPY1101" in prompt


def test_un_curso_con_forma_inesperada_no_tumba_la_consulta(tmp_path, monkeypatch):
    raro = tmp_path / "cursos"
    raro.mkdir()
    (raro / "RARO.json").write_text(
        json.dumps({"codigo": "RARO", "ras": ["no soy un dict"], "eas": 7}),
        encoding="utf-8",
    )
    monkeypatch.setattr(yap, "CURSOS_DIR", str(raro))
    monkeypatch.setattr(yap, "RAG_INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setattr(yap, "RAG_ENABLED", True)
    monkeypatch.setattr(yap, "_RAG_INDEX", None)
    chunks = yap._rag_build_chunks()
    assert any("RARO" in c["text"] for c in chunks)
    yap._RAG_INDEX = None


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (None, ""),
        ("hola", "hola"),
        (["a", "b"], "a, b"),
        ({"id": "IL1", "descripcion": "Describe"}, "IL1: Describe"),
        ([{"id": "X"}, "y", None], "X, y"),
        (3, "3"),
    ],
)
def test_rag_texto(valor, esperado):
    assert yap._rag_texto(valor) == esperado
