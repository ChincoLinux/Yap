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

from pathlib import Path


# La version vive en VERSION, que es la fuente de verdad del repo. La leen
# build-deb.sh y los workflows; un valor aqui se desincroniza en cada release.
def _leer_version() -> str:
    # Al instalar, yap_desktop/ y VERSION viven en el mismo site-packages.
    # En el repo, VERSION esta un nivel arriba.
    for base in (
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
    ):
        candidato = base / "VERSION"
        if candidato.is_file():
            return candidato.read_text(encoding="utf-8").strip()
    return "0.0.0"


__version__ = _leer_version()
__author__ = "ChincoLinux"
__url__ = "https://github.com/ChincoLinux/Yap"

from yap_desktop.app import main

__all__ = ["main"]
