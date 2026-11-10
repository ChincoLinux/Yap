"""
yap/native_bridge.py — Puente de alto rendimiento Rust & C++ para Yap (ChincoLinux).

Permite acelerar operaciones críticas para equipos de 2-3 GB de RAM y CPU-only:
1. Rust Core (yap_rust_core):
   - Detección instantánea de RAM física y disponible sin crear subprocesos.
   - Índice invertido y ranking BM25 con listas de posteo y tokenización rápida.
2. C++ Llama Bridge (yap_cpp_llama) & LibLlama:
   - Enlace directo a memoria compartida sin llamadas periódicas a subprocess.Popen.
   - Control granular de tamaño de lote (n_batch=128) y contexto (n_ctx=1024) para mínimo consumo de RAM.
   - Temporizador de descarga automática por reposo (auto-unload idle).

Diseñado con compatibilidad estricta: si los binarios nativos no están compilados,
hace fallback 100% transparente a la biblioteca estándar de Python y a llama-cli.
"""

import os
import sys
import ctypes
import ctypes.util
from typing import Optional, List, Tuple, Dict, Any, Callable

# Rutas estándar de búsqueda para bibliotecas nativas de Yap
DIRECTORIO_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANDIDATOS_RUST = [
    os.path.join(DIRECTORIO_RAIZ, "bin", "yap_rust_core.dll" if sys.platform == "win32" else "libyap_rust_core.so"),
    os.path.join(DIRECTORIO_RAIZ, "native", "yap_rust_core", "target", "release", "yap_rust_core.dll" if sys.platform == "win32" else "libyap_rust_core.so"),
    "/opt/yap/lib/libyap_rust_core.so",
    "/usr/local/lib/libyap_rust_core.so",
]

CANDIDATOS_CPP = [
    os.path.join(DIRECTORIO_RAIZ, "bin", "yap_cpp_llama.dll" if sys.platform == "win32" else "libyap_cpp_llama.so"),
    os.path.join(DIRECTORIO_RAIZ, "native", "yap_cpp_llama", "yap_cpp_llama.dll" if sys.platform == "win32" else "libyap_cpp_llama.so"),
    "/opt/yap/lib/libyap_cpp_llama.so",
    "/usr/local/lib/libyap_cpp_llama.so",
]


def _cargar_biblioteca(candidatos: List[str], nombre_lib: str) -> Optional[ctypes.CDLL]:
    for ruta in candidatos:
        if os.path.isfile(ruta):
            try:
                return ctypes.CDLL(ruta)
            except Exception:
                continue
    # Intento vía dynamic loader del sistema
    hallado = ctypes.util.find_library(nombre_lib)
    if hallado:
        try:
            return ctypes.CDLL(hallado)
        except Exception:
            pass
    return None


# Carga perezosa de módulos nativos
_RUST_LIB: Optional[ctypes.CDLL] = None
_RUST_INTENTADO = False

_CPP_LIB: Optional[ctypes.CDLL] = None
_CPP_INTENTADO = False


def obtener_rust_core() -> Optional[ctypes.CDLL]:
    """Retorna el CDLL de yap_rust_core si está disponible, o None."""
    global _RUST_LIB, _RUST_INTENTADO
    if not _RUST_INTENTADO:
        _RUST_INTENTADO = True
        if os.environ.get("YAP_DISABLE_NATIVE", "0") != "1":
            _RUST_LIB = _cargar_biblioteca(CANDIDATOS_RUST, "yap_rust_core")
            if _RUST_LIB:
                _configurar_firmas_rust(_RUST_LIB)
    return _RUST_LIB


def _configurar_firmas_rust(lib: ctypes.CDLL):
    try:
        lib.yap_rust_version.restype = ctypes.c_char_p
        lib.yap_detect_total_ram_mb.restype = ctypes.c_ulonglong
        lib.yap_detect_available_ram_mb.restype = ctypes.c_ulonglong
        lib.yap_is_low_memory_system.argtypes = [ctypes.c_ulonglong]
        lib.yap_is_low_memory_system.restype = ctypes.c_int

        lib.yap_bm25_init.argtypes = [ctypes.c_float, ctypes.c_float]
        lib.yap_bm25_init.restype = ctypes.c_void_p

        lib.yap_bm25_free.argtypes = [ctypes.c_void_p]
        lib.yap_bm25_free.restype = None

        lib.yap_bm25_add_document.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t]
        lib.yap_bm25_add_document.restype = ctypes.c_int

        lib.yap_bm25_search.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
        ]
        lib.yap_bm25_search.restype = ctypes.c_int
    except Exception:
        pass


def obtener_cpp_llama() -> Optional[ctypes.CDLL]:
    """Retorna el CDLL de yap_cpp_llama si está disponible, o None."""
    global _CPP_LIB, _CPP_INTENTADO
    if not _CPP_INTENTADO:
        _CPP_INTENTADO = True
        if os.environ.get("YAP_DISABLE_NATIVE", "0") != "1":
            _CPP_LIB = _cargar_biblioteca(CANDIDATOS_CPP, "yap_cpp_llama")
            if _CPP_LIB:
                _configurar_firmas_cpp(_CPP_LIB)
    return _CPP_LIB


def _configurar_firmas_cpp(lib: ctypes.CDLL):
    try:
        lib.yap_cpp_bridge_version.restype = ctypes.c_char_p
        lib.yap_llama_is_loaded.restype = ctypes.c_bool
        lib.yap_llama_unload_model.restype = None
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Detección acelerada de memoria con Rust (con fallback a Python puro)
# ---------------------------------------------------------------------------

def detectar_ram_nativa_mb() -> Optional[int]:
    """Consulta la RAM total en MB directamente vía Rust si está disponible."""
    rust = obtener_rust_core()
    if rust:
        try:
            total = rust.yap_detect_total_ram_mb()
            if total > 0:
                return int(total)
        except Exception:
            pass
    return None


def es_equipo_escasos_recursos_nativo(umbral_mb: int = 3500) -> Optional[bool]:
    """Consulta si es equipo de bajos recursos directamente vía Rust."""
    rust = obtener_rust_core()
    if rust:
        try:
            res = rust.yap_is_low_memory_system(ctypes.c_ulonglong(umbral_mb))
            return bool(res == 1)
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Motor BM25 Acelerado en Rust (con fallback a Python)
# ---------------------------------------------------------------------------

class BM25RustWrapper:
    """Envoltorio de alto rendimiento para el índice BM25 implementado en Rust."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self._rust = obtener_rust_core()
        self._ctx = None
        if self._rust:
            try:
                self._ctx = self._rust.yap_bm25_init(ctypes.c_float(k1), ctypes.c_float(b))
            except Exception:
                self._ctx = None

    def esta_disponible(self) -> bool:
        return self._rust is not None and self._ctx is not None

    def agregar_documento(self, doc_id: int, texto: str):
        if not self._ctx:
            return
        texto_bytes = texto.encode("utf-8", errors="ignore")
        self._rust.yap_bm25_add_document(
            self._ctx,
            ctypes.c_size_t(doc_id),
            texto_bytes,
            ctypes.c_size_t(len(texto_bytes)),
        )

    def buscar(self, query: str, top_k: int = 5) -> List[Tuple[int, float]]:
        if not self._ctx:
            return []
        query_bytes = query.encode("utf-8", errors="ignore")
        max_res = max(1, top_k)
        out_ids = (ctypes.c_size_t * max_res)()
        out_scores = (ctypes.c_float * max_res)()

        n = self._rust.yap_bm25_search(
            self._ctx,
            query_bytes,
            ctypes.c_size_t(len(query_bytes)),
            ctypes.c_size_t(top_k),
            out_ids,
            out_scores,
            ctypes.c_size_t(max_res),
        )

        resultados = []
        for i in range(max(0, n)):
            resultados.append((int(out_ids[i]), float(out_scores[i])))
        return resultados

    def liberar(self):
        if self._rust and self._ctx:
            try:
                self._rust.yap_bm25_free(self._ctx)
            except Exception:
                pass
            self._ctx = None

    def __del__(self):
        self.liberar()
