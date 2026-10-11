"""yap_desktop — Módulo de interfaz gráfica de escritorio para Yap.

Implementa:
  - Icono residente en la bandeja del sistema (issue #153)
  - Ventana flotante de chat rápido (issues #155, #156)
  - Menú contextual de clic derecho (issue #154)
  - Botones de acción rápida (issue #157)
  - Motor en segundo plano desacoplado (issue #152)
  - Atajo global de teclado (issue #158)
  - Auto-arranque y packaging (issue #159)

Uso:
    python3 -m yap_desktop          # inicia la app
    python3 -m yap_desktop --help
"""

__version__ = "1.0.1"
__author__ = "ChincoLinux"
__url__ = "https://github.com/ChincoLinux/Yap"

from yap_desktop.app import main

__all__ = ["main"]
