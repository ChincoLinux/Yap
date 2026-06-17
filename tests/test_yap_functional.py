"""
test_yap_functional.py — Pruebas funcionales para Yap

Verifica que el sistema cumple con los requisitos funcionales:
  1. Apertura de aplicaciones via whitelist
  2. Webfetch con resumen
  3. Busqueda en Wikipedia via API REST
  4. Consulta directa al LLM
  5. Modo interactivo y por comando
  6. Clasificacion de intenciones

Ejecucion: python3 -m pytest tests/test_yap_functional.py -v
"""

import pytest
import sys
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock, ANY

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


# ============================================================
# 1. APERTURA DE APLICACIONES
# ============================================================

class TestOpenApp:
    """Requisito: El agente puede abrir aplicaciones de la whitelist."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.apps_path = os.path.join(self.tmp_dir, "apps.conf")
        with open(self.apps_path, "w") as f:
            f.write("LibreOffice:libreoffice\n")
            f.write("Firefox:firefox-esr,firefox\n")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_abrir_app_exitosa(self, mock_popen, mock_run, mock_which):
        """Abrir una app permitida debe devolver [OK]."""
        mock_which.return_value = "/usr/bin/libreoffice"
        mock_run.return_value = Mock(stdout="7.5.0", stderr="")

        with patch.object(yap, "WHITELIST_APPS", self.apps_path):
            result = yap.cmd_open_app("LibreOffice")

        assert "[OK]" in result
        # title() convierte "LibreOffice" a "Libreoffice", usamos lower()
        assert "libreoffice" in result.lower()

    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("subprocess.Popen")
    @patch.object(yap, "notify")
    def test_abrir_app_con_binario_alternativo(self, mock_notify, mock_popen, mock_which, mock_run):
        """Si firefox-esr no existe, debe usar firefox."""
        mock_run.return_value = Mock(stdout="", stderr="")
        mock_which.side_effect = lambda x: "/usr/bin/firefox" if x == "firefox" else None

        with patch.object(yap, "WHITELIST_APPS", self.apps_path):
            yap.cmd_open_app("Firefox")

        mock_popen.assert_called_once_with(
            ["/usr/bin/firefox"],
            stdout=ANY, stderr=ANY
        )

    def test_app_no_encontrada_mensaje_graceful(self):
        """App no en whitelist debe mostrar mensaje graceful con alternativas."""
        with patch.object(yap, "WHITELIST_APPS", self.apps_path):
            result = yap.cmd_open_app("Chrome")

        assert "[ERROR]" in result
        assert "no disponible" in result.lower()
        # Debe listar alternativas en minusculas
        assert "firefox" in result.lower() or "libreoffice" in result.lower()


# ============================================================
# 2. WEBFETCH
# ============================================================

class TestWebfetch:
    """Requisito: El agente puede obtener y resumir contenido web."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.web_path = os.path.join(self.tmp_dir, "web.conf")
        with open(self.web_path, "w") as f:
            f.write("wikipedia.org\n")
            f.write("debian.org\n")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_dominio_bloqueado_mensaje_graceful(self):
        """Dominio bloqueado debe mostrar lista de permitidos."""
        with patch.object(yap, "WHITELIST_WEB", self.web_path):
            result = yap.cmd_webfetch("https://malware.com/exploit")

        assert "[ERROR]" in result
        assert "bloqueado" in result.lower()
        assert "wikipedia.org" in result or "debian.org" in result

    def test_subdominio_permitido(self):
        """Subdominio de un dominio permitido debe funcionar."""
        with patch.object(yap, "WHITELIST_WEB", self.web_path):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_ctx = MagicMock()
                mock_ctx.read.return_value = b"<html><body>Contenido</body></html>"
                mock_urlopen.return_value.__enter__.return_value = mock_ctx
                result = yap.cmd_webfetch("https://es.wikipedia.org/wiki/Linux")

        assert "[ERROR]" not in result

    @patch("urllib.request.urlopen")
    def test_fetch_contenido_se_limpia(self, mock_urlopen):
        """El HTML debe limpiarse (tags eliminados)."""
        mock_ctx = MagicMock()
        mock_ctx.read.return_value = b"<html><body><p>Texto</p></body></html>"
        mock_urlopen.return_value.__enter__.return_value = mock_ctx

        with patch.object(yap, "WHITELIST_WEB", self.web_path):
            result, _ = yap.cmd_webfetch("https://wikipedia.org/test", feed_to_llm=True)

        assert "<html>" not in result
        assert "<body>" not in result
        assert "Texto" in result


# ============================================================
# 3. CLASIFICACION DE INTENCIONES
# ============================================================

class TestIntentClassification:
    """Requisito: El LLM clasifica intenciones (open_app, search, webfetch, query)."""

    @patch("subprocess.run")
    def test_classify_open_app(self, mock_run):
        """Entrada 'Abre Firefox' debe clasificar como open_app."""
        mock_run.return_value = Mock(stdout="open_app|firefox", stderr="")
        action, param = yap.classify_intent("Abre Firefox")
        assert action == "open_app"
        assert param == "firefox"

    @patch("subprocess.run")
    def test_classify_search(self, mock_run):
        """Entrada 'busca que es linux' debe clasificar como search."""
        mock_run.return_value = Mock(stdout="search|que es linux", stderr="")
        action, param = yap.classify_intent("busca que es linux")
        assert action == "search"

    @patch("subprocess.run")
    def test_classify_webfetch(self, mock_run):
        mock_run.return_value = Mock(
            stdout="webfetch|https://es.wikipedia.org/wiki/Linux",
            stderr=""
        )
        action, param = yap.classify_intent("Busca https://es.wikipedia.org/wiki/Linux")
        assert action == "webfetch"

    @patch("subprocess.run")
    def test_classify_query(self, mock_run):
        mock_run.return_value = Mock(stdout="query|que es debian?", stderr="")
        action, param = yap.classify_intent("Que es Debian?")
        assert action == "query"

    def test_fallback_a_query(self):
        """Si el LLM falla, debe clasificar como query por defecto."""
        from subprocess import TimeoutExpired
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = TimeoutExpired("llama-cli", 30)
            action, param = yap.classify_intent("Hola")
        assert action == "query"


# ============================================================
# 4. CONSULTA AL LLM
# ============================================================

class TestQuery:
    """Requisito: El agente consulta al LLM local."""

    @patch("subprocess.run")
    def test_cmd_query_respuesta_exitosa(self, mock_run):
        """cmd_query debe devolver la respuesta del LLM."""
        mock_run.return_value = Mock(
            stdout="Linux es un sistema operativo de codigo abierto.",
            stderr=""
        )
        result = yap.cmd_query("Que es Linux?", store_history=False)
        assert "Linux" in result
        assert "sistema operativo" in result

    @patch("subprocess.run")
    def test_cmd_query_timeout(self, mock_run):
        """Timeout debe devolver mensaje de advertencia."""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired("llama-cli", 120)
        result = yap.cmd_query("test", store_history=False)
        assert "[WARN]" in result
        assert "Tiempo de espera" in result

    @patch("subprocess.run")
    def test_cmd_query_sin_respuesta(self, mock_run):
        """Respuesta vacia debe mostrar stderr."""
        mock_run.return_value = Mock(stdout="", stderr="(sin respuesta)")
        result = yap.cmd_query("test", store_history=False)
        assert "(sin respuesta)" in result


# ============================================================
# 5. HISTORIAL DE CONVERSACION
# ============================================================

class TestHistory:
    """Requisito: El historial de conversacion funciona correctamente."""

    def setup_method(self):
        yap.HISTORY.clear()

    @patch("subprocess.run")
    def test_historial_se_almacena(self, mock_run):
        mock_run.return_value = Mock(stdout="Respuesta de prueba.", stderr="")
        yap.cmd_query("Hola", store_history=True)
        assert len(yap.HISTORY) == 1
        assert yap.HISTORY[0][0] == "Hola"
        assert yap.HISTORY[0][1] == "Respuesta de prueba."

    @patch("subprocess.run")
    def test_historial_no_almacena_si_false(self, mock_run):
        mock_run.return_value = Mock(stdout="Resumen.", stderr="")
        yap.cmd_query("Resume esto", store_history=False)
        assert len(yap.HISTORY) == 0

    @patch("subprocess.run")
    def test_historial_limitado(self, mock_run):
        mock_run.return_value = Mock(stdout="Resp.", stderr="")
        for i in range(10):
            yap.cmd_query(f"Mensaje {i}", store_history=True)
        assert len(yap.HISTORY) <= yap.MAX_HISTORY


# ============================================================
# 6. SISTEMA DE NOTIFICACIONES
# ============================================================

class TestNotifications:
    """Requisito: El agente emite notificaciones graficas."""

    @patch("subprocess.run")
    def test_notify_enviado(self, mock_run):
        mock_run.return_value = Mock()
        yap.notify("Titulo", "Mensaje", urgency="normal")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "notify-send" in args[0]
        assert "Titulo" in args
        assert "Mensaje" in args

    @patch("subprocess.run")
    def test_notify_urgency_levels(self, mock_run):
        yap.notify("Alerta", "Peligro", urgency="critical")
        args = mock_run.call_args[0][0]
        assert "-u" in args
        idx = args.index("-u")
        assert args[idx + 1] == "critical"


# ============================================================
# 7. ARQUITECTURA Y COMPONENTES
# ============================================================

class TestArchitecture:
    """Verificar que el codigo sigue la arquitectura definida."""

    def test_main_existe(self):
        assert hasattr(yap, "main") and callable(yap.main)

    def test_handle_action_existe(self):
        assert hasattr(yap, "handle_action") and callable(yap.handle_action)

    def test_interpret_existe(self):
        assert hasattr(yap, "interpret") and callable(yap.interpret)

    def test_load_whitelist_existe(self):
        assert hasattr(yap, "load_whitelist") and callable(yap.load_whitelist)

    def test_load_domain_whitelist_existe(self):
        assert hasattr(yap, "load_domain_whitelist") and callable(yap.load_domain_whitelist)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
