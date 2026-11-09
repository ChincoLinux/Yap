"""
tests/test_yap_ctypes.py — Pruebas unitarias para el motor C/C++ vía ctypes.
"""

import os
import sys
import threading
from unittest.mock import patch, MagicMock

import pytest

from yap.llm_ctypes import (
    LibLlamaEngine,
    es_ctypes_disponible,
    encontrar_biblioteca_llama,
    query_ctypes,
)


def test_singleton_engine():
    e1 = LibLlamaEngine.get_instance()
    e2 = LibLlamaEngine.get_instance()
    assert e1 is e2


def test_es_ctypes_disponible_con_flag_forzado():
    with patch.dict(os.environ, {"YAP_FORCE_CLI": "1"}):
        assert es_ctypes_disponible() is False


def test_liberar_memoria():
    engine = LibLlamaEngine.get_instance()
    engine._llm = MagicMock()
    engine._modelo_cargado_path = "modelo_dummy.gguf"
    engine.liberar_memoria()
    assert engine.esta_cargado() is False
    assert engine._modelo_cargado_path is None


def test_query_ctypes_con_archivo_inexistente():
    res = query_ctypes("hola", "archivo_no_existe_123.gguf")
    assert res is None


def test_query_ctypes_mock_inference():
    engine = LibLlamaEngine.get_instance()
    engine.liberar_memoria()

    mock_llm = MagicMock()
    mock_llm.return_value = [
        {"choices": [{"text": "Hola "}]},
        {"choices": [{"text": "Mundo"}]},
    ]
    tokens = []

    def on_token(t):
        tokens.append(t)

    with patch.object(engine, "asegurar_modelo", return_value=True):
        engine._llm = mock_llm
        engine._modelo_cargado_path = "mock.gguf"

        res, stats = engine.stream(
            prompt="test",
            max_tokens=50,
            on_token=on_token,
        )

        assert res == "Hola Mundo"
        assert tokens == ["Hola ", "Mundo"]
        assert stats["generados"] == 2
        assert stats["motor"] == "ctypes_libllama"
