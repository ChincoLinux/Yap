"""Actions de GitHub pineadas por SHA (#240).

Ninguna action estaba pineada. trufflehog — el scanner de secretos —
apuntaba a `main`, el ref mas movil que existe, y tres workflows con
`contents: write` usaban tags mutables de softprops/action-gh-release.
Un tag reescrito ahi daria escritura sobre el repo y publicaria binarios
como release oficial.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOWS = RAIZ / ".github" / "workflows"

SHA40 = re.compile(r"^[0-9a-f]{40}$")
USA = re.compile(r"^\s*uses:\s*(\S+)@(\S+)")

# Acciones que escriben en el repo: para ellas el pineado no es opcional.
ESCRITURA = ("softprops/action-gh-release",)


def _todas():
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        for numero, linea in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
            m = USA.match(linea)
            if m:
                yield wf.name, numero, m.group(1), m.group(2).split()[0], linea.strip()


def test_ninguna_action_sin_pinear():
    """Un tag es mutable: quien lo reescriba ejecuta codigo con nuestro token."""
    malos = [
        f"{f}:{n}  {linea}"
        for f, n, accion, ref, linea in _todas()
        if not SHA40.match(ref)
    ]
    assert not malos, "actions sin pinear por SHA:\n" + "\n".join(malos)


def test_hay_actions_pineadas():
    """Si el analisis no ve ninguna, algo se rompio en el propio test."""
    encontradas = list(_todas())
    assert len(encontradas) > 20, f"solo se vieron {len(encontradas)} referencias"


def test_trufflehog_no_apunta_a_main():
    """El scanner de secretos debe ser de los mas fijos, no de los menos."""
    for f, n, accion, ref, linea in _todas():
        if "trufflehog" in accion:
            assert ref != "main", f"trufflehog apunta a main en {f}:{n}"
            assert SHA40.match(ref), f"trufflehog sin pinear en {f}:{n}"
            return
    raise AssertionError("trufflehog ya no figura en los workflows")


def test_trufflehog_no_esta_en_una_rama():
    for f, n, accion, ref, linea in _todas():
        if "trufflehog" in accion:
            assert (
                "main" not in linea.split("#")[0]
            ), f"trufflehog sigue referenciando una rama en {f}:{n}"


def test_las_de_escritura_estan_pineadas():
    """Un tag reescrito en una action con contents:write da escritura."""
    for f, n, accion, ref, linea in _todas():
        if any(accion.startswith(e) for e in ESCRITURA):
            assert SHA40.match(ref), f"{accion} sin pinear en {f}:{n}"


def test_el_pineado_conserva_la_version_en_comentario():
    """Sin el comentario, nadie sabe que version hay ni como actualizarla."""
    sin_comentario = [
        f"{f}:{n}  {linea}"
        for f, n, accion, ref, linea in _todas()
        if SHA40.match(ref) and "#" not in linea
    ]
    assert not sin_comentario, "pineados sin la version en comentario:\n" + "\n".join(
        sin_comentario
    )


def test_no_hay_referencias_a_ramas():
    """Ademas de main: develop, master, o cualquier otra."""
    ramas = ("main", "master", "develop", "dev", "HEAD")
    for f, n, accion, ref, linea in _todas():
        if ref in ramas:
            raise AssertionError(f"{accion}@{ref} apunta a una rama en {f}:{n}")
