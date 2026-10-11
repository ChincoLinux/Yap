"""app.py — Entry point de Yap Desktop (issue #152, #159).

Orquesta:
  1. YapDaemon   — motor de inferencia en segundo plano
  2. YapWidget   — ventana flotante de chat
  3. YapTrayIcon — icono de bandeja + menú contextual
  4. HotkeyListener — atajo global Ctrl+Shift+Y

Uso:
    python3 -m yap_desktop
    python3 -m yap_desktop --minimized   # arranca sin mostrar la ventana
    python3 -m yap_desktop --help
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="yap-desktop",
        description="Yap — Asistente IA local (interfaz de escritorio)",
    )
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Arrancar minimizado en la bandeja (no mostrar la ventana al inicio)",
    )
    parser.add_argument(
        "--hotkey",
        default=None,
        help="Atajo de teclado global (ej. 'ctrl+shift+y'). Sobreescribe la config.",
    )
    parser.add_argument(
        "--python", default=None, help="Intérprete Python a usar para invocar yap.py"
    )
    parser.add_argument("--debug", action="store_true", help="Activa logging detallado")
    return parser.parse_args()


def _setup_autostart_linux() -> None:
    """Instala el archivo .desktop de auto-arranque en ~/.config/autostart/."""
    autostart_dir = Path.home() / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    target = autostart_dir / "yap-desktop.desktop"
    if target.exists():
        return

    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Yap Desktop\n"
        "Comment=Asistente IA local de ChincoLinux\n"
        f"Exec={sys.executable} -m yap_desktop --minimized\n"
        "Hidden=false\n"
        "NoDisplay=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    try:
        target.write_text(content, encoding="utf-8")
        logger.info("Auto-arranque instalado en %s", target)
    except OSError as e:
        logger.warning("No se pudo instalar el auto-arranque: %s", e)


def main() -> int:
    """Punto de entrada principal."""
    args = _parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # ── Importar Qt ───────────────────────────────────────────────────────
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            print(
                "ERROR: Se requiere PyQt6 o PySide6.\n"
                "  pip install PyQt6\n"
                "  # o\n"
                "  pip install PySide6",
                file=sys.stderr,
            )
            return 1

    # ── Verificar soporte de bandeja ──────────────────────────────────────
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Yap")
    app.setApplicationVersion("1.0.1")
    app.setOrganizationName("ChincoLinux")
    # No salir cuando se cierra la última ventana (quedamos en la bandeja)
    app.setQuitOnLastWindowClosed(False)

    from PyQt6.QtWidgets import QSystemTrayIcon

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print(
            "ERROR: No hay bandeja del sistema disponible en este escritorio.",
            file=sys.stderr,
        )
        return 1

    # ── Daemon ────────────────────────────────────────────────────────────
    from yap_desktop.daemon import YapDaemon

    daemon = YapDaemon(python_exe=args.python)
    daemon.start()

    # ── Widget ────────────────────────────────────────────────────────────
    from yap_desktop.widget import YapWidget

    widget = YapWidget(daemon=daemon)

    # ── Tray ──────────────────────────────────────────────────────────────
    from yap_desktop.tray import YapTrayIcon

    tray = YapTrayIcon(widget=widget, daemon=daemon)
    tray.show()

    # Actualizar estado del tray periódicamente
    try:
        from PyQt6.QtCore import QTimer
    except ImportError:
        from PySide6.QtCore import QTimer

    def _update_status():
        tray.update_status(daemon.status)

    status_timer = QTimer()
    status_timer.timeout.connect(_update_status)
    status_timer.start(2000)  # cada 2 segundos

    # ── Hotkey ────────────────────────────────────────────────────────────
    from yap_desktop.hotkey import HotkeyListener

    def _toggle():
        if widget.isVisible():
            widget.hide()
        else:
            widget.show_near_tray()

    hotkey_listener = HotkeyListener(
        callback=_toggle,
        hotkey=args.hotkey,
    )
    backend = hotkey_listener.start()
    logger.info("Hotkey backend: %s, atajo: %s", backend, hotkey_listener.hotkey)

    # ── Auto-arranque (solo Linux, primera vez) ───────────────────────────
    if sys.platform.startswith("linux"):
        _setup_autostart_linux()

    # ── Mostrar ventana (si no es minimizado) ─────────────────────────────
    if not args.minimized:
        widget.show_near_tray()

    # Notificación de inicio
    tray.showMessage(
        "Yap listo",
        f"Asistente IA local iniciado. Atajo: {hotkey_listener.hotkey}",
        msecs=3000,
    )

    # ── Event loop ────────────────────────────────────────────────────────
    try:
        ret = app.exec()
    finally:
        hotkey_listener.stop()
        daemon.stop()

    return ret
