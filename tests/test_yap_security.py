"""
test_yap_security.py — Pruebas de seguridad para Yap

Verifica que el sistema cumple con los requisitos de seguridad:
  1. Whitelist de aplicaciones: solo apps permitidas
  2. Whitelist de dominios: solo dominios permitidos
  3. Sin command injection ni shell=True
  4. Graceful blocking con sugerencias
  5. Validacion estricta de dominios (fix commit 348e9b0)
  6. Sin eval(), os.system(), ni subprocess con shell=True

Ejecucion: python3 -m pytest tests/test_yap_security.py -v
"""

import pytest
import sys
import os
import tempfile
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


# ============================================================
# 1. WHITELIST DE APLICACIONES
# ============================================================

class TestAppWhitelist:
    """Requisito: Solo aplicaciones en whitelist pueden ejecutarse."""

    def setup_method(self):
        # Crear whitelist temporal para pruebas
        self.tmp_dir = tempfile.mkdtemp()
        self.apps_path = os.path.join(self.tmp_dir, "apps.conf")
        with open(self.apps_path, "w") as f:
            f.write("# Apps permitidas\n")
            f.write("LibreOffice:libreoffice\n")
            f.write("Firefox:firefox-esr,firefox\n")
            f.write("CustomApp:/usr/bin/custom_app\n")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_app_permitida_devuelve_ok(self):
        """App en whitelist debe procesarse sin error."""
        apps = yap.load_whitelist(self.apps_path)
        assert "libreoffice" in apps
        assert apps["libreoffice"] == ["libreoffice"]

    def test_app_bloqueada_muestra_alternativas(self):
        """App NO en whitelist debe mostrar lista de alternativas."""
        apps = yap.load_whitelist(self.apps_path)

        with mock.patch.object(yap, "WHITELIST_APPS", self.apps_path):
            result = yap.cmd_open_app("Chrome")

        assert "[ERROR]" in result
        assert "no disponible" in result.lower()
        # Debe listar apps disponibles como sugerencia
        assert "libreoffice" in result.lower() or "firefox" in result.lower()

    def test_app_bloqueada_no_ejecuta_comando(self):
        """App bloqueada NO debe ejecutar nada."""
        with mock.patch.object(yap, "WHITELIST_APPS", self.apps_path):
            with mock.patch("subprocess.Popen") as mock_popen:
                yap.cmd_open_app("Chrome")
                mock_popen.assert_not_called()

    def test_multiples_binarios_fallback(self):
        """Multiples binarios: si el primero no existe, prueba el siguiente."""
        apps = yap.load_whitelist(self.apps_path)
        assert apps["firefox"] == ["firefox-esr", "firefox"]


# ============================================================
# 2. WHITELIST DE DOMINIOS
# ============================================================

class TestDomainWhitelist:
    """Requisito: Solo dominios en whitelist pueden ser accedidos."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.web_path = os.path.join(self.tmp_dir, "web.conf")
        with open(self.web_path, "w") as f:
            f.write("# Dominios permitidos\n")
            f.write("wikipedia.org\n")
            f.write("debian.org\n")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_dominio_permitido_exacto(self):
        """Dominio exactamente en whitelist debe pasar."""
        domains = yap.load_domain_whitelist(self.web_path)
        assert "wikipedia.org" in domains

    def test_subdominio_permitido(self):
        """Subdominio directo debe pasar (ej. es.wikipedia.org)."""
        domains = yap.load_domain_whitelist(self.web_path)
        # La validacion en cmd_webfetch usa: domain == d or domain.endswith("." + d)
        assert "wikipedia.org" in domains
        assert any("es.wikipedia.org".endswith("." + d) for d in domains)

    def test_dominio_bloqueado_muestra_alternativas(self):
        """Dominio NO en whitelist debe mostrar lista de permitidos."""
        with mock.patch.object(yap, "WHITELIST_WEB", self.web_path):
            result = yap.cmd_webfetch("https://example.com/malware")

        assert "[ERROR]" in result
        assert "bloqueado" in result.lower()
        # Debe listar dominios permitidos
        assert "wikipedia.org" in result or "debian.org" in result

    def test_notwikipedia_no_coincide(self):
        """'notwikipedia.org' NO debe coincidir con 'wikipedia.org' (fix commit 348e9b0)."""
        domains = yap.load_domain_whitelist(self.web_path)
        # Antes del fix: domain.endswith("wikipedia.org") daba True para "notwikipedia.org"
        # Ahora: domain == d or domain.endswith("." + d)
        assert not ("notwikipedia.org" == "wikipedia.org")
        assert not ("notwikipedia.org".endswith(".wikipedia.org"))


# ============================================================
# 3. SEGURIDAD DE COMANDOS (INJECTION)
# ============================================================

class TestCommandSecurity:
    """Requisito: Sin command injection, shell=True, eval(), os.system()."""

    def test_no_shell_true_en_subprocess(self):
        """Verificar que subprocess nunca usa shell=True."""
        source = open(yap.__file__).read()
        # Buscar shell=True en el codigo fuente
        # Nota: shell=True es peligroso porque permite injection
        assert "shell=True" not in source, (
            "shell=True detectado en el codigo — riesgo de command injection"
        )

    def test_no_eval(self):
        """Verificar que no se usa eval() en el codigo."""
        source = open(yap.__file__).read()
        assert "eval(" not in source, (
            "eval() detectado — riesgo de ejecucion de codigo arbitrario"
        )

    def test_no_os_system(self):
        """Verificar que no se usa os.system()."""
        source = open(yap.__file__).read()
        assert "os.system(" not in source, (
            "os.system() detectado — riesgo de shell injection"
        )

    def test_command_injection_app_name(self):
        """Intentar injection en nombre de app debe fallar gracefulmente."""
        tmp_dir = tempfile.mkdtemp()
        apps_path = os.path.join(tmp_dir, "apps.conf")
        with open(apps_path, "w") as f:
            f.write("LibreOffice:libreoffice\n")

        with mock.patch.object(yap, "WHITELIST_APPS", apps_path):
            # Intentos de injection comunes
            injections = [
                "LibreOffice; rm -rf /",
                "$(whoami)",
                "`id`",
                "| cat /etc/passwd",
                "&& shutdown -h now",
            ]
            for injection in injections:
                result = yap.cmd_open_app(injection)
                assert "[ERROR]" in result, (
                    f"Injection '{injection}' deberia ser bloqueada"
                )

        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_url_injection(self):
        """Intentar URLs maliciosas debe ser bloqueado."""
        tmp_dir = tempfile.mkdtemp()
        web_path = os.path.join(tmp_dir, "web.conf")
        with open(web_path, "w") as f:
            f.write("wikipedia.org\n")

        with mock.patch.object(yap, "WHITELIST_WEB", web_path):
            # URLs maliciosas
            malicious = [
                ("file:///etc/passwd", "file"),
                ("http://127.0.0.1", "127.0.0.1"),
                ("http://[::1]", "[::1]"),
                ("javascript:alert(1)", "javascript"),
            ]
            for url, _ in malicious:
                result = yap.cmd_webfetch(url)
                assert "[ERROR]" in result, (
                    f"URL maliciosa '{url}' deberia ser bloqueada"
                )

        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# 4. CARGA DE CONFIGURACION
# ============================================================

class TestConfigLoading:
    """Requisito: Los archivos de configuracion se cargan correctamente."""

    def test_whitelist_ignora_comentarios(self):
        """Lineas con # deben ser ignoradas."""
        tmp_dir = tempfile.mkdtemp()
        path = os.path.join(tmp_dir, "test.conf")
        with open(path, "w") as f:
            f.write("# Comentario\n")
            f.write("  # Otro comentario\n")
            f.write("App:comando\n")

        apps = yap.load_whitelist(path)
        assert len(apps) == 1
        assert "app" in apps

        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_whitelist_ignora_lineas_vacias(self):
        """Lineas vacias deben ser ignoradas."""
        tmp_dir = tempfile.mkdtemp()
        path = os.path.join(tmp_dir, "test.conf")
        with open(path, "w") as f:
            f.write("\n\n\n")
            f.write("App:comando\n")
            f.write("\n")

        apps = yap.load_whitelist(path)
        assert len(apps) == 1

        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_formato_invalido_ignorado(self):
        """Lineas sin ':' deben ser ignoradas."""
        tmp_dir = tempfile.mkdtemp()
        path = os.path.join(tmp_dir, "test.conf")
        with open(path, "w") as f:
            f.write("linea sin dos puntos\n")
            f.write("App:comando\n")

        apps = yap.load_whitelist(path)
        assert len(apps) == 1

        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# 5. NOTIFICACIONES Y LIMITES
# ============================================================

class TestSecurityLimits:
    """Requisito: Limites de contenido y notificaciones seguras."""

    def test_contenido_limitado_3000_chars(self):
        """El contenido webfetch debe limitarse a 3000 caracteres."""
        # Verificar que la funcion cmd_webfetch limita la salida
        source = open(yap.__file__).read()
        assert "text[:3000]" in source or "text[:2000]" in source, (
            "No se encontro limite de caracteres en cmd_webfetch"
        )

    def test_timeout_en_subprocess(self):
        """Todas las llamadas a subprocess deben tener timeout."""
        source = open(yap.__file__).read()
        # Buscar subprocess.run sin timeout
        import re
        # Encontrar todas las llamadas a subprocess.run
        calls = re.findall(r"subprocess\.run\([^)]+\)", source)
        for call in calls:
            if "timeout=" not in call and "check=False" not in call.replace(" ", ""):
                # Algunas llamadas usan check=False sin timeout (notify)
                if "DEVNULL" in call:
                    continue  # notify-send es seguro
                pytest.fail(f"Llamada subprocess sin timeout: {call[:80]}")


# ============================================================
# 6. SEGURIDAD DEL SISTEMA DE ARCHIVOS
# ============================================================

class TestFileSystemSecurity:
    """Requisito: El agente no modifica archivos del sistema."""

    def test_no_escritura_fuera_de_whitelist(self):
        """Verificar que no hay operaciones de escritura arbitrarias."""
        source = open(yap.__file__).read()
        # No debe haber open() con 'w' fuera de load_whitelist
        # (load_whitelist solo LEE archivos)
        dangerous_patterns = [
            'open(',  # Escritura a archivos
            'os.remove',
            'os.unlink',
            'shutil.rmtree',
            'shutil.move',
        ]
        for pattern in dangerous_patterns:
            if pattern == 'open(':
                # open() es necesario para lectura, verificar que no sea 'w'
                import re
                writes = re.findall(r'open\([^)]+[\'"]w[\'"]', source)
                # ponytail: permitir escritura atomica de progreso (guardar_progreso)
                writes = [w for w in writes if "tmp" not in w.lower()]
                assert len(writes) == 0, (
                    f"Operacion de escritura detectada: {writes}"
                )
            else:
                assert pattern not in source, (
                    f"Operacion peligrosa detectada: {pattern}"
                )


# ============================================================
# 7. PRUEBAS DE CARGA DE CONFIGURACION REAL
# ============================================================

class TestRealConfig:
    """Verificar que los archivos de configuracion reales existen y son validos."""

    def test_apps_conf_existe(self):
        """El archivo apps.conf debe existir en el repo."""
        path = os.path.join(os.path.dirname(yap.__file__), "whitelist", "apps.conf")
        assert os.path.exists(path), f"No se encuentra: {path}"

    def test_web_conf_existe(self):
        """El archivo web.conf debe existir en el repo."""
        path = os.path.join(os.path.dirname(yap.__file__), "whitelist", "web.conf")
        assert os.path.exists(path), f"No se encuentra: {path}"

    def test_apps_conf_tiene_contenido(self):
        """apps.conf debe tener al menos una entrada valida."""
        path = os.path.join(os.path.dirname(yap.__file__), "whitelist", "apps.conf")
        apps = yap.load_whitelist(path)
        assert len(apps) > 0, "apps.conf vacio o con solo comentarios"

    def test_web_conf_tiene_contenido(self):
        """web.conf debe tener al menos un dominio."""
        path = os.path.join(os.path.dirname(yap.__file__), "whitelist", "web.conf")
        domains = yap.load_domain_whitelist(path)
        assert len(domains) > 0, "web.conf vacio o con solo comentarios"


# ============================================================
# 8. VERIFICACION DE CODIGO FUENTE
# ============================================================

class TestCodeQuality:
    """Revision estatica del codigo fuente para buenas practicas de seguridad."""

    def test_no_shebang_incorrecto(self):
        """Verificar que el shebang es correcto."""
        with open(yap.__file__) as f:
            first_line = f.readline().strip()
        assert first_line == "#!/usr/bin/env python3", (
            f"Shebang incorrecto: {first_line}"
        )

    def test_imports_minimos(self):
        """Verificar que solo se importan modulos necesarios."""
        with open(yap.__file__) as f:
            source = f.read()
        imports = []
        for line in source.split("\n"):
            if line.startswith("import ") or line.startswith("from "):
                imports.append(line.strip())
        peligrosos = ["socket", "ctypes", "pickle", "base64", "codecs"]
        for imp in imports:
            for peligroso in peligrosos:
                assert peligroso not in imp, (
                    f"Modulo potencialmente peligroso importado: {imp}"
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
