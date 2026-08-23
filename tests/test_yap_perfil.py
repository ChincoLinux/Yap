"""
test_yap_perfil.py — Pruebas de la gestión de perfil de usuario (#24)

Verifica:
  1. Perfil JSON en ~/.config/yap/profile.json respetando $XDG_CONFIG_HOME
  2. Escritura atómica (escribir en .tmp y reemplazar el original)
  3. Autogeneración con valores por defecto si falta o está corrupto
  4. Validaciones: nivel ∈ {basico, intermedio, avanzado}, idioma ∈ {es, en}
  5. Subcomandos CLI: yap perfil [nombre|nivel|idioma <valor>]
  6. Inyección de nombre/nivel/curso_activo en el system prompt del LLM
     (las estadísticas NO se inyectan para no gastar KV cache/tokens)

Ejecucion: python3 -m pytest tests/test_yap_perfil.py -v
"""

import pytest
import sys
import os
import json
import tempfile
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


def perfil_tmp():
    """Devuelve una ruta temporal para profile.json (nunca toca el HOME real)."""
    return os.path.join(tempfile.mkdtemp(), "profile.json")


def escribir_perfil(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ============================================================
# 1. RUTA Y XDG_CONFIG_HOME
# ============================================================

class TestConfigDir:
    """Requisito: profile.json vive en ~/.config/yap respetando $XDG_CONFIG_HOME."""

    def test_xdg_config_home_respetado(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/cfg"}):
            assert yap._config_dir() == os.path.join("/custom/cfg", "yap")

    def test_xdg_vacio_usa_default(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": ""}):
            esperado = os.path.join(os.path.expanduser("~/.config"), "yap")
            assert yap._config_dir() == esperado

    def test_xdg_no_definido_usa_default(self):
        env = {k: v for k, v in os.environ.items() if k != "XDG_CONFIG_HOME"}
        with mock.patch.dict(os.environ, env, clear=True):
            esperado = os.path.join(os.path.expanduser("~/.config"), "yap")
            assert yap._config_dir() == esperado

    def test_xdg_ruta_relativa_se_ignora(self):
        """La spec XDG exige rutas absolutas; las relativas se ignoran."""
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "relativa/no-abs"}):
            esperado = os.path.join(os.path.expanduser("~/.config"), "yap")
            assert yap._config_dir() == esperado

    def test_profile_file_apunta_a_config_dir(self):
        assert os.path.basename(yap.PROFILE_FILE) == "profile.json"
        assert os.path.basename(os.path.dirname(yap.PROFILE_FILE)) == "yap"


# ============================================================
# 2. AUTORGENERACIÓN Y VALORES POR DEFECTO
# ============================================================

class TestAutogeneracion:
    """Requisito: si no existe o está corrupto, se autogenera uno válido."""

    CLAVES_SCHEMA = {
        "nombre", "fecha_primer_uso", "nivel", "cursos_inscritos",
        "curso_activo", "preferencias", "onboarding_completed", "estadisticas",
    }

    def test_archivo_inexistente_genera_defaults(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            for clave in self.CLAVES_SCHEMA:
                assert clave in perfil, f"falta la clave '{clave}'"

    def test_archivo_inexistente_se_persiste(self):
        """El default autogenerado queda escrito en disco (fecha_primer_uso fija)."""
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            assert os.path.exists(pf)
            with open(pf, encoding="utf-8") as f:
                guardado = json.load(f)
            assert guardado["fecha_primer_uso"] == perfil["fecha_primer_uso"]

    def test_json_corrupto_regenera_defaults(self):
        pf = perfil_tmp()
        os.makedirs(os.path.dirname(pf), exist_ok=True)
        with open(pf, "w", encoding="utf-8") as f:
            f.write("esto no es json {{{")
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            assert perfil["nivel"] == "basico"
            assert perfil["nombre"] == ""

    def test_json_no_dict_regenera_defaults(self):
        pf = perfil_tmp()
        escribir_perfil(pf, ["no", "soy", "un", "dict"])
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            assert perfil["nivel"] == "basico"

    def test_defaults_son_validos(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            assert perfil["nivel"] in yap.NIVELES_VALIDOS
            assert perfil["preferencias"]["idioma"] in yap.IDIOMAS_VALIDOS
            assert isinstance(perfil["estadisticas"], dict)
            assert isinstance(perfil["cursos_inscritos"], list)

    def test_fecha_primer_uso_formato_iso(self):
        import re
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", perfil["fecha_primer_uso"])


class TestNormalizacion:
    """Requisito: un perfil cargado siempre cumple el esquema y los dominios."""

    def test_claves_faltantes_se_rellenan(self):
        pf = perfil_tmp()
        escribir_perfil(pf, {"nombre": "María"})
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            assert perfil["nombre"] == "María"
            assert perfil["nivel"] == "basico"  # rellenado
            assert "idioma" in perfil["preferencias"]
            assert "sesiones_totales" in perfil["estadisticas"]

    def test_nivel_invalido_vuelve_a_basico(self):
        pf = perfil_tmp()
        escribir_perfil(pf, {"nivel": "genial"})
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            assert yap.cargar_perfil()["nivel"] == "basico"

    def test_idioma_invalido_vuelve_a_es(self):
        pf = perfil_tmp()
        escribir_perfil(pf, {"preferencias": {"idioma": "fr"}})
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            assert perfil["preferencias"]["idioma"] == "es"

    def test_preferencias_corruptas_no_rompen_carga(self):
        pf = perfil_tmp()
        escribir_perfil(pf, {"nombre": "Ana", "preferencias": "corrupto"})
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            assert perfil["nombre"] == "Ana"
            assert isinstance(perfil["preferencias"], dict)

    def test_datos_existentes_se_preservan(self):
        pf = perfil_tmp()
        data = {
            "nombre": "María", "nivel": "avanzado",
            "cursos_inscritos": ["FPY1101"], "curso_activo": "FPY1101",
            "onboarding_completed": True,
            "preferencias": {"tema": "oscuro"},
            "estadisticas": {"sesiones_totales": 7},
        }
        escribir_perfil(pf, data)
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            assert perfil["curso_activo"] == "FPY1101"
            assert perfil["preferencias"]["tema"] == "oscuro"
            # merge parcial: el resto de preferencias sigue existiendo
            assert perfil["preferencias"]["idioma"] == "es"
            assert perfil["estadisticas"]["preguntas_totales"] == 0


# ============================================================
# 3. ESCRITURA ATÓMICA
# ============================================================

class TestEscrituraAtomica:
    """Requisito: escribir en .profile.json.tmp y reemplazar el original."""

    def test_no_queda_tmp_tras_guardar(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.guardar_perfil(yap._perfil_por_defecto())
            assert not os.path.exists(pf + ".tmp")
            assert os.path.exists(pf)

    def test_guardar_crea_directorio_si_no_existe(self):
        pf = os.path.join(tempfile.mkdtemp(), "sub", "dir", "profile.json")
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.guardar_perfil(yap._perfil_por_defecto())
            assert os.path.exists(pf)

    def test_contenido_guardado_es_json_valido_utf8(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.guardar_perfil({"nombre": "María"})
            with open(pf, encoding="utf-8") as f:
                assert json.load(f)["nombre"] == "María"

    def test_fallo_escritura_preserva_original(self):
        """Si el proceso muere a mitad de escritura (Ctrl+C), el original queda intacto."""
        pf = perfil_tmp()
        original = yap._perfil_por_defecto()
        original["nombre"] = "Original"
        escribir_perfil(pf, original)
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            with mock.patch("json.dump", side_effect=KeyboardInterrupt):
                with pytest.raises(KeyboardInterrupt):
                    yap.guardar_perfil(yap._perfil_por_defecto())
            # El archivo original NO fue tocado
            with open(pf, encoding="utf-8") as f:
                assert json.load(f)["nombre"] == "Original"


# ============================================================
# 4. VALIDACIONES Y ACTUALIZADORES
# ============================================================

class TestValidaciones:
    """Requisito: nivel solo acepta basico/intermedio/avanzado; idioma solo es/en."""

    @pytest.mark.parametrize("nivel", ["basico", "intermedio", "avanzado"])
    def test_niveles_validos_persisten(self, nivel):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_nivel(nivel)
            assert yap.cargar_perfil()["nivel"] == nivel

    @pytest.mark.parametrize("nivel", ["experto", "novato", "", "123"])
    def test_niveles_invalidos_rechazados(self, nivel):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            with pytest.raises(ValueError):
                yap.actualizar_nivel(nivel)

    def test_nivel_mayusculas_se_normaliza(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_nivel("AVANZADO")
            assert yap.cargar_perfil()["nivel"] == "avanzado"

    @pytest.mark.parametrize("idioma", ["es", "en"])
    def test_idiomas_validos_persisten_en_preferencias(self, idioma):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_idioma(idioma)
            assert yap.cargar_perfil()["preferencias"]["idioma"] == idioma

    @pytest.mark.parametrize("idioma", ["fr", "de", "ENGLISH", "", "e"])
    def test_idiomas_invalidos_rechazados(self, idioma):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            with pytest.raises(ValueError):
                yap.actualizar_idioma(idioma)

    def test_nombre_valido_actualiza(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_nombre("María González")
            assert yap.cargar_perfil()["nombre"] == "María González"

    def test_nombre_con_espacios_se_recorta(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_nombre("  Ana  ")
            assert yap.cargar_perfil()["nombre"] == "Ana"

    @pytest.mark.parametrize("nombre", ["", "   "])
    def test_nombre_vacio_rechazado(self, nombre):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            with pytest.raises(ValueError):
                yap.actualizar_nombre(nombre)

    def test_update_no_destruye_otras_claves(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_nombre("María")
            yap.actualizar_nivel("intermedio")
            perfil = yap.cargar_perfil()
            assert perfil["nombre"] == "María"
            assert perfil["nivel"] == "intermedio"
            assert perfil["preferencias"]["idioma"] == "es"


# ============================================================
# 5. COMANDOS CLI
# ============================================================

class TestCmdPerfil:
    """Requisito: yap perfil [subcomando] muestra y actualiza el perfil."""

    def test_sin_args_muestra_perfil_formateado(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("")
            assert "Mi Perfil" in out
            assert "Nivel" in out
            assert "(sin definir)" in out

    def test_ver_muestra_perfil(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            assert "Mi Perfil" in yap.cmd_perfil("ver")

    def test_subcomando_nombre(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("nombre María")
            assert out.startswith("[OK]")
            assert yap.cargar_perfil()["nombre"] == "María"

    def test_subcomando_nivel(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("nivel intermedio")
            assert out.startswith("[OK]")
            assert yap.cargar_perfil()["nivel"] == "intermedio"

    def test_subcomando_idioma(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("idioma en")
            assert out.startswith("[OK]")
            assert yap.cargar_perfil()["preferencias"]["idioma"] == "en"

    def test_nivel_invalido_devuelve_error_no_excepcion(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("nivel experto")
            assert out.startswith("[ERROR]")
            assert yap.cargar_perfil()["nivel"] == "basico"

    def test_idioma_invalido_devuelve_error(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("idioma fr")
            assert out.startswith("[ERROR]")

    def test_campo_desconocido_devuelve_error(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("edad 20")
            assert out.startswith("[ERROR]")
            assert "nombre" in out  # sugiere campos disponibles

    def test_valor_faltante_devuelve_error(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("nombre")
            assert out.startswith("[ERROR]")

    def test_nombre_multopalabra(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("nombre María José González")
            assert out.startswith("[OK]")
            assert yap.cargar_perfil()["nombre"] == "María José González"

    def test_muestra_estadisticas_en_pantalla(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("")
            assert "Estadísticas" in out or "Sesiones" in out


class TestRoutingPerfil:
    """Requisito: interpret() enruta 'perfil ...' y handle_action lo despacha."""

    def test_interpret_perfil_simple(self):
        action, param = yap.interpret("perfil")
        assert action == "perfil"
        assert param == ""

    def test_interpret_mi_perfil(self):
        action, param = yap.interpret("mi perfil")
        assert action == "perfil"

    def test_interpret_perfil_con_subcomando(self):
        action, param = yap.interpret("perfil nombre María")
        assert action == "perfil"
        assert param == "nombre María"

    def test_interpret_conserva_mayusculas_del_valor(self):
        _, param = yap.interpret("PERFIL NOMBRE MARÍA")
        assert param == "NOMBRE MARÍA"

    def test_handle_action_despacha_perfil(self, capsys):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.handle_action("perfil", "", "perfil")
        captured = capsys.readouterr()
        assert "Mi Perfil" in captured.out

    def test_handle_action_actualiza_nombre(self, capsys):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.handle_action("perfil", "nombre María", "perfil nombre María")
            captured = capsys.readouterr()
            assert "[OK]" in captured.out
            assert yap.cargar_perfil()["nombre"] == "María"


# ============================================================
# 6. INYECCIÓN EN EL SYSTEM PROMPT DEL LLM
# ============================================================

class TestSystemPromptInjection:
    """Requisito: inyectar nombre, nivel y curso_activo; NUNCA estadísticas."""

    def _perfil_lleno(self):
        perfil = yap._perfil_por_defecto()
        perfil.update({
            "nombre": "María", "nivel": "avanzado", "curso_activo": "FPY1101",
        })
        perfil["estadisticas"]["sesiones_totales"] = 42
        return perfil

    def test_inyecta_nombre_nivel_curso(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf), \
             mock.patch.object(yap, "SYSTEM_PROMPT", "BASE."):
            yap.guardar_perfil(self._perfil_lleno())
            sp = yap._system_prompt()
            assert "BASE." in sp
            assert "María" in sp
            assert "avanzado" in sp
            assert "FPY1101" in sp

    def test_no_inyecta_estadisticas(self):
        """Las estadísticas se excluyen para no desperdiciar KV cache/tokens."""
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf), \
             mock.patch.object(yap, "SYSTEM_PROMPT", "BASE."):
            yap.guardar_perfil(self._perfil_lleno())
            sp = yap._system_prompt()
            assert "sesiones_totales" not in sp
            assert "estadisticas" not in sp.lower()

    def test_perfil_sin_datos_inyecta_solo_nivel(self):
        """Sin nombre ni curso activo solo se inyecta el nivel (siempre existe)."""
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf), \
             mock.patch.object(yap, "SYSTEM_PROMPT", "BASE."):
            yap.guardar_perfil(yap._perfil_por_defecto())  # nombre vacío
            sp = yap._system_prompt()
            assert sp == "BASE. Contexto: su nivel es basico."
            assert "(sin definir)" not in sp

    def test_cmd_query_construye_prompt_con_perfil(self):
        """cmd_query usa el prompt dinámico al llamar a llama-cli."""
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf), \
             mock.patch.object(yap, "SYSTEM_PROMPT", "BASE."), \
             mock.patch("subprocess.run") as mock_run:
            yap.guardar_perfil(self._perfil_lleno())
            mock_run.return_value = mock.Mock(
                stdout="respuesta", stderr="", returncode=0)
            yap.cmd_query("¿Qué es una variable?", store_history=False)
        cmd = mock_run.call_args[0][0]
        full_prompt = cmd[cmd.index("-p") + 1]
        assert "María" in full_prompt
        assert "FPY1101" in full_prompt
        assert "sesiones_totales" not in full_prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
