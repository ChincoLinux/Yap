"""Aísla el perfil i18n para que los tests no dependan de ~/.config/yap/profile.json."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


@pytest.fixture(autouse=True)
def _isolate_i18n(tmp_path, monkeypatch):
    monkeypatch.setattr(yap, "PROFILE_FILE", str(tmp_path / "profile.json"))
    monkeypatch.delenv("YAP_LANG", raising=False)
    monkeypatch.delenv("YAP_I18N_DIR", raising=False)
    yap.reset_i18n()
    yield
    yap.reset_i18n()
