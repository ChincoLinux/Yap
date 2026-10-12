"""tests/test_packaging_scripts.py — Scripts de empaquetado (#34).

Comprueba que los scripts de shell del repo parsean (sh -n) y que el script de
integracion en ChincoLinux OS cubre los 8 puntos de su issue.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS = [
    "build-deb.sh",
    "setup.sh",
    "packaging/test-install-debian.sh",
    "packaging/test-integration-os.sh",
]
INTEGRACION = os.path.join(RAIZ, "packaging", "test-integration-os.sh")


def _ruta(relativo):
    return os.path.join(RAIZ, relativo)


def _interprete(relativo):
    """El intérpeter que declara el shebang: en Ubuntu /bin/sh es dash y no
    acepta los bashismos de setup.sh (#183)."""
    with open(_ruta(relativo), encoding="utf-8", errors="replace") as f:
        shebang = f.readline()
    return "bash" if "bash" in shebang else "sh"


class TestSintaxisShell:
    def test_los_scripts_parsean(self):
        for relativo in SCRIPTS:
            ruta = _ruta(relativo)
            assert os.path.isfile(ruta), f"existe {relativo}"
            proceso = subprocess.run(
                [_interprete(relativo), "-n", ruta],
                capture_output=True,
                text=True,
                timeout=30,
                stdin=subprocess.DEVNULL,
            )
            assert proceso.returncode == 0, f"{relativo}: {proceso.stderr}"

    def test_interprete_según_shebang(self):
        assert _interprete("setup.sh") == "bash"
        assert _interprete("build-deb.sh") == "bash"
        assert _interprete("packaging/test-install-debian.sh") == "sh"
        assert _interprete("packaging/test-integration-os.sh") == "sh"


class TestScriptIntegracion:
    def test_help_sale_cero(self):
        proceso = subprocess.run(
            ["sh", INTEGRACION, "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
        assert proceso.returncode == 0
        assert "Verificacion de integracion" in proceso.stdout
        # la ayuda no corre las comprobaciones
        assert "[FALLA]" not in proceso.stdout

    def test_cubre_los_ocho_puntos_del_issue(self):
        with open(INTEGRACION, encoding="utf-8") as f:
            contenido = f.read()
        puntos = [
            "command -v yap",  # 1. en el PATH
            "--apparmor-status",  # 2. enforce
            "yap ayuda",  # 3. ayuda
            "yap curso FPY1101",  # 4. curso
            "/etc/yap/whitelist/apps.conf",  # 5. whitelists
            "/opt/yap/models/",  # 6. modelo
            "aa-exec",  # 7. denegacion AppArmor
            "--daemon-status",  # 8. daemon
        ]
        for punto in puntos:
            assert punto in contenido, f"falta la comprobacion: {punto}"

    def test_no_instala_nada(self):
        """Sólo verifica: sin apt, sin dpkg, sin systemctl."""
        with open(INTEGRACION, encoding="utf-8") as f:
            contenido = f.read()
        for prohibido in ("apt-get install", "dpkg -i", "systemctl enable"):
            assert prohibido not in contenido
