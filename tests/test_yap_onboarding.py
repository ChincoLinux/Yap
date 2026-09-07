import os
import json
import tempfile
import yap
from unittest.mock import patch, mock_open


def test_cargar_perfil_autogenerates_on_missing():
    """cargar_perfil() should auto-generate a default profile, never None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "profile.json")
        with patch.object(yap, "PROFILE_FILE", path):
            perfil = yap.cargar_perfil()
            assert perfil is not None
            assert isinstance(perfil, dict)
            assert "nombre" in perfil
            assert "nivel" in perfil
            assert "onboarding_completed" in perfil
            assert perfil["onboarding_completed"] is False
            # Should have persisted the file
            assert os.path.exists(path)


def test_cargar_perfil_loads_existing():
    mock_data = '{"nombre": "Estudiante", "onboarding_completed": true}'
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "profile.json")
        with open(path, "w") as f:
            f.write(mock_data)
        with patch.object(yap, "PROFILE_FILE", path):
            perfil = yap.cargar_perfil()
            assert perfil["nombre"] == "Estudiante"
            assert perfil["onboarding_completed"] is True


@patch("builtins.print")
@patch("sys.stdout.write")
@patch("builtins.input", side_effect=["", "", "", "Juan"])
def test_run_onboarding(mock_input, mock_write, mock_print):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "profile.json")
        with patch.object(yap, "PROFILE_FILE", path):
            perfil = yap.run_onboarding()
            assert perfil["nombre"] == "Juan"
            assert perfil["onboarding_completed"] is True
            # Should have all default keys from _perfil_por_defecto
            assert "nivel" in perfil
            assert "preferencias" in perfil
