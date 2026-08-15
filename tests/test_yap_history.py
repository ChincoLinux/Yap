"""
test_yap_history.py — Pruebas del historial persistente entre sesiones (#13)

Verifica:
  1. Guardado de sesiones en ~/.config/yap/history.json
  2. Carga de sesiones anteriores
  3. Comando `historial` muestra resumen
  4. Comando `historial --ultimo` restaura contexto
  5. Límite de sesiones retenidas (MAX_HISTORY_SESSIONS)
  6. Escritura atómica
  7. Manejo de archivos corruptos/inexistentes
  8. Integración con interpret() y handle_action()

Ejecucion: python3 -m pytest tests/test_yap_history.py -v
"""

import pytest
import sys
import os
import tempfile
import json
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


class TestHistorySave:
    """Requisito: Las sesiones se guardan atómicamente en history.json."""

    def test_save_session_vacia_no_guarda(self):
        """Si HISTORY está vacío, no se guarda nada."""
        tmp = tempfile.mkdtemp()
        hist_file = os.path.join(tmp, "history.json")
        with mock.patch.object(yap, "HISTORY_FILE", hist_file):
            with mock.patch.object(yap, "HISTORY", []):
                yap._save_history_session()
                assert not os.path.exists(hist_file)

    def test_save_session_con_contenido(self):
        """Una sesión con turnos se guarda correctamente."""
        tmp = tempfile.mkdtemp()
        hist_file = os.path.join(tmp, "history.json")
        with mock.patch.object(yap, "HISTORY_FILE", hist_file):
            with mock.patch.object(yap, "HISTORY", [("hola", "hola de vuelta")]):
                yap._save_history_session()
                with open(hist_file) as f:
                    data = json.load(f)
                assert len(data) == 1
                assert data[0]["turns"][0]["user"] == "hola"
                assert data[0]["turns"][0]["assistant"] == "hola de vuelta"
                assert "timestamp" in data[0]

    def test_save_session_atomic(self):
        """Verifica que no queda archivo .tmp después de guardar."""
        tmp = tempfile.mkdtemp()
        hist_file = os.path.join(tmp, "history.json")
        with mock.patch.object(yap, "HISTORY_FILE", hist_file):
            with mock.patch.object(yap, "HISTORY", [("test", "resp")]):
                yap._save_history_session()
                assert not os.path.exists(hist_file + ".tmp")

    def test_save_multiple_sessions_acumula(self):
        """Guardar dos sesiones crea una lista con 2 elementos."""
        tmp = tempfile.mkdtemp()
        hist_file = os.path.join(tmp, "history.json")
        with mock.patch.object(yap, "HISTORY_FILE", hist_file):
            with mock.patch.object(yap, "HISTORY", [("q1", "a1")]):
                yap._save_history_session()
            with mock.patch.object(yap, "HISTORY", [("q2", "a2")]):
                yap._save_history_session()
            sessions = yap._load_history_sessions()
            assert len(sessions) == 2


class TestHistoryLoad:
    """Requisito: Las sesiones se cargan correctamente."""

    def test_load_archivo_inexistente(self):
        with mock.patch.object(yap, "HISTORY_FILE", "/nonexistent/path.json"):
            assert yap._load_history_sessions() == []

    def test_load_json_invalido(self):
        tmp = tempfile.mkdtemp()
        hist_file = os.path.join(tmp, "history.json")
        with open(hist_file, "w") as f:
            f.write("not json{{{")
        with mock.patch.object(yap, "HISTORY_FILE", hist_file):
            assert yap._load_history_sessions() == []

    def test_load_formato_no_lista(self):
        """Si el JSON no es una lista, retorna vacío."""
        tmp = tempfile.mkdtemp()
        hist_file = os.path.join(tmp, "history.json")
        with open(hist_file, "w") as f:
            json.dump({"not": "a list"}, f)
        with mock.patch.object(yap, "HISTORY_FILE", hist_file):
            assert yap._load_history_sessions() == []


class TestMaxSessions:
    """Requisito: Se retienen solo las últimas N sesiones."""

    def test_trim_al_limite(self):
        """Al superar MAX_HISTORY_SESSIONS, se eliminan las más antiguas."""
        tmp = tempfile.mkdtemp()
        hist_file = os.path.join(tmp, "history.json")
        with mock.patch.object(yap, "HISTORY_FILE", hist_file):
            with mock.patch.object(yap, "MAX_HISTORY_SESSIONS", 3):
                for i in range(5):
                    with mock.patch.object(yap, "HISTORY", [(f"q{i}", f"a{i}")]):
                        yap._save_history_session()
                sessions = yap._load_history_sessions()
                assert len(sessions) == 3
                # Debe mantener las últimas 3 (q2, q3, q4)
                assert sessions[0]["turns"][0]["user"] == "q2"
                assert sessions[-1]["turns"][0]["user"] == "q4"


class TestCmdHistorial:
    """Requisito: cmd_historial muestra resumen y restaura contexto."""

    def test_historial_vacio(self):
        with mock.patch.object(yap, "HISTORY_FILE", "/nonexistent/path.json"):
            result = yap.cmd_historial()
            assert "No hay historial" in result

    def test_historial_muestra_sesiones(self):
        tmp = tempfile.mkdtemp()
        hist_file = os.path.join(tmp, "history.json")
        sessions = [
            {"timestamp": "2026-01-01T10:00:00", "turns": [{"user": "hola", "assistant": "hi"}]},
            {"timestamp": "2026-01-02T11:00:00", "turns": [{"user": "chao", "assistant": "bye"}]},
        ]
        with open(hist_file, "w") as f:
            json.dump(sessions, f)
        with mock.patch.object(yap, "HISTORY_FILE", hist_file):
            result = yap.cmd_historial()
            assert "Sesión 1" in result
            assert "Sesión 2" in result
            assert "hola" in result

    def test_historial_ultimo_restaura_contexto(self):
        """historial --ultimo carga los turnos en HISTORY."""
        tmp = tempfile.mkdtemp()
        hist_file = os.path.join(tmp, "history.json")
        sessions = [
            {"timestamp": "2026-01-01T10:00:00", "turns": [
                {"user": "que es python", "assistant": "un lenguaje"},
                {"user": "y java", "assistant": "otro lenguaje"},
            ]},
        ]
        with open(hist_file, "w") as f:
            json.dump(sessions, f)
        with mock.patch.object(yap, "HISTORY_FILE", hist_file):
            with mock.patch.object(yap, "HISTORY", []):
                result = yap.cmd_historial(resume_last=True)
                assert "Contexto restaurado" in result
                assert len(yap.HISTORY) == 2
                assert yap.HISTORY[0][0] == "que es python"

    def test_historial_ultimo_sin_sesiones(self):
        with mock.patch.object(yap, "HISTORY_FILE", "/nonexistent/path.json"):
            result = yap.cmd_historial(resume_last=True)
            assert "No hay historial" in result

    def test_historial_ultimo_sesion_vacia(self):
        """Si la última sesión no tiene turnos, avisa."""
        tmp = tempfile.mkdtemp()
        hist_file = os.path.join(tmp, "history.json")
        sessions = [{"timestamp": "2026-01-01", "turns": []}]
        with open(hist_file, "w") as f:
            json.dump(sessions, f)
        with mock.patch.object(yap, "HISTORY_FILE", hist_file):
            result = yap.cmd_historial(resume_last=True)
            assert "no tiene conversación" in result or "vacía" in result or "vacia" in result


class TestInterpretRouting:
    """Requisito: interpret() enruta 'historial' y 'historial --ultimo'."""

    def test_interpret_historial(self):
        action, param = yap.interpret("historial")
        assert action == "historial"
        assert param == "historial"

    def test_interpret_historial_ultimo(self):
        action, param = yap.interpret("historial --ultimo")
        assert action == "historial"
        assert param == "--ultimo"


class TestHandleActionIntegration:
    """Requisito: handle_action maneja 'historial' correctamente."""

    def test_handle_historial_muestra_resumen(self):
        with mock.patch.object(yap, "cmd_historial", return_value="resumen"):
            yap.handle_action("historial", "historial", "historial")

    def test_handle_historial_ultimo_restaura(self):
        with mock.patch.object(yap, "cmd_historial", return_value="restaurado"):
            yap.handle_action("historial", "--ultimo", "historial --ultimo")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
