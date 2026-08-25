"""
test_yap_config_escolar.py — Pruebas de la configuración para entorno escolar (#33)

Verifica:
  1. Las whitelists incluyen las aplicaciones y dominios educativos
  2. Todas las entradas tienen formato válido y parsean sin pérdidas
  3. La coincidencia de dominios sigue siendo estricta con las entradas nuevas
  4. setup.sh carga el perfil AppArmor en modo enforce

Ejecucion: python3 -m pytest tests/test_yap_config_escolar.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS_CONF = os.path.join(RAIZ, "whitelist", "apps.conf")
WEB_CONF = os.path.join(RAIZ, "whitelist", "web.conf")
SETUP_SH = os.path.join(RAIZ, "setup.sh")


def leer(path):
    """Lee un archivo del repositorio. Encoding explícito: el del sistema
    no es UTF-8 en todas las plataformas."""
    with open(path, encoding="utf-8") as f:
        return f.read()


# ============================================================
# 1. APLICACIONES EDUCATIVAS
# ============================================================

class TestAppsEducativas:
    """Requisito: whitelist de aplicaciones preconfigurada para el aula."""

    APPS_REQUERIDAS = [
        "libreoffice", "firefox", "pseint", "thonny", "scratch",
        "kalzium", "geogebra", "krita", "gcompris",
    ]

    def test_todas_las_apps_requeridas_estan(self):
        apps = yap.load_whitelist(APPS_CONF)
        faltan = [a for a in self.APPS_REQUERIDAS if a not in apps]
        assert not faltan, f"faltan en apps.conf: {faltan}"

    def test_cada_app_tiene_al_menos_un_binario(self):
        for nombre, binarios in yap.load_whitelist(APPS_CONF).items():
            assert binarios, f"'{nombre}' no declara ningun binario"
            assert all(b.strip() for b in binarios), f"'{nombre}' tiene un binario vacio"

    def test_no_hay_claves_duplicadas(self):
        """Una clave repetida se sobrescribe en silencio al cargar."""
        claves = []
        for linea in leer(APPS_CONF).splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and ":" in linea:
                claves.append(linea.split(":", 1)[0].strip().lower())
        assert len(claves) == len(set(claves)), "hay aplicaciones duplicadas"

    def test_las_apps_con_nombre_variable_declaran_alternativas(self):
        """El nombre del binario cambia entre versiones de Debian."""
        apps = yap.load_whitelist(APPS_CONF)
        assert len(apps["firefox"]) > 1, "firefox debe declarar firefox-esr y firefox"
        assert len(apps["gcompris"]) > 1, "gcompris debe declarar gcompris-qt y gcompris"

    def test_ninguna_linea_valida_se_pierde_al_parsear(self):
        entradas = sum(
            1 for l in leer(APPS_CONF).splitlines()
            if l.strip() and not l.strip().startswith("#")
        )
        assert len(yap.load_whitelist(APPS_CONF)) == entradas


# ============================================================
# 2. DOMINIOS EDUCATIVOS
# ============================================================

class TestDominiosEducativos:
    """Requisito: whitelist de dominios preconfigurada para el aula."""

    DOMINIOS_REQUERIDOS = [
        "wikipedia.org", "debian.org",
        "scratch.mit.edu", "khanacademy.org", "coursera.org",
    ]

    def test_todos_los_dominios_requeridos_estan(self):
        dominios = yap.load_domain_whitelist(WEB_CONF)
        faltan = [d for d in self.DOMINIOS_REQUERIDOS if d not in dominios]
        assert not faltan, f"faltan en web.conf: {faltan}"

    def test_los_dominios_estan_en_minusculas(self):
        for d in yap.load_domain_whitelist(WEB_CONF):
            assert d == d.lower()

    def test_no_hay_esquemas_ni_rutas(self):
        """web.conf lista dominios, no URLs."""
        for d in yap.load_domain_whitelist(WEB_CONF):
            assert "://" not in d, f"'{d}' incluye esquema"
            assert "/" not in d, f"'{d}' incluye una ruta"

    def test_no_hay_dominios_duplicados(self):
        dominios = yap.load_domain_whitelist(WEB_CONF)
        assert len(dominios) == len(set(dominios))

    def test_la_coincidencia_sigue_siendo_estricta(self):
        """Un dominio nuevo no debe abrir la puerta a otros parecidos."""
        dominios = yap.load_domain_whitelist(WEB_CONF)

        def permitido(dom):
            return any(d == dom or dom.endswith("." + d) for d in dominios)

        assert permitido("khanacademy.org")

        assert permitido("es.khanacademy.org")
        assert not permitido("notkhanacademy.org")
        assert not permitido("khanacademy.org.attacker.com")

    def test_subdominios_de_scratch_permitidos(self):
        dominios = yap.load_domain_whitelist(WEB_CONF)

        def permitido(dom):
            return any(d == dom or dom.endswith("." + d) for d in dominios)

        assert permitido("scratch.mit.edu")
        assert not permitido("mit.edu"), "solo scratch.mit.edu, no todo mit.edu"


# ============================================================
# 3. APPARMOR EN MODO ENFORCE
# ============================================================

class TestAppArmorEnforce:
    """Requisito: el perfil se carga en modo enforce por defecto."""

    def test_setup_carga_el_perfil(self):
        contenido = leer(SETUP_SH)
        assert "apparmor_parser -r" in contenido
        assert "/etc/apparmor.d/" in contenido

    def test_el_perfil_no_declara_modo_complain(self):
        """Sin flags=(complain), apparmor_parser carga en enforce."""
        perfil = leer(os.path.join(RAIZ, "apparmor", "usr.local.bin.yap"))
        assert "flags=(complain)" not in perfil
        assert "complain" not in perfil.split("profile yap")[1].split("{")[0]

    def test_setup_no_usa_aa_complain(self):
        assert "aa-complain" not in leer(SETUP_SH)
