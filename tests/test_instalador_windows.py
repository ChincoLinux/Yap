"""Version del instalador de Windows (#242).

El .iss llevaba "1.0.1" hardcodeado mientras VERSION iba por 1.0.6: cinco
releases de instaladores con nombre y registro equivocados. El build no
inyectaba la version con /DMyAppVersion=.
"""

import re
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent
ISS = RAIZ / "packaging" / "windows" / "yap-installer.iss"
PS1 = RAIZ / "packaging" / "windows" / "build-windows.ps1"


def _version_real():
    return (RAIZ / "VERSION").read_text(encoding="utf-8").strip()


class TestIss:
    def test_iss_no_hardcodea_version(self):
        """Ningun #define puede fijar una version real: eso era el bug.

        El unico permitido es el fallback 0.0.0, protegido por #ifndef.
        """
        texto = ISS.read_text(encoding="utf-8")
        definiciones = re.findall(
            r'^\s*#define\s+MyAppVersion\s+"([^"]+)"', texto, re.M
        )
        assert definiciones, "falta el #define de MyAppVersion"
        for valor in definiciones:
            assert valor == "0.0.0", (
                f"MyAppVersion hardcodeado a '{valor}' en el .iss: "
                "debe inyectarse desde VERSION con /DMyAppVersion="
            )
        assert (
            "#ifndef MyAppVersion" in texto
        ), "el #define sin #ifndef se usaria aunque el build inyecte la version"

    def test_iss_declara_version_por_defecto_invalida(self):
        """Sin /D debe salir 0.0.0, a proposito: nada que parezca real."""
        texto = ISS.read_text(encoding="utf-8")
        assert "#ifndef MyAppVersion" in texto, "falta la guarda #ifndef"
        assert '"0.0.0"' in texto, "el fallback debe ser 0.0.0, no una version real"

    def test_iss_usa_myappversion_en_salida_y_registro(self):
        """Nombre del .exe y clave de desinstalador cogen la variable."""
        texto = ISS.read_text(encoding="utf-8")
        assert "OutputBaseFilename=yap-{#MyAppVersion}-setup" in texto
        assert "AppVersion={#MyAppVersion}" in texto
        assert 'ValueName: "Version"' in texto
        assert 'ValueData: "{#MyAppVersion}"' in texto

    def test_iss_sin_version_de_otros_ficheros(self):
        """Ni 1.0.1 ni la version vigente: ninguna version escrita a mano."""
        texto = ISS.read_text(encoding="utf-8")
        version = _version_real()
        for mencion in re.findall(r"\b\d+\.\d+\.\d+\b", texto):
            assert mencion == "0.0.0", (
                f"el .iss menciona la version {mencion}; solo se admite "
                "0.0.0 como placeholder"
            )
            assert version not in texto or mencion == version


class TestBuildPs1:
    def test_lee_version_de_fichero_version(self):
        texto = PS1.read_text(encoding="utf-8")
        assert 'Join-Path $RepoRoot "VERSION"' in texto, "no lee VERSION"

    def test_inyecta_la_version_en_iscc(self):
        """Sin /D, el #ifndef deja 0.0.0 y sale un instalador sin version."""
        texto = PS1.read_text(encoding="utf-8")
        assert "/DMyAppVersion=$YapVersion" in texto, "ISCC no recibe la version"

    def test_valida_semver_antes_de_compilar(self):
        texto = PS1.read_text(encoding="utf-8")
        assert "-notmatch" in texto, "no valida el formato de VERSION"

    def test_version_actual_es_semver(self):
        """Si VERSION se corrompe, este test avisa antes que el build."""
        assert re.fullmatch(r"\d+\.\d+\.\d+([-+][0-9A-Za-z.]+)?", _version_real())


class TestDivergencia:
    def test_no_queda_la_version_antigua_1_0_1(self):
        """La version que estaba hardcodeada no debe volver."""
        for fichero in (ISS, PS1):
            texto = fichero.read_text(encoding="utf-8")
            if fichero == ISS:
                assert not re.search(r'#define\s+MyAppVersion\s+"1\.0\.1"', texto)
            else:
                assert '"1.0.1"' not in texto

    def test_version_del_build_coincide_con_version(self):
        """El camino correcto: inyectada desde VERSION, no escrita a mano."""
        ps1 = PS1.read_text(encoding="utf-8")
        assert '"VERSION"' in ps1
        # El .iss no repite el valor que VERSION ya tiene.
        iss = ISS.read_text(encoding="utf-8")
        assert _version_real() not in iss or "#ifndef" in iss
