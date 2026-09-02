"""
test_yap_i18n.py — Pruebas de soporte multi-idioma (#36)

Verifica:
  1. Catálogos JSON (es completo, en completo, arn parcial)
  2. t() con fallback a español
  3. yap perfil idioma cambia y persiste el idioma
  4. interpret() enruta perfil/profile
  5. El prompt del LLM sigue el idioma del perfil
  6. Wikipedia usa el host del idioma

Ejecucion: python3 -m pytest tests/test_yap_i18n.py -v
"""

import json
import os
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap

I18N_DIR = os.path.join(os.path.dirname(__file__), "..", "i18n")


def _load(lang):
    with open(os.path.join(I18N_DIR, f"{lang}.json"), encoding="utf-8") as f:
        return json.load(f)


class TestCatalogos:
    """Requisito: infraestructura i18n con JSON es/en/arn."""

    def test_archivos_existen(self):
        for lang in ("es", "en", "arn"):
            path = os.path.join(I18N_DIR, f"{lang}.json")
            assert os.path.isfile(path), f"falta {path}"

    def test_json_valido(self):
        for lang in ("es", "en", "arn"):
            data = _load(lang)
            assert isinstance(data, dict)
            assert data.get("lang", {}).get("code") == lang

    def test_idiomas_soportados(self):
        assert yap.SUPPORTED_LANGS == ("es", "en", "arn")
        assert yap.DEFAULT_LANG == "es"

    def test_en_cubre_todas_las_claves_de_es(self):
        es_keys = set(yap.i18n_keys("es"))
        en_keys = set(yap.i18n_keys("en"))
        faltan = sorted(es_keys - en_keys)
        assert not faltan, f"en.json no traduce: {faltan[:10]}"

    def test_arn_es_parcial(self):
        es_keys = set(yap.i18n_keys("es"))
        arn_keys = set(yap.i18n_keys("arn"))
        assert arn_keys, "arn.json no tiene claves de interfaz"
        assert len(arn_keys) < len(es_keys)

    def test_arn_cubre_nucleo_de_interfaz(self):
        for key in (
            "lang.native_name",
            "llm.system_prompt",
            "profile.set",
            "profile.current",
            "help.body",
            "ui.goodbye",
            "error.app_unavailable",
        ):
            assert key in yap.i18n_keys("arn"), f"arn.json debe traducir {key}"


class TestTranslate:
    """Requisito: t() traduce y cae a español si falta la clave."""

    def test_default_es_espanol(self):
        assert yap.get_lang() == "es"
        assert "no disponible" in yap.t("error.app_unavailable", app="X", available="Y")

    def test_en_traduce(self):
        yap.set_lang("en", persist=False)
        assert "is not available" in yap.t("error.app_unavailable", app="X", available="Y")
        assert yap.t("ui.goodbye") == "Bye"

    def test_arn_traduce_nucleo(self):
        yap.set_lang("arn", persist=False)
        assert yap.t("ui.goodbye") == "Pewmayu"
        assert "Mapudungun" in yap.t("lang.native_name")

    def test_arn_fallback_a_es(self):
        yap.set_lang("arn", persist=False)
        # telemetry.privacy no está en arn.json → español
        assert "dato" in yap.t("telemetry.privacy").lower() or "envia" in yap.t("telemetry.privacy").lower()

    def test_clave_inexistente_devuelve_la_clave(self):
        assert yap.t("no.existe.nunca") == "no.existe.nunca"

    def test_interpolacion(self):
        text = yap.t("error.app_unavailable", app="Firefox", available="LibreOffice")
        assert "Firefox" in text
        assert "LibreOffice" in text

    def test_yap_lang_env(self, monkeypatch):
        monkeypatch.setenv("YAP_LANG", "en")
        yap.reset_i18n()
        assert yap.get_lang() == "en"

    def test_idioma_invalido_en_env_cae_a_es(self, monkeypatch):
        monkeypatch.setenv("YAP_LANG", "xx")
        yap.reset_i18n()
        assert yap.get_lang() == "es"


class TestNormalizeLang:
    def test_aliases(self):
        assert yap.normalize_lang("español") == "es"
        assert yap.normalize_lang("English") == "en"
        assert yap.normalize_lang("mapudungun") == "arn"
        assert yap.normalize_lang("mapuche") == "arn"
        assert yap.normalize_lang("nope") is None


class TestPerfilIdioma:
    """Requisito: yap perfil idioma es|en|arn funcional y persistente."""

    def test_mostrar_default(self):
        out = yap.cmd_perfil()
        assert "es" in out.lower() or "Español" in out or "espanol" in out.lower()

    def test_cambiar_a_en_persiste(self):
        out = yap.cmd_perfil("idioma", "en")
        assert "English" in out
        assert yap.get_lang() == "en"
        data = yap._load_profile()
        assert data.get("idioma") == "en"

    def test_cambiar_a_arn(self):
        out = yap.cmd_perfil("idioma", "mapudungun")
        assert yap.get_lang() == "arn"
        assert "Mapudungun" in out

    def test_idioma_desconocido(self):
        out = yap.cmd_perfil("idioma", "klingon")
        assert "klingon" in out
        assert yap.get_lang() == "es"

    def test_escritura_atomica(self):
        yap.cmd_perfil("idioma", "en")
        assert os.path.exists(yap.PROFILE_FILE)
        assert not os.path.exists(yap.PROFILE_FILE + ".tmp")

    def test_perfil_corrupto_cae_a_es(self):
        os.makedirs(os.path.dirname(yap.PROFILE_FILE), exist_ok=True)
        with open(yap.PROFILE_FILE, "w", encoding="utf-8") as f:
            f.write("{ no json")
        yap.reset_i18n()
        assert yap.get_lang() == "es"

    def test_idioma_invalido_en_perfil_cae_a_es(self):
        yap._save_profile({"idioma": "xx"})
        yap.reset_i18n()
        assert yap.get_lang() == "es"

    def test_subcomando_ayuda(self):
        out = yap.cmd_perfil("volar")
        assert "perfil idioma" in out.lower() or "profile language" in out.lower()


class TestInterpretPerfil:
    def test_perfil_pelado(self):
        assert yap.interpret("perfil") == ("perfil", "")

    def test_perfil_idioma_en(self):
        assert yap.interpret("perfil idioma en") == ("perfil", "idioma en")

    def test_profile_language_arn(self):
        assert yap.interpret("profile language arn") == ("perfil", "language arn")

    def test_aliases_ingles(self):
        assert yap.interpret("help")[0] == "help"
        assert yap.interpret("progress") == ("progreso", "progreso")
        assert yap.interpret("history --last") == ("historial", "--ultimo")
        assert yap.interpret("session new") == ("sesion", "new")
        assert yap.interpret("guide") == ("guia", "guia")


class TestHandleActionPerfil:
    def test_despacha_cmd_perfil(self):
        with patch.object(yap, "cmd_perfil", return_value="ok") as mock_cmd:
            with patch.object(yap, "registrar_uso"):
                yap.handle_action("perfil", "idioma en", "perfil idioma en")
        mock_cmd.assert_called_once_with("idioma", "en")


class TestLlmSigueIdioma:
    """Requisito: el LLM responde en el idioma del perfil."""

    @patch("subprocess.run")
    def test_system_prompt_en_ingles(self, mock_run):
        mock_run.return_value = Mock(stdout="Hello", stderr="")
        yap.set_lang("en", persist=False)
        yap.cmd_query("hi", store_history=False)
        prompt = mock_run.call_args[0][0][mock_run.call_args[0][0].index("-p") + 1]
        assert "educational assistant in English" in prompt
        assert "en espanol" not in prompt

    @patch("subprocess.run")
    def test_system_prompt_en_mapudungun(self, mock_run):
        mock_run.return_value = Mock(stdout="Mari mari", stderr="")
        yap.set_lang("arn", persist=False)
        yap.cmd_query("mari mari", store_history=False)
        prompt = mock_run.call_args[0][0][mock_run.call_args[0][0].index("-p") + 1]
        assert "mapudungun" in prompt.lower()

    def test_system_prompt_funcion(self):
        yap.set_lang("en", persist=False)
        assert "English" in yap.system_prompt()
        yap.set_lang("es", persist=False)
        assert "espanol" in yap.system_prompt()


class TestWikipediaHost:
    def test_es_y_arn_usan_es(self):
        assert yap.wikipedia_host() == "es.wikipedia.org"
        yap.set_lang("arn", persist=False)
        assert yap.wikipedia_host() == "es.wikipedia.org"

    def test_en_usa_en(self):
        yap.set_lang("en", persist=False)
        assert yap.wikipedia_host() == "en.wikipedia.org"


class TestMensajesPorIdioma:
    def test_open_app_en_ingles(self, tmp_path):
        yap.set_lang("en", persist=False)
        apps = tmp_path / "apps.conf"
        apps.write_text("LibreOffice:libreoffice\n", encoding="utf-8")
        with patch.object(yap, "WHITELIST_APPS", str(apps)):
            result = yap.cmd_open_app("Chrome")
        assert "is not available" in result

    def test_open_app_default_sigue_en_espanol(self, tmp_path):
        apps = tmp_path / "apps.conf"
        apps.write_text("LibreOffice:libreoffice\n", encoding="utf-8")
        with patch.object(yap, "WHITELIST_APPS", str(apps)):
            result = yap.cmd_open_app("Chrome")
        assert "no disponible" in result.lower()

    def test_help_en_ingles(self):
        yap.set_lang("en", persist=False)
        body = yap.t("help.body")
        assert "Open app" in body or "profile language" in body
        assert "Preguntar:" not in body
