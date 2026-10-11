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
"""

from __future__ import annotations

import os
import sys
import queue
import threading
import subprocess
import shutil
from pathlib import Path
from typing import Callable, Optional

# Ruta al script principal yap.py (busca relativo a este módulo y luego en PATH)
def _find_yap_script() -> Path:
    """Devuelve la ruta a yap.py."""
    # 0. Variable de entorno (máxima prioridad)
    env_path = os.environ.get("YAP_SCRIPT")
    if env_path and os.path.exists(env_path):
        return Path(env_path)
    # 1. Relativo al paquete (instalación normal)
    candidate = Path(__file__).parent.parent / "yap.py"
    if candidate.exists():
        return candidate
    # 2. /opt/yap/yap.py (instalación .deb/.rpm)
    candidate = Path("/opt/yap/yap.py")
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        "yap.py no encontrado. Instala Yap o define YAP_SCRIPT=/ruta/a/yap.py"
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
        except FileNotFoundError as e:
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

            if self._current_proc is None and stdout:
                return stdout.strip()
            if stderr:
                return f"[Error interno] {stderr.strip()[:200]}"
            return stdout.strip() or "(sin respuesta)"

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
