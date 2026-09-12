"""
test_yap_accesibilidad.py — Pruebas de la funcionalidad de Accesibilidad (#37)

Fase 4 (P2): alto contraste, fuentes grandes (2x), lector de pantalla y
navegación por teclado bajo `yap perfil accesibilidad [OPCION]`.

Verifica:
  1. Defaults y normalización de preferencias.accesibilidad en el perfil
  2. Activación/guardado de cada opción (on/off, aliases, opciones inválidas)
  3. Sanitización de códigos ANSI cuando el lector de pantalla u Orca está activo
  4. Detección de Orca con mock de shutil.which y de procesos (sin shell=True)
  5. Paleta de alto contraste (blanco puro sobre fondo negro)
  6. Escala 2x de fuentes (ancho y alto), ANSI-safe
  7. Estructura CLI: yap perfil accesibilidad [opción] [on|off]
  8. Navegación por teclado en menús (Tab/Flechas/Enter/Esc) con reader inyectado
  9. Ruteo en interpret()/handle_action() y aplicaciones al arranque

Ejecucion: python3 -m pytest tests/test_yap_accesibilidad.py -v
"""

import io
import json
import os
import tempfile
import unittest.mock as mock

import pytest

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


def perfil_tmp():
    """Devuelve una ruta temporal para profile.json (nunca toca el HOME real)."""
    return os.path.join(tempfile.mkdtemp(), "profile.json")


def escribir_perfil(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


@pytest.fixture(autouse=True)
def _entorno_accesibilidad_limpio():
    """Aísla el estado global mutable entre tests (paleta + cache Orca + filtro)."""
    yap._ORCA_ACTIVO = False
    yap._FILTRO_SALIDA_ACTIVO = False
    yield
    yap.restaurar_paleta()
    yap._ORCA_ACTIVO = None
    yap._FILTRO_SALIDA_ACTIVO = False


# ============================================================
# 1. DEFAULTS Y NORMALIZACIÓN EN EL PERFIL
# ============================================================

class TestDefaultsPerfil:
    """Requisito: el perfil incluye preferencias.accesibilidad con defaults off."""

    def test_perfil_default_tiene_accesibilidad_off(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            acc = perfil["preferencias"]["accesibilidad"]
            assert acc == yap.ACCESIBILIDAD_DEFECTO
            assert acc["alto_contraste"] is False
            assert acc["fuentes_grandes"] is False
            assert acc["lector_pantalla"] is False
            assert acc["navegacion_teclado"] is False

    def test_normalizacion_rellena_accesibilidad_ausente(self):
        pf = perfil_tmp()
        escribir_perfil(pf, {"nombre": "Ana", "preferencias": {"tema": "oscuro"}})
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            assert perfil["preferencias"]["accesibilidad"] == yap.ACCESIBILIDAD_DEFECTO

    def test_normalizacion_accesibilidad_corrupta_vuelve_a_defaults(self):
        pf = perfil_tmp()
        escribir_perfil(pf, {"preferencias": {"accesibilidad": "corrupto"}})
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            assert perfil["preferencias"]["accesibilidad"] == yap.ACCESIBILIDAD_DEFECTO

    @pytest.mark.parametrize(
        "valor,esperado",
        [
            ("si", True), ("sí", True), ("on", True), ("1", True), ("true", True),
            (1, True), (True, True), (0, False), ("no", False), ("off", False),
            (False, False), ("basura", False), ("", False),
        ],
    )
    def test_normalizacion_coerce_bool(self, valor, esperado):
        pf = perfil_tmp()
        acc = {"alto_contraste": valor}
        escribir_perfil(pf, {"preferencias": {"accesibilidad": acc}})
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            assert perfil["preferencias"]["accesibilidad"]["alto_contraste"] is esperado

    def test_normalizacion_conserva_opciones_validas_existentes(self):
        pf = perfil_tmp()
        acc = {"lector_pantalla": "si", "navegacion_teclado": "no"}
        escribir_perfil(pf, {"preferencias": {"accesibilidad": acc}})
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            perfil = yap.cargar_perfil()
            a = perfil["preferencias"]["accesibilidad"]
            assert a["lector_pantalla"] is True
            assert a["navegacion_teclado"] is False
            assert a["fuentes_grandes"] is False  # rellenado


# ============================================================
# 2. ACTUALIZACIÓN DE OPCIONES
# ============================================================

class TestActualizarAccesibilidad:
    """Requisito: cada opción se activa, guarda y persiste en el perfil."""

    def test_opciones_validas_se_guarda(self):
        for opcion in yap.OPCIONES_ACCESIBILIDAD:
            pf = perfil_tmp()
            with mock.patch.object(yap, "PROFILE_FILE", pf):
                perfil = yap.actualizar_accesibilidad(opcion)
                clave = yap.OPCIONES_ACCESIBILIDAD[opcion]
                assert perfil["preferencias"]["accesibilidad"][clave] is True
                # Persistido en disco
                assert yap.cargar_perfil()["preferencias"]["accesibilidad"][clave] is True

    def test_sin_valor_activa(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_accesibilidad("lector-pantalla")
            assert yap.cargar_perfil()["preferencias"]["accesibilidad"]["lector_pantalla"] is True

    @pytest.mark.parametrize("valor,esperado", [
        ("on", True), ("off", False), ("1", True), ("0", False),
        ("si", True), ("sí", True), ("no", False), ("yes", True),
        ("true", True), ("false", False), ("activar", True), ("desactivar", False),
    ])
    def test_valores_on_off_aceptados(self, valor, esperado):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_accesibilidad("alto-contraste", valor)
            got = yap.cargar_perfil()["preferencias"]["accesibilidad"]["alto_contraste"]
            assert got is esperado

    def test_valores_invalidos_no_soportados_se_apagan(self):
        """Valor desconocido = fail-safe (off). Nunca activa por accidente."""
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_accesibilidad("fuentes-grandes", "quizas")
            got = yap.cargar_perfil()["preferencias"]["accesibilidad"]["fuentes_grandes"]
            assert got is False

    def test_aliases_normalizan_a_clave_canonica(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_accesibilidad("lector de pantalla", "on")
            assert yap.cargar_perfil()["preferencias"]["accesibilidad"]["lector_pantalla"] is True

    def test_guiones_y_guiones_bajos_equivalentes(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_accesibilidad("altocontraste", "on")
            yap.actualizar_accesibilidad("navegacion_teclado", "on")
            a = yap.cargar_perfil()["preferencias"]["accesibilidad"]
            assert a["alto_contraste"] is True
            assert a["navegacion_teclado"] is True

    def test_opcion_desconocida_rechazada(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            with pytest.raises(ValueError):
                yap.actualizar_accesibilidad("brillo", "on")

    def test_actualizar_no_destruye_otras_opciones(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_accesibilidad("alto-contraste", "on")
            yap.actualizar_accesibilidad("lector-pantalla", "on")
            a = yap.cargar_perfil()["preferencias"]["accesibilidad"]
            assert a["alto_contraste"] is True
            assert a["lector_pantalla"] is True
            assert a["fuentes_grandes"] is False

    def test_canonizacion_opcion_invalida_devuelve_none(self):
        assert yap._canonizar_opcion_accesibilidad("no-existe") is None

    def test_parsear_valor_sin_dato_activa(self):
        assert yap._parsear_valor_accesibilidad(None) is True
        assert yap._parsear_valor_accesibilidad("") is True
        assert yap._parsear_valor_accesibilidad("off") is False


# ============================================================
# 3. SANITIZACIÓN ANSI
# ============================================================

class TestSanitizarSalida:
    """Requisito: con lector de pantalla u Orca, la salida no lleva ANSI."""

    def test_elimina_colores_sgr(self):
        assert yap.sanitizar_salida("\033[92mHola\033[0m") == "Hola"

    def test_elimina_estilos(self):
        assert yap.sanitizar_salida("\033[1mNegrita\033[0m") == "Negrita"

    def test_elimina_movimiento_de_cursor(self):
        assert yap.sanitizar_salida("\033[2J\033[Hlolo") == "lolo"
        assert yap.sanitizar_salida("\033[1A\033[5B") == ""

    def test_elimina_secuencias_oscy_charset(self):
        assert yap.sanitizar_salida("\x1b]0;titulo\x07texto") == "texto"
        assert yap.sanitizar_salida("\x1b(0texto") == "texto"

    def test_deja_texto_plano_intacto(self):
        assert yap.sanitizar_salida("Texto plano 123") == "Texto plano 123"
        assert yap.sanitizar_salida("") == ""

    def test_salida_compleja_sin_anexos(self):
        raw = "Estado: \033[92mOK\033[0m \033[1m[3]\033[0m \033[90mgris\033[0m"
        assert yap.sanitizar_salida(raw) == "Estado: OK [3] gris"

    def test_lector_pantalla_activo_sanea_via_aplicar_accesibilidad(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_accesibilidad("lector-pantalla", "on")
            assert yap.aplicar_accesibilidad("\033[91mX\033[0m") == "X"

    def test_orca_activo_sanea_via_aplicar_accesibilidad(self):
        yap._ORCA_ACTIVO = True
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            assert yap.aplicar_accesibilidad("\033[91mX\033[0m") == "X"

    def test_lector_inactivo_conserta_texto(self):
        yap._ORCA_ACTIVO = False
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            assert yap.aplicar_accesibilidad("Hola") == "Hola"

    def test_filtro_de_salida_sanea_ansi(self):
        buf = io.StringIO()
        filtro = yap._FiltroSalida(buf, sanea_ansi=True)
        filtro.write("A \033[92mverde\033[0m")
        assert buf.getvalue() == "A verde"


# ============================================================
# 4. DETECCIÓN DE ORCA
# ============================================================

class TestDetectarOrca:
    """Requisito: detección con shutil.which y procesos (sin shell=True)."""

    def test_sin_binario_no_consulta_procesos(self):
        with mock.patch.object(yap.shutil, "which", return_value=None) as mw, \
             mock.patch("subprocess.run") as mr:
            assert yap.detectar_orca() is False
            mw.assert_called_once_with("orca")
            mr.assert_not_called()

    def test_proceso_orca_activo_devuelve_true(self):
        with mock.patch.object(yap.shutil, "which", return_value="/usr/bin/orca"), \
             mock.patch("subprocess.run") as mr:
            mr.return_value = mock.Mock(stdout="bash\norca\nxterm", returncode=0)
            assert yap.detectar_orca() is True

    def test_binario_sin_proceso_devuelve_false(self):
        with mock.patch.object(yap.shutil, "which", return_value="/usr/bin/orca"), \
             mock.patch("subprocess.run") as mr:
            mr.return_value = mock.Mock(stdout="bash\npython3", returncode=0)
            assert yap.detectar_orca() is False

    def test_sin_ps_asume_activo_fail_safe(self):
        """Si no se puede comprobar, se asume activo (a11y fail-safe)."""
        with mock.patch.object(yap.shutil, "which", return_value="/usr/bin/orca"), \
             mock.patch("subprocess.run", side_effect=FileNotFoundError):
            assert yap.detectar_orca() is True

    def test_llamada_subprocess_segura(self):
        """HD-YAP-SEC-001: lista explícita de args, shell=False, timeout=."""
        with mock.patch.object(yap.shutil, "which", return_value="/usr/bin/orca"), \
             mock.patch("subprocess.run") as mr:
            mr.return_value = mock.Mock(stdout="orca\n", returncode=0)
            yap.detectar_orca()
            args = mr.call_args[0][0]
            assert args == ["ps", "-eo", "comm"]
            kwargs = mr.call_args[1]
            assert kwargs.get("shell") is not True
            assert "timeout" in kwargs
            assert "timeout=" not in kwargs  # keyword, nunca en la cadena de comando

    def test_lector_activo_si_orca_detectado(self):
        yap._ORCA_ACTIVO = True
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            assert yap.lector_pantalla_activo() is True

    def test_lector_inactivo_sin_orca(self):
        yap._ORCA_ACTIVO = False
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            assert yap.lector_pantalla_activo() is False

    def test_lector_activo_por_preferencia(self):
        yap._ORCA_ACTIVO = False
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_accesibilidad("lector-pantalla", "on")
            assert yap.lector_pantalla_activo() is True


# ============================================================
# 5. ALTO CONTRASTE
# ============================================================

class TestAltoContraste:
    """Requisito: esquema de blanco puro sobre fondo negro, sin degradados."""

    def test_paleta_alto_contraste_es_blanco_puro(self):
        yap.aplicar_alto_contraste()
        try:
            assert yap.C["GREEN"] == "\033[97m"
            assert yap.C["CYAN"] == "\033[97m"
            assert yap.C["YELLOW"] == "\033[97m"
            assert yap.C["RED"] == "\033[97m"
            assert yap.C["BLUE"] == "\033[97m"
            assert yap.C["GRAY"] == "\033[97m"      # sin gris degradado
            assert yap.C["RESET"] == "\033[0m"
            assert yap.C["BOLD"] == "\033[1;97m"
        finally:
            yap.restaurar_paleta()

    def test_restaurar_paleta_vuelve_a_original(self):
        original = dict(yap.PALETA_DEFAULT)
        yap.aplicar_alto_contraste()
        yap.restaurar_paleta()
        assert yap.C == original

    def test_alto_contraste_activo_reporta_true(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_accesibilidad("alto-contraste", "on")
            assert yap.alto_contraste_activo() is True
        pf2 = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf2):
            assert yap.alto_contraste_activo() is False

    def test_aplicar_preferencias_aplica_paleta_contraste(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_accesibilidad("alto-contraste", "on")
            yap.aplicar_preferencias_accesibilidad()
            assert yap.C["CYAN"] == "\033[97m"
            yap.restaurar_paleta()


# ============================================================
# 6. FUENTES GRANDES (2X)
# ============================================================

class TestFuentesGrandes:
    """Requisito: escala 2x de la salida tipográfica e interfaz CLI."""

    def test_texto_ampliado_duplica_ancho_y_alto(self):
        assert yap.texto_ampliado("Hola") == "HHoollaa\nHHoollaa"

    def test_texto_ampliado_multi_filas(self):
        assert yap.texto_ampliado("A\nB") == "AA\nAA\nBB\nBB"

    def test_texto_ampliado_sanea_ansi(self):
        assert yap.texto_ampliado("\033[92mA\033[0m") == "AA\nAA"

    def test_aplicar_accesibilidad_escala_2x_sin_lector(self):
        yap._ORCA_ACTIVO = False
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_accesibilidad("fuentes-grandes", "on")
            assert yap.aplicar_accesibilidad("Hola") == "HHoollaa\nHHoollaa"

    def test_lector_activo_prioriza_sanear_no_escalar(self):
        yap._ORCA_ACTIVO = True
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_accesibilidad("fuentes-grandes", "on")
            # Con lector activo no se escala: la síntesis no debe leer texto 2x
            assert yap.aplicar_accesibilidad("\033[92mHola\033[0m") == "Hola"

    def test_filtro_de_salida_escala_2x(self):
        buf = io.StringIO()
        filtro = yap._FiltroSalida(buf, escala_2x=True)
        filtro.write("Hola")
        assert buf.getvalue() == "HHoollaa\nHHoollaa"


# ============================================================
# 7. ESTRUCTURA CLI: yap perfil accesibilidad [OPCION]
# ============================================================

class TestCmdAccesibilidad:
    """Requisito: subcomandos de configuración bajo `yap perfil accesibilidad`."""

    def test_sin_args_muestra_estado(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_accesibilidad("")
            assert "Accesibilidad" in out
            assert "Alto contraste" in out
            assert "Lector de pantalla" in out
            assert "navegacion-teclado" in out

    def test_activa_opcion(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_accesibilidad("lector-pantalla")
            assert out.startswith("[OK]")
            assert "Lector de pantalla" in out
            assert "activada" in out
            assert yap.cargar_perfil()["preferencias"]["accesibilidad"]["lector_pantalla"] is True

    def test_desactiva_con_off(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.actualizar_accesibilidad("lector-pantalla", "on")
            out = yap.cmd_accesibilidad("lector-pantalla off")
            assert out.startswith("[OK]")
            assert "desactivada" in out

    def test_opcion_invalida_devuelve_error(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_accesibilidad("brillo on")
            assert out.startswith("[ERROR]")
            assert "alto-contraste" in out  # sugiere opciones

    def test_cmd_perfil_accesibilidad_activa(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("accesibilidad fuentes-grandes")
            assert out.startswith("[OK]")
            assert "Fuentes grandes" in out
            assert yap.cargar_perfil()["preferencias"]["accesibilidad"]["fuentes_grandes"] is True

    def test_cmd_perfil_accesibilidad_muestra_estado(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("accesibilidad")
            assert "Accesibilidad" in out
            assert "Orca detectado" in out

    def test_cmd_perfil_a11y_alias(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("a11y navegacion-teclado on")
            assert out.startswith("[OK]")
            assert yap.cargar_perfil()["preferencias"]["accesibilidad"]["navegacion_teclado"] is True

    def test_perfil_formateado_muestra_accesibilidad(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            out = yap.cmd_perfil("")
            assert "Accesibilidad" in out
            assert "Alto contraste" in out

    def test_guardar_no_deja_tmp(self):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.cmd_accesibilidad("alto-contraste on")
            assert os.path.exists(pf)
            assert not os.path.exists(pf + ".tmp")


# ============================================================
# 8. NAVEGACIÓN POR TECLADO
# ============================================================

class TestNavegacionTeclado:
    """Requisito: menús recorribles solo con Tab/Flechas/Enter/Esc."""

    def test_enter_elegir_primera(self):
        teclas = iter(["enter"])
        resultado = yap.menu_interactivo("Menu", ["A", "B"], reader=lambda: next(teclas))
        assert resultado == 0

    def test_flechas_mueven_seleccion(self):
        teclas = iter(["down", "down", "enter"])
        resultado = yap.menu_interactivo("Menu", ["A", "B", "C"], reader=lambda: next(teclas))
        assert resultado == 2

    def test_tab_cicla(self):
        teclas = iter(["tab", "tab", "tab", "tab", "enter"])
        resultado = yap.menu_interactivo("M", ["A", "B", "C"], reader=lambda: next(teclas))
        assert resultado == 1

    def test_flecha_arriba_envuelve(self):
        teclas = iter(["up", "enter"])  # desde 0 sube al último (0-based n-1)
        resultado = yap.menu_interactivo("M", ["A", "B"], reader=lambda: next(teclas))
        assert resultado == 1

    def test_esc_cancela(self):
        teclas = iter(["esc"])
        assert yap.menu_interactivo("M", ["A", "B"], reader=lambda: next(teclas)) is None

    def test_q_cancela_tras_navegar(self):
        teclas = iter(["down", "q"])
        assert yap.menu_interactivo("M", ["A", "B"], reader=lambda: next(teclas)) is None

    def test_mayusculas_en_tokens(self):
        teclas = iter(["DOWN", "ENTER"])
        resultado = yap.menu_interactivo("M", ["A", "B"], reader=lambda: next(teclas))
        assert resultado == 1

    def test_sin_opciones_devuelve_none(self):
        assert yap.menu_interactivo("M", []) is None


# ============================================================
# 9. RUTEO Y APLICACIÓN AL ARRANQUE
# ============================================================

class TestRoutingYArranque:
    """Requisito: yap perfil accesibilidad ... y arranque aplica el entorno."""

    def test_interpret_perfil_accesibilidad(self):
        action, param = yap.interpret("perfil accesibilidad alto-contraste")
        assert action == "perfil"
        assert param == "accesibilidad alto-contraste"

    def test_interpret_top_level_accesibilidad(self):
        action, param = yap.interpret("accesibilidad lector-pantalla")
        assert action == "perfil"
        assert param == "accesibilidad lector-pantalla"

    def test_interpret_top_level_a11y(self):
        action, param = yap.interpret("a11y navegacion-teclado on")
        assert action == "perfil"
        assert param == "accesibilidad navegacion-teclado on"

    def test_handle_action_actualiza_accesibilidad(self, capsys):
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            yap.handle_action("perfil", "accesibilidad alto-contraste",
                              "perfil accesibilidad alto-contraste")
            captured = capsys.readouterr()
            assert "[OK]" in captured.out
            assert yap.cargar_perfil()["preferencias"]["accesibilidad"]["alto_contraste"] is True

    def test_instalar_filtro_con_lector_activo(self):
        original_stdout = yap.sys.stdout
        yap._FILTRO_SALIDA_ACTIVO = False
        pf = perfil_tmp()
        try:
            with mock.patch.object(yap, "PROFILE_FILE", pf):
                yap.actualizar_accesibilidad("lector-pantalla", "on")
                ok = yap._instalar_filtro_salida()
                assert ok is True
                assert isinstance(yap.sys.stdout, yap._FiltroSalida)
                assert yap.sys.stdout.sanea_ansi is True
                yap.sys.stdout.write("\033[92mHola\033[0m")
        finally:
            yap._FILTRO_SALIDA_ACTIVO = False
            yap.sys.stdout = original_stdout

    def test_instalar_filtro_con_orca_detectado(self):
        original_stdout = yap.sys.stdout
        yap._ORCA_ACTIVO = True
        yap._FILTRO_SALIDA_ACTIVO = False
        pf = perfil_tmp()
        try:
            with mock.patch.object(yap, "PROFILE_FILE", pf):
                assert yap._instalar_filtro_salida() is True
        finally:
            yap._FILTRO_SALIDA_ACTIVO = False
            yap.sys.stdout = original_stdout

    def test_instalar_filtro_no_instala_con_defaults(self):
        yap._ORCA_ACTIVO = False
        yap._FILTRO_SALIDA_ACTIVO = False
        pf = perfil_tmp()
        with mock.patch.object(yap, "PROFILE_FILE", pf):
            assert yap._instalar_filtro_salida() is False
        yap._FILTRO_SALIDA_ACTIVO = False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])