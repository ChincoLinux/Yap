#!/usr/bin/env python3
"""Medicion del RAG local (#214): recall@k, coste y contaminacion.

Mide la recuperacion, no la generacion: no hace falta modelo ni llama-cli.
Usa el camino real de Yap (`rag_retrieve`, con su recorte por presupuesto
de tokens) sobre dos corpus:

  * desarrollo: lo que indexa un checkout del repo (docs/, USAGE.md,
    AGENTS.md, whitelist/ y cursos/).
  * instalado:  lo que indexa un equipo con el .deb. `yap.py` vive en
    /opt/yap y el corpus se busca junto a el; build-deb.sh no instala alli
    docs/ ni whitelist/ ni USAGE.md, asi que solo quedan los cursos de
    /etc/yap/cursos.

Uso:

    python3 tests/rag_eval.py                # informe en texto
    python3 tests/rag_eval.py --json r.json  # ademas, resultados en JSON
    python3 tests/benchmark.py --rag         # lo mismo, desde el benchmark
"""

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PREGUNTAS = Path(__file__).resolve().parent / "rag_eval" / "preguntas.json"
KS = (1, 3, 5, 8)

sys.path.insert(0, str(RAIZ))
import yap  # noqa: E402


def _plegar(texto):
    return texto.lower().translate(yap._RAG_ACCENT_MAP)


def cargar_preguntas(path=PREGUNTAS):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def corpus(nombre):
    """Rutas del corpus `desarrollo` o `instalado` (ver docstring)."""
    yap.CURSOS_DIR = str(RAIZ / "cursos")
    todas = yap._rag_corpus_paths()
    if nombre == "desarrollo":
        return todas
    if nombre == "instalado":
        cursos = os.path.realpath(yap.CURSOS_DIR)
        return [p for p in todas if os.path.dirname(p) == cursos]
    raise ValueError(nombre)


def construir_indice(rutas, chunk_size=None):
    """Indice BM25 sobre `rutas`, con el chunking real de Yap."""
    original = yap._rag_corpus_paths
    original_chunk = yap._rag_chunk_text
    yap._rag_corpus_paths = lambda: list(rutas)
    if chunk_size:
        yap._rag_chunk_text = lambda t, s, _n=chunk_size: original_chunk(t, s, _n)
    try:
        t0 = time.perf_counter()
        chunks = yap._rag_build_chunks()
        idx = yap.RagBM25Index()
        idx.build(chunks)
        ms = (time.perf_counter() - t0) * 1000
    finally:
        yap._rag_corpus_paths = original
        yap._rag_chunk_text = original_chunk
    return idx, chunks, ms


def acierta(fragmento, aceptables):
    fuente = os.path.basename(fragmento.get("source", ""))
    texto = _plegar(fragmento.get("text", ""))
    return any(
        fuente == a["fuente"] and _plegar(a["marca"]) in texto for a in aceptables
    )


def alcanzable(chunks, aceptables):
    """La respuesta esta en el corpus: algun fragmento la contiene."""
    return any(acierta(c, aceptables) for c in chunks)


def _tokens(fragmentos):
    # Mismo estimador que rag_retrieve: palabras / 0.75
    return sum(len(f.get("text", "").split()) / 0.75 for f in fragmentos)


def medir_corpus(nombre, datos):
    rutas = corpus(nombre)
    idx, chunks, ms_build = construir_indice(rutas)
    yap._RAG_INDEX = idx
    yap.RAG_ENABLED = True

    filas = []
    for p in datos["preguntas"]:
        crudos = idx.query(p["pregunta"], top_k=max(KS))
        t0 = time.perf_counter()
        inyectados = yap.rag_retrieve(p["pregunta"])
        ms = (time.perf_counter() - t0) * 1000
        rango = next(
            (i + 1 for i, f in enumerate(crudos) if acierta(f, p["aceptables"])), None
        )
        filas.append(
            {
                "id": p["id"],
                "alcanzable": alcanzable(chunks, p["aceptables"]),
                "rango": rango,
                "en_prompt": any(acierta(f, p["aceptables"]) for f in inyectados),
                "fragmentos_en_prompt": len(inyectados),
                "tokens_en_prompt": round(_tokens(inyectados)),
                "fuentes_en_prompt": [
                    os.path.basename(f["source"]) for f in inyectados
                ],
                "score_top1": round(crudos[0]["score"], 2) if crudos else 0.0,
                "ms": round(ms, 2),
            }
        )

    controles = []
    for c in datos["controles"]:
        crudos = idx.query(c, top_k=1)
        inyectados = yap.rag_retrieve(c)
        controles.append(
            {
                "pregunta": c,
                "contaminada": bool(inyectados),
                "tokens_en_prompt": round(_tokens(inyectados)),
                "score_top1": round(crudos[0]["score"], 2) if crudos else 0.0,
                "fuente_top1": os.path.basename(crudos[0]["source"]) if crudos else "",
            }
        )
    yap._RAG_INDEX = None
    return resumir(nombre, rutas, chunks, ms_build, filas, controles)


def _pct(n, d):
    return round(100.0 * n / d, 1) if d else 0.0


def resumir(nombre, rutas, chunks, ms_build, filas, controles):
    n = len(filas)
    alc = [f for f in filas if f["alcanzable"]]
    recall = {
        f"@{k}": _pct(sum(1 for f in filas if f["rango"] and f["rango"] <= k), n)
        for k in KS
    }
    recall_alc = {
        f"@{k}": _pct(sum(1 for f in alc if f["rango"] and f["rango"] <= k), len(alc))
        for k in KS
    }
    ms = sorted(f["ms"] for f in filas)
    scores_ok = [f["score_top1"] for f in filas if f["rango"] == 1]
    scores_ctrl = [c["score_top1"] for c in controles]
    return {
        "corpus": nombre,
        "ficheros": len(rutas),
        "fragmentos": len(chunks),
        "indice_ms": round(ms_build, 1),
        "preguntas": n,
        "alcanzables": len(alc),
        "recall_crudo": recall,
        "recall_crudo_alcanzables": recall_alc,
        "en_prompt": _pct(sum(1 for f in filas if f["en_prompt"]), n),
        "fragmentos_en_prompt_media": round(
            statistics.mean(f["fragmentos_en_prompt"] for f in filas), 2
        ),
        "tokens_en_prompt_media": round(
            statistics.mean(f["tokens_en_prompt"] for f in filas)
        ),
        "tokens_en_prompt_max": max(f["tokens_en_prompt"] for f in filas),
        "latencia_ms_mediana": round(statistics.median(ms), 2),
        "latencia_ms_p95": ms[int(0.95 * (len(ms) - 1))],
        "controles": len(controles),
        "controles_contaminados": _pct(
            sum(1 for c in controles if c["contaminada"]), len(controles)
        ),
        "score_top1_acierto_mediana": (
            round(statistics.median(scores_ok), 2) if scores_ok else None
        ),
        "score_top1_control_max": max(scores_ctrl) if scores_ctrl else None,
        "detalle": filas,
        "detalle_controles": controles,
    }


def barrido(datos, chunk_sizes=(50, 100, 300, 1000), umbrales=(0, 2, 4, 6)):
    """Recall@5 por tamano de chunk, y aciertos/controles por umbral de score.

    El umbral no existe hoy en Yap: se simula sobre el score BM25 del mejor
    fragmento, para saber si filtraria los controles sin perder aciertos.
    """
    filas = []
    for nombre in ("desarrollo", "instalado"):
        rutas = corpus(nombre)
        for n in chunk_sizes:
            idx, chunks, _ = construir_indice(rutas, chunk_size=n)
            alc = [p for p in datos["preguntas"] if alcanzable(chunks, p["aceptables"])]
            mejores = []
            for p in alc:
                ok = [
                    f
                    for f in idx.query(p["pregunta"], top_k=yap.RAG_TOP_K)
                    if acierta(f, p["aceptables"])
                ]
                mejores.append(ok[0]["score"] if ok else None)
            ctrl = [
                (idx.query(c, top_k=1) or [{"score": 0.0}])[0]["score"]
                for c in datos["controles"]
            ]
            filas.append(
                {
                    "corpus": nombre,
                    "chunk_size": n,
                    "fragmentos": len(chunks),
                    "alcanzables": len(alc),
                    "recall5_alcanzables": _pct(
                        sum(1 for m in mejores if m is not None), len(alc)
                    ),
                    "umbrales": {
                        str(u): {
                            "aciertos": sum(
                                1 for m in mejores if m is not None and m >= u
                            ),
                            "controles_bloqueados": sum(1 for c in ctrl if c < u),
                        }
                        for u in umbrales
                    },
                }
            )
    return filas


def medir(path=PREGUNTAS):
    datos = cargar_preguntas(path)
    viejo = (yap.CURSOS_DIR, yap.RAG_INDEX_DIR, yap._RAG_INDEX, yap.RAG_ENABLED)
    yap.RAG_INDEX_DIR = tempfile.mkdtemp(prefix="yap-rag-eval-")
    try:
        return {
            "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ajustes": {
                "RAG_TOP_K": yap.RAG_TOP_K,
                "RAG_MAX_CONTEXT_TOKENS": yap.RAG_MAX_CONTEXT_TOKENS,
                "RAG_CHUNK_SIZE": yap.RAG_CHUNK_SIZE,
            },
            "corpus": [medir_corpus(c, datos) for c in ("desarrollo", "instalado")],
            "barrido": barrido(datos),
        }
    finally:
        yap.CURSOS_DIR, yap.RAG_INDEX_DIR, yap._RAG_INDEX, yap.RAG_ENABLED = viejo


def informe(res):
    a = res["ajustes"]
    lineas = [
        f"RAG — {res['fecha']}  top_k={a['RAG_TOP_K']} "
        f"max_tokens={a['RAG_MAX_CONTEXT_TOKENS']} chunk={a['RAG_CHUNK_SIZE']}",
    ]
    for c in res["corpus"]:
        lineas += [
            "",
            f"[{c['corpus']}] {c['ficheros']} ficheros, {c['fragmentos']} fragmentos, "
            f"indice en {c['indice_ms']} ms",
            f"  alcanzables: {c['alcanzables']}/{c['preguntas']}",
            "  recall crudo:       "
            + "  ".join(f"{k} {v}%" for k, v in c["recall_crudo"].items()),
            "  ... alcanzables:    "
            + "  ".join(f"{k} {v}%" for k, v in c["recall_crudo_alcanzables"].items()),
            f"  llega al prompt:    {c['en_prompt']}%  "
            f"(media {c['fragmentos_en_prompt_media']} fragmentos, "
            f"{c['tokens_en_prompt_media']} tokens, max {c['tokens_en_prompt_max']})",
            f"  latencia:           mediana {c['latencia_ms_mediana']} ms, "
            f"p95 {c['latencia_ms_p95']} ms",
            f"  controles con contexto: {c['controles_contaminados']}%  "
            f"(score top1 max {c['score_top1_control_max']} vs mediana de aciertos "
            f"{c['score_top1_acierto_mediana']})",
        ]
    lineas += [
        "",
        "barrido (recall@5 sobre alcanzables; umbral: aciertos / controles bloqueados)",
    ]
    for b in res.get("barrido", []):
        um = "  ".join(
            f"u{u}: {v['aciertos']}/{v['controles_bloqueados']}"
            for u, v in b["umbrales"].items()
        )
        lineas.append(
            f"  {b['corpus']:10} chunk={b['chunk_size']:<5} "
            f"frag={b['fragmentos']:<4} r@5={b['recall5_alcanzables']}%  {um}"
        )
    return "\n".join(lineas)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Medicion del RAG local (#214)")
    parser.add_argument("--json", default=None, help="escribir resultados en JSON")
    args = parser.parse_args(argv)
    res = medir()
    print(informe(res))
    if args.json:
        Path(args.json).write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nJSON escrito en {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
