"""ROADMAP.md sincronizado con el repo (#243).

El roadmap marcaba como "Pendiente" a #32, #34 y #40 — los tres cerrados —
y seguía fijando la Fase 3 en "para ChincoLinux OS", una decisión de alcance
ya descartada. Ninguno de los epics abiertos (#199, #208) aparecía.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ROADMAP = RAIZ / "docs" / "ROADMAP.md"


def _texto():
    return ROADMAP.read_text(encoding="utf-8")


class TestSinPendientesObsoletos:
    def test_no_queda_el_estado_pendiente(self):
        """Ninguna fila puede decir "Pendiente": era el error del roadmap."""
        for linea in _texto().splitlines():
            if not linea.startswith("|"):
                continue
            assert "| Pendiente" not in linea, f"fila con estado pendiente: {linea}"

    def test_los_issues_cerrados_de_fase_3_no_estan_como_abiertos(self):
        texto = _texto()
        for numero in ("| 32 |", "| 34 |", "| 40 |"):
            for linea in texto.splitlines():
                if linea.startswith(numero):
                    assert (
                        "Cerrado" in linea
                    ), f"{numero} no aparece como cerrado: {linea}"

    def test_27_aparece_completado(self):
        """#27 se resolvio con el PR #61."""
        for linea in _texto().splitlines():
            if linea.startswith("| 27 |"):
                assert "Completado" in linea, linea
                return
        raise AssertionError("#27 ya no figura en el roadmap")


class TestAlcanceDeclarado:
    def test_fase_3_no_esta_atada_a_chincolinux(self):
        texto = _texto()
        assert (
            "Empaquetado para ChincoLinux OS" not in texto
        ), "la Fase 3 vuelve a limitarse a ChincoLinux OS"
        assert "integrarse en la ISO de ChincoLinux" not in texto
        assert "Empaquetado multiplataforma" in texto

    def test_vision_no_promete_solo_chincolinux(self):
        parrafo = _texto().split("## Visión", 1)[1].split("##", 1)[0]
        assert (
            "multiplataforma" in parrafo.lower()
        ), "la vision no declara empaquetado multiplataforma"

    def test_mencionan_los_cuatro_formatos(self):
        texto = _texto()
        for formato in (".deb", ".rpm", "Flatpak", "Windows"):
            assert formato in texto, f"falta el formato {formato}"


class TestEpicsNuevos:
    def test_epic_desktop(self):
        texto = _texto()
        assert "#199" in texto, "falta el epic YAP DESKTOP AI FOR STUDENT"
        assert "YAP DESKTOP AI FOR STUDENT" in texto

    def test_epic_web(self):
        texto = _texto()
        assert "#208" in texto, "falta el epic YAP WEB"
        assert "YAP WEB" in texto

    def test_seccion_de_seguridad(self):
        """Los issues de seguridad bloquean cualquier release."""
        texto = _texto()
        assert "## Seguridad" in texto
        assert "| 213 |" in texto, "falta el P0 #213 de seguridad"

    def test_subissues_del_epic_desktop(self):
        texto = _texto()
        for numero in (201, 202, 203, 204, 205, 206):
            assert f"| {numero} |" in texto, f"falta el sub-issue {numero}"


class TestCifras:
    def test_yap_py_supera_la_cota(self):
        """El roadmap cita cotas, no cifras exactas.

        Un igual exacto se romperia en cada PR que toque yap.py: el numero
        debe expresar "es un monolito que hay que dividir", no reflejar el
        fichero en cada commit. Ver #239, donde la auditoria de seguridad
        seguia citando 932 lineas de un fichero de mas de 8000.
        """
        reales = len((RAIZ / "yap.py").read_text(encoding="utf-8").splitlines())
        cita = re.search(r"`yap\.py` \(más de (\d+) líneas\)", _texto())
        assert cita, "no se cita el tamano de yap.py"
        cota = int(cita.group(1))
        assert (
            reales > cota
        ), f"el roadmap dice mas de {cota} lineas, y yap.py tiene {reales}"
        # Y la cota sigue describiendo el problema: un monolito grande.
        assert cota > 1000

    def test_yap_desktop_supera_la_cota(self):
        desktop = RAIZ / "yap_desktop"
        if not desktop.exists():
            return
        reales = sum(
            len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
            for p in desktop.rglob("*.py")
        )
        cita = re.search(r"`yap_desktop/`, más de (\d+) líneas", _texto())
        assert cita, "no se cita el tamano de yap_desktop"
        assert reales > int(
            cita.group(1)
        ), f"el roadmap dice mas de {cita.group(1)}, y hay {reales}"

    def test_fecha_de_actualizacion(self):
        assert re.search(r"\*\*Última actualización:\*\* \d{4}-\d{2}-\d{2}", _texto())

    def test_suspendidos_sin_tocar(self):
        """Los cloud-suspended no se tocan: solo se documentan."""
        assert "cloud-suspended" in _texto()
