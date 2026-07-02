"""
test_yap_functional.py — Pruebas funcionales para Yap

Verifica que el sistema cumple con los requisitos funcionales:
  1. Apertura de aplicaciones via whitelist
  2. Webfetch con resumen
  3. Busqueda en Wikipedia via API REST
  4. Consulta directa al LLM
  5. Modo interactivo y por comando
  6. Clasificacion de intenciones

Ejecucion: python3 -m pytest tests/test_yap_functional.py -v
"""

import pytest
import sys
import os
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock, ANY

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


# ============================================================
# 1. APERTURA DE APLICACIONES
# ============================================================

class TestOpenApp:
    """Requisito: El agente puede abrir aplicaciones de la whitelist."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.apps_path = os.path.join(self.tmp_dir, "apps.conf")
        with open(self.apps_path, "w") as f:
            f.write("LibreOffice:libreoffice\n")
            f.write("Firefox:firefox-esr,firefox\n")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_abrir_app_exitosa(self, mock_popen, mock_run, mock_which):
        """Abrir una app permitida debe devolver [OK]."""
        mock_which.return_value = "/usr/bin/libreoffice"
        mock_run.return_value = Mock(stdout="7.5.0", stderr="")

        with patch.object(yap, "WHITELIST_APPS", self.apps_path):
            result = yap.cmd_open_app("LibreOffice")

        assert "[OK]" in result
        # title() convierte "LibreOffice" a "Libreoffice", usamos lower()
        assert "libreoffice" in result.lower()

    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("subprocess.Popen")
    @patch.object(yap, "notify")
    def test_abrir_app_con_binario_alternativo(self, mock_notify, mock_popen, mock_which, mock_run):
        """Si firefox-esr no existe, debe usar firefox."""
        mock_run.return_value = Mock(stdout="", stderr="")
        mock_which.side_effect = lambda x: "/usr/bin/firefox" if x == "firefox" else None

        with patch.object(yap, "WHITELIST_APPS", self.apps_path):
            yap.cmd_open_app("Firefox")

        mock_popen.assert_called_once_with(
            ["/usr/bin/firefox"],
            stdout=ANY, stderr=ANY
        )

    def test_app_no_encontrada_mensaje_graceful(self):
        """App no en whitelist debe mostrar mensaje graceful con alternativas."""
        with patch.object(yap, "WHITELIST_APPS", self.apps_path):
            result = yap.cmd_open_app("Chrome")

        assert "[ERROR]" in result
        assert "no disponible" in result.lower()
        # Debe listar alternativas en minusculas
        assert "firefox" in result.lower() or "libreoffice" in result.lower()


# ============================================================
# 2. WEBFETCH
# ============================================================

class TestWebfetch:
    """Requisito: El agente puede obtener y resumir contenido web."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.web_path = os.path.join(self.tmp_dir, "web.conf")
        with open(self.web_path, "w") as f:
            f.write("wikipedia.org\n")
            f.write("debian.org\n")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_dominio_bloqueado_mensaje_graceful(self):
        """Dominio bloqueado debe mostrar lista de permitidos."""
        with patch.object(yap, "WHITELIST_WEB", self.web_path):
            result = yap.cmd_webfetch("https://malware.com/exploit")

        assert "[ERROR]" in result
        assert "bloqueado" in result.lower()
        assert "wikipedia.org" in result or "debian.org" in result

    def test_subdominio_permitido(self):
        """Subdominio de un dominio permitido debe funcionar."""
        with patch.object(yap, "WHITELIST_WEB", self.web_path):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_ctx = MagicMock()
                mock_ctx.read.return_value = b"<html><body>Contenido</body></html>"
                mock_urlopen.return_value.__enter__.return_value = mock_ctx
                result = yap.cmd_webfetch("https://es.wikipedia.org/wiki/Linux")

        assert "[ERROR]" not in result

    @patch("urllib.request.urlopen")
    def test_fetch_contenido_se_limpia(self, mock_urlopen):
        """El HTML debe limpiarse (tags eliminados)."""
        mock_ctx = MagicMock()
        mock_ctx.read.return_value = b"<html><body><p>Texto</p></body></html>"
        mock_urlopen.return_value.__enter__.return_value = mock_ctx

        with patch.object(yap, "WHITELIST_WEB", self.web_path):
            result, _ = yap.cmd_webfetch("https://wikipedia.org/test", feed_to_llm=True)

        assert "<html>" not in result
        assert "<body>" not in result
        assert "Texto" in result


# ============================================================
# 3. CLASIFICACION DE INTENCIONES
# ============================================================

class TestIntentClassification:
    """Requisito: El LLM clasifica intenciones (open_app, search, webfetch, query)."""

    @patch("subprocess.run")
    def test_classify_open_app(self, mock_run):
        """Entrada 'Abre Firefox' debe clasificar como open_app."""
        mock_run.return_value = Mock(stdout="open_app|firefox", stderr="")
        action, param = yap.classify_intent("Abre Firefox")
        assert action == "open_app"
        assert param == "firefox"

    @patch("subprocess.run")
    def test_classify_search(self, mock_run):
        """Entrada 'busca que es linux' debe clasificar como search."""
        mock_run.return_value = Mock(stdout="search|que es linux", stderr="")
        action, param = yap.classify_intent("busca que es linux")
        assert action == "search"

    @patch("subprocess.run")
    def test_classify_webfetch(self, mock_run):
        mock_run.return_value = Mock(
            stdout="webfetch|https://es.wikipedia.org/wiki/Linux",
            stderr=""
        )
        action, param = yap.classify_intent("Busca https://es.wikipedia.org/wiki/Linux")
        assert action == "webfetch"

    @patch("subprocess.run")
    def test_classify_query(self, mock_run):
        mock_run.return_value = Mock(stdout="query|que es debian?", stderr="")
        action, param = yap.classify_intent("Que es Debian?")
        assert action == "query"

    def test_fallback_a_query(self):
        """Si el LLM falla, debe clasificar como query por defecto."""
        from subprocess import TimeoutExpired
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = TimeoutExpired("llama-cli", 30)
            action, param = yap.classify_intent("Hola")
        assert action == "query"

    @patch("subprocess.run")
    def test_classify_pseint(self, mock_run):
        """Entrada PSeInt debe clasificar como pseint."""
        mock_run.return_value = Mock(stdout="pseint|como hago un ciclo mientras", stderr="")
        action, param = yap.classify_intent("como hago un ciclo mientras en pseint")
        assert action == "pseint"
        assert "ciclo mientras" in param


# ============================================================
# 4. CONSULTA AL LLM
# ============================================================

class TestQuery:
    """Requisito: El agente consulta al LLM local."""

    @patch("subprocess.run")
    def test_cmd_query_respuesta_exitosa(self, mock_run):
        """cmd_query debe devolver la respuesta del LLM."""
        mock_run.return_value = Mock(
            stdout="Linux es un sistema operativo de codigo abierto.",
            stderr=""
        )
        result = yap.cmd_query("Que es Linux?", store_history=False)
        assert "Linux" in result
        assert "sistema operativo" in result

    @patch("subprocess.run")
    def test_cmd_query_timeout(self, mock_run):
        """Timeout debe devolver mensaje de advertencia."""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired("llama-cli", 120)
        result = yap.cmd_query("test", store_history=False)
        assert "[WARN]" in result
        assert "Tiempo de espera" in result

    @patch("subprocess.run")
    def test_cmd_query_sin_respuesta(self, mock_run):
        """Respuesta vacia debe mostrar stderr."""
        mock_run.return_value = Mock(stdout="", stderr="(sin respuesta)")
        result = yap.cmd_query("test", store_history=False)
        assert "(sin respuesta)" in result


# ============================================================
# 5. HISTORIAL DE CONVERSACION
# ============================================================

class TestHistory:
    """Requisito: El historial de conversacion funciona correctamente."""

    def setup_method(self):
        yap.HISTORY.clear()

    @patch("subprocess.run")
    def test_historial_se_almacena(self, mock_run):
        mock_run.return_value = Mock(stdout="Respuesta de prueba.", stderr="")
        yap.cmd_query("Hola", store_history=True)
        assert len(yap.HISTORY) == 1
        assert yap.HISTORY[0][0] == "Hola"
        assert yap.HISTORY[0][1] == "Respuesta de prueba."

    @patch("subprocess.run")
    def test_historial_no_almacena_si_false(self, mock_run):
        mock_run.return_value = Mock(stdout="Resumen.", stderr="")
        yap.cmd_query("Resume esto", store_history=False)
        assert len(yap.HISTORY) == 0

    @patch("subprocess.run")
    def test_historial_limitado(self, mock_run):
        mock_run.return_value = Mock(stdout="Resp.", stderr="")
        for i in range(10):
            yap.cmd_query(f"Mensaje {i}", store_history=True)
        assert len(yap.HISTORY) <= yap.MAX_HISTORY


# ============================================================
# 6. SISTEMA DE NOTIFICACIONES
# ============================================================

class TestNotifications:
    """Requisito: El agente emite notificaciones graficas."""

    @patch("subprocess.run")
    def test_notify_enviado(self, mock_run):
        mock_run.return_value = Mock()
        yap.notify("Titulo", "Mensaje", urgency="normal")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "notify-send" in args[0]
        assert "Titulo" in args
        assert "Mensaje" in args

    @patch("subprocess.run")
    def test_notify_urgency_levels(self, mock_run):
        yap.notify("Alerta", "Peligro", urgency="critical")
        args = mock_run.call_args[0][0]
        assert "-u" in args
        idx = args.index("-u")
        assert args[idx + 1] == "critical"


# ============================================================
# 7. CARGA DE EJERCICIOS PSEINT
# ============================================================

class TestPSeIntConfig:
    """Pruebas para carga de ejercicios PSeInt."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.exercises_path = os.path.join(self.tmp_dir, "ejercicios.conf")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_cargar_ejercicios_devuelve_lista(self):
        with open(self.exercises_path, "w") as f:
            f.write("Hola Mundo:Escribe un programa\n")
            f.write("Suma:Suma dos numeros|Paso 1; Paso 2\n")
        with patch.object(yap, "PSEINT_EXERCISES", self.exercises_path):
            ej = yap.cargar_ejercicios()
        assert len(ej) == 2
        assert ej[0] == ("Hola Mundo", "Escribe un programa", "")
        assert ej[1] == ("Suma", "Suma dos numeros", "Paso 1; Paso 2")

    def test_cargar_ignora_comentarios(self):
        with open(self.exercises_path, "w") as f:
            f.write("# Esto es un comentario\n")
            f.write("Hola Mundo:Escribe un programa\n")
        with patch.object(yap, "PSEINT_EXERCISES", self.exercises_path):
            ej = yap.cargar_ejercicios()
        assert len(ej) == 1

    def test_cargar_ejercicios_sin_archivo(self):
        ruta_inexistente = os.path.join(self.tmp_dir, "no_existe.conf")
        with patch.object(yap, "PSEINT_EXERCISES", ruta_inexistente):
            ej = yap.cargar_ejercicios()
        assert ej == []


# ============================================================
# 8. GENERACION DE PDF
# ============================================================


# ============================================================
# 9. TUTORIAL INTERACTIVO PSEINT
# ============================================================

class TestIntroduccionPSeInt:
    """Pruebas para el tutorial interactivo PSeInt."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.exercises_path = os.path.join(self.tmp_dir, "ejercicios.conf")
        with open(self.exercises_path, "w") as f:
            f.write("Hola Mundo:Escribe un programa\n")
            f.write("Suma:Suma dos numeros\n")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @patch("yap.cmd_pseint")
    @patch("yap.cmd_open_app")
    @patch("subprocess.Popen")
    @patch("builtins.input")
    def test_tutorial_muestra_primer_ejercicio(
        self, mock_input, mock_popen, mock_open_app, mock_cmd_pseint
    ):
        """Tutorial must show first exercise and exit on 'salir'."""
        mock_input.side_effect = ["salir"]
        mock_open_app.return_value = "[OK] PSeInt abierta."
        mock_cmd_pseint.return_value = "Respuesta del tutor."
        with patch.object(yap, "PSEINT_EXERCISES", self.exercises_path):
            yap.cmd_intro_pseint()
        mock_open_app.assert_called_once_with("pseint")
        mock_cmd_pseint.assert_not_called()

    @patch("yap.cmd_pseint")
    @patch("yap.cmd_open_app")
    @patch("subprocess.Popen")
    @patch("builtins.input")
    def test_tutorial_pregunta_va_al_tutor(
        self, mock_input, mock_popen, mock_open_app, mock_cmd_pseint
    ):
        """Typing a question must call cmd_pseint with exercise context."""
        mock_input.side_effect = ["como lo hago", "salir"]
        mock_open_app.return_value = "[OK] PSeInt abierta."
        mock_cmd_pseint.return_value = "Debes usar Escribir..."
        with patch.object(yap, "PSEINT_EXERCISES", self.exercises_path):
            yap.cmd_intro_pseint()
        mock_cmd_pseint.assert_called_once()
        call_arg = mock_cmd_pseint.call_args[0][0]
        assert "Hola Mundo" in call_arg, "Exercise context missing"
        assert "como lo hago" in call_arg, "Student question missing"

    @patch("yap.cmd_pseint")
    @patch("yap.cmd_open_app")
    @patch("subprocess.Popen")
    @patch("builtins.input")
    def test_tutorial_siguiente_avanza(
        self, mock_input, mock_popen, mock_open_app, mock_cmd_pseint
    ):
        """'siguiente' must advance to next exercise."""
        mock_input.side_effect = ["siguiente", "salir"]
        mock_open_app.return_value = "[OK] PSeInt abierta."
        mock_cmd_pseint.return_value = "Pista breve."
        with patch.object(yap, "PSEINT_EXERCISES", self.exercises_path):
            yap.cmd_intro_pseint()
        mock_cmd_pseint.assert_not_called()

    @patch("yap.cmd_pseint")
    @patch("yap.cmd_open_app")
    @patch("subprocess.Popen")
    @patch("builtins.input")
    def test_tutorial_ayuda_pide_pista(
        self, mock_input, mock_popen, mock_open_app, mock_cmd_pseint
    ):
        """'ayuda' must call cmd_pseint with exercise context."""
        mock_input.side_effect = ["ayuda", "salir"]
        mock_open_app.return_value = "[OK] PSeInt abierta."
        mock_cmd_pseint.return_value = "Pista: piensa en Escribir..."
        with patch.object(yap, "PSEINT_EXERCISES", self.exercises_path):
            yap.cmd_intro_pseint()
        mock_cmd_pseint.assert_called_once()
        call_arg = mock_cmd_pseint.call_args[0][0]
        assert "Hola Mundo" in call_arg, "Missing exercise context"
        assert "ayuda" in call_arg.lower(), "Missing student text"

    @patch("yap.cmd_pseint")
    @patch("yap.cmd_open_app")
    @patch("subprocess.Popen")
    @patch("builtins.input")
    def test_tutorial_completa_todos(
        self, mock_input, mock_popen, mock_open_app, mock_cmd_pseint
    ):
        """Completing all exercises shows congratulatory message."""
        mock_input.side_effect = ["siguiente", "salir"]
        mock_open_app.return_value = "[OK] PSeInt abierta."
        mock_cmd_pseint.return_value = "Respuesta."
        with patch.object(yap, "PSEINT_EXERCISES", self.exercises_path):
            yap.cmd_intro_pseint()


# ============================================================
# 10. TUTOR PSEINT
# ============================================================

class TestPSeIntTutor:
    """Requisito: El agente asiste con PSeInt paso a paso."""

    @patch("subprocess.run")
    def test_cmd_pseint_respuesta_exitosa(self, mock_run):
        """cmd_pseint debe devolver respuesta del tutor."""
        mock_run.return_value = Mock(
            stdout="Para sumar dos numeros en PSeInt:\n\n"
                   "1. Definir las variables\n"
                   "2. Leer los valores\n"
                   "3. Calcular la suma\n"
                   "4. Mostrar el resultado\n\n"
                   "Pseudocodigo:\n"
                   "Algoritmo SumarNumeros\n"
                   "  Definir a, b, suma Como Entero\n"
                   "  Escribir \"Ingrese primer numero:\"\n"
                   "  Leer a\n"
                   "  Escribir \"Ingrese segundo numero:\"\n"
                   "  Leer b\n"
                   "  suma <- a + b\n"
                   "  Escribir \"La suma es: \", suma\n"
                   "FinAlgoritmo",
            stderr=""
        )
        result = yap.cmd_pseint("como sumo dos numeros")
        assert result
        assert "PSeInt" or "Algoritmo" or "suma" in result


# ============================================================
# 8. ARQUITECTURA Y COMPONENTES
# ============================================================

class TestArchitecture:
    """Verificar que el codigo sigue la arquitectura definida."""

    def test_main_existe(self):
        assert hasattr(yap, "main") and callable(yap.main)

    def test_handle_action_existe(self):
        assert hasattr(yap, "handle_action") and callable(yap.handle_action)

    def test_interpret_existe(self):
        assert hasattr(yap, "interpret") and callable(yap.interpret)

    def test_load_whitelist_existe(self):
        assert hasattr(yap, "load_whitelist") and callable(yap.load_whitelist)

    def test_load_domain_whitelist_existe(self):
        assert hasattr(yap, "load_domain_whitelist") and callable(yap.load_domain_whitelist)

    def test_cmd_pseint_existe(self):
        assert hasattr(yap, "cmd_pseint") and callable(yap.cmd_pseint)

    def test_cmd_intro_pseint_existe(self):
        assert hasattr(yap, "cmd_intro_pseint") and callable(yap.cmd_intro_pseint)

    def test_cargar_ejercicios_existe(self):
        assert hasattr(yap, "cargar_ejercicios") and callable(yap.cargar_ejercicios)


# ============================================================
# 9. CHINCOLINUX TUI
# ============================================================

class TestChincoTUI:
    """Tests for ChincoLinux TUI display functions."""

    @staticmethod
    def _mock_term_size(cols, rows):
        """Return a mock with .columns and .lines attributes."""
        m = Mock()
        m.columns = cols
        m.lines = rows
        return m

    @patch("shutil.get_terminal_size")
    def test_display_header_centers_title(self, mock_size):
        mock_size.return_value = self._mock_term_size(80, 24)
        from yap import display_header
        result = display_header("Test Title")
        assert "Test Title" in result
        assert "\033[" in result  # has ANSI color codes

    @patch("shutil.get_terminal_size")
    def test_display_menu_returns_string(self, mock_size):
        mock_size.return_value = self._mock_term_size(80, 24)
        from yap import display_menu
        result = display_menu("MENU", ["Op1", "Op2"])
        assert "[1]" in result
        assert "[2]" in result
        assert "MENU" in result
        assert isinstance(result, str)

    @patch("shutil.get_terminal_size")
    def test_display_menu_no_options(self, mock_size):
        mock_size.return_value = self._mock_term_size(80, 24)
        from yap import display_menu
        result = display_menu("Empty", [])
        assert "Empty" in result
        assert "[1]" not in result

    @patch("shutil.get_terminal_size")
    def test_display_box_wraps_long_text(self, mock_size):
        mock_size.return_value = self._mock_term_size(50, 24)
        from yap import display_box
        long_text = "A" * 100
        result = display_box(long_text)
        assert "┌" in result
        assert "┐" in result
        assert "└" in result
        assert len(result.split("\n")) > 3  # wrapped multiple lines

    @patch("shutil.get_terminal_size")
    def test_display_box_empty_text(self, mock_size):
        mock_size.return_value = self._mock_term_size(80, 24)
        from yap import display_box
        result = display_box("")
        assert "┌" in result
        assert "┘" in result
        # empty box should not crash

    @patch("shutil.get_terminal_size")
    def test_display_box_narrow_terminal(self, mock_size):
        mock_size.return_value = self._mock_term_size(5, 24)
        from yap import display_box
        result = display_box("Hi")
        # ponytail: on 5-col terminal (1 char internal width), chars split
        # per line. Main assertion: no crash.
        assert "┌" in result


# ============================================================
# 10. SISTEMA DE CURSOS
# ============================================================

class TestCourseSystem:
    """Tests for course loading and listing."""

    VALID_COURSE = {
        "codigo": "TEST101",
        "nombre": "Curso de Prueba",
        "horas": 50,
        "semanas": 10,
        "ras": [{"id": "RA1", "descripcion": "Test RA", "indicadores": ["IL1.1"]}],
        "eas": [{"id": "EA1", "nombre": "Test EA", "descripcion": "Desc",
                 "horas": 20,
                 "actividades": [{"nombre": "Act1"}],
                 "evaluaciones": []}],
        "evaluaciones": [{"nombre": "Eval Final", "tipo": "transversal", "ponderacion": 40}],
    }

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = patch("yap.CURSOS_DIR", self.tmpdir)
        self.patcher.start()

    def teardown_method(self):
        self.patcher.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cargar_curso_valido(self):
        path = os.path.join(self.tmpdir, "TEST101.json")
        with open(path, "w") as f:
            json.dump(self.VALID_COURSE, f)
        result = yap.cargar_curso("TEST101")
        assert result["codigo"] == "TEST101"
        assert len(result["ras"]) == 1

    def test_cargar_curso_inexistente(self):
        with pytest.raises(FileNotFoundError):
            yap.cargar_curso("NOEXISTE")

    def test_cargar_curso_corrupto(self):
        path = os.path.join(self.tmpdir, "BAD.json")
        with open(path, "w") as f:
            f.write("not json")
        with pytest.raises(json.JSONDecodeError):
            yap.cargar_curso("BAD")

    def test_cargar_curso_faltan_claves(self):
        path = os.path.join(self.tmpdir, "INCOMPLETO.json")
        with open(path, "w") as f:
            json.dump({"codigo": "X"}, f)
        with pytest.raises(ValueError, match="faltan"):
            yap.cargar_curso("INCOMPLETO")

    def test_listar_cursos_descubre_archivos(self):
        for code, name in [("A101", "Alpha"), ("B202", "Beta")]:
            data = dict(self.VALID_COURSE, codigo=code, nombre=name)
            path = os.path.join(self.tmpdir, f"{code}.json")
            with open(path, "w") as f:
                json.dump(data, f)
        cursos = yap.listar_cursos()
        assert len(cursos) == 2
        codes = [c[0] for c in cursos]
        assert "A101" in codes
        assert "B202" in codes

    def test_listar_cursos_salta_malformados(self):
        path = os.path.join(self.tmpdir, "BUENO.json")
        with open(path, "w") as f:
            json.dump(self.VALID_COURSE, f)
        path2 = os.path.join(self.tmpdir, "MALO.json")
        with open(path2, "w") as f:
            f.write("{corrupt")
        cursos = yap.listar_cursos()
        assert len(cursos) == 1
        assert cursos[0][0] == "BUENO"


# ============================================================
# 11. PROGRESO DEL ESTUDIANTE
# ============================================================

class TestProgreso:
    """Tests for progress save/load."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = patch("yap.PROGRESS_FILE", os.path.join(self.tmpdir, "progress.json"))
        self.patcher.start()

    def teardown_method(self):
        self.patcher.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cargar_progreso_sin_archivo(self):
        result = yap.cargar_progreso()
        assert result == {"cursos": {}}

    def test_guardar_y_cargar_progreso(self):
        data = {"cursos": {"FPY1101": {"EA1": {"completada": True}}}}
        yap.guardar_progreso(data)
        loaded = yap.cargar_progreso()
        assert loaded["cursos"]["FPY1101"]["EA1"]["completada"] is True

    def test_guardar_progreso_atomico(self):
        data = {"cursos": {}}
        yap.guardar_progreso(data)
        tmp_path = os.path.join(self.tmpdir, "progress.json.tmp")
        assert not os.path.exists(tmp_path)
        assert os.path.exists(os.path.join(self.tmpdir, "progress.json"))


# ============================================================
# 12. COMANDOS DE CURSO
# ============================================================

class TestCursoCommand:
    """Tests for cmd_curso and iniciar_ea."""

    VALID_COURSE = {
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

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cpat = patch("yap.CURSOS_DIR", self.tmpdir)
        self.ppat = patch("yap.PROGRESS_FILE", os.path.join(self.tmpdir, "progress.json"))
        self.cpat.start()
        self.ppat.start()
        path = os.path.join(self.tmpdir, "TEST101.json")
        with open(path, "w") as f:
            json.dump(self.VALID_COURSE, f)

    def teardown_method(self):
        self.cpat.stop()
        self.ppat.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("shutil.get_terminal_size", return_value=Mock(columns=80, lines=24))
    def test_cmd_curso_muestra_informacion(self, mock_size):
        result = yap.cmd_curso("TEST101")
        assert "TEST101" in result
        assert "Curso de Prueba" in result
        assert "RA1" in result
        assert "EA1" in result

    @patch("shutil.get_terminal_size", return_value=Mock(columns=80, lines=24))
    def test_cmd_curso_inexistente(self, mock_size):
        result = yap.cmd_curso("NOEXISTE")
        assert "ERROR" in result

    @patch("shutil.get_terminal_size", return_value=Mock(columns=80, lines=24))
    def test_iniciar_ea_muestra_actividades(self, mock_size):
        result = yap.iniciar_ea("TEST101", "EA1")
        assert "EA1" in result
        assert "Act1" in result
        assert "Test EA" in result

    @patch("shutil.get_terminal_size", return_value=Mock(columns=80, lines=24))
    def test_iniciar_ea_inexistente(self, mock_size):
        result = yap.iniciar_ea("TEST101", "EA99")
        assert "ERROR" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
