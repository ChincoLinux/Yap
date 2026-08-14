"""
test_yap_confirmation.py — Pruebas de la capa de confirmación humana (#12)

Verifica:
  1. Acciones sensibles requieren confirmación
  2. Acciones no sensibles no requieren confirmación
  3. Modo no-interactivo deniega por defecto
  4. Confirmaciones se registran y persisten
  5. Nivel "trusted" funciona tras N confirmaciones
  6. handle_action integra confirmación para open_app y webfetch

Ejecucion: python3 -m pytest tests/test_yap_confirmation.py -v
"""

import pytest
import sys
import os
import tempfile
import json
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


class TestSensitiveActions:
    """Requisito: Acciones sensibles están definidas en SENSITIVE_ACTIONS."""

    def test_open_app_es_sensible(self):
        assert "open_app" in yap.SENSITIVE_ACTIONS

    def test_webfetch_es_sensible(self):
        assert "webfetch" in yap.SENSITIVE_ACTIONS

    def test_query_no_es_sensible(self):
        assert "query" not in yap.SENSITIVE_ACTIONS

    def test_niveles_validos(self):
        for action, level in yap.SENSITIVE_ACTIONS.items():
            assert level in ("always", "new", "trusted"), (
                f"Nivel inválido para {action}: {level}"
            )


class TestConfirmAction:
    """Requisito: confirm_action devuelve True/False correctamente."""

    def test_accion_no_sensible_retorna_true(self):
        with mock.patch.object(yap, "SENSITIVE_ACTIONS", {}):
            assert yap.confirm_action("query", "test") is True

    def test_no_interactivo_denia_por_defecto(self):
        """En modo no-interactivo (sin TTY), deniega acciones sensibles."""
        with mock.patch.object(yap, "SENSITIVE_ACTIONS", {"open_app": "always"}):
            with mock.patch("sys.stdin") as mock_stdin:
                mock_stdin.isatty.return_value = False
                assert yap.confirm_action("open_app", "firefox") is False

    def test_usuario_confirma_retorna_true(self):
        """Usuario responde 's' → True."""
        with mock.patch.object(yap, "SENSITIVE_ACTIONS", {"open_app": "always"}):
            with mock.patch("sys.stdin") as mock_stdin:
                mock_stdin.isatty.return_value = True
                with mock.patch("builtins.input", return_value="s"):
                    with mock.patch.object(yap, "_record_confirmation"):
                        assert yap.confirm_action("open_app", "firefox") is True

    def test_usuario_denia_retorna_false(self):
        """Usuario responde 'n' → False."""
        with mock.patch.object(yap, "SENSITIVE_ACTIONS", {"open_app": "always"}):
            with mock.patch("sys.stdin") as mock_stdin:
                mock_stdin.isatty.return_value = True
                with mock.patch("builtins.input", return_value="n"):
                    assert yap.confirm_action("open_app", "firefox") is False

    def test_usuario_vacio_denia(self):
        """Usuario presiona Enter (vacío) → False (default N)."""
        with mock.patch.object(yap, "SENSITIVE_ACTIONS", {"open_app": "always"}):
            with mock.patch("sys.stdin") as mock_stdin:
                mock_stdin.isatty.return_value = True
                with mock.patch("builtins.input", return_value=""):
                    assert yap.confirm_action("open_app", "firefox") is False

    def test_eof_denia(self):
        """EOFError → False."""
        with mock.patch.object(yap, "SENSITIVE_ACTIONS", {"open_app": "always"}):
            with mock.patch("sys.stdin") as mock_stdin:
                mock_stdin.isatty.return_value = True
                with mock.patch("builtins.input", side_effect=EOFError):
                    assert yap.confirm_action("open_app", "firefox") is False


class TestTrustedLevel:
    """Requisito: Nivel 'trusted' confía tras N confirmaciones."""

    def test_trusted_bypassa_confirmacion(self):
        """Tras N confirmaciones, no pregunta."""
        with mock.patch.object(yap, "SENSITIVE_ACTIONS", {"open_app": "trusted"}):
            with mock.patch.object(yap, "_is_trusted", return_value=True):
                assert yap.confirm_action("open_app", "firefox") is True

    def test_trusted_no_bypassa_si_no_alcanza(self):
        """Si no alcanza el threshold, pregunta."""
        with mock.patch.object(yap, "SENSITIVE_ACTIONS", {"open_app": "trusted"}):
            with mock.patch.object(yap, "_is_trusted", return_value=False):
                with mock.patch("sys.stdin") as mock_stdin:
                    mock_stdin.isatty.return_value = False
                    assert yap.confirm_action("open_app", "firefox") is False


class TestConfirmationPersistence:
    """Requisito: Confirmaciones se guardan atómicamente."""

    def test_record_confirmation_incrementa(self):
        tmp = tempfile.mkdtemp()
        conf_file = os.path.join(tmp, "confirmations.json")
        with mock.patch.object(yap, "CONFIRMATION_FILE", conf_file):
            yap._record_confirmation("open_app", "firefox")
            yap._record_confirmation("open_app", "firefox")
            data = yap._load_confirmations()
            assert data["open_app:firefox"] == 2

    def test_load_confirmations_archivo_inexistente(self):
        with mock.patch.object(yap, "CONFIRMATION_FILE", "/nonexistent/path.json"):
            assert yap._load_confirmations() == {}

    def test_load_confirmations_json_invalido(self):
        tmp = tempfile.mkdtemp()
        conf_file = os.path.join(tmp, "confirmations.json")
        with open(conf_file, "w") as f:
            f.write("not json{{{")
        with mock.patch.object(yap, "CONFIRMATION_FILE", conf_file):
            assert yap._load_confirmations() == {}

    def test_save_atomic(self):
        """Verifica que se usa escritura atómica (tmp + rename)."""
        tmp = tempfile.mkdtemp()
        conf_file = os.path.join(tmp, "confirmations.json")
        with mock.patch.object(yap, "CONFIRMATION_FILE", conf_file):
            yap._save_confirmations({"test": 1})
            assert os.path.exists(conf_file)
            with open(conf_file) as f:
                assert json.load(f) == {"test": 1}
            # No debe quedar archivo .tmp
            assert not os.path.exists(conf_file + ".tmp")


class TestHandleActionIntegration:
    """Requisito: handle_action integra confirmación para open_app y webfetch."""

    def test_open_app_cancelado_no_ejecuta(self):
        """Si confirm_action devuelve False, no se ejecuta cmd_open_app."""
        with mock.patch.object(yap, "confirm_action", return_value=False):
            with mock.patch.object(yap, "cmd_open_app") as mock_cmd:
                yap.handle_action("open_app", "firefox", "abre firefox")
                mock_cmd.assert_not_called()

    def test_open_app_confirmado_ejecuta(self):
        """Si confirm_action devuelve True, se ejecuta cmd_open_app."""
        with mock.patch.object(yap, "confirm_action", return_value=True):
            with mock.patch.object(yap, "cmd_open_app", return_value="[OK]"):
                yap.handle_action("open_app", "firefox", "abre firefox")

    def test_webfetch_cancelado_no_ejecuta(self):
        """Si confirm_action devuelve False, no se ejecuta cmd_webfetch."""
        with mock.patch.object(yap, "confirm_action", return_value=False):
            with mock.patch.object(yap, "cmd_webfetch") as mock_cmd:
                yap.handle_action("webfetch", "https://example.com", "fetch url")
                mock_cmd.assert_not_called()

    def test_webfetch_confirmado_ejecuta(self):
        """Si confirm_action devuelve True, se ejecuta cmd_webfetch."""
        with mock.patch.object(yap, "confirm_action", return_value=True):
            with mock.patch.object(yap, "cmd_webfetch", return_value="ok"):
                with mock.patch.object(yap, "cmd_query", return_value="ok"):
                    yap.handle_action("webfetch", "https://wikipedia.org", "fetch")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
