#!/usr/bin/env python3
"""
yap_core.py — Motor central desacoplado y asíncrono para Yap (#152)

Provee una capa de abstracción headless que ejecuta consultas,
inferencia (llama-cli y Super Yap) y acciones de Yap de forma no bloqueante
mediante hilos (threading) y colas thread-safe (queue).
Permite a interfaces gráficas, widgets de escritorio (barra de tareas)
o frontends recibir streaming de tokens y eventos en tiempo real sin
congelar el hilo principal de la UI ni bloquear la consola.
"""

import sys
import os
import time
import threading
import queue
import subprocess
import shutil
import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Callable, Optional, Dict, Any, List, Tuple

import yap


# ── Constantes y Eventos ──────────────────────────────────────────

class EventType:
    START = "start"
    TOKEN = "token"
    DONE = "done"
    ERROR = "error"
    STATUS = "status"
    ACTION = "action"
    CANCELLED = "cancelled"


class Event:
    """Evento emitido durante el ciclo de vida de una consulta o acción."""
    def __init__(self, event_type: str, data: Any = None, task_id: str = ""):
        self.type = event_type
        self.data = data
        self.task_id = task_id
        self.timestamp = time.time()

    def __repr__(self) -> str:
        return f"<Event type={self.type!r} task_id={self.task_id!r} data={self.data!r}>"


# ── Representación de Tarea Asíncrona ─────────────────────────────

class YapTask:
    """Representa una tarea de Yap encolada, en ejecución o completada."""
    _id_counter = 0
    _id_lock = threading.Lock()

    def __init__(
        self,
        task_id: Optional[str] = None,
        prompt: str = "",
        action: str = "",
        param: str = "",
        on_token: Optional[Callable[[str], None]] = None,
        on_done: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ):
        if task_id is None:
            with YapTask._id_lock:
                YapTask._id_counter += 1
                task_id = f"task-{YapTask._id_counter}"
        self.task_id = task_id
        self.prompt = prompt
        self.action = action
        self.param = param
        self.status = "pending"  # pending, running, completed, failed, cancelled
        self.result: Optional[str] = None
        self.error: Optional[str] = None
        self.tokens: List[str] = []

        self.on_token = on_token
        self.on_done = on_done
        self.on_error = on_error
        self.on_status = on_status

        self._event = threading.Event()
        self._cancel_requested = threading.Event()
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def cancel(self):
        """Solicita la cancelación de la tarea y termina cualquier subproceso activo."""
        self._cancel_requested.set()
        with self._lock:
            if self._proc and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                except OSError:
                    pass

    def is_cancelled(self) -> bool:
        return self._cancel_requested.is_set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Bloquea hasta que la tarea termine o expire el timeout. Retorna True si terminó."""
        return self._event.wait(timeout=timeout)

    def get_result(self, timeout: Optional[float] = None) -> str:
        """Espera y retorna el resultado. Lanza TimeoutError o RuntimeError si falló."""
        if not self._event.wait(timeout=timeout):
            raise TimeoutError(f"Tarea {self.task_id} no completada dentro del timeout")
        if self.status == "failed":
            raise RuntimeError(self.error or "Error desconocido en la ejecución")
        if self.status == "cancelled":
            raise RuntimeError("Tarea cancelada")
        return self.result or ""

    def __repr__(self) -> str:
        return f"<YapTask id={self.task_id!r} status={self.status!r} action={self.action!r}>"


# ── Inferencia con Streaming de Tokens ─────────────────────────────

def stream_llama(
    cmd: List[str],
    timeout_s: int = 120,
    on_token: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    task: Optional[YapTask] = None,
) -> str:
    """Ejecuta llama-cli con streaming de tokens hacia el callback on_token.

    Usa subprocess.Popen sin shell (seguro contra inyecciones) y con stdin DEVNULL.
    Emite tokens o fragmentos conforme se producen y respeta estrictamente el timeout.
    """
    bin_name = cmd[0] if cmd else "llama-cli"
    if shutil.which(bin_name) is None:
        return "[ERROR] llama-cli no instalado. Ejecuta el setup de Yap."

    start_time = time.time()
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        return "[ERROR] llama-cli no instalado. Ejecuta el setup de Yap."

    if task is not None:
        with task._lock:
            task._proc = proc

    collected_chunks: List[str] = []
    tokens_yielded: List[str] = []

    # Bucle de lectura no bloqueante con timeout
    try:
        while True:
            # Verificar cancelación
            if cancel_event and cancel_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return "[WARN] Operación cancelada por el usuario."

            # Verificar timeout
            elapsed = time.time() - start_time
            if elapsed > timeout_s:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return f"[WARN] Tiempo de espera agotado ({timeout_s}s)"

            # Leer caracter o fragmento si hay disponible
            char = proc.stdout.read(1) if proc.stdout else ""
            if char:
                collected_chunks.append(char)
                # Filtrar tokens especiales de BOS/HEADER si aparecen
                if on_token:
                    on_token(char)
                tokens_yielded.append(char)
            else:
                # Comprobar si el proceso ya terminó
                if proc.poll() is not None:
                    # Leer restante si queda
                    if proc.stdout:
                        remaining = proc.stdout.read()
                        if remaining:
                            collected_chunks.append(remaining)
                            if on_token:
                                on_token(remaining)
                            tokens_yielded.append(remaining)
                    break
                time.sleep(0.01)

        proc.wait(timeout=5)
        raw_output = "".join(collected_chunks).strip()
        stderr_output = proc.stderr.read().strip() if proc.stderr else ""

        # Limpiar tokens del modelo
        for tok in [yap.BOS, yap.HEADER, yap.FOOTER, yap.EOT, "[end of text]"]:
            raw_output = raw_output.replace(tok, "")
        cleaned = raw_output.strip()
        return cleaned if cleaned else (stderr_output or "(sin respuesta)")

    except Exception as err:
        try:
            proc.kill()
        except OSError:
            pass
        return f"[ERROR] Error durante la inferencia: {err}"
    finally:
        if task is not None:
            with task._lock:
                task._proc = None


def query_stream(
    prompt: str,
    context: Optional[str] = None,
    store_history: bool = True,
    allow_super_fallback: bool = True,
    on_token: Optional[Callable[[str], None]] = None,
    on_done: Optional[Callable[[str], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
    on_status: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    task: Optional[YapTask] = None,
) -> str:
    """Consulta de inferencia que soporta streaming de tokens hacia callbacks.

    Si Super Yap está activo o local tarda demasiado, recurre a Super Yap.
    Si se usa local, llama a llama-cli con streaming interactivo.
    """
    if on_status:
        on_status("Preparando consulta...")

    # Comprobar si corresponde usar Super Yap
    if (
        allow_super_fallback
        and yap._super_disponible()
        and (
            yap._SUPER_MODO == "super"
            or yap._hay_internet()
            or yap._excede_tokens_local(prompt, context)
        )
    ):
        motivo = (
            "Hay internet; se usa Super Yap en la nube."
            if (yap._SUPER_MODO == "super" or yap._hay_internet())
            else "La consulta supera los tokens del modelo local."
        )
        if on_status:
            on_status(f"Consultando Super Yap ({motivo})...")

        super_out = yap._responder_super_por_fallback(
            prompt, context, store_history, motivo,
        )
        if super_out:
            if on_token:
                on_token(super_out)
            if on_done:
                on_done(super_out)
            return super_out

    # Armado del prompt local con contexto e historial
    parts = [yap.BOS]
    parts.append(f"{yap.HEADER}system{yap.FOOTER}\n\n{yap._system_prompt()}{yap.EOT}")

    for user_msg, assistant_msg in yap.HISTORY:
        parts.append(f"{yap.HEADER}user{yap.FOOTER}\n\n{user_msg}{yap.EOT}")
        parts.append(f"{yap.HEADER}assistant{yap.FOOTER}\n\n{assistant_msg}{yap.EOT}")

    rag_ctx = yap._rag_context_for_query(prompt)
    if rag_ctx:
        parts.append(f"{yap.HEADER}user{yap.FOOTER}\n\n{rag_ctx}{yap.EOT}")
    if context:
        parts.append(f"{yap.HEADER}user{yap.FOOTER}\n\nContexto:\n{context}{yap.EOT}")
    parts.append(f"{yap.HEADER}user{yap.FOOTER}\n\n{prompt}{yap.EOT}")
    parts.append(f"{yap.HEADER}assistant{yap.FOOTER}\n\n")

    full_prompt = "".join(parts)

    cmd = [
        "llama-cli",
        "-m", yap.MODEL_PATH,
        "-p", full_prompt,
        "-n", "384",
        "--temp", str(yap.LLAMA_TEMP_QUERY),
        "--ctx-size", str(yap.MAX_CTX),
        "--cache-type-k", "q8_0",
        "--cache-type-v", "q8_0",
        "--flash-attn",
        "--threads", str(yap.LLAMA_THREADS),
        "-no-cnv",
        "--no-display-prompt",
    ]

    timeout_s = yap._local_llama_timeout()
    if on_status:
        on_status(f"Iniciando inferencia local (timeout {timeout_s}s)...")

    result = stream_llama(
        cmd,
        timeout_s=timeout_s,
        on_token=on_token,
        cancel_event=cancel_event,
        task=task,
    )

    if "[WARN] Tiempo de espera agotado" in result and allow_super_fallback and yap._super_disponible():
        if on_status:
            on_status("Tiempo local agotado; consultando Super Yap...")
        super_out = yap._responder_super_por_fallback(
            prompt, context, store_history,
            "El modelo local tardó demasiado.",
        )
        if super_out:
            result = super_out
            if on_token:
                on_token(super_out)

    if store_history and result not in ("(sin respuesta)", "") and not result.startswith("[WARN]") and not result.startswith("[ERROR]"):
        yap.HISTORY.append((prompt, result))
        if len(yap.HISTORY) > yap.MAX_HISTORY:
            yap.HISTORY.pop(0)

    if on_done:
        on_done(result)
    return result


# ── Despacho Headless de Acciones ─────────────────────────────────

def execute_action_headless(
    action: str,
    param: str,
    original_input: str = "",
    on_token: Optional[Callable[[str], None]] = None,
    on_status: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    task: Optional[YapTask] = None,
) -> str:
    """Ejecuta una acción de Yap de forma headless, retornando el resultado en texto."""
    yap.registrar_uso(action)

    if action == "open_app":
        return yap.cmd_open_app(param)

    elif action == "search":
        query = param
        wikipedia_api = (
            "https://es.wikipedia.org/w/api.php?action=query"
            "&prop=extracts&exintro=&explaintext=&exchars=2000"
            "&titles=" + urllib.parse.quote(query) + "&format=json"
        )
        if on_status:
            on_status(f"Buscando '{query}' en Wikipedia...")
        content = yap.cmd_webfetch(wikipedia_api, feed_to_llm=True)
        if isinstance(content, tuple):
            text, _ = content
            if on_status:
                on_status("Resumiendo contenido con LLM...")
            res = query_stream(
                f"Resume el siguiente contenido sobre '{query}':",
                context=text,
                store_history=False,
                on_token=on_token,
                on_status=on_status,
                cancel_event=cancel_event,
                task=task,
            )
            source = "https://es.wikipedia.org/wiki/" + query.replace(" ", "_")
            full_res = f"{res}\n\nFuente: {source}"
            if not res.startswith("[WARN]") and not res.startswith("[ERROR]"):
                yap.HISTORY.append((query, res))
                if len(yap.HISTORY) > yap.MAX_HISTORY:
                    yap.HISTORY.pop(0)
            return full_res
        return str(content)

    elif action == "webfetch":
        content = yap.cmd_webfetch(param, feed_to_llm=True)
        if isinstance(content, tuple):
            text, _ = content
            if on_status:
                on_status("Resumiendo contenido web con LLM...")
            return query_stream(
                f"Resume el siguiente contenido sobre '{param}':",
                context=text,
                store_history=False,
                on_token=on_token,
                on_status=on_status,
                cancel_event=cancel_event,
                task=task,
            )
        return str(content)

    elif action == "pseint":
        if on_status:
            on_status("Consultando tutor PSeInt...")
        return yap.cmd_pseint(param)

    elif action == "introduccion_pseint":
        yap.cmd_intro_pseint()
        return "Tutorial interactivo de PSeInt iniciado."

    elif action == "curso":
        parts = [p.strip() for p in param.split(":", 1)]
        codigo = parts[0].upper()
        if len(parts) > 1 and parts[1].lower().startswith("ea"):
            return yap.iniciar_ea(codigo, parts[1])
        return yap.cmd_curso(codigo)

    elif action == "guia":
        return yap.cmd_guia()

    elif action == "progreso":
        return yap.cmd_mostrar_progreso()

    elif action == "perfil":
        return yap.cmd_perfil(param)

    elif action == "historial":
        resume = param == "--ultimo"
        return yap.cmd_historial(resume_last=resume)

    elif action == "sesion":
        partes = param.split(" ", 1)
        sub_cmd = partes[0] if partes else ""
        arg = partes[1] if len(partes) > 1 else ""
        return yap.cmd_sesion(sub_cmd, arg)

    elif action == "telemetria":
        return yap.cmd_telemetria(param)

    elif action == "super":
        return yap.cmd_super_status()

    elif action == "super_modo":
        return yap.cmd_super_modo(param)

    elif action == "super_query":
        if on_status:
            on_status("Consultando Super Yap...")
        return yap.cmd_query_super(param or original_input)

    elif action == "apparmor_status":
        return yap.cmd_apparmor_status()

    elif action == "menu_opcion":
        return param

    elif action == "rag":
        return yap.cmd_rag(param)

    elif action == "menu":
        return yap.cmd_menu()

    elif action == "help":
        return (
            "Comandos de Yap:\n"
            "  Preguntar:     Cualquier pregunta directa al AI\n"
            "  Abrir app:     'Abre [aplicación]' (Firefox, Terminal, etc.)\n"
            "  Wikipedia:     'Busca [tema]' (resumen desde Wikipedia)\n"
            "  Tutor PSeInt:  Preguntas sobre programación con PSeInt\n"
            "  Curso:         'curso FPY1101' — acceder al plan de estudio\n"
            "  Progreso:      'progreso' — ver avance formativo\n"
            "  Historial:     'historial' — ver sesiones anteriores\n"
            "  Super Yap:     'super' — estado de Gradio Cloud Run\n"
            "  RAG:           'rag' — búsqueda y estado del índice local\n"
            "  Perfil:        'perfil' — ver o actualizar perfil\n"
        )

    else:
        # Consulta libre al LLM
        return query_stream(
            original_input,
            on_token=on_token,
            on_status=on_status,
            cancel_event=cancel_event,
            task=task,
        )


# ── Motor Central Headless (YapCore) ──────────────────────────────

class YapCore:
    """Motor asíncrono y desacoplado de Yap para interfaces gráficas y headless."""

    def __init__(self, max_queue_size: int = 100):
        self._queue: "queue.Queue[Optional[YapTask]]" = queue.Queue(maxsize=max_queue_size)
        self._event_queue: "queue.Queue[Event]" = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._running = False
        self._busy = False
        self._lock = threading.Lock()
        self._current_task: Optional[YapTask] = None
        self._subscribers: List[Callable[[Event], None]] = []

    def start(self):
        """Inicia el hilo de ejecución en segundo plano (daemon)."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._worker = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="YapCoreWorker",
            )
            self._worker.start()

    def stop(self, timeout: float = 5.0):
        """Detiene de forma limpia el hilo de ejecución en segundo plano."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            if self._current_task:
                self._current_task.cancel()
            self._queue.put(None)
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=timeout)

    def is_running(self) -> bool:
        """Indica si el worker en segundo plano está activo."""
        return self._running

    def is_busy(self) -> bool:
        """Indica si hay una tarea en ejecución en este momento."""
        with self._lock:
            return self._busy

    def get_current_task(self) -> Optional[YapTask]:
        """Retorna la tarea actualmente en ejecución, si existe."""
        with self._lock:
            return self._current_task

    def cancel_current(self):
        """Cancela la tarea actualmente en ejecución."""
        with self._lock:
            if self._current_task:
                self._current_task.cancel()

    def subscribe(self, callback: Callable[[Event], None]):
        """Registra un suscriptor para recibir todos los eventos emitidos."""
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Event], None]):
        """Elimina un suscriptor previamente registrado."""
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def get_event(self, block: bool = True, timeout: Optional[float] = None) -> Optional[Event]:
        """Obtiene un evento de la cola para procesamiento en bucles GUI."""
        try:
            return self._event_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def _emit(self, event_type: str, data: Any = None, task_id: str = ""):
        event = Event(event_type, data, task_id)
        self._event_queue.put(event)
        with self._lock:
            subs = list(self._subscribers)
        for sub in subs:
            try:
                sub(event)
            except Exception:
                pass

    def _worker_loop(self):
        """Bucle principal del hilo de fondo que consume y procesa tareas."""
        while self._running:
            try:
                task = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if task is None:  # Señal de apagado
                break

            with self._lock:
                self._busy = True
                self._current_task = task
            task.status = "running"
            self._emit(EventType.START, task.prompt or task.action, task.task_id)

            def _token_cb(token: str):
                task.tokens.append(token)
                self._emit(EventType.TOKEN, token, task.task_id)
                if task.on_token:
                    try:
                        task.on_token(token)
                    except Exception:
                        pass

            def _status_cb(st: str):
                self._emit(EventType.STATUS, st, task.task_id)
                if task.on_status:
                    try:
                        task.on_status(st)
                    except Exception:
                        pass

            try:
                if task.is_cancelled():
                    task.status = "cancelled"
                    task.result = "[WARN] Tarea cancelada"
                    self._emit(EventType.CANCELLED, task.result, task.task_id)
                else:
                    # Determinar acción o inferencia
                    if task.action:
                        out = execute_action_headless(
                            task.action,
                            task.param,
                            task.prompt,
                            on_token=_token_cb,
                            on_status=_status_cb,
                            cancel_event=task._cancel_requested,
                            task=task,
                        )
                    else:
                        act, par = yap.interpret(task.prompt)
                        task.action = act
                        task.param = par
                        self._emit(EventType.ACTION, {"action": act, "param": par}, task.task_id)
                        out = execute_action_headless(
                            act,
                            par,
                            task.prompt,
                            on_token=_token_cb,
                            on_status=_status_cb,
                            cancel_event=task._cancel_requested,
                            task=task,
                        )

                    if task.is_cancelled():
                        task.status = "cancelled"
                        task.result = "[WARN] Tarea cancelada"
                        self._emit(EventType.CANCELLED, task.result, task.task_id)
                    else:
                        task.status = "completed"
                        task.result = out
                        self._emit(EventType.DONE, out, task.task_id)
                        if task.on_done:
                            try:
                                task.on_done(out)
                            except Exception:
                                pass

            except Exception as err:
                task.status = "failed"
                task.error = str(err)
                self._emit(EventType.ERROR, str(err), task.task_id)
                if task.on_error:
                    try:
                        task.on_error(str(err))
                    except Exception:
                        pass

            finally:
                task._event.set()
                with self._lock:
                    self._busy = False
                    self._current_task = None
                self._queue.task_done()

    def submit(self, task: YapTask) -> YapTask:
        """Encola una tarea en el motor y asegura que el worker esté activo."""
        self.start()
        self._queue.put(task)
        return task

    def query_async(
        self,
        prompt: str,
        context: Optional[str] = None,
        store_history: bool = True,
        allow_super_fallback: bool = True,
        on_token: Optional[Callable[[str], None]] = None,
        on_done: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> YapTask:
        """Encola una consulta de lenguaje natural para ejecución asíncrona no bloqueante."""
        task = YapTask(
            prompt=prompt,
            action="query",
            param=prompt,
            on_token=on_token,
            on_done=on_done,
            on_error=on_error,
            on_status=on_status,
        )
        return self.submit(task)

    def execute_async(
        self,
        user_input: str,
        on_token: Optional[Callable[[str], None]] = None,
        on_done: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> YapTask:
        """Encola un comando o consulta general (interpreta y despacha en segundo plano)."""
        task = YapTask(
            prompt=user_input,
            on_token=on_token,
            on_done=on_done,
            on_error=on_error,
            on_status=on_status,
        )
        return self.submit(task)

    def execute_headless(self, user_input: str) -> str:
        """Ejecuta de manera síncrona pero headless (sin terminal interactiva)."""
        act, par = yap.interpret(user_input)
        return execute_action_headless(act, par, user_input)


# ── Instancia Global del Motor ────────────────────────────────────

_GLOBAL_ENGINE: Optional[YapCore] = None
_GLOBAL_LOCK = threading.Lock()


def get_engine() -> YapCore:
    """Retorna la instancia global del motor YapCore (singleton)."""
    global _GLOBAL_ENGINE
    with _GLOBAL_LOCK:
        if _GLOBAL_ENGINE is None:
            _GLOBAL_ENGINE = YapCore()
        return _GLOBAL_ENGINE


def reset_engine():
    """Detiene y reinicia la instancia global de YapCore (útil para pruebas)."""
    global _GLOBAL_ENGINE
    with _GLOBAL_LOCK:
        if _GLOBAL_ENGINE is not None:
            _GLOBAL_ENGINE.stop()
            _GLOBAL_ENGINE = None


# ── Detección e Instalación Automática de Llama ───────────────────

REPO_DIR = os.path.abspath(os.path.dirname(__file__))
LOCAL_BIN_DIR = os.path.join(REPO_DIR, "bin")
LOCAL_MODELS_DIR = os.path.join(REPO_DIR, "models")
LLAMA_WIN_ZIP_URL = "https://github.com/ggerganov/llama.cpp/releases/download/b5097/llama-b5097-bin-win-avx2-x64.zip"
MODEL_3B_HF_URL = "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf?download=true"
MODEL_1B_HF_URL = "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf?download=true"


def sincronizar_rutas_locales():
    """Añade bin/ local al PATH si contiene llama-cli y asocia models/ si existe."""
    if os.path.isdir(LOCAL_BIN_DIR):
        bin_exe = "llama-cli.exe" if sys.platform == "win32" else "llama-cli"
        if os.path.isfile(os.path.join(LOCAL_BIN_DIR, bin_exe)):
            if LOCAL_BIN_DIR not in os.environ.get("PATH", "").split(os.pathsep):
                os.environ["PATH"] = LOCAL_BIN_DIR + os.pathsep + os.environ.get("PATH", "")

    if hasattr(yap, "MODEL_PATH"):
        modelo_actual = yap.MODEL_PATH
        if not (os.path.isfile(modelo_actual) and os.path.getsize(modelo_actual) > 100_000_000):
            cand_3b = os.path.join(LOCAL_MODELS_DIR, getattr(yap, "MODEL_3B_NAME", "Llama-3.2-3B-Instruct-Q4_K_M.gguf"))
            cand_1b = os.path.join(LOCAL_MODELS_DIR, getattr(yap, "MODEL_1B_NAME", "Llama-3.2-1B-Instruct-Q4_K_M.gguf"))
            if os.path.isfile(cand_3b) and os.path.getsize(cand_3b) > 100_000_000:
                yap.MODEL_PATH = cand_3b
            elif os.path.isfile(cand_1b) and os.path.getsize(cand_1b) > 100_000_000:
                yap.MODEL_PATH = cand_1b


def esta_llama_instalado() -> bool:
    """Revisa si llama-cli y el modelo GGUF están instalados y disponibles."""
    sincronizar_rutas_locales()
    tiene_binario = shutil.which("llama-cli") is not None
    modelo_path = getattr(yap, "MODEL_PATH", "")
    tiene_modelo = bool(modelo_path and os.path.isfile(modelo_path) and os.path.getsize(modelo_path) > 100_000_000)
    return tiene_binario and tiene_modelo


def instalar_llama_automaticamente(descargar_3b: bool = True, on_status: Optional[Callable[[str], None]] = None) -> bool:
    """Descarga e instala automáticamente llama-cli y el modelo si no están presentes."""
    def _status(msg: str):
        if on_status:
            on_status(msg)
        else:
            print(f"[YAP AUTO-INSTALL] {msg}")

    sincronizar_rutas_locales()

    # 1. Instalar binario llama-cli si no se encuentra
    if shutil.which("llama-cli") is None:
        if sys.platform == "win32":
            _status("Descargando llama-cli precompilado para Windows...")
            os.makedirs(LOCAL_BIN_DIR, exist_ok=True)
            tmp_zip = os.path.join(LOCAL_BIN_DIR, "llama-temp.zip")
            try:
                urllib.request.urlretrieve(LLAMA_WIN_ZIP_URL, tmp_zip)
                _status("Extrayendo binarios en bin/...")
                import zipfile
                with zipfile.ZipFile(tmp_zip, "r") as zf:
                    zf.extractall(LOCAL_BIN_DIR)
                if os.path.isfile(tmp_zip):
                    os.remove(tmp_zip)
                sincronizar_rutas_locales()
                _status("✓ llama-cli instalado correctamente.")
            except Exception as err:
                _status(f"[ERROR] No se pudo descargar llama-cli: {err}")
                return False
        else:
            _status("[AVISO] En Linux, compila con 'bash setup.sh'.")

    # 2. Instalar modelo GGUF si no existe
    sincronizar_rutas_locales()
    modelo_path = getattr(yap, "MODEL_PATH", "")
    if not (os.path.isfile(modelo_path) and os.path.getsize(modelo_path) > 100_000_000):
        os.makedirs(LOCAL_MODELS_DIR, exist_ok=True)
        nombre_modelo = getattr(yap, "MODEL_3B_NAME" if descargar_3b else "MODEL_1B_NAME", "Llama-3.2-3B-Instruct-Q4_K_M.gguf")
        url_modelo = MODEL_3B_HF_URL if descargar_3b else MODEL_1B_HF_URL
        destino = os.path.join(LOCAL_MODELS_DIR, nombre_modelo)
        part_dest = destino + ".part"

        _status(f"Descargando {nombre_modelo} desde Hugging Face...")
        try:
            req = urllib.request.Request(url_modelo, headers={"User-Agent": "Yap-AutoInstaller/1.0"})
            with urllib.request.urlopen(req) as resp, open(part_dest, "wb") as f_out:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                last_p = 0
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f_out.write(chunk)
                    downloaded += len(chunk)
                    if total > 0 and (time.time() - last_p > 2.0 or downloaded == total):
                        last_p = time.time()
                        pct = (downloaded / total) * 100
                        mb_d = downloaded / (1024 * 1024)
                        mb_t = total / (1024 * 1024)
                        _status(f"Descargando: {pct:.1f}% ({mb_d:.0f} MB / {mb_t:.0f} MB)")

            with open(part_dest, "rb") as vf:
                magic = vf.read(4)
            if magic != b"GGUF":
                if os.path.isfile(part_dest):
                    os.remove(part_dest)
                _status("[ERROR] Archivo inválido (no es formato GGUF).")
                return False

            if os.path.isfile(destino):
                os.remove(destino)
            os.rename(part_dest, destino)
            yap.MODEL_PATH = destino
            _status(f"✓ Modelo {nombre_modelo} descargado y verificado.")
        except Exception as err:
            if os.path.isfile(part_dest):
                try:
                    os.remove(part_dest)
                except Exception:
                    pass
            _status(f"[ERROR] Error descargando modelo: {err}")
            return False

    sincronizar_rutas_locales()
    return esta_llama_instalado()


def asegurar_llama_instalado(auto_instalar: bool = True) -> bool:
    """Verifica si llama está instalado; si no, lo instala automáticamente."""
    sincronizar_rutas_locales()
    if esta_llama_instalado():
        return True
    # En entorno de pruebas automatizadas (pytest) o con flag desactivada, no descargar gigabytes
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("YAP_NO_AUTO_INSTALL"):
        return False
    if auto_instalar:
        return instalar_llama_automaticamente()
    return False

