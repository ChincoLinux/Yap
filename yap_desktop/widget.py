"""widget.py — Ventana flotante de chat rápido (issues #155, #156, #157).

Implementa:
  - Ventana sin bordes posicionada sobre el icono de bandeja (#155)
  - Chat con historial, input field y render básico de Markdown (#156)
  - Botones de acción rápida: Cursos, Ejercicios, Historial, Perfil (#157)
  - Toggle Local / Nube (Super Yap) (#157)
  - Atajo Ctrl+Shift+Y para mostrar/ocultar (#158 — definido en hotkey.py)
"""

from __future__ import annotations

from yap_desktop.utils import md_to_html as _md_to_html

try:
    from PyQt6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QPushButton,
        QLineEdit,
        QTextEdit,
        QLabel,
        QFrame,
    )
    from PyQt6.QtGui import QKeySequence, QShortcut
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal as Signal
    from PyQt6.QtWidgets import QApplication
except ImportError:
    from PySide6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QPushButton,
        QLineEdit,
        QTextEdit,
        QLabel,
        QFrame,
    )
    from PySide6.QtGui import QKeySequence, QShortcut
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtWidgets import QApplication


# Paleta de colores (dark theme educativo)
_COLORS = {
    "bg_window": "#1a1a2e",
    "bg_header": "#16213e",
    "bg_input": "#0f3460",
    "bg_user_msg": "#0f3460",
    "bg_yap_msg": "#1a1a2e",
    "accent": "#2ecc71",
    "text": "#e0e0e0",
    "text_dim": "#888888",
    "border": "#2ecc71",
}

_QSS = f"""
QWidget#YapWidget {{
    background-color: {_COLORS['bg_window']};
    border: 2px solid {_COLORS['border']};
    border-radius: 12px;
}}
QTextEdit#ChatArea {{
    background-color: {_COLORS['bg_window']};
    color: {_COLORS['text']};
    border: none;
    font-size: 13px;
}}
QLineEdit#InputField {{
    background-color: {_COLORS['bg_input']};
    color: {_COLORS['text']};
    border: 1px solid {_COLORS['border']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}}
QPushButton.quick-action {{
    background-color: {_COLORS['bg_header']};
    color: {_COLORS['accent']};
    border: 1px solid {_COLORS['border']};
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
}}
QPushButton.quick-action:hover {{
    background-color: {_COLORS['bg_input']};
}}
QPushButton#SendBtn {{
    background-color: {_COLORS['accent']};
    color: #000000;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: bold;
}}
QPushButton#SendBtn:hover {{
    background-color: #27ae60;
}}
QPushButton#CloseBtn {{
    background-color: transparent;
    color: {_COLORS['text_dim']};
    border: none;
    font-size: 16px;
}}
QPushButton#CloseBtn:hover {{
    color: {_COLORS['text']};
}}
"""


class YapWidget(QWidget):
    """Ventana flotante de chat rápido."""

    #: Emitida cuando el usuario envía una consulta (texto)
    query_submitted = Signal(str)

    def __init__(self, daemon=None, parent=None):
        super().__init__(parent)
        self._daemon = daemon
        self._super_mode = False  # False=local, True=Super Yap (nube)
        self._setup_window()
        self._setup_ui()
        self._setup_shortcuts()
        self.hide()

    # ─── Configuración de la ventana ─────────────────────────────────────────

    def _setup_window(self) -> None:
        """Configura la ventana como widget flotante sin bordes."""
        self.setObjectName("YapWidget")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(400)
        self.setMinimumHeight(500)
        self.setStyleSheet(_QSS)

    def _setup_ui(self) -> None:
        """Construye la interfaz."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(
            f"background-color: {_COLORS['bg_header']}; "
            f"border-radius: 10px 10px 0 0;"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 8, 8)

        title = QLabel("🤖 Yap")
        title.setStyleSheet(
            f"color: {_COLORS['accent']}; font-weight: bold; font-size: 14px;"
        )
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Toggle local/nube
        self._toggle_btn = QPushButton("Local")
        self._toggle_btn.setProperty("class", "quick-action")
        self._toggle_btn.setToolTip("Alternar entre modelo local y Super Yap (nube)")
        self._toggle_btn.clicked.connect(self._toggle_super)
        header_layout.addWidget(self._toggle_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.hide)
        header_layout.addWidget(close_btn)

        layout.addWidget(header)

        # ── Botones de acción rápida ──────────────────────────────────────
        actions_frame = QFrame()
        actions_frame.setStyleSheet(f"background-color: {_COLORS['bg_header']};")
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(10, 4, 10, 8)
        actions_layout.setSpacing(6)

        quick_actions = [
            ("📚 Cursos", "curso FPY1101"),
            ("✏️ Ejercicios", "ejercicios"),
            ("📋 Historial", "historial"),
            ("👤 Perfil", "perfil"),
        ]
        for label, cmd in quick_actions:
            btn = QPushButton(label)
            btn.setProperty("class", "quick-action")
            btn.clicked.connect(lambda checked, c=cmd: self._send_quick(c))
            actions_layout.addWidget(btn)

        layout.addWidget(actions_frame)

        # ── Área de chat ─────────────────────────────────────────────────
        self._chat_area = QTextEdit()
        self._chat_area.setObjectName("ChatArea")
        self._chat_area.setReadOnly(True)
        self._chat_area.setAcceptRichText(True)
        layout.addWidget(self._chat_area, stretch=1)

        # ── Indicador de estado ───────────────────────────────────────────
        self._status_label = QLabel("● Listo")
        self._status_label.setStyleSheet(
            f"color: {_COLORS['accent']}; font-size: 11px; "
            f"background-color: {_COLORS['bg_window']}; padding: 4px 12px;"
        )
        layout.addWidget(self._status_label)

        # ── Input ─────────────────────────────────────────────────────────
        input_frame = QFrame()
        input_frame.setStyleSheet(
            f"background-color: {_COLORS['bg_window']}; "
            f"border-radius: 0 0 10px 10px;"
        )
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(10, 8, 10, 10)
        input_layout.setSpacing(8)

        self._input = QLineEdit()
        self._input.setObjectName("InputField")
        self._input.setPlaceholderText("Escribe una pregunta o comando...")
        self._input.returnPressed.connect(self._on_send)
        input_layout.addWidget(self._input, stretch=1)

        send_btn = QPushButton("Enviar")
        send_btn.setObjectName("SendBtn")
        send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(send_btn)

        layout.addWidget(input_frame)

        # Mensaje de bienvenida
        self._append_message(
            "Yap",
            "¡Hola! Soy Yap, tu asistente IA local. " "¿En qué puedo ayudarte hoy?",
            is_user=False,
        )

    def _setup_shortcuts(self) -> None:
        """Define atajos de teclado de la ventana."""
        # Esc para cerrar
        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc.activated.connect(self.hide)

    # ─── Lógica de mensajes ───────────────────────────────────────────────────

    def _append_message(self, sender: str, text: str, is_user: bool = True) -> None:
        """Agrega un mensaje al área de chat con formato HTML."""
        color = _COLORS["bg_user_msg"] if is_user else _COLORS["bg_yap_msg"]
        align = "right" if is_user else "left"
        sender_color = _COLORS["accent"] if not is_user else _COLORS["text_dim"]

        html_text = _md_to_html(text)
        bubble = (
            f'<div style="text-align:{align};margin:6px 0;">'
            f'<span style="color:{sender_color};font-size:11px;font-weight:bold;">'
            f'{sender}</span><br>'
            f'<span style="background:{color};color:{_COLORS["text"]};'
            f'padding:6px 10px;border-radius:8px;display:inline-block;'
            f'max-width:85%;text-align:left;">{html_text}</span>'
            f'</div>'
        )
        self._chat_area.append(bubble)
        # Scroll al final
        sb = self._chat_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_send(self) -> None:
        """Maneja el envío de una consulta."""
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._append_message("Tú", text, is_user=True)
        self._set_busy(True)

        if self._daemon:
            self._daemon.query(text, self._on_response)
        else:
            # Sin daemon: respuesta de placeholder
            QTimer.singleShot(
                500,
                lambda: self._on_response(
                    "(Daemon no disponible. Verifica que Yap está instalado.)"
                ),
            )

    def _send_quick(self, cmd: str) -> None:
        """Envía un comando rápido al daemon."""
        self._input.setText(cmd)
        self._on_send()

    def _on_response(self, response: str) -> None:
        """Callback llamado con la respuesta del daemon (puede ser en otro hilo)."""
        # Usar QTimer para ejecutar en el hilo de Qt
        QTimer.singleShot(0, lambda: self._show_response(response))

    def _show_response(self, response: str) -> None:
        self._append_message("Yap", response, is_user=False)
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        """Actualiza el indicador de estado."""
        if busy:
            self._status_label.setText("◌ Procesando...")
            self._status_label.setStyleSheet(
                f"color: #f39c12; font-size: 11px; "
                f"background-color: {_COLORS['bg_window']}; padding: 4px 12px;"
            )
        else:
            self._status_label.setText("● Listo")
            self._status_label.setStyleSheet(
                f"color: {_COLORS['accent']}; font-size: 11px; "
                f"background-color: {_COLORS['bg_window']}; padding: 4px 12px;"
            )

    def _toggle_super(self) -> None:
        """Alterna entre modo local y Super Yap (nube)."""
        self._super_mode = not self._super_mode
        if self._super_mode:
            self._toggle_btn.setText("☁ Nube")
            self._toggle_btn.setStyleSheet("color: #3498db;")
        else:
            self._toggle_btn.setText("Local")
            self._toggle_btn.setStyleSheet("")

    # ─── Posicionamiento ──────────────────────────────────────────────────────

    def show_near_tray(self) -> None:
        """Muestra la ventana cerca del icono de bandeja (esquina inferior derecha)."""
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            x = geom.right() - self.width() - 20
            y = geom.bottom() - self.height() - 60
            self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()
