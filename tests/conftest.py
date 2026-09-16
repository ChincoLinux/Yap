"""Aislamiento de Super Yap: los tests no hablan con Cloud Run.

test_yap_super.py borra YAP_SUPER_* en setup_method para probar el auto
Gradio. El resto de la suite fuerza el Yap local.
"""

import os

import pytest


@pytest.fixture(autouse=True)
def _sin_super_nube_en_tests(monkeypatch):
    if os.environ.get("YAP_SUPER_ENABLED", "").strip() == "":
        monkeypatch.setenv("YAP_SUPER_ENABLED", "0")
