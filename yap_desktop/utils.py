"""utils.py — Utilidades de yap_desktop que NO dependen de Qt.

Contiene funciones puras que pueden testearse sin instalar PyQt6/PySide6.
"""

from __future__ import annotations

import html
import re


def md_to_html(text: str) -> str:
    """Convierte Markdown básico a HTML para el área de chat.

    Soporta:
      - **negrita**
      - *cursiva*
      - `código inline`
      - ```bloque de código```
      - listas con guión (- item)
      - saltos de línea → <br>

    El texto de entrada se escapa antes de procesar marcas Markdown,
    previniendo inyección HTML.
    """
    # 1. Escape HTML
    text = html.escape(text)

    # 2. Bloques de código (```...```)
    text = re.sub(
        r'```(.*?)```',
        r'<pre style="background:#1e1e1e;color:#d4d4d4;padding:6px;'
        r'border-radius:4px;font-family:monospace;">\1</pre>',
        text, flags=re.DOTALL
    )

    # 3. Código inline (`...`)
    text = re.sub(
        r'`([^`]+)`',
        r'<code style="background:#2d2d2d;color:#ce9178;padding:1px 4px;'
        r'border-radius:2px;font-family:monospace;">\1</code>',
        text
    )

    # 4. Negrita (**...**)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # 5. Cursiva (*...*)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)

    # 6. Listas (- item)
    text = re.sub(r'^- (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', text, flags=re.DOTALL)

    # 7. Saltos de línea
    text = text.replace('\n', '<br>')

    return text
