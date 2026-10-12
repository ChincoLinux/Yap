"""La version de la GUI no puede hardcodearse.

VERSION es la fuente de verdad: la leen build-deb.sh, build-packages.yml y
auto-release.yml. Un valor escrito a mano en yap_desktop/ se desincroniza en
cada release, y ya había pasado —__version__ se quedó en 1.0.1 cuando el repo
iba por 1.0.6.
"""

from pathlib import Path

import yap_desktop


def test_version_de_gui_coincide_con_VERSION():
    repo = Path(yap_desktop.__file__).resolve().parent.parent
    esperada = (repo / "VERSION").read_text(encoding="utf-8").strip()
    assert yap_desktop.__version__ == esperada, (
        f"yap_desktop.__version__={yap_desktop.__version__!r} pero VERSION={esperada!r}. "
        "No escribas la version a mano: se lee del fichero VERSION."
    )


def test_no_hay_version_hardcodeada_en_el_fuente():
    fuente = Path(yap_desktop.__file__).read_text(encoding="utf-8")
    for linea in fuente.splitlines():
        if "__version__" in linea and "=" in linea and "def " not in linea:
            assert "_leer_version" in fuente, (
                "yap_desktop/__init__.py asigna __version__ de forma directa. "
                "Usa _leer_version() para leer VERSION."
            )
            break


def test_app_py_no_literal_de_version():
    """app.py pasaba setApplicationVersion("1.0.1") — el literal se fue de la GUI."""
    app = Path(yap_desktop.__file__).parent / "app.py"
    contenido = app.read_text(encoding="utf-8")
    assert (
        'setApplicationVersion("' not in contenido
    ), "yap_desktop/app.py fija la version como literal. Usa __version__."
