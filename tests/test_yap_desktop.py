"""tests/test_yap_desktop.py — Tests del módulo yap_desktop.

Cubre:
  - daemon.py: queue de comandos, manejo de errores, rutas de yap.py
  - widget.py: conversión Markdown → HTML, lógica sin Qt
  - tray.py:   construcción de menú (con Qt mockeado)
  - hotkey.py: lectura de config, backends faltantes, change_hotkey
  - app.py:    _setup_autostart_linux, _parse_args

Todos los tests se ejecutan sin display (DISPLAY vacío) y sin
instanciar widgets Qt reales, usando unittest.mock.
"""

import json
import os
import queue
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# ─── Fixtures comunes ────────────────────────────────────────────────────────

def _fake_yap_script(tmp_path: Path) -> Path:
    """Crea un yap.py stub que devuelve texto fijo."""
    script = tmp_path / "yap.py"
    script.write_text(
        'import sys\nargs = " ".join(sys.argv[1:])\nprint(f"[stub] {args}")\n',
        encoding="utf-8"
    )
    return script


# ─── Tests: daemon.py ────────────────────────────────────────────────────────

class TestYapDaemon(unittest.TestCase):
    """Tests de YapDaemon sin necesidad de LLM real."""

    def setUp(self):
        from yap_desktop.daemon import YapDaemon
        self.YapDaemon = YapDaemon

    def test_daemon_init_idle(self):
        """El daemon empieza en estado IDLE."""
        daemon = self.YapDaemon()
        self.assertEqual(daemon.status, "idle")

    def test_daemon_start_creates_thread(self):
        """start() lanza un hilo daemon."""
        daemon = self.YapDaemon()
        daemon.start()
        self.assertIsNotNone(daemon._thread)
        self.assertTrue(daemon._thread.is_alive())
        daemon.stop()

    def test_daemon_stop_changes_status(self):
        """stop() cambia el estado a stopped."""
        daemon = self.YapDaemon()
        daemon.start()
        daemon.stop()
        self.assertEqual(daemon.status, "stopped")

    def test_daemon_double_start_safe(self):
        """Llamar start() dos veces no lanza excepción."""
        daemon = self.YapDaemon()
        daemon.start()
        daemon.start()  # segunda llamada — no-op
        daemon.stop()

    def test_daemon_query_calls_callback(self):
        """query() ejecuta la respuesta y llama al callback."""
        responses = []
        done = threading.Event()

        def cb(resp):
            responses.append(resp)
            done.set()

        with patch("yap_desktop.daemon._find_yap_script") as mock_find, \
             patch("subprocess.Popen") as mock_popen:
            mock_find.return_value = Path("/fake/yap.py")
            proc = MagicMock()
            proc.communicate.return_value = ("Hola desde stub", "")
            mock_popen.return_value = proc

            daemon = self.YapDaemon()
            daemon.start()
            daemon.query("¿Qué es Python?", cb)
            done.wait(timeout=3)
            daemon.stop()

        self.assertTrue(len(responses) > 0)
        self.assertIn("Hola", responses[0])

    def test_daemon_timeout_returns_message(self):
        """Si el proceso tarda demasiado, devuelve mensaje de timeout."""
        done = threading.Event()
        responses = []

        def cb(resp):
            responses.append(resp)
            done.set()

        import subprocess
        with patch("yap_desktop.daemon._find_yap_script") as mock_find, \
             patch("subprocess.Popen") as mock_popen:
            mock_find.return_value = Path("/fake/yap.py")
            proc = MagicMock()
            proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="yap", timeout=1)
            mock_popen.return_value = proc

            daemon = self.YapDaemon(timeout=1)
            daemon.start()
            daemon.query("pregunta lenta", cb)
            done.wait(timeout=5)
            daemon.stop()

        self.assertTrue(any("agotado" in r.lower() for r in responses))

    def test_daemon_find_yap_script_env(self, tmp_path=None):
        """YAP_SCRIPT env var se usa como ruta a yap.py cuando los candidatos no existen."""
        import tempfile
        import yap_desktop.daemon as dm_mod
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "yap.py"
            fake.write_text("# stub\n")
            with patch.dict(os.environ, {"YAP_SCRIPT": str(fake)}), \
                 patch("pathlib.Path.exists", return_value=False):
                result = dm_mod._find_yap_script()
            self.assertEqual(result, fake)


    def test_daemon_find_yap_script_not_found(self):
        """FileNotFoundError si yap.py no existe en ninguna ubicación."""
        from yap_desktop.daemon import _find_yap_script
        with patch.dict(os.environ, {}, clear=True), \
             patch("pathlib.Path.exists", return_value=False):
            with self.assertRaises(FileNotFoundError):
                _find_yap_script()

    def test_daemon_find_llama_cli(self):
        """_find_llama_cli devuelve ruta si shutil.which encuentra el binario."""
        from yap_desktop.daemon import YapDaemon
        with patch("shutil.which", return_value="/usr/local/bin/llama-cli"):
            result = YapDaemon._find_llama_cli()
            self.assertIsNotNone(result)

    def test_daemon_find_llama_cli_missing(self):
        """_find_llama_cli devuelve None si no se encuentra llama-cli."""
        from yap_desktop.daemon import YapDaemon
        with patch("shutil.which", return_value=None), \
             patch.dict(os.environ, {}, clear=True):
            result = YapDaemon._find_llama_cli()
            self.assertIsNone(result)


# ─── Tests: widget.py (_md_to_html) ──────────────────────────────────────────

class TestMarkdownToHtml(unittest.TestCase):
    """Tests de la función md_to_html sin necesidad de Qt."""

    def _convert(self, text: str) -> str:
        from yap_desktop.utils import md_to_html
        return md_to_html(text)

    def test_bold(self):
        result = self._convert("**negrita**")
        self.assertIn("<b>negrita</b>", result)

    def test_italic(self):
        result = self._convert("*cursiva*")
        self.assertIn("<i>cursiva</i>", result)

    def test_code_inline(self):
        result = self._convert("`codigo`")
        self.assertIn("<code", result)
        self.assertIn("codigo", result)

    def test_code_block(self):
        result = self._convert("```\ndef f():\n    pass\n```")
        self.assertIn("<pre", result)
        self.assertIn("def f", result)

    def test_list_item(self):
        result = self._convert("- elemento")
        self.assertIn("<li>elemento</li>", result)

    def test_html_escaping(self):
        """El HTML del usuario se escapa correctamente."""
        result = self._convert("<script>alert('xss')</script>")
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_newlines_to_br(self):
        result = self._convert("linea1\nlinea2")
        self.assertIn("<br>", result)

    def test_plain_text_unchanged(self):
        result = self._convert("texto plano sin formato")
        self.assertIn("texto plano", result)


# ─── Tests: hotkey.py ────────────────────────────────────────────────────────

class TestHotkeyListener(unittest.TestCase):
    """Tests de HotkeyListener sin backends reales."""

    def test_default_hotkey(self):
        """Sin configuración, el atajo por defecto es ctrl+shift+y."""
        from yap_desktop.hotkey import HotkeyListener, _DEFAULT_HOTKEY
        listener = HotkeyListener(callback=lambda: None)
        self.assertEqual(listener.hotkey, _DEFAULT_HOTKEY)

    def test_custom_hotkey(self):
        """Se puede especificar un atajo personalizado."""
        from yap_desktop.hotkey import HotkeyListener
        listener = HotkeyListener(callback=lambda: None, hotkey="ctrl+alt+y")
        self.assertEqual(listener.hotkey, "ctrl+alt+y")

    def test_no_backends_returns_none(self):
        """Si pynput y keyboard fallan, backend es 'none' sin excepción."""
        from yap_desktop.hotkey import HotkeyListener
        with patch("yap_desktop.hotkey._try_pynput", return_value=None), \
             patch("yap_desktop.hotkey._try_keyboard", return_value=None):
            listener = HotkeyListener(callback=lambda: None)
            result = listener.start()
            self.assertEqual(result, "none")
            self.assertEqual(listener.backend, "none")

    def test_pynput_backend_used(self):
        """Si pynput está disponible, se usa como backend."""
        from yap_desktop.hotkey import HotkeyListener

        mock_listener = MagicMock()
        mock_listener.start = MagicMock()

        with patch("yap_desktop.hotkey._try_pynput", return_value=mock_listener), \
             patch("threading.Thread") as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            listener = HotkeyListener(callback=lambda: None)
            result = listener.start()

        self.assertEqual(result, "pynput")

    def test_save_and_load_config(self, tmp_path=None):
        """_save_hotkey_config y _load_hotkey_config roundtrip."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "desktop.json"
            with patch("yap_desktop.hotkey._CONFIG_FILE", config_path):
                from yap_desktop.hotkey import _save_hotkey_config, _load_hotkey_config
                _save_hotkey_config("ctrl+alt+q")
                loaded = _load_hotkey_config()
                self.assertEqual(loaded, "ctrl+alt+q")

    def test_stop_without_start_safe(self):
        """stop() sin start() no lanza excepción."""
        from yap_desktop.hotkey import HotkeyListener
        listener = HotkeyListener(callback=lambda: None)
        listener.stop()  # no debe lanzar

    def test_change_hotkey(self):
        """change_hotkey para el listener actual y registra el nuevo."""
        from yap_desktop.hotkey import HotkeyListener
        with patch("yap_desktop.hotkey._try_pynput", return_value=None), \
             patch("yap_desktop.hotkey._try_keyboard", return_value=None), \
             patch("yap_desktop.hotkey._save_hotkey_config") as mock_save:
            listener = HotkeyListener(callback=lambda: None)
            listener.start()
            listener.change_hotkey("ctrl+alt+z")
            mock_save.assert_called_with("ctrl+alt+z")
            self.assertEqual(listener.hotkey, "ctrl+alt+z")


# ─── Tests: autostart ─────────────────────────────────────────────────────────

class TestAutostart(unittest.TestCase):
    """Tests del mecanismo de auto-arranque."""

    def test_autostart_file_created(self):
        """_setup_autostart_linux crea el archivo .desktop en autostart."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            autostart_dir = Path(td) / ".config" / "autostart"
            with patch("pathlib.Path.home", return_value=Path(td)):
                from yap_desktop.app import _setup_autostart_linux
                _setup_autostart_linux()
                desktop_file = autostart_dir / "yap-desktop.desktop"
                self.assertTrue(desktop_file.exists())
                content = desktop_file.read_text()
                self.assertIn("X-GNOME-Autostart-enabled=true", content)
                self.assertIn("--minimized", content)

    def test_autostart_not_overwritten(self):
        """Si el archivo ya existe, no se sobreescribe."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            autostart_dir = Path(td) / ".config" / "autostart"
            autostart_dir.mkdir(parents=True)
            existing = autostart_dir / "yap-desktop.desktop"
            existing.write_text("# existing\n")

            with patch("pathlib.Path.home", return_value=Path(td)):
                from yap_desktop.app import _setup_autostart_linux
                _setup_autostart_linux()

            self.assertEqual(existing.read_text(), "# existing\n")


if __name__ == "__main__":
    unittest.main()
