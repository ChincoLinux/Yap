"""
test_yap_telemetry.py — Pruebas de la telemetría local anónima (#38)

Verifica:
  1. Almacenamiento en ~/.config/yap/telemetry.json con escritura atómica
  2. Registro de contadores por acción
  3. Detección de funciones nunca usadas
  4. Comando `telemetria` y sus subcomandos
  5. Exportación anónima y opt-in
  6. Privacidad: no se registra contenido ni se transmite nada
  7. Enrutado en interpret() y despacho en handle_action()

Ejecucion: python3 -m pytest tests/test_yap_telemetry.py -v
"""

import sys
import os
import tempfile
import shutil
import json
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


class TelemetryTestBase:
    """Aísla telemetry.json y su exportación en un directorio temporal."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tfile = os.path.join(self.tmpdir, "telemetry.json")
        self.efile = os.path.join(self.tmpdir, "telemetry-export.json")
        self.patchers = [
            mock.patch.object(yap, "TELEMETRY_FILE", self.tfile),
            mock.patch.object(yap, "TELEMETRY_EXPORT", self.efile),
        ]
        for p in self.patchers:
            p.start()

    def teardown_method(self):
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def leer(self):
        with open(self.tfile, encoding="utf-8") as f:
            return json.load(f)


# ============================================================
# 1. ALMACENAMIENTO
# ============================================================

class TestTelemetryStore(TelemetryTestBase):
    """Requisito: telemetry.json con escritura atómica."""

    def test_load_sin_archivo_devuelve_estructura_vacia(self):
        datos = yap._load_telemetry()
        assert datos["comandos"] == {}
        assert datos["activa"] is True

    def test_write_es_atomico(self):
        yap._write_telemetry_file(yap._telemetria_vacia())
        assert not os.path.exists(self.tfile + ".tmp")
        assert os.path.exists(self.tfile)

    def test_load_json_corrupto_no_revienta(self):
        with open(self.tfile, "w", encoding="utf-8") as f:
            f.write("{ roto")
        assert yap._load_telemetry()["comandos"] == {}

    def test_load_estructura_invalida_se_descarta(self):
        with open(self.tfile, "w", encoding="utf-8") as f:
            json.dump(["no", "es", "un", "dict"], f)
        assert yap._load_telemetry()["comandos"] == {}

    def test_estructura_tiene_las_claves_esperadas(self):
        yap.registrar_uso("query")
        datos = self.leer()
        for clave in ("version", "activa", "creado", "actualizado", "comandos"):
            assert clave in datos, f"falta '{clave}'"

    def test_error_de_escritura_no_rompe_el_flujo(self):
        """La telemetría nunca debe interrumpir lo que el usuario está haciendo."""
        with mock.patch.object(yap, "_write_telemetry_file", side_effect=OSError("disco lleno")):
            yap.registrar_uso("query")  # no debe lanzar


# ============================================================
# 2. REGISTRO DE USO
# ============================================================

class TestRegistrarUso(TelemetryTestBase):
    """Requisito: contadores por acción."""

    def test_incrementa_el_contador(self):
        yap.registrar_uso("query")
        yap.registrar_uso("query")
        assert self.leer()["comandos"]["query"] == 2

    def test_acciones_distintas_se_cuentan_por_separado(self):
        yap.registrar_uso("query")
        yap.registrar_uso("open_app")
        comandos = self.leer()["comandos"]
        assert comandos["query"] == 1
        assert comandos["open_app"] == 1

    def test_accion_desconocida_cuenta_como_query(self):
        """handle_action trata lo desconocido como query; el conteo debe coincidir."""
        yap.registrar_uso("accion_inventada")
        assert self.leer()["comandos"] == {"query": 1}

    def test_actualiza_la_marca_de_tiempo(self):
        yap.registrar_uso("query")
        assert self.leer()["actualizado"] is not None

    def test_no_registra_si_esta_desactivada(self):
        yap._telemetria_conmutar(False)
        yap.registrar_uso("query")
        assert self.leer()["comandos"] == {}

    def test_vuelve_a_registrar_al_reactivar(self):
        yap._telemetria_conmutar(False)
        yap.registrar_uso("query")
        yap._telemetria_conmutar(True)
        yap.registrar_uso("query")
        assert self.leer()["comandos"]["query"] == 1


# ============================================================
# 3. FUNCIONES SIN USAR
# ============================================================

class TestAccionesSinUsar(TelemetryTestBase):
    """Requisito: detectar funciones que nunca se han usado."""

    def test_sin_datos_todas_estan_sin_usar(self):
        assert set(yap._acciones_sin_usar({})) == set(yap.ACCIONES_CONOCIDAS)

    def test_una_usada_sale_de_la_lista(self):
        sin_usar = yap._acciones_sin_usar({"query": 3})
        assert "query" not in sin_usar
        assert "pseint" in sin_usar

    def test_contador_en_cero_sigue_contando_como_sin_usar(self):
        assert "query" in yap._acciones_sin_usar({"query": 0})


# ============================================================
# 4. COMANDO telemetria
# ============================================================

class TestCmdTelemetria(TelemetryTestBase):
    """Requisito: `yap telemetria` muestra el resumen."""

    def test_resumen_sin_datos(self):
        assert "Todavia no hay datos" in yap.cmd_telemetria()

    def test_resumen_muestra_totales(self):
        for _ in range(3):
            yap.registrar_uso("query")
        salida = yap.cmd_telemetria()
        assert "3" in salida
        assert "Consulta directa al AI" in salida

    def test_resumen_lista_las_no_usadas(self):
        yap.registrar_uso("query")
        assert "Nunca usadas" in yap.cmd_telemetria()

    def test_resumen_avisa_que_nada_se_envia(self):
        yap.registrar_uso("query")
        assert "ningun dato se envia automaticamente" in yap.cmd_telemetria().lower()

    def test_desactivar_y_activar(self):
        assert "desactivada" in yap.cmd_telemetria("desactivar")
        assert yap.telemetria_activa() is False
        assert "activada" in yap.cmd_telemetria("activar")
        assert yap.telemetria_activa() is True

    def test_borrar_limpia_los_contadores(self):
        yap.registrar_uso("query")
        yap.cmd_telemetria("borrar")
        assert self.leer()["comandos"] == {}

    def test_borrar_conserva_la_preferencia_de_opt_out(self):
        yap.cmd_telemetria("desactivar")
        yap.cmd_telemetria("borrar")
        assert yap.telemetria_activa() is False

    def test_subcomando_desconocido_muestra_ayuda(self):
        assert "telemetria exportar" in yap.cmd_telemetria("volar")


# ============================================================
# 5. EXPORTACIÓN ANÓNIMA
# ============================================================

class TestExportacion(TelemetryTestBase):
    """Requisito: exportación anónima y opt-in."""

    def test_sin_datos_no_exporta(self):
        assert "No hay datos" in yap.cmd_telemetria("exportar")
        assert not os.path.exists(self.efile)

    def test_exportar_crea_el_archivo(self):
        yap.registrar_uso("query")
        yap.cmd_telemetria("exportar")
        assert os.path.exists(self.efile)

    def test_exportar_es_atomico(self):
        yap.registrar_uso("query")
        yap.cmd_telemetria("exportar")
        assert not os.path.exists(self.efile + ".tmp")

    def test_el_export_solo_lleva_contadores(self):
        yap.registrar_uso("query")
        yap.cmd_telemetria("exportar")
        with open(self.efile, encoding="utf-8") as f:
            export = json.load(f)
        assert set(export.keys()) == {"version", "comandos", "total", "sin_usar"}

    def test_el_export_no_lleva_fechas(self):
        """Las fechas de uso podrían correlacionarse con una persona concreta."""
        yap.registrar_uso("query")
        yap.cmd_telemetria("exportar")
        contenido = open(self.efile, encoding="utf-8").read()
        assert "creado" not in contenido
        assert "actualizado" not in contenido

    def test_el_export_no_lleva_rutas_ni_usuario(self):
        yap.registrar_uso("query")
        yap.cmd_telemetria("exportar")
        contenido = open(self.efile, encoding="utf-8").read()
        assert os.path.expanduser("~") not in contenido
        assert "/home/" not in contenido
        assert "C:\\" not in contenido

    def test_exportar_no_envia_nada(self):
        """Opt-in significa que exportar escribe un archivo, no que transmita."""
        yap.registrar_uso("query")
        with mock.patch("urllib.request.urlopen") as red:
            yap.cmd_telemetria("exportar")
        red.assert_not_called()


# ============================================================
# 6. PRIVACIDAD
# ============================================================

class TestPrivacidad(TelemetryTestBase):
    """Requisito: no se registra contenido y no se transmite nada."""

    def test_no_se_guarda_el_parametro_de_la_accion(self):
        """El texto que escribe el estudiante no debe quedar registrado."""
        with mock.patch.object(yap, "cmd_query", return_value="respuesta"):
            yap.handle_action("query", "mi nombre es Juan Perez", "mi nombre es Juan Perez")
        contenido = open(self.tfile, encoding="utf-8").read()
        assert "Juan" not in contenido
        assert "nombre" not in contenido

    def test_solo_se_guardan_enteros(self):
        yap.registrar_uso("query")
        yap.registrar_uso("open_app")
        for valor in self.leer()["comandos"].values():
            assert isinstance(valor, int)

    def test_las_claves_son_acciones_conocidas(self):
        yap.registrar_uso("query")
        yap.registrar_uso("cualquier cosa rara")
        for clave in self.leer()["comandos"]:
            assert clave in yap.ACCIONES_CONOCIDAS

    def test_registrar_uso_no_abre_conexiones(self):
        with mock.patch("urllib.request.urlopen") as red:
            yap.registrar_uso("query")
        red.assert_not_called()

    def test_el_modulo_de_telemetria_no_usa_la_red(self):
        """Verificación estática sobre el bloque de telemetría del fuente."""
        with open(yap.__file__, encoding="utf-8") as f:
            fuente = f.read()
        inicio = fuente.index("# ── Telemetría local anónima")
        fin = fuente.index("def cargar_progreso():")
        bloque = fuente[inicio:fin]
        for prohibido in ("urlopen", "urllib", "socket", "requests", "post("):
            assert prohibido not in bloque, f"la telemetría referencia '{prohibido}'"


# ============================================================
# 7. ENRUTADO Y DESPACHO
# ============================================================

class TestTelemetryRouting(TelemetryTestBase):
    """Requisito: 'telemetria' se enruta sin pasar por el LLM."""

    def test_interpret_telemetria_pelada(self):
        assert yap.interpret("telemetria") == ("telemetria", "")

    def test_interpret_con_tilde(self):
        assert yap.interpret("telemetría") == ("telemetria", "")

    def test_interpret_subcomando(self):
        assert yap.interpret("telemetria exportar") == ("telemetria", "exportar")

    def test_interpret_no_llama_al_llm(self):
        with mock.patch.object(yap, "classify_intent") as clasificador:
            yap.interpret("telemetria")
        clasificador.assert_not_called()

    def test_handle_action_despacha_telemetria(self):
        with mock.patch.object(yap, "cmd_telemetria", return_value="ok") as cmd:
            yap.handle_action("telemetria", "exportar", "telemetria exportar")
        cmd.assert_called_once_with("exportar")

    def test_handle_action_registra_cada_accion(self):
        with mock.patch.object(yap, "cmd_query", return_value="r"):
            yap.handle_action("query", "hola", "hola")
        assert self.leer()["comandos"]["query"] == 1
