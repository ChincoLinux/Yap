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


def test_piso_de_recall_instalado(res):
    """Antes de #262 el aula solo veia los cursos: 24/42 alcanzables."""
    inst = _corpus(res, "instalado")
    assert (
        inst["alcanzables"] == inst["preguntas"]
    ), "hay preguntas sin respuesta en el aula"
    assert inst["recall_crudo"]["@5"] >= 85.0, inst["recall_crudo"]


def test_el_aula_y_el_checkout_indexan_lo_mismo(res):
    """Si un cambio de empaquetado los separa, el RAG del aula diverge del
    que se mide y se desarrolla (#262)."""
    dev, inst = _corpus(res, "desarrollo"), _corpus(res, "instalado")
    assert dev["ficheros"] == inst["ficheros"]
    assert dev["fragmentos"] == inst["fragmentos"]


def test_ningun_documento_de_desarrollo_llega_al_prompt(res):
    permitidas = {"USAGE.md", "apps.conf", "web.conf"}
    for c in res["corpus"]:
        for f in c["detalle"]:
            ajenas = {
                x
                for x in f["fuentes_en_prompt"]
                if x not in permitidas and not x.endswith(".json")
            }
            assert not ajenas, f"{c['corpus']} {f['id']}: {ajenas}"


def test_la_simulacion_del_aula_sigue_a_build_deb():
    """rag_eval._arbol_instalado copia el layout del .deb; si build-deb.sh o
    postinst cambian de rutas, la simulacion miente."""
    deb = (RAIZ / "build-deb.sh").read_text(encoding="utf-8")
    postinst = (RAIZ / "packaging/yap/DEBIAN/postinst").read_text(encoding="utf-8")
    assert "usr/share/doc/yap/$doc" in deb and "USAGE.md" in deb
    assert '"$YAP_ETC/whitelist' in postinst or "$YAP_ETC/whitelist" in postinst
    assert "$YAP_ETC/cursos" in postinst
    assert yap.DOC_DIR == "/usr/share/doc/yap"
    assert yap.WHITELIST_APPS.startswith(yap.CONFIG_DIR)


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


def test_el_filtro_no_pierde_aciertos(res):
    """Lo que BM25 recupera en el top 5 sigue llegando al prompt (#263)."""
    for c in res["corpus"]:
        assert c["en_prompt"] >= c["recall_crudo"]["@5"] - 0.01, c["corpus"]


def test_techo_de_contaminacion(res):
    """Antes de #263, 10/10 controles recibian contexto. Medido: 3/10."""
    for c in res["corpus"]:
        assert c["controles_contaminados"] <= 30.0, (
            c["corpus"],
            c["detalle_controles"],
        )


def test_barrido_de_cobertura_es_monotono(res):
    """Subir el minimo nunca anade contexto: si lo hace, el filtro esta roto."""
    filas = res["barrido_cobertura"]
    assert len(filas) >= 3
    for a, b in zip(filas, filas[1:]):
        assert b["controles_contaminados"] <= a["controles_contaminados"]
        assert b["tokens_en_prompt_media"] <= a["tokens_en_prompt_media"]
