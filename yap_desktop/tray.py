"""tray.py — Icono residente en la bandeja del sistema (issues #153, #154).

Implementa:
  - QSystemTrayIcon con icono SVG generado programáticamente
  - Menú contextual de clic derecho (#154):
      · Abrir Yap        → muestra/oculta la ventana flotante
      · Estado del modelo → muestra estado del daemon
      · ─────────────
      · Preferencias     → abre ~/.config/yap/ en el gestor de archivos
      · Ayuda            → abre README en el navegador
      · ─────────────
      · Salir            → termina la aplicación
  - Clic izquierdo → show/hide widget (#155)
  - Tooltip: 'Yap — Asistente IA local'
"""

from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path
from typing import Optional

try:
    from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
    from PyQt6.QtCore import Qt, QSize
    _QT_BACKEND = "PyQt6"
except ImportError:
    try:
        from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
        from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
        from PySide6.QtCore import Qt, QSize
        _QT_BACKEND = "PySide6"
    except ImportError:
        raise ImportError(
            "Se requiere PyQt6 o PySide6. Instala con:\n"
            "  pip install PyQt6\n"
            "  # o\n"
            "  pip install PySide6"
        )


def _make_icon(size: int = 64) -> QIcon:
    """Genera un icono SVG programáticamente (sin archivo externo).

    El icono es un cuadrado redondeado verde con la letra 'Y' en blanco.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Fondo verde redondeado
    painter.setBrush(QColor("#2ecc71"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, size, size, size * 0.2, size * 0.2)

    # Letra 'Y' en blanco
    font = QFont("Arial", int(size * 0.55), QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(0, 0, size, size, Qt.AlignmentFlag.AlignCenter, "Y")

    painter.end()
    return QIcon(pixmap)


class YapTrayIcon(QSystemTrayIcon):
    """Icono de bandeja del sistema para Yap."""

    def __init__(self, widget, daemon, parent=None):
        """
        Args:
            widget: instancia de YapWidget (ventana flotante).
            daemon: instancia de YapDaemon.
            parent: QObject padre.
        """
        super().__init__(parent)
        self._widget = widget
        self._daemon = daemon
        self._setup_icon()
        self._setup_menu()
        self._connect_signals()
        self.setToolTip("Yap — Asistente IA local")

    # ─── Setup ───────────────────────────────────────────────────────────────

    def _setup_icon(self) -> None:
        """Carga el icono (archivo externo o generado)."""
        # Buscar icono en ubicaciones conocidas
        icon_paths = [
            Path(__file__).parent.parent / "packaging" / "desktop" / "yap.png",
            Path("/usr/share/pixmaps/yap.png"),
            Path("/opt/yap/yap.png"),
        ]
        for p in icon_paths:
            if p.exists():
                self.setIcon(QIcon(str(p)))
                return
        # Fallback: icono generado
        self.setIcon(_make_icon())

    def _setup_menu(self) -> None:
        """Construye el menú contextual de clic derecho."""
        menu = QMenu()

        # Acción principal
        self._action_toggle = menu.addAction("⊞  Abrir Yap")
        self._action_toggle.triggered.connect(self._toggle_widget)

        menu.addSeparator()

        # Estado del daemon
        self._action_status = menu.addAction("● Inicializando...")
        self._action_status.setEnabled(False)

        menu.addSeparator()

        # Acciones secundarias
        act_prefs = menu.addAction("⚙  Preferencias")
        act_prefs.triggered.connect(self._open_config_dir)

        act_help = menu.addAction("?  Ayuda")
        act_help.triggered.connect(self._open_help)

        menu.addSeparator()

        act_quit = menu.addAction("✕  Salir")
        act_quit.triggered.connect(self._quit_app)

        self.setContextMenu(menu)

    def _connect_signals(self) -> None:
        """Conecta señales del tray icon."""
        self.activated.connect(self._on_activated)

    # ─── Slots ───────────────────────────────────────────────────────────────

    def _on_activated(self, reason) -> None:
        """Maneja clic en el icono."""
        # Trigger = clic izquierdo o doble clic
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._toggle_widget()

    def _toggle_widget(self) -> None:
        """Muestra u oculta la ventana flotante."""
        if self._widget.isVisible():
            self._widget.hide()
            self._action_toggle.setText("⊞  Abrir Yap")
        else:
            self._widget.show_near_tray()
            self._action_toggle.setText("⊟  Cerrar Yap")

    def _open_config_dir(self) -> None:
        """Abre el directorio de configuración en el gestor de archivos."""
        config_dir = Path.home() / ".config" / "yap"
        config_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(config_dir))
        else:
            import subprocess
            xdg = "xdg-open"
            subprocess.Popen([xdg, str(config_dir)], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, timeout=5)

    def _open_help(self) -> None:
        """Abre la guía de uso en el navegador."""
        webbrowser.open("https://github.com/ChincoLinux/Yap/blob/main/USAGE.md")

    def _quit_app(self) -> None:
        """Detiene el daemon y sale de la aplicación."""
        if self._daemon:
            self._daemon.stop()
        QApplication.instance().quit()

    # ─── API pública ─────────────────────────────────────────────────────────

    def update_status(self, status: str) -> None:
        """Actualiza el texto de estado en el menú.

        Args:
            status: 'idle', 'busy', 'error', 'stopped'
        """
        icons = {"idle": "●", "busy": "◌", "error": "✗", "stopped": "○"}
        labels = {
            "idle":    "Modelo listo",
            "busy":    "Procesando...",
            "error":   "Error en el modelo",
            "stopped": "Daemon detenido",
        }
        icon = icons.get(status, "?")
        label = labels.get(status, status)
        self._action_status.setText(f"{icon}  {label}")
