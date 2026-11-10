"""
tests/test_yap_native.py — Pruebas unitarias para los puentes nativos Rust y C++ (ultra-lowmem2).
"""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

from yap.native_bridge import (
    obtener_rust_core,
    obtener_cpp_llama,
    detectar_ram_nativa_mb,
    es_equipo_escasos_recursos_nativo,
    BM25RustWrapper,
)
from yap import RagBM25Index, _detectar_ram_mb
from yap_core import detectar_ram_mb


def test_detectar_ram_nativa_sin_lib():
    with patch("yap.native_bridge.obtener_rust_core", return_value=None):
        assert detectar_ram_nativa_mb() is None
        assert es_equipo_escasos_recursos_nativo(3500) is None


def test_detectar_ram_nativa_con_mock_rust():
    mock_rust = MagicMock()
    mock_rust.yap_detect_total_ram_mb.return_value = 2048
    mock_rust.yap_is_low_memory_system.return_value = 1

    with patch("yap.native_bridge.obtener_rust_core", return_value=mock_rust):
        assert detectar_ram_nativa_mb() == 2048
        assert es_equipo_escasos_recursos_nativo(3500) is True


def test_yap_init_detectar_ram_usa_rust_si_disponible():
    with patch("yap.native_bridge.detectar_ram_nativa_mb", return_value=2048):
        assert _detectar_ram_mb() == 2048


def test_yap_core_detectar_ram_usa_rust_si_disponible():
    with patch("yap.native_bridge.detectar_ram_nativa_mb", return_value=3072):
        assert detectar_ram_mb() == 3072


def test_bm25_rust_wrapper_sin_lib():
    with patch("yap.native_bridge.obtener_rust_core", return_value=None):
        wrapper = BM25RustWrapper(k1=1.5, b=0.75)
        assert wrapper.esta_disponible() is False
        assert wrapper.buscar("python", top_k=3) == []


def test_bm25_rust_wrapper_con_mock_rust():
    mock_rust = MagicMock()
    mock_rust.yap_bm25_init.return_value = 0x12345678
    mock_rust.yap_bm25_add_document.return_value = 0

    def mock_search(ctx, q, q_len, top_k, out_ids, out_scores, max_res):
        out_ids[0] = 42
        out_scores[0] = 3.5
        return 1

    mock_rust.yap_bm25_search.side_effect = mock_search

    with patch("yap.native_bridge.obtener_rust_core", return_value=mock_rust):
        wrapper = BM25RustWrapper(k1=1.5, b=0.75)
        assert wrapper.esta_disponible() is True
        wrapper.agregar_documento(42, "variables y tipos de datos en python")
        res = wrapper.buscar("variables python", top_k=5)
        assert res == [(42, 3.5)]


def test_rag_bm25_index_integracion_rust():
    chunks = [
        {"id": 0, "text": "Algoritmos y diagramas de flujo en PSeInt"},
        {"id": 1, "text": "Estructuras condicionales si-entonces en Python"},
    ]

    mock_rust_wrapper = MagicMock()
    mock_rust_wrapper.esta_disponible.return_value = True
    mock_rust_wrapper.buscar.return_value = [(1, 4.2), (0, 1.1)]

    idx = RagBM25Index()
    with patch("yap.native_bridge.BM25RustWrapper", return_value=mock_rust_wrapper):
        idx.build(chunks)
        res = idx.query("estructuras condicionales", top_k=2)
        assert res == [(4.2, 1), (1.1, 0)]
        assert mock_rust_wrapper.agregar_documento.call_count == 2


def test_candidatos_cpp_llama_en_llm_ctypes():
    from yap.llm_ctypes import CANDIDATOS_LIBLLAMA
    rutas_str = " ".join(CANDIDATOS_LIBLLAMA)
    assert "yap_cpp_llama" in rutas_str
