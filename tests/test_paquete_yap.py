"""Estructura del paquete instalable (#204).

`yap.py` pasó de 8220 líneas en un fichero a un paquete `yap/` con la
implementación en `__init__.py`, un `__main__.py` y un shim en la raíz.

El shim existe porque `setup.sh`, los `.spec` de RPM, el Flatpak, el
`.iss` de Windows y `build-deb.sh` ejecutan o instalan `yap.py` por su
ruta. Sin él habría que tocar los cinco a la vez.
"""

import os
import subprocess
import sys
from pathlib import Path

import yap

RAIZ = Path(yap.RAIZ_INSTALACION)
PAQUETE = RAIZ / "yap"
SHIM = RAIZ / "yap.py"


def _lineas(p):
    return len(Path(p).read_text(encoding="utf-8").splitlines())


class TestEstructura:
    def test_el_paquete_existe(self):
        assert (PAQUETE / "__init__.py").is_file()
        assert (PAQUETE / "__main__.py").is_file()

    def test_el_shim_existe_en_la_raiz(self):
        assert SHIM.is_file(), "falta el shim yap.py en la raiz"

    def test_yap_file_apunta_a_la_implementacion(self):
        """24 tests leen yap.__file__ para parsear la fuente.

        Si apuntara al shim leerian una decena de lineas y los chequeos
        de seguridad pasarian en verde sin comprobar nada.
        """
        assert Path(yap.__file__).name == "__init__.py"
        assert (
            _lineas(yap.__file__) > 8000
        ), f"yap.__file__ apunta a {_lineas(yap.__file__)} lineas: eso es el shim"

    def test_el_shim_es_delgado(self):
        """El shim no debe acumular logica: eso es lo que se estaba partiendo."""
        assert _lineas(SHIM) < 60, f"el shim tiene {_lineas(SHIM)} lineas"

    def test_importar_yap_no_importa_el_shim(self):
        """El paquete manda sobre el modulo del mismo nombre."""
        doc = yap.__doc__ or ""
        assert "Yap" in doc or "agente" in doc.lower()


class TestPuntosDeEntrada:
    def test_main_esta_exportado(self):
        assert callable(yap.main)

    def test_m_yap_funciona(self):
        r = subprocess.run(
            [sys.executable, "-m", "yap", "--help"],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(RAIZ),
        )
        assert r.returncode == 0, r.stderr[-500:]

    def test_el_shim_funciona(self):
        r = subprocess.run(
            [sys.executable, str(SHIM), "--help"],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(RAIZ),
        )
        assert r.returncode == 0, r.stderr[-500:]

    def test_ambos_dan_lo_mismo(self):
        """Sin cambio visible para el alumno: el shim y -m son equivalentes."""
        a = subprocess.run(
            [sys.executable, "-m", "yap", "--help"],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(RAIZ),
        )
        b = subprocess.run(
            [sys.executable, str(SHIM), "--help"],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(RAIZ),
        )
        assert a.stdout == b.stdout, "el shim y -m yap imprimen distinto"

    def test_main_no_esta_muerto_en_el_init(self):
        """__init__ se importa como 'yap', nunca como '__main__'.

        Su bloque if __name__ == '__main__' es inalcanzable, y por eso
        hace falta __main__.py.
        """
        texto = (PAQUETE / "__init__.py").read_text(encoding="utf-8")
        assert (
            'if __name__ == "__main__"' in texto
        ), "el bloque main del init es el que quedo inalcanzable"
        assert (PAQUETE / "__main__.py").read_text(encoding="utf-8").count("main") >= 1


class TestRutasDeDatos:
    """Los datos viven al lado del codigo, no dentro del paquete."""

    def test_raiz_instalacion_es_el_padre_del_paquete(self):
        assert Path(yap.RAIZ_INSTALACION) == PAQUETE.parent

    def test_i18n_se_encuentra(self):
        """El bug clasico de este refactor: i18n/ no se encontraba."""
        dirs = yap._i18n_dirs()
        encontrados = [d for d in dirs if os.path.isfile(os.path.join(d, "es.json"))]
        assert encontrados, f"no se encontró es.json en {dirs}"

    def test_i18n_funciona_traduciendo(self):
        """Si no se encontrara el catalogo devolveria la clave literal."""
        clave = "help.body"
        salida = yap.t(clave)
        assert clave not in salida, f"i18n no se cargó, devuelve la clave: {salida}"

    def test_hay_una_forma_de_resolver_recursos(self):
        """El issue pedia importlib.resources con fallback."""
        assert callable(getattr(yap, "_dirs_recurso", None))


class TestEmpaquetadoDelPaquete:
    """Lo que falló en #253 con yap_core: instalar el modulo y no el paquete."""

    RAIZ = Path(__file__).resolve().parent.parent

    def test_deb_instala_el_paquete(self):
        t = (self.RAIZ / "build-deb.sh").read_text(encoding="utf-8")
        assert '"$SCRIPT_DIR/yap"' in t, "build-deb.sh no instala el paquete yap/"

    def test_rpm_instala_y_declara_el_paquete(self):
        t = (self.RAIZ / "packaging/rpm/yap.spec").read_text(encoding="utf-8")
        assert "cp -r yap" in t
        assert "/opt/yap/yap/\n" in t + "\n", "falta en %files"

    def test_flatpak_instala_el_paquete(self):
        t = (self.RAIZ / "packaging/flatpak/org.chincolinux.Yap.json").read_text(
            encoding="utf-8"
        )
        assert "yap" in t and "cp -r yap" in t

    def test_windows_instala_el_paquete(self):
        t = (self.RAIZ / "packaging/windows/yap-installer.iss").read_text(
            encoding="utf-8"
        )
        assert 'Source: "yap\\*"' in t

    def test_ningun_target_se_queda_sin_el_paquete(self):
        """Cada fichero que instala yap.py debe instalar tambien yap/."""
        rutas = [
            "build-deb.sh",
            os.path.join("packaging", "rpm", "yap.spec"),
            os.path.join("packaging", "flatpak", "org.chincolinux.Yap.json"),
            os.path.join("packaging", "windows", "yap-installer.iss"),
        ]
        for rel in rutas:
            t = (self.RAIZ / rel).read_text(encoding="utf-8")
            assert "yap" in t
            tiene_paquete = any(
                patron in t for patron in ("cp -r yap", '"$SCRIPT_DIR/yap"', "yap\\*")
            )
            assert tiene_paquete, f"{rel} no empaqueta el paquete yap/"
