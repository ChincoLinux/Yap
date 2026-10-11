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


class TestSintaxisShell:
    def test_los_scripts_parsean(self):
        for relativo in SCRIPTS:
            ruta = _ruta(relativo)
            assert os.path.isfile(ruta), f"existe {relativo}"
            proceso = subprocess.run(
                ["sh", "-n", ruta],
                capture_output=True,
                text=True,
                timeout=30,
                stdin=subprocess.DEVNULL,
            )
            assert proceso.returncode == 0, f"{relativo}: {proceso.stderr}"


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
