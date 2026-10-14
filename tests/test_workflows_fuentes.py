"""Los gates de CI revisan el codigo real, no solo el shim (#267).

Desde #254 la implementacion vive en yap/ y yap.py es un shim de pocas
lineas. Los gates de seguridad, estilo y dependencias seguian mirando solo
yap.py: un `import pickle` en yap/__init__.py pasaba en verde.

Y el paso estatico de test.yml usaba `! grep ... && echo`, que bash -e
nunca trata como fallo: no fallo nunca, encontrara lo que encontrara.
"""

import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def _texto(nombre):
    return (WORKFLOWS / nombre).read_text(encoding="utf-8")


def _lineas_de_codigo():
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        for n, linea in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
            if not linea.strip().startswith("#"):
                yield wf.name, n, linea


def test_ningun_gate_parsea_solo_el_shim():
    malos = [
        f"{w}:{n}" for w, n, linea in _lineas_de_codigo() if "open('yap.py')" in linea
    ]
    assert not malos, f"gates que solo parsean yap.py: {malos}"


def test_linters_incluyen_el_paquete():
    malos = [
        f"{w}:{n}  {linea.strip()}"
        for w, n, linea in _lineas_de_codigo()
        if re.search(r"\b(ruff (format|check)|pyflakes)\b", linea)
        and "tests/" in linea
        and "yap/" not in linea
    ]
    assert not malos, "linters que no revisan yap/:\n" + "\n".join(malos)


def test_grep_de_patrones_prohibidos_incluye_el_paquete():
    for nombre in ("pr-quality-suite.yml", "test.yml"):
        t = _texto(nombre)
        assert "shell=True" in t, f"{nombre} ya no busca shell=True"
        assert re.search(r"(find yap |\*\.py yap/)", t), f"{nombre} no busca en yap/"


def test_ningun_gate_niega_grep_bajo_errexit():
    """`! grep X && echo ok` nunca hace fallar el paso con bash -e."""
    malos = [
        f"{w}:{n}  {linea.strip()}"
        for w, n, linea in _lineas_de_codigo()
        if re.match(r"\s*!\s*grep\b", linea)
    ]
    assert not malos, "gates que no pueden fallar:\n" + "\n".join(malos)


def test_build_packages_se_dispara_y_empaqueta_el_paquete():
    t = _texto("build-packages.yml")
    assert "- 'yap/**'" in t, "un cambio en yap/ no dispara la construccion"
    assert re.search(
        r"tar czf .*\n\s+--transform .*\n\s+yap\.py yap/ ", t
    ), "el tarball del RPM no incluye yap/"
