"""Sin credenciales hardcodeadas (#213).

La clave de invocación de Cloud Run vivía como constante en `yap.py` desde
el commit 51202e7. Está en el historial y en todo clone: borrarla del código
no la invalida, hay que revocarla en GCP. Lo que este test impide es que
entre otra.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

FUENTES = ["yap.py"]
FUENTES += [
    str(p.relative_to(RAIZ)) for p in sorted((RAIZ / "yap_desktop").rglob("*.py"))
]
FUENTES += [
    str(p.relative_to(RAIZ))
    for p in sorted((RAIZ / "agent-platform").glob("*.example"))
]

# Nombres que prometen un secreto.
NOMBRE_SECRETO = re.compile(
    r"(?i)\b([A-Z_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)[A-Z_]*)\s*="
)

# Valor de alta entropia: suficiente longitud y sin espacios.
ALTA_ENTROPIA = re.compile(r"""["']([A-Za-z0-9+/=_\-]{20,})["']""")

# Palabras que no son un secreto aunque el nombre lo parezca.
EXCEPTOS = re.compile(
    r"(?i)(example|placeholder|sample|dummy|fake|prueba|test|<|vacio|vacío|\{\{|none|null)"
)


def _candidatas():
    for rel in FUENTES:
        ruta = RAIZ / rel
        if not ruta.is_file():
            continue
        for numero, linea in enumerate(
            ruta.read_text(encoding="utf-8").splitlines(), 1
        ):
            if linea.lstrip().startswith("#"):
                continue
            if NOMBRE_SECRETO.search(linea):
                yield rel, numero, linea.strip()


def test_ninguna_constante_llave_secreto_con_valor():
    """Una constante que promete un secreto y lleva uno de alta entropia."""
    malas = []
    for rel, numero, linea in _candidatas():
        if EXCEPTOS.search(linea):
            continue
        m = ALTA_ENTROPIA.search(linea)
        if not m:
            continue
        valor = m.group(1)
        # Un hex corto o un path no es una credencial.
        if re.fullmatch(r"[0-9a-f]{8,64}", valor) and len(valor) <= 40:
            continue
        malas.append(f"{rel}:{numero}  {linea[:70]}")
    assert not malas, "posibles credenciales hardcodeadas:\n" + "\n".join(malas)


def test_super_token_no_tiene_clave_por_defecto():
    """#213: el token solo puede venir del entorno o de un fichero 600."""
    yap = (RAIZ / "yap.py").read_text(encoding="utf-8")
    assert (
        "SUPER_NUBE_KEY_DEFAULT" not in yap
    ), "vuelve a existir una clave por defecto en yap.py"
    assert "SUPER_NUBE_KEY_DEFAULT" not in "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in sorted((RAIZ / "yap_desktop").rglob("*.py"))
    ), "vuelve a existir en yap_desktop/"


def test_super_token_falla_cerrado():
    """Sin configuración no hay token; no se inventa ninguno."""
    import importlib
    import os
    import tempfile
    from unittest.mock import patch

    yap = importlib.import_module("yap")
    with tempfile.TemporaryDirectory() as vacio:
        with patch.dict(
            "os.environ",
            {"YAP_SUPER_TOKEN": "", "YAP_SUPER_TOKEN_FILE": f"{vacio}/no-existe"},
            clear=False,
        ):
            os.environ.pop("YAP_SUPER_TOKEN", None)
            assert yap._super_token() == ""


def test_el_token_del_entorno_si_llega():
    """La via oficial sigue funcionando: YAP_SUPER_TOKEN."""
    import importlib
    from unittest.mock import patch

    yap = importlib.import_module("yap")
    with patch.dict("os.environ", {"YAP_SUPER_TOKEN": "tok-del-entorno"}):
        assert yap._super_token() == "tok-del-entorno"


def test_el_token_del_entorno_no_se_imprime_en_status():
    import importlib

    yap = importlib.import_module("yap")
    from unittest.mock import patch

    with patch.dict("os.environ", {"YAP_SUPER_TOKEN": "otra-clave-sensible"}):
        salida = yap.cmd_super_status()
    assert "otra-clave-sensible" not in salida


def test_el_ejemplo_no_contiene_credenciales():
    """super.env.example debe llevar valores vacios, no valores reales."""
    ejemplo = RAIZ / "agent-platform" / "super.env.example"
    if not ejemplo.is_file():
        return
    for numero, linea in enumerate(ejemplo.read_text(encoding="utf-8").splitlines(), 1):
        limpia = linea.split("#")[0]
        if not limpia.strip():
            continue
        if re.match(r"^YAP_SUPER_TOKEN\s*=\s*\S", limpia):
            raise AssertionError(
                f"super.env.example:{numero} trae un token con valor: {limpia.strip()[:40]}"
            )
