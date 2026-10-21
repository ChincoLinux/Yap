"""daemon.py — Motor de Yap en segundo plano (issue #152).

Desacopla el backend de yap.py de la CLI, permitiendo que la GUI
envíe consultas y reciba respuestas de forma asíncrona sin bloquear
la interfaz.

Arquitectura:
    GUI thread
      └─► YapDaemon.query(text, callback)
            └─► _worker thread (DaemonWorker)
                  └─► subprocess: python3 yap.py --one-shot <text>
                        └─► llama-cli (proceso hijo de yap.py)

Fixes (issue #202 — GUI no llega a ningún paquete instalado):
  - _find_yap_script: amplía la búsqueda a todas las rutas de
    instalación del paquete .deb/.rpm y al módulo yap instalado
    vía pip (importlib.util.find_spec).
  - _run_query: corrige condición lógicamente muerta que descartaba
    stdout (self._current_proc se ponía a None antes de chequearlo).
"""

from __future__ import annotations

import logging
import os
import sys
import queue
import threading
import subprocess
import shutil
from pathlib import Path
from typing import Callable, Optional


logger = logging.getLogger(__name__)


# Ruta al script principal yap.py (busca relativo a este módulo y luego en PATH)
def _find_yap_script() -> Path:
    """Devuelve la ruta a yap.py.

    Orden de búsqueda (fix #202):
      0. Variable de entorno YAP_SCRIPT (máxima prioridad).
      1. Relativo al paquete yap_desktop (checkout / desarrollo).
      2. /opt/yap/yap.py  — instalación .deb/.rpm.
      3. /usr/share/yap/yap.py  — ruta alternativa de empaquetado.
      4. Módulo ``yap`` instalado vía pip: se usa su __main__.py
         como punto de entrada equivalente a ``python -m yap``.
      5. ``yap`` en el PATH del sistema (symlink del .deb).
    """
    import importlib.util

    # 0. Variable de entorno (máxima prioridad)
    env_path = os.environ.get("YAP_SCRIPT")
    if env_path and os.path.exists(env_path):
        return Path(env_path)

    # 1. Relativo al paquete yap_desktop (checkout / desarrollo)
    candidate = Path(__file__).parent.parent / "yap.py"
    if candidate.exists():
        return candidate

    # 2. /opt/yap/yap.py  — instalación .deb/.rpm
    candidate = Path("/opt/yap/yap.py")
    if candidate.exists():
        return candidate

    # 3. /usr/share/yap/yap.py  — ruta alternativa de empaquetado
    candidate = Path("/usr/share/yap/yap.py")
    if candidate.exists():
        return candidate

    # 4. Módulo yap instalado vía pip (importlib)
    spec = importlib.util.find_spec("yap")
    if spec and spec.origin:
        origin = Path(spec.origin)
        # Preferir yap.py en el directorio raíz del paquete si existe
        root_yap = origin.parent / "yap.py"
        if root_yap.exists():
            return root_yap
        # __main__.py del paquete como fallback
        main_py = origin.parent / "__main__.py"
        if main_py.exists():
            return main_py

    # 5. yap en el PATH del sistema (symlink /usr/local/bin/yap)
    yap_in_path = shutil.which("yap")
    if yap_in_path:
        resolved = Path(yap_in_path).resolve()
        if resolved.exists():
            return resolved

    raise FileNotFoundError(
        "yap.py no encontrado. Instala el paquete yap o define "
        "YAP_SCRIPT=/ruta/a/yap.py"
    )


YAP_SCRIPT = None  # se resuelve la primera vez que se necesita


class DaemonStatus:
    """Estado del daemon."""

    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    STOPPED = "stopped"


class _WorkerTask:
    """Tarea interna enviada al hilo worker."""

    __slots__ = ("text", "callback", "cancelled")

    def __init__(self, text: str, callback: Callable[[str], None]):
        self.text = text
        self.callback = callback
        self.cancelled = False


_STOP_SENTINEL = object()  # señal de parada para el worker


class YapDaemon:
    """Motor de Yap en segundo plano.

    Ejemplo de uso:
        daemon = YapDaemon()
        daemon.start()
        daemon.query("¿Qué es un algoritmo?", lambda resp: print(resp))
        daemon.stop()
    """

    def __init__(self, python_exe: Optional[str] = None, timeout: int = 120):
        """
        Args:
            python_exe: intérprete Python a usar (None = sys.executable).
            timeout:    segundos máximos por consulta al LLM.
        """
        self._python = python_exe or sys.executable
        self._timeout = timeout
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._status = DaemonStatus.IDLE
        self._status_lock = threading.Lock()
        self._current_proc: Optional[subprocess.Popen] = None

    # ─── API pública ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Inicia el hilo worker en segundo plano."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, name="YapDaemonWorker", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Para el worker y cancela cualquier consulta en curso."""
        self._queue.put(_STOP_SENTINEL)
        if self._current_proc:
            try:
                self._current_proc.terminate()
            except Exception:
                pass
        with self._status_lock:
            self._status = DaemonStatus.STOPPED

    def query(self, text: str, callback: Callable[[str], None]) -> None:
        """Encola una consulta al LLM.

        Args:
            text:     texto de la consulta del usuario.
            callback: función llamada con la respuesta (en el hilo worker).
        """
        task = _WorkerTask(text=text, callback=callback)
        self._queue.put(task)

    @property
    def status(self) -> str:
        with self._status_lock:
            return self._status

    # ─── Worker interno ──────────────────────────────────────────────────────

    def _run(self) -> None:
        """Bucle principal del hilo worker."""
        global YAP_SCRIPT
        try:
            if YAP_SCRIPT is None:
                YAP_SCRIPT = _find_yap_script()
        except FileNotFoundError:
            with self._status_lock:
                self._status = DaemonStatus.ERROR
            return

        while True:
            item = self._queue.get()
            if item is _STOP_SENTINEL:
                break

            task: _WorkerTask = item
            if task.cancelled:
                continue

            with self._status_lock:
                self._status = DaemonStatus.BUSY

            response = self._run_query(task.text)
            task.callback(response)

            with self._status_lock:
                self._status = DaemonStatus.IDLE

    def _run_query(self, text: str) -> str:
        """Ejecuta yap.py --one-shot <text> y devuelve la respuesta."""
        global YAP_SCRIPT
        cmd = [self._python, str(YAP_SCRIPT), "--one-shot", text]

        # Pasar llama-cli si se conoce su ubicación
        env = os.environ.copy()
        llama_cli = self._find_llama_cli()
        if llama_cli:
            env["YAP_LLAMA_CLI"] = llama_cli

        try:
            self._current_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                env=env,
                text=True,
            )
            stdout, stderr = self._current_proc.communicate(timeout=self._timeout)
            self._current_proc = None

            # fix #202: stdout se prioriza sobre stderr.
            # llama.cpp escribe métricas y avisos en stderr aunque la
            # respuesta sea válida; solo se trata como error si stdout
            # está vacío y stderr contiene algo relevante.
            if stdout.strip():
                if stderr.strip():
                    logger.debug("yap stderr (no fatal): %s", stderr.strip()[:200])
                return stdout.strip()
            if stderr.strip():
                return f"[Error interno] {stderr.strip()[:200]}"
            return "(sin respuesta)"

        except subprocess.TimeoutExpired:
            if self._current_proc:
                self._current_proc.kill()
                self._current_proc = None
            return "[Tiempo de espera agotado — el modelo tardó demasiado]"
        except Exception as e:
            self._current_proc = None
            return f"[Error al invocar Yap: {e}]"

    @staticmethod
    def _find_llama_cli() -> Optional[str]:
        """Busca llama-cli en ubicaciones conocidas."""
        candidates = [
            os.environ.get("YAP_LLAMA_CLI"),
            "/usr/local/bin/llama-cli",
            "/opt/yap/bin/llama-cli",
        ]
        for c in candidates:
            if c and shutil.which(c):
                return c
        found = shutil.which("llama-cli")
        return found
