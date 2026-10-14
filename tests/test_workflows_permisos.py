"""Permisos explicitos en todos los workflows (#255).

Sin bloque `permissions:` un workflow hereda el default de Settings, que
no aparece en ningun diff: si alguien lo cambia a write, los workflows se
amplian en silencio. Y un PAT no lo limita ese bloque, asi que cada uso
de uno debe explicar en el propio fichero por que hace falta.

Sin PyYAML: CI solo instala pytest, y basta con mirar la columna 0.
"""

import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
PAT = re.compile(r"secrets\.[A-Z_]*PAT\b")


def _workflows():
    fs = sorted(WORKFLOWS.glob("*.yml"))
    assert len(fs) >= 10, f"solo se vieron {len(fs)} workflows"
    return fs


def test_todos_declaran_permissions_a_nivel_raiz():
    sin = [
        f.name
        for f in _workflows()
        if not re.search(r"^permissions:", f.read_text(encoding="utf-8"), re.M)
    ]
    assert not sin, f"workflows sin permissions: a nivel raiz: {sin}"


def test_ninguno_usa_write_all():
    con = [
        f.name
        for f in _workflows()
        if re.search(
            r"^\s*permissions:\s*write-all", f.read_text(encoding="utf-8"), re.M
        )
    ]
    assert not con, f"write-all en: {con}"


def test_cada_pat_esta_justificado_en_el_fichero():
    """Un PAT ignora permissions:; el motivo debe estar junto al uso."""
    malos = []
    usos = 0
    for f in _workflows():
        lineas = f.read_text(encoding="utf-8").splitlines()
        for i, linea in enumerate(lineas):
            if PAT.search(linea) and not linea.strip().startswith("#"):
                usos += 1
                previas = " ".join(lineas[max(0, i - 6) : i])
                if "#255" not in previas or "PAT" not in previas:
                    malos.append(f"{f.name}:{i + 1}")
    assert usos > 0, "no se vio ningun PAT: el test ya no mide nada"
    assert not malos, f"PAT sin justificacion junto al uso: {malos}"


def test_auto_add_no_concede_nada_al_github_token():
    t = (WORKFLOWS / "auto-add-to-project.yml").read_text(encoding="utf-8")
    assert re.search(r"^permissions:\s*\{\}", t, re.M)
