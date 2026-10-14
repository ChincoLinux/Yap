"""El harness de medicion del RAG (#214) funciona y sostiene un piso.

Los pisos no son la meta: son la medicion de 2026-10-13 menos un margen.
Si un cambio en el RAG los rompe, la regresion se ve en CI en vez de en
el aula. Ver docs/RAG.md, seccion Medicion.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import rag_eval  # noqa: E402
import yap  # noqa: E402


@pytest.fixture(scope="module")
def res():
    return rag_eval.medir()


def _corpus(res, nombre):
    return next(c for c in res["corpus"] if c["corpus"] == nombre)


def test_el_conjunto_es_suficiente():
    datos = rag_eval.cargar_preguntas()
    assert len(datos["preguntas"]) >= 30
    assert len(datos["controles"]) >= 8
    ids = [p["id"] for p in datos["preguntas"]]
    assert len(ids) == len(set(ids))


def test_toda_pregunta_tiene_respuesta_en_el_corpus_de_desarrollo(res):
    """Si una marca no existe en el corpus, la pregunta no mide nada."""
    dev = _corpus(res, "desarrollo")
    malas = [f["id"] for f in dev["detalle"] if not f["alcanzable"]]
    assert not malas, f"preguntas sin respuesta en el corpus: {malas}"


def test_piso_de_recall_desarrollo(res):
    dev = _corpus(res, "desarrollo")
    assert dev["recall_crudo"]["@5"] >= 85.0, dev["recall_crudo"]


def test_piso_de_recall_instalado_sobre_lo_alcanzable(res):
    inst = _corpus(res, "instalado")
    assert inst["alcanzables"] >= 20
    assert inst["recall_crudo_alcanzables"]["@5"] >= 90.0


def test_el_presupuesto_de_tokens_se_respeta(res):
    for c in res["corpus"]:
        assert c["tokens_en_prompt_max"] <= yap.RAG_MAX_CONTEXT_TOKENS


def test_lo_que_llega_al_prompt_no_supera_lo_recuperado(res):
    for c in res["corpus"]:
        assert c["en_prompt"] <= c["recall_crudo"]["@5"] + 0.01


def test_no_toca_el_indice_del_usuario(res):
    """medir() usa un directorio temporal y restaura el estado de yap."""
    assert yap._RAG_INDEX is None
    assert "yap-rag-eval-" not in yap.RAG_INDEX_DIR


def test_barrido_cubre_ambos_corpus(res):
    corpus = {b["corpus"] for b in res["barrido"]}
    assert corpus == {"desarrollo", "instalado"}


def test_benchmark_rag_corre_sin_modelo(tmp_path):
    salida = tmp_path / "r.json"
    r = subprocess.run(
        [sys.executable, "tests/benchmark.py", "--rag", "--json", str(salida)],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        env={**os.environ, "PATH": "/usr/bin:/bin"},
    )
    assert r.returncode == 0, r.stderr
    assert "recall" in r.stdout
    assert salida.is_file()
