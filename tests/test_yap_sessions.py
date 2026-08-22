"""
test_yap_sessions.py — Pruebas del control de sesiones (#21)

Verifica:
  1. Almacenamiento en ~/.config/yap/sessions.json con escritura atómica
  2. CRUD de sesiones: nueva, pausar, retomar, cerrar, listar
  3. Límite de sesiones abiertas simultáneas (MAX_OPEN_SESSIONS)
  4. Guardado y restauración del contexto de conversación (HISTORY)
  5. Integración con el historial persistente (#13)
  6. Integración con el sistema de cursos (#8)
  7. Banner de estado y prompt con ID de sesión
  8. Enrutado en interpret() y despacho en handle_action()
  9. Flujo de salida: pausar o cerrar

Ejecucion: python3 -m pytest tests/test_yap_sessions.py -v
"""

import pytest
import sys
import os
import tempfile
import shutil
import json
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


class SessionTestBase:
    """Aísla sessions.json, history.json y HISTORY en un directorio temporal."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sessions_file = os.path.join(self.tmpdir, "sessions.json")
        self.history_file = os.path.join(self.tmpdir, "history.json")
        self.patchers = [
            mock.patch.object(yap, "SESSIONS_FILE", self.sessions_file),
            mock.patch.object(yap, "HISTORY_FILE", self.history_file),
            mock.patch.object(yap, "HISTORY", []),
        ]
        for p in self.patchers:
            p.start()

    def teardown_method(self):
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def leer_sessions(self):
        with open(self.sessions_file, encoding="utf-8") as f:
            return json.load(f)


# ============================================================
# 1. ALMACENAMIENTO
# ============================================================

class TestSessionStore(SessionTestBase):
    """Requisito: sessions.json con estructura válida y escritura atómica."""

    def test_load_sin_archivo_devuelve_lista_vacia(self):
        assert yap._load_sessions() == []

    def test_write_y_load_roundtrip(self):
        yap._write_sessions_file([{"id": 1, "estado": yap.ESTADO_ACTIVA}])
        assert yap._load_sessions()[0]["id"] == 1

    def test_write_es_atomico(self):
        """No debe quedar un .tmp huérfano tras escribir."""
        yap._write_sessions_file([{"id": 1}])
        assert not os.path.exists(self.sessions_file + ".tmp")
        assert os.path.exists(self.sessions_file)

    def test_load_json_corrupto_no_revienta(self):
        with open(self.sessions_file, "w", encoding="utf-8") as f:
            f.write("{ esto no es json")
        assert yap._load_sessions() == []

    def test_load_formato_no_lista_se_descarta(self):
        with open(self.sessions_file, "w", encoding="utf-8") as f:
            json.dump({"no": "es una lista"}, f)
        assert yap._load_sessions() == []

    def test_estructura_de_sesion_nueva(self):
        s, err = yap.sesion_nueva()
        assert err is None
        for clave in ("id", "inicio", "actualizada", "curso", "ea", "estado", "turnos"):
            assert clave in s, f"falta la clave '{clave}'"
        assert s["estado"] == yap.ESTADO_ACTIVA
        assert s["turnos"] == []

    def test_ids_son_secuenciales(self):
        a, _ = yap.sesion_nueva()
        b, _ = yap.sesion_nueva()
        assert b["id"] == a["id"] + 1


# ============================================================
# 2. CRUD DE SESIONES
# ============================================================

class TestSessionCRUD(SessionTestBase):
    """Requisito: comandos nueva/pausar/retomar/cerrar funcionales."""

    def test_nueva_queda_activa(self):
        s, _ = yap.sesion_nueva()
        assert yap._sesion_activa(yap._load_sessions())["id"] == s["id"]

    def test_nueva_pausa_la_anterior(self):
        """Solo puede haber una sesión activa a la vez."""
        a, _ = yap.sesion_nueva()
        yap.sesion_nueva()
        guardadas = {s["id"]: s["estado"] for s in yap._load_sessions()}
        assert guardadas[a["id"]] == yap.ESTADO_PAUSADA
        assert list(guardadas.values()).count(yap.ESTADO_ACTIVA) == 1

    def test_pausar_sin_activa_devuelve_none(self):
        assert yap.sesion_pausar() is None

    def test_pausar_cambia_estado(self):
        s, _ = yap.sesion_nueva()
        pausada = yap.sesion_pausar()
        assert pausada["id"] == s["id"]
        assert yap._load_sessions()[0]["estado"] == yap.ESTADO_PAUSADA

    def test_cerrar_sin_activa_devuelve_none(self):
        assert yap.sesion_cerrar() is None

    def test_cerrar_cambia_estado(self):
        yap.sesion_nueva()
        cerrada = yap.sesion_cerrar()
        assert cerrada["estado"] == yap.ESTADO_CERRADA
        assert yap._load_sessions()[0]["estado"] == yap.ESTADO_CERRADA

    def test_retomar_sin_pausadas_devuelve_error(self):
        s, err = yap.sesion_retomar()
        assert s is None
        assert "pausada" in err.lower()

    def test_retomar_por_id(self):
        a, _ = yap.sesion_nueva()
        yap.sesion_nueva()  # pausa la primera
        retomada, err = yap.sesion_retomar(a["id"])
        assert err is None
        assert retomada["id"] == a["id"]
        assert retomada["estado"] == yap.ESTADO_ACTIVA

    def test_retomar_acepta_formato_s7(self):
        """El usuario ve 'S3' en el prompt; debe poder escribirlo así."""
        a, _ = yap.sesion_nueva()
        yap.sesion_nueva()
        retomada, err = yap.sesion_retomar(f"S{a['id']}")
        assert err is None
        assert retomada["id"] == a["id"]

    def test_retomar_id_inexistente_devuelve_error(self):
        yap.sesion_nueva()
        yap.sesion_pausar()
        s, err = yap.sesion_retomar(999)
        assert s is None
        assert "999" in err

    def test_retomar_sin_id_usa_la_ultima_pausada(self):
        yap.sesion_nueva()
        b, _ = yap.sesion_nueva()
        yap.sesion_pausar()  # pausa b; a ya estaba pausada
        retomada, err = yap.sesion_retomar()
        assert err is None
        assert retomada["id"] == b["id"]

    def test_retomar_pausa_la_activa_actual(self):
        a, _ = yap.sesion_nueva()
        b, _ = yap.sesion_nueva()  # a queda pausada, b activa
        yap.sesion_retomar(a["id"])
        estados = {s["id"]: s["estado"] for s in yap._load_sessions()}
        assert estados[a["id"]] == yap.ESTADO_ACTIVA
        assert estados[b["id"]] == yap.ESTADO_PAUSADA


# ============================================================
# 3. LÍMITE DE SESIONES ABIERTAS
# ============================================================

class TestSessionLimit(SessionTestBase):
    """Requisito: límite de sesiones abiertas simultáneas, configurable."""

    def test_limite_por_defecto_es_3(self):
        assert yap.MAX_OPEN_SESSIONS == 3

    def test_bloquea_al_alcanzar_el_limite(self):
        with mock.patch.object(yap, "MAX_OPEN_SESSIONS", 2):
            yap.sesion_nueva()
            yap.sesion_nueva()
            s, err = yap.sesion_nueva()
        assert s is None
        assert "2" in err

    def test_cerrar_libera_un_hueco(self):
        with mock.patch.object(yap, "MAX_OPEN_SESSIONS", 1):
            yap.sesion_nueva()
            bloqueada, err = yap.sesion_nueva()
            assert bloqueada is None
            yap.sesion_cerrar()
            liberada, err2 = yap.sesion_nueva()
        assert err2 is None
        assert liberada is not None

    def test_cerradas_no_cuentan_como_abiertas(self):
        yap.sesion_nueva()
        yap.sesion_cerrar()
        assert yap._sesiones_abiertas(yap._load_sessions()) == []


# ============================================================
# 4. CONTEXTO DE CONVERSACIÓN
# ============================================================

class TestSessionContext(SessionTestBase):
    """Requisito: pausar guarda el contexto; retomar lo carga en HISTORY."""

    def test_pausar_guarda_los_turnos(self):
        yap.sesion_nueva()
        yap.HISTORY.append(("que es una variable", "un espacio de memoria"))
        pausada = yap.sesion_pausar()
        assert pausada["turnos"][0]["user"] == "que es una variable"
        assert pausada["turnos"][0]["assistant"] == "un espacio de memoria"

    def test_pausar_limpia_history_en_memoria(self):
        yap.sesion_nueva()
        yap.HISTORY.append(("hola", "hola"))
        yap.sesion_pausar()
        assert yap.HISTORY == []

    def test_retomar_restaura_los_turnos(self):
        a, _ = yap.sesion_nueva()
        yap.HISTORY.append(("pregunta 1", "respuesta 1"))
        yap.sesion_pausar()
        yap.sesion_retomar(a["id"])
        assert yap.HISTORY == [("pregunta 1", "respuesta 1")]

    def test_nueva_empieza_con_contexto_limpio(self):
        yap.sesion_nueva()
        yap.HISTORY.append(("vieja", "vieja"))
        yap.sesion_nueva()
        assert yap.HISTORY == []

    def test_retomar_respeta_max_history(self):
        """No se cargan más turnos de los que cabe en el contexto del LLM."""
        a, _ = yap.sesion_nueva()
        for i in range(yap.MAX_HISTORY + 5):
            yap.HISTORY.append((f"p{i}", f"r{i}"))
        yap.sesion_pausar()
        yap.sesion_retomar(a["id"])
        assert len(yap.HISTORY) == yap.MAX_HISTORY

    def test_cerrar_limpia_history_en_memoria(self):
        yap.sesion_nueva()
        yap.HISTORY.append(("hola", "hola"))
        yap.sesion_cerrar()
        assert yap.HISTORY == []


# ============================================================
# 5. INTEGRACIÓN CON EL HISTORIAL (#13)
# ============================================================

class TestSessionHistoryIntegration(SessionTestBase):
    """Requisito: al cerrar, la sesión se archiva en history.json."""

    def test_cerrar_archiva_en_historial(self):
        yap.sesion_nueva()
        yap.HISTORY.append(("consulta", "respuesta"))
        yap.sesion_cerrar()
        archivadas = yap._load_history_sessions()
        assert len(archivadas) == 1
        assert archivadas[0]["turns"][0]["user"] == "consulta"
        assert "timestamp" in archivadas[0]

    def test_cerrar_sin_turnos_no_archiva_basura(self):
        yap.sesion_nueva()
        yap.sesion_cerrar()
        assert yap._load_history_sessions() == []

    def test_pausar_no_archiva_en_historial(self):
        """Las sesiones pausadas no llegan al historial hasta cerrarse."""
        yap.sesion_nueva()
        yap.HISTORY.append(("consulta", "respuesta"))
        yap.sesion_pausar()
        assert yap._load_history_sessions() == []

    def test_historial_ultimo_ve_la_sesion_cerrada(self):
        """Cerrar una sesión la deja disponible para 'historial --ultimo'."""
        yap.sesion_nueva()
        yap.HISTORY.append(("tema", "explicacion"))
        yap.sesion_cerrar()
        yap.cmd_historial(resume_last=True)
        assert yap.HISTORY == [("tema", "explicacion")]

    def test_archivado_respeta_max_history_sessions(self):
        with mock.patch.object(yap, "MAX_HISTORY_SESSIONS", 2):
            for i in range(4):
                yap.sesion_nueva()
                yap.HISTORY.append((f"p{i}", f"r{i}"))
                yap.sesion_cerrar()
        assert len(yap._load_history_sessions()) == 2


# ============================================================
# 6. INTEGRACIÓN CON CURSOS (#8)
# ============================================================

CURSO_PRUEBA = {
    "codigo": "TEST101",
    "nombre": "Curso de Prueba",
    "horas": 50, "semanas": 10,
    "ambiente": "Lab",
    "herramientas": ["Python"],
    "ras": [{"id": "RA1", "descripcion": "Test RA", "indicadores": ["IL1.1"]}],
    "eas": [{"id": "EA1", "nombre": "Test EA", "descripcion": "Desc EA",
             "horas": 20, "ponderacion": 100,
             "actividades": [{"orden": 1, "nombre": "Act1", "descripcion": "Hacer algo"}],
             "evaluaciones": []}],
    "evaluaciones": [],
}


class TestSessionCourseIntegration(SessionTestBase):
    """Requisito: entrar a un curso/EA asocia la sesión activa."""

    def setup_method(self):
        super().setup_method()
        self.cursos_dir = tempfile.mkdtemp()
        self.extra = [
            mock.patch.object(yap, "CURSOS_DIR", self.cursos_dir),
            mock.patch.object(yap, "PROGRESS_FILE",
                              os.path.join(self.tmpdir, "progress.json")),
        ]
        for p in self.extra:
            p.start()
        with open(os.path.join(self.cursos_dir, "TEST101.json"), "w", encoding="utf-8") as f:
            json.dump(CURSO_PRUEBA, f)

    def teardown_method(self):
        for p in self.extra:
            p.stop()
        shutil.rmtree(self.cursos_dir, ignore_errors=True)
        super().teardown_method()

    def test_cmd_curso_abre_sesion_si_no_hay(self):
        yap.cmd_curso("TEST101")
        activa = yap._sesion_activa(yap._load_sessions())
        assert activa is not None
        assert activa["curso"] == "TEST101"

    def test_cmd_curso_reutiliza_la_sesion_activa(self):
        s, _ = yap.sesion_nueva()
        yap.cmd_curso("TEST101")
        sessions = yap._load_sessions()
        assert len(sessions) == 1
        assert sessions[0]["id"] == s["id"]
        assert sessions[0]["curso"] == "TEST101"

    def test_curso_inexistente_no_abre_sesion(self):
        yap.cmd_curso("NOEXISTE")
        assert yap._load_sessions() == []

    def test_asociar_ea(self):
        yap.sesion_asociar(curso="TEST101", ea="EA1")
        activa = yap._sesion_activa(yap._load_sessions())
        assert activa["curso"] == "TEST101"
        assert activa["ea"] == "EA1"

    @mock.patch("builtins.input", side_effect=["salir"])
    def test_iniciar_ea_asocia_la_ea(self, mock_input):
        import io as _io
        with mock.patch("sys.stdout.write", _io.StringIO().write):
            yap.iniciar_ea("TEST101", "EA1")
        activa = yap._sesion_activa(yap._load_sessions())
        assert activa["ea"] == "EA1"

    def test_ea_inexistente_no_abre_sesion(self):
        yap.iniciar_ea("TEST101", "EA99")
        assert yap._load_sessions() == []

    def test_asociar_no_pisa_el_curso_con_none(self):
        yap.sesion_asociar(curso="TEST101")
        yap.sesion_asociar(ea="EA1")
        activa = yap._sesion_activa(yap._load_sessions())
        assert activa["curso"] == "TEST101"
        assert activa["ea"] == "EA1"


# ============================================================
# 7. BANNER Y PROMPT
# ============================================================

class TestSessionPrompt(SessionTestBase):
    """Requisito: el prompt muestra el ID de la sesión activa."""

    def test_prompt_sin_sesion_no_lleva_marca(self):
        assert "[S" not in yap.session_prompt()
        assert "Chinco" in yap.session_prompt()

    def test_prompt_con_sesion_lleva_el_id(self):
        s, _ = yap.sesion_nueva()
        assert f"[S{s['id']}]" in yap.session_prompt()

    def test_banner_vacio_sin_sesion(self):
        assert yap.session_banner() == ""

    def test_banner_muestra_id_y_estado(self):
        s, _ = yap.sesion_nueva()
        banner = yap.session_banner()
        assert f"#{s['id']}" in banner
        assert yap.ESTADO_ACTIVA in banner

    def test_banner_muestra_curso_y_ea(self):
        yap.sesion_asociar(curso="FPY1101", ea="EA1")
        banner = yap.session_banner()
        assert "FPY1101" in banner
        assert "EA1" in banner


# ============================================================
# 8. COMANDO sesion
# ============================================================

class TestCmdSesion(SessionTestBase):
    """Requisito: subcomandos de 'sesion' devuelven salida usable."""

    def test_estado_sin_sesiones(self):
        assert "No hay sesiones abiertas" in yap.cmd_sesion()

    def test_nueva(self):
        out = yap.cmd_sesion("nueva")
        assert "#1" in out
        assert yap._sesion_activa(yap._load_sessions()) is not None

    def test_nueva_bloqueada_por_limite(self):
        with mock.patch.object(yap, "MAX_OPEN_SESSIONS", 1):
            yap.cmd_sesion("nueva")
            out = yap.cmd_sesion("nueva")
        assert "Limite" in out

    def test_pausar_sin_activa(self):
        assert "No hay ninguna sesion activa" in yap.cmd_sesion("pausar")

    def test_pausar(self):
        yap.cmd_sesion("nueva")
        assert "pausada" in yap.cmd_sesion("pausar")

    def test_cerrar_sin_activa(self):
        assert "No hay ninguna sesion activa" in yap.cmd_sesion("cerrar")

    def test_cerrar(self):
        yap.cmd_sesion("nueva")
        assert "cerrada" in yap.cmd_sesion("cerrar")

    def test_retomar_sin_pausadas(self):
        assert "No hay sesiones pausadas" in yap.cmd_sesion("retomar")

    def test_retomar_por_id(self):
        s, _ = yap.sesion_nueva()
        yap.sesion_pausar()
        assert "retomada" in yap.cmd_sesion("retomar", str(s["id"]))

    def test_listar_vacio(self):
        assert "No hay sesiones registradas" in yap.cmd_sesion("listar")

    def test_listar_muestra_todas(self):
        yap.sesion_nueva()
        yap.sesion_cerrar()
        yap.sesion_nueva()
        out = yap.cmd_sesion("listar")
        assert "S1" in out and "S2" in out

    def test_estado_muestra_pausadas(self):
        yap.sesion_nueva()
        yap.sesion_pausar()
        out = yap.cmd_sesion()
        assert "Pausadas" in out

    def test_subcomando_desconocido_muestra_ayuda(self):
        out = yap.cmd_sesion("volar")
        assert "sesion nueva" in out


# ============================================================
# 9. ENRUTADO Y DESPACHO
# ============================================================

class TestSessionRouting(SessionTestBase):
    """Requisito: 'sesion ...' se enruta sin pasar por el LLM."""

    def test_interpret_sesion_pelada(self):
        assert yap.interpret("sesion") == ("sesion", "")

    def test_interpret_con_tilde(self):
        assert yap.interpret("sesión") == ("sesion", "")

    def test_interpret_subcomando(self):
        assert yap.interpret("sesion nueva") == ("sesion", "nueva")

    def test_interpret_subcomando_con_id(self):
        assert yap.interpret("sesion retomar 3") == ("sesion", "retomar 3")

    def test_interpret_no_llama_al_llm(self):
        """El router de teclado debe atrapar 'sesion' antes del clasificador."""
        with mock.patch.object(yap, "classify_intent") as clasificador:
            yap.interpret("sesion listar")
            clasificador.assert_not_called()

    def test_handle_action_despacha_sesion(self):
        with mock.patch.object(yap, "cmd_sesion", return_value="ok") as cmd:
            yap.handle_action("sesion", "retomar 3", "sesion retomar 3")
        cmd.assert_called_once_with("retomar", "3")

    def test_handle_action_sesion_sin_subcomando(self):
        with mock.patch.object(yap, "cmd_sesion", return_value="ok") as cmd:
            yap.handle_action("sesion", "", "sesion")
        cmd.assert_called_once_with("", "")

    def test_clasificador_acepta_la_accion_sesion(self):
        salida = mock.Mock(stdout="sesion|pausar", stderr="")
        with mock.patch("subprocess.run", return_value=salida):
            assert yap.classify_intent("quiero pausar") == ("sesion", "pausar")


# ============================================================
# 10. FLUJO DE SALIDA
# ============================================================

class TestSessionExit(SessionTestBase):
    """Requisito: al salir con sesión activa, preguntar pausar o cerrar."""

    def test_sin_sesion_activa_no_pregunta(self):
        with mock.patch("builtins.input") as entrada:
            yap._sesion_al_salir()
        entrada.assert_not_called()

    def test_sin_tty_pausa_por_seguridad(self):
        """Sin terminal no se puede preguntar; pausar no pierde contexto."""
        yap.sesion_nueva()
        yap.HISTORY.append(("hola", "hola"))
        with mock.patch("sys.stdin.isatty", return_value=False):
            yap._sesion_al_salir()
        assert yap._load_sessions()[0]["estado"] == yap.ESTADO_PAUSADA

    def test_respuesta_p_pausa(self):
        yap.sesion_nueva()
        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("builtins.input", return_value="p"):
            yap._sesion_al_salir()
        assert yap._load_sessions()[0]["estado"] == yap.ESTADO_PAUSADA

    def test_enter_cierra_por_defecto(self):
        """La opción por defecto es cerrar (p/C, la C va en mayúscula)."""
        yap.sesion_nueva()
        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("builtins.input", return_value=""):
            yap._sesion_al_salir()
        assert yap._load_sessions()[0]["estado"] == yap.ESTADO_CERRADA

    def test_eof_cierra_por_defecto(self):
        yap.sesion_nueva()
        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("builtins.input", side_effect=EOFError):
            yap._sesion_al_salir()
        assert yap._load_sessions()[0]["estado"] == yap.ESTADO_CERRADA

    def test_no_duplica_el_archivado_al_salir(self):
        """Cerrar limpia HISTORY, asi el atexit de #13 no vuelve a archivar."""
        yap.sesion_nueva()
        yap.HISTORY.append(("unica", "vez"))
        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("builtins.input", return_value=""):
            yap._sesion_al_salir()
        yap._save_history_session()  # lo que corre atexit al terminar el proceso
        assert len(yap._load_history_sessions()) == 1

    def test_sin_sesion_el_atexit_sigue_guardando(self):
        """Sin sesiones, el comportamiento de #13 no cambia."""
        yap.HISTORY.append(("suelta", "respuesta"))
        yap._sesion_al_salir()
        yap._save_history_session()
        assert len(yap._load_history_sessions()) == 1

    def test_cerrar_al_salir_archiva_el_contexto(self):
        yap.sesion_nueva()
        yap.HISTORY.append(("ultima", "respuesta"))
        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("builtins.input", return_value=""):
            yap._sesion_al_salir()
        assert yap._load_history_sessions()[0]["turns"][0]["user"] == "ultima"
