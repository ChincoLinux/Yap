"""La documentacion para agentes y revisores describe el codigo real (#271).

Tras #204 el codigo esta en yap/ y yap.py es un shim. REVIEW.md seguia
mandando `ruff check yap.py` y AGENTS.md/CLAUDE.md/README.md daban cifras
fijas (1079 tests, 8196 lineas, 11 workflows) que ya no eran ciertas.
Las cifras pasan a cotas inferiores; estos tests las sostienen.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = ("AGENTS.md", "CLAUDE.md", "README.md", "docs/REVIEW.md")


def _t(rel):
    return (RAIZ / rel).read_text(encoding="utf-8")


def test_review_manda_revisar_el_paquete():
    t = _t("docs/REVIEW.md")
    for herramienta in ("ruff format --check", "ruff check", "pyflakes"):
        lineas = [ln for ln in t.splitlines() if herramienta in ln]
        assert lineas, f"REVIEW.md ya no menciona {herramienta}"
        assert all(
            "yap/" in ln for ln in lineas
        ), f"{herramienta} sin yap/ en REVIEW.md"
    assert "Prohibido en `yap.py`" not in t


def test_ningun_doc_dice_que_yap_py_es_el_agente_entero():
    for rel in DOCS:
        t = _t(rel)
        assert "Un solo archivo" not in t, rel
        assert not re.search(r"yap\.py`? \(\d+ l[ií]neas", t), rel


def test_cota_de_pruebas_declarada():
    """Los docs dicen 'mas de 1200 pruebas'. Cuenta estatica: cota inferior
    de lo que recoge pytest (la parametrizacion solo suma)."""
    n = sum(
        len(re.findall(r"^\s*def test_", f.read_text(encoding="utf-8"), re.M))
        for f in (RAIZ / "tests").glob("test_*.py")
    )
    assert n > 1200, n


def test_numero_de_workflows_declarado():
    reales = len(list((RAIZ / ".github/workflows").glob("*.yml")))
    for rel in ("AGENTS.md", "CLAUDE.md"):
        declarados = {int(n) for n in re.findall(r"\b(\d+) workflows\b", _t(rel))}
        assert declarados <= {reales}, f"{rel} declara {declarados}, hay {reales}"


def test_estructura_documenta_el_paquete():
    for rel in ("AGENTS.md", "CLAUDE.md", "README.md"):
        t = _t(rel)
        assert "├── yap/" in t, f"{rel} no muestra el paquete yap/"
        assert "├── yap_core.py" in t, f"{rel} no muestra yap_core.py"
