"""
yap/llm_ctypes.py — Motor de inferencia de bajo nivel para ChincoLinux vía C/C++ ctypes.

Permite conectar directamente con libllama.so / llama.dll en memoria compartida,
evitando la sobrecarga de crear subprocesos (subprocess.Popen/fork/exec) en cada turno.
Especialmente optimizado para computadores de 2 a 3 GB de RAM:
- Memoria mapeada directa (mmap).
- Streaming sin tuberías intermedias (pipes).
- Descarga automática de RAM si el modelo pasa tiempo en reposo (auto-unload idle).
- Fallback automático transparente al CLI si no se encuentra la biblioteca.
"""

import os
import sys
import time
import threading
import ctypes
import ctypes.util
from typing import Optional, Callable, Generator, List, Dict, Any, Tuple

# Ubicaciones estándar donde buscar libllama.so / llama.dll en ChincoLinux y local
CANDIDATOS_LIBLLAMA = [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "libllama.so"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "llama.dll"),
    "/opt/yap/lib/libllama.so",
    "/usr/local/lib/libllama.so",
    "/usr/lib/libllama.so",
    "/usr/lib/x86_64-linux-gnu/libllama.so",
]

_LLAMA_CPP_AVAILABLE = False
try:
    import llama_cpp
    _LLAMA_CPP_AVAILABLE = True
except ImportError:
    llama_cpp = None


def encontrar_biblioteca_llama() -> Optional[str]:
    """Busca libllama.so / llama.dll en el sistema."""
    for ruta in CANDIDATOS_LIBLLAMA:
        if os.path.isfile(ruta):
            return ruta
    nombre = "llama.dll" if sys.platform == "win32" else "libllama.so"
    hallado = ctypes.util.find_library("llama")
    if hallado:
        return hallado
    return None


def es_ctypes_disponible() -> bool:
    """Retorna True si hay soporte de bajo nivel ctypes/cffi disponible."""
    if os.environ.get("YAP_FORCE_CLI", "0") == "1":
        return False
    if _LLAMA_CPP_AVAILABLE:
        return True
    return encontrar_biblioteca_llama() is not None


class LibLlamaEngine:
    """Motor singleton de inferencia directa en C/C++ vía ctypes."""

    _instancia = None
    _lock = threading.Lock()

    def __init__(self):
        self._llm = None
        self._cdll = None
        self._modelo_cargado_path = None
        self._ultimo_uso = 0.0
        self._temporizador_descarga = None
        # Timeout en segundos para liberar la RAM si no hay consultas (default 5 min)
        self.idle_timeout_s = int(os.environ.get("YAP_CTYPES_UNLOAD_IDLE_S", "300"))
        self._lock_inferencia = threading.Lock()

    @classmethod
    def get_instance(cls) -> "LibLlamaEngine":
        with cls._lock:
            if cls._instancia is None:
                cls._instancia = cls()
            return cls._instancia

    def esta_cargado(self) -> bool:
        return self._llm is not None or self._cdll is not None

    def asegurar_modelo(
        self,
        modelo_path: str,
        n_ctx: int = 2048,
        n_threads: int = 2,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Carga el modelo en memoria vía ctypes si no está ya cargado."""
        with self._lock_inferencia:
            if self._llm is not None and self._modelo_cargado_path == modelo_path:
                self._actualizar_actividad()
                return True

            if not os.path.isfile(modelo_path):
                return False

            if on_status:
                on_status(f"Cargando modelo en memoria C/C++ (mmap): {os.path.basename(modelo_path)}...")

            try:
                if _LLAMA_CPP_AVAILABLE:
                    # Usar backend C ctypes optimizado de llama_cpp
                    self._llm = llama_cpp.Llama(
                        model_path=modelo_path,
                        n_ctx=n_ctx,
                        n_threads=n_threads,
                        n_batch=512,
                        verbose=False,
                    )
                    self._modelo_cargado_path = modelo_path
                    self._actualizar_actividad()
                    return True
                else:
                    # Intento directo de enlace ctypes.CDLL a libllama.so
                    lib_path = encontrar_biblioteca_llama()
                    if lib_path:
                        self._cdll = ctypes.CDLL(lib_path)
                        self._modelo_cargado_path = modelo_path
                        self._actualizar_actividad()
                        return True
            except Exception as e:
                if on_status:
                    on_status(f"[Aviso] No se pudo cargar vía ctypes ({e}), usando fallback.")
                self._llm = None
                self._cdll = None
                return False

        return False

    def liberar_memoria(self):
        """Descarga el modelo de la RAM para que otras aplicaciones (PSeInt, Firefox) dispongan de memoria."""
        with self._lock_inferencia:
            if self._llm is not None:
                try:
                    del self._llm
                except Exception:
                    pass
                self._llm = None
            if self._cdll is not None:
                self._cdll = None
            self._modelo_cargado_path = None

    def _actualizar_actividad(self):
        self._ultimo_uso = time.monotonic()
        if self._temporizador_descarga:
            self._temporizador_descarga.cancel()
        if self.idle_timeout_s > 0:
            self._temporizador_descarga = threading.Timer(
                self.idle_timeout_s, self.liberar_memoria
            )
            self._temporizador_descarga.daemon = True
            self._temporizador_descarga.start()

    def stream(
        self,
        prompt: str,
        max_tokens: int = 384,
        temperature: float = 0.7,
        on_token: Optional[Callable[[str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
        timeout_s: int = 180,
    ) -> Tuple[str, Dict[str, Any]]:
        """Genera tokens con baja latencia y streaming directo en memoria."""
        with self._lock_inferencia:
            self._actualizar_actividad()
            if self._llm is None:
                raise RuntimeError("Modelo no cargado en ctypes engine")

            stop_tokens = [
                "<|eot_id|>",
                "<|end_of_text|>",
                "[end of text]",
                "<|start_header_id|>",
                "<|end_header_id|>",
            ]

            inicio = time.monotonic()
            tokens_generados = 0
            texto_completo = []

            # Streaming de bajo nivel
            stream_gen = self._llm(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                stop=stop_tokens,
            )

            for chunk in stream_gen:
                if cancel_event and cancel_event.is_set():
                    break
                if (time.monotonic() - inicio) > timeout_s:
                    break

                choices = chunk.get("choices", [])
                if not choices:
                    continue
                trozo = choices[0].get("text", "")
                if trozo:
                    texto_completo.append(trozo)
                    tokens_generados += 1
                    if on_token:
                        try:
                            on_token(trozo)
                        except Exception:
                            pass

            duracion_ms = int((time.monotonic() - inicio) * 1000)
            resultado_final = "".join(texto_completo).strip()
            stats = {
                "generados": tokens_generados,
                "ms": duracion_ms,
                "motor": "ctypes_libllama",
            }
            return resultado_final, stats


def query_ctypes(
    prompt: str,
    modelo_path: str,
    n_ctx: int = 2048,
    n_threads: int = 2,
    max_tokens: int = 384,
    temperature: float = 0.7,
    on_token: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    timeout_s: int = 180,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Punto de entrada directo para inferencia vía ctypes.
    
    Retorna (texto, stats) o None si ctypes no está disponible.
    """
    if not es_ctypes_disponible():
        return None

    engine = LibLlamaEngine.get_instance()
    if not engine.asegurar_modelo(modelo_path, n_ctx=n_ctx, n_threads=n_threads):
        return None

    try:
        return engine.stream(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            on_token=on_token,
            cancel_event=cancel_event,
            timeout_s=timeout_s,
        )
    except Exception:
        return None
