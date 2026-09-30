"""Aislamiento global para tests de Yap:

- Aísla el perfil i18n para que los tests no dependan de ~/.config/yap/profile.json.
- Aislamiento de Super Yap: los tests no hablan con Cloud Run.
  test_yap_super.py borra YAP_SUPER_* en setup_method para probar el auto
  Gradio. El resto de la suite fuerza el Yap local.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


@pytest.fixture(autouse=True)
def _isolate_i18n(tmp_path, monkeypatch):
    profile_dir = tmp_path / "yap"
    profile_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(yap, "PROFILE_FILE", str(profile_dir / "profile.json"))
    monkeypatch.delenv("YAP_LANG", raising=False)
    monkeypatch.delenv("YAP_I18N_DIR", raising=False)
    yap.reset_i18n()
    yield
    yap.reset_i18n()


@pytest.fixture(autouse=True)
def _sin_super_nube_en_tests(monkeypatch):
    if os.environ.get("YAP_SUPER_ENABLED", "").strip() == "":
        monkeypatch.setenv("YAP_SUPER_ENABLED", "0")
    if os.environ.get("YAP_SUPER_INTERNET", "").strip() == "":
        monkeypatch.setenv("YAP_SUPER_INTERNET", "0")

