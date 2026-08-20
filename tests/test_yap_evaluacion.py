"""
test_yap_evaluacion.py — Evaluación automática de actividades (#23)

Cubre:
  1. Schema de tipos de evaluación en cursos
  2. Parser robusto del JSON del LLM (fallback a texto plano)
  3. evaluar_actividad() para los 4 tipos (LLM mockeado)
  4. progress.json: puntaje, intentos, fecha de aprobación
  5. Máximo 3 intentos (configurable) y saltar
  6. yap progreso: %, promedio, reprobadas, nota chilena
  7. Integración con FPY1101 y con el contexto de sesión (#21)
"""

import json
import os
import tempfile
from unittest.mock import Mock, patch

import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap

REPO_CURSOS = os.path.join(os.path.dirname(__file__), "..", "cursos")


def _eval_ok(**overrides):
    data = {
        "aprobado": True,
        "puntaje": 90,
        "feedback": "Bien",
        "criterios_cumplidos": ["c1"],
        "criterios_fallidos": [],
        "sugerencia": "",
        "error": False,
    }
    data.update(overrides)
    return data


def _eval_fail(**overrides):
    data = {
        "aprobado": False,
        "puntaje": 30,
        "feedback": "Falta completar",
        "criterios_cumplidos": [],
        "criterios_fallidos": ["c1"],
        "sugerencia": "Repasa el contenido",
        "error": False,
    }
    data.update(overrides)
    return data


def _llm_stdout(payload):
    if isinstance(payload, dict):
        payload = json.dumps(payload, ensure_ascii=False)
    return Mock(stdout=payload, stderr="")


# ============================================================
# 1. SCHEMA
# ============================================================

class TestSchemaEvaluacion:
    """El JSON de curso acepta tipos de evaluación y rechaza los inválidos."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = patch.object(yap, "CURSOS_DIR", self.tmpdir)
        self.patcher.start()

    def teardown_method(self):
        self.patcher.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, data, name="TEST101.json"):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path

    def _base(self, actividad):
        return {
            "codigo": "TEST101",
            "nombre": "Curso de Prueba",
            "horas": 10,
            "semanas": 2,
            "ras": [{"id": "RA1", "descripcion": "RA", "indicadores": ["IL1"]}],
            "eas": [{
                "id": "EA1",
                "nombre": "EA",
                "descripcion": "d",
                "horas": 4,
                "actividades": [actividad],
                "evaluaciones": [],
            }],
            "evaluaciones": [],
        }

    def test_schema_constante_documenta_los_cuatro_tipos(self):
        assert yap.TIPOS_EVALUACION == (
            "respuesta_libre", "codigo_pseint", "opcion_multiple", "completar",
        )
        assert "tipo" in yap.SCHEMA_EVALUACION_ACTIVIDAD
        assert "criterios_evaluacion" in yap.SCHEMA_EVALUACION_ACTIVIDAD

    def test_actividad_sin_tipo_sigue_siendo_valida(self):
        data = self._base({"orden": 1, "nombre": "Act", "descripcion": "d"})
        self._write(data)
        curso = yap.cargar_curso("TEST101")
        assert curso["eas"][0]["actividades"][0]["nombre"] == "Act"

    def test_tipo_invalido_rechazado(self):
        data = self._base({
            "orden": 1, "nombre": "Act", "descripcion": "d", "tipo": "ensayo",
        })
        self._write(data)
        with pytest.raises(ValueError, match="tipo"):
            yap.cargar_curso("TEST101")

    def test_opcion_multiple_requiere_respuesta_y_opciones(self):
        data = self._base({
            "orden": 1, "nombre": "Act", "descripcion": "d",
            "tipo": "opcion_multiple",
        })
        self._write(data)
        with pytest.raises(ValueError, match="respuesta_correcta"):
            yap.cargar_curso("TEST101")

        data["eas"][0]["actividades"][0]["respuesta_correcta"] = "A"
        self._write(data)
        with pytest.raises(ValueError, match="opciones"):
            yap.cargar_curso("TEST101")

    def test_criterios_deben_ser_lista(self):
        data = self._base({
            "orden": 1, "nombre": "Act", "descripcion": "d",
            "tipo": "respuesta_libre",
            "criterios_evaluacion": "no es lista",
        })
        self._write(data)
        with pytest.raises(ValueError, match="criterios_evaluacion"):
            yap.cargar_curso("TEST101")

    def test_opcion_multiple_valida(self):
        data = self._base({
            "orden": 1, "nombre": "Act", "descripcion": "d",
            "tipo": "opcion_multiple",
            "opciones": ["A", "B"],
            "respuesta_correcta": "A",
            "criterios_evaluacion": ["elige A"],
        })
        self._write(data)
        curso = yap.cargar_curso("TEST101")
        assert curso["eas"][0]["actividades"][0]["tipo"] == "opcion_multiple"

    def test_max_intentos_invalido(self):
        data = self._base({
            "orden": 1, "nombre": "Act", "descripcion": "d",
            "tipo": "completar",
            "max_intentos": 0,
        })
        self._write(data)
        with pytest.raises(ValueError, match="max_intentos"):
            yap.cargar_curso("TEST101")


# ============================================================
# 2. PARSER JSON DEL LLM
# ============================================================

class TestParserEvaluacion:
    CRITERIOS = ["c1", "c2"]

    def test_json_limpio(self):
        raw = json.dumps({
            "aprobado": True,
            "puntaje": 88,
            "feedback": "ok",
            "criterios_cumplidos": ["c1", "c2"],
            "criterios_fallidos": [],
            "sugerencia": "",
        })
        r = yap.parsear_json_evaluacion(raw, self.CRITERIOS)
        assert r["aprobado"] is True
        assert r["puntaje"] == 88
        assert r["parseado"] is True
        assert r["error"] is False

    def test_json_en_markdown(self):
        raw = "```json\n{\"aprobado\": false, \"puntaje\": 40, \"feedback\": \"falta\"}\n```"
        r = yap.parsear_json_evaluacion(raw, self.CRITERIOS)
        assert r["aprobado"] is False
        assert r["puntaje"] == 40
        assert r["parseado"] is True

    def test_json_mezclado_con_prosa(self):
        raw = "Aqui va mi evaluacion:\n{\"aprobado\": true, \"puntaje\": 75, \"feedback\": \"bien\"}\nFin."
        r = yap.parsear_json_evaluacion(raw, self.CRITERIOS)
        assert r["aprobado"] is True
        assert r["puntaje"] == 75

    def test_json_con_coma_final(self):
        raw = '{"aprobado": true, "puntaje": 91, "feedback": "ok",}'
        r = yap.parsear_json_evaluacion(raw, self.CRITERIOS)
        assert r["aprobado"] is True
        assert r["puntaje"] == 91

    def test_fallback_texto_aprobado(self):
        r = yap.parsear_json_evaluacion(
            "La respuesta esta correcta. Aprobado. puntaje 80",
            self.CRITERIOS,
        )
        assert r["aprobado"] is True
        assert r["puntaje"] == 80
        assert r["parseado"] is False
        assert r["criterios_cumplidos"] == self.CRITERIOS

    def test_fallback_texto_reprobado(self):
        r = yap.parsear_json_evaluacion(
            "No cumple los criterios. Respuesta incorrecta.",
            self.CRITERIOS,
        )
        assert r["aprobado"] is False
        assert r["parseado"] is False
        assert r["criterios_fallidos"] == self.CRITERIOS

    def test_error_llm_no_aprueba(self):
        r = yap.parsear_json_evaluacion("[ERROR] llama-cli no instalado.", self.CRITERIOS)
        assert r["error"] is True
        assert r["aprobado"] is False

    def test_timeout_es_error(self):
        r = yap.parsear_json_evaluacion("[WARN] Tiempo de espera agotado (120s)")
        assert r["error"] is True

    def test_puntaje_se_acota_a_0_100(self):
        r = yap.parsear_json_evaluacion('{"aprobado": true, "puntaje": 150}')
        assert r["puntaje"] == 100
        r = yap.parsear_json_evaluacion('{"aprobado": false, "puntaje": -4}')
        assert r["puntaje"] == 0

    def test_aprobado_string_si(self):
        r = yap.parsear_json_evaluacion('{"aprobado": "si", "puntaje": 70}')
        assert r["aprobado"] is True

    def test_vacio_cae_a_fallback(self):
        r = yap.parsear_json_evaluacion("", self.CRITERIOS)
        assert r["aprobado"] is False
        assert r["parseado"] is False


# ============================================================
# 3. evaluar_actividad — 4 tipos
# ============================================================

class TestEvaluarActividad:
    CRITERIOS = ["criterio uno", "criterio dos"]

    def test_respuesta_vacia_no_llama_llm(self):
        with patch("subprocess.run") as mock_run:
            r = yap.evaluar_actividad("", self.CRITERIOS, tipo="respuesta_libre")
        mock_run.assert_not_called()
        assert r["aprobado"] is False
        assert r["puntaje"] == 0

    def test_opcion_multiple_correcta_sin_llm(self):
        act = {
            "tipo": "opcion_multiple",
            "opciones": ["while True", "for i in range(10)", "if i < 10"],
            "respuesta_correcta": "for i in range(10)",
            "criterios_evaluacion": self.CRITERIOS,
        }
        with patch("subprocess.run") as mock_run:
            r = yap.evaluar_actividad("B", self.CRITERIOS, tipo="opcion_multiple", actividad=act)
            r2 = yap.evaluar_actividad(
                "for i in range(10)", self.CRITERIOS, tipo="opcion_multiple", actividad=act
            )
            r3 = yap.evaluar_actividad("b)", self.CRITERIOS, tipo="opcion_multiple", actividad=act)
        mock_run.assert_not_called()
        assert r["aprobado"] is True
        assert r["puntaje"] == 100
        assert r2["aprobado"] is True
        assert r3["aprobado"] is True

    def test_opcion_multiple_incorrecta(self):
        act = {
            "opciones": ["A", "B", "C"],
            "respuesta_correcta": "A",
        }
        with patch("subprocess.run") as mock_run:
            r = yap.evaluar_actividad("C", ["elige A"], tipo="opcion_multiple", actividad=act)
        mock_run.assert_not_called()
        assert r["aprobado"] is False
        assert r["puntaje"] == 0

    def test_opcion_multiple_letra_contra_letra(self):
        act = {"opciones": ["entrada", "proceso", "salida"], "respuesta_correcta": "B"}
        r = yap.evaluar_actividad("b", [], tipo="opcion_multiple", actividad=act)
        assert r["aprobado"] is True
        r = yap.evaluar_actividad("proceso", [], tipo="opcion_multiple", actividad=act)
        assert r["aprobado"] is True
        r = yap.evaluar_actividad("A", [], tipo="opcion_multiple", actividad=act)
        assert r["aprobado"] is False

    @patch("subprocess.run")
    def test_respuesta_libre_usa_llm(self, mock_run):
        mock_run.return_value = _llm_stdout({
            "aprobado": True,
            "puntaje": 85,
            "feedback": "Cubre los componentes",
            "criterios_cumplidos": ["criterio uno"],
            "criterios_fallidos": [],
            "sugerencia": "",
        })
        r = yap.evaluar_actividad(
            "Un algoritmo es una receta con entrada proceso y salida",
            self.CRITERIOS,
            tipo="respuesta_libre",
            actividad={"nombre": "Algoritmos", "descripcion": "Define algoritmo"},
        )
        assert r["aprobado"] is True
        assert r["puntaje"] == 85
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "llama-cli"

    @patch("subprocess.run")
    def test_codigo_pseint_valida_sintaxis_y_logica(self, mock_run):
        mock_run.return_value = _llm_stdout({
            "aprobado": True,
            "puntaje": 92,
            "feedback": "Sintaxis PSeInt correcta y suma bien",
            "criterios_cumplidos": self.CRITERIOS,
            "criterios_fallidos": [],
            "sugerencia": "",
        })
        codigo = (
            "Algoritmo Suma\n"
            "Definir a, b, c Como Entero\n"
            "Leer a, b\n"
            "c <- a + b\n"
            "Escribir c\n"
            "FinAlgoritmo"
        )
        r = yap.evaluar_actividad(
            codigo, self.CRITERIOS, tipo="codigo_pseint",
            actividad={"nombre": "Suma", "enunciado": "Suma dos numeros"},
        )
        assert r["aprobado"] is True
        prompt = mock_run.call_args[0][0][mock_run.call_args[0][0].index("-p") + 1]
        assert "PSeInt" in prompt or "pseint" in prompt.lower()
        assert "Algoritmo Suma" in prompt

    @patch("subprocess.run")
    def test_completar_usa_llm(self, mock_run):
        mock_run.return_value = _llm_stdout({
            "aprobado": True,
            "puntaje": 100,
            "feedback": "Completo entrada, proceso y salida",
            "criterios_cumplidos": self.CRITERIOS,
            "criterios_fallidos": [],
            "sugerencia": "",
        })
        r = yap.evaluar_actividad(
            "entrada, proceso y salida",
            self.CRITERIOS,
            tipo="completar",
            actividad={"enunciado": "Completa las tres partes"},
        )
        assert r["aprobado"] is True
        prompt = mock_run.call_args[0][0][mock_run.call_args[0][0].index("-p") + 1]
        assert "completar" in prompt.lower()

    @patch("subprocess.run")
    def test_llm_texto_plano_se_parsea(self, mock_run):
        mock_run.return_value = _llm_stdout(
            "El estudiante no cumple el criterio. Respuesta incorrecta. puntaje 35"
        )
        r = yap.evaluar_actividad("asdf", self.CRITERIOS, tipo="respuesta_libre")
        assert r["aprobado"] is False
        assert r["parseado"] is False
        assert r["error"] is False

    @patch("subprocess.run")
    def test_llm_timeout_no_aprueba_y_marca_error(self, mock_run):
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired("llama-cli", 120)
        r = yap.evaluar_actividad("algo", self.CRITERIOS, tipo="respuesta_libre")
        assert r["error"] is True
        assert r["aprobado"] is False

    def test_tipo_desconocido_cae_a_respuesta_libre(self):
        with patch("subprocess.run", return_value=_llm_stdout({
            "aprobado": True, "puntaje": 70, "feedback": "ok",
        })) as mock_run:
            r = yap.evaluar_actividad("x", self.CRITERIOS, tipo="ensayo")
        mock_run.assert_called_once()
        assert r["aprobado"] is True


# ============================================================
# 4. PROGRESS.JSON
# ============================================================

class TestProgresoEvaluacion:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ppat = patch.object(yap, "PROGRESS_FILE", os.path.join(self.tmpdir, "progress.json"))
        self.ppat.start()

    def teardown_method(self):
        self.ppat.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_intento_aprobado_guarda_puntaje_intentos_fecha(self):
        progress = {"cursos": {}}
        rec = yap.registrar_intento_actividad(
            progress, "FPY1101", "EA1", 1, _eval_ok(puntaje=85)
        )
        assert rec["aprobado"] is True
        assert rec["puntaje"] == 85
        assert rec["intentos"] == 1
        assert rec["fecha_aprobacion"]
        yap.guardar_progreso(progress)
        loaded = yap.cargar_progreso()
        act = loaded["cursos"]["FPY1101"]["EA1"]["actividades"]["1"]
        assert act["puntaje"] == 85
        assert act["intentos"] == 1
        assert act["fecha_aprobacion"]

    def test_error_llm_no_incrementa_intentos(self):
        progress = {"cursos": {}}
        rec = yap.registrar_intento_actividad(
            progress, "FPY1101", "EA1", 1,
            _eval_fail(error=True, puntaje=0, feedback="sin llm"),
        )
        assert rec["intentos"] == 0

    def test_reintentos_acumulan(self):
        progress = {"cursos": {}}
        yap.registrar_intento_actividad(progress, "FPY1101", "EA1", 2, _eval_fail())
        rec = yap.registrar_intento_actividad(progress, "FPY1101", "EA1", 2, _eval_ok())
        assert rec["intentos"] == 2
        assert rec["aprobado"] is True

    def test_saltar_deja_puntaje_cero_si_no_hubo_intento(self):
        progress = {"cursos": {}}
        rec = yap.saltar_actividad(progress, "FPY1101", "EA1", 3)
        assert rec["saltada"] is True
        assert rec["aprobado"] is False
        assert rec["puntaje"] == 0

    def test_finalizar_ea_calcula_nota_chilena(self):
        progress = {"cursos": {}}
        yap.registrar_intento_actividad(progress, "FPY1101", "EA1", 1, _eval_ok(puntaje=100))
        yap.registrar_intento_actividad(progress, "FPY1101", "EA1", 2, _eval_ok(puntaje=80))
        yap.registrar_intento_actividad(progress, "FPY1101", "EA1", 3, _eval_fail(puntaje=20))
        ea = yap._finalizar_ea(progress, "FPY1101", "EA1")
        assert ea["completada"] is True
        assert ea["puntaje_promedio"] == round((100 + 80 + 20) / 3, 1)
        assert ea["nota_final"] == yap.nota_chilena(ea["puntaje_promedio"])
        assert ea["fecha_completada"]

    def test_progreso_viejo_sin_actividades_sigue_cargando(self):
        data = {"cursos": {"FPY1101": {"EA1": {"completada": True, "actividad_actual": 4}}}}
        yap.guardar_progreso(data)
        loaded = yap.cargar_progreso()
        assert loaded["cursos"]["FPY1101"]["EA1"]["completada"] is True


class TestNotaChilena:
    def test_extremos_y_aprobacion(self):
        assert yap.nota_chilena(0) == 1.0
        assert yap.nota_chilena(60) == 4.0
        assert yap.nota_chilena(100) == 7.0

    def test_intermedios(self):
        assert yap.nota_chilena(30) == 2.5
        assert yap.nota_chilena(80) == 5.5

    def test_acota_fuera_de_rango(self):
        assert yap.nota_chilena(-10) == 1.0
        assert yap.nota_chilena(200) == 7.0

    def test_entrada_invalida(self):
        assert yap.nota_chilena("x") == 1.0


# ============================================================
# 5. FLUJO iniciar_ea: intentos, saltar, sesion
# ============================================================

class TestFlujoEvaluacion:
    COURSE = {
        "codigo": "TEST101",
        "nombre": "Curso de Prueba",
        "horas": 50, "semanas": 10,
        "ambiente": "Lab",
        "herramientas": ["Python"],
        "ras": [{"id": "RA1", "descripcion": "Test RA", "indicadores": ["IL1.1"]}],
        "eas": [{
            "id": "EA1",
            "nombre": "Test EA",
            "descripcion": "Desc EA",
            "horas": 20,
            "ponderacion": 100,
            "actividades": [{
                "orden": 1,
                "nombre": "Act evaluable",
                "descripcion": "Responde",
                "tipo": "respuesta_libre",
                "criterios_evaluacion": ["menciona X"],
                "enunciado": "Que es X?",
            }],
            "evaluaciones": [],
        }],
        "evaluaciones": [],
    }

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cpat = patch.object(yap, "CURSOS_DIR", self.tmpdir)
        self.ppat = patch.object(yap, "PROGRESS_FILE", os.path.join(self.tmpdir, "progress.json"))
        self.cpat.start()
        self.ppat.start()
        with open(os.path.join(self.tmpdir, "TEST101.json"), "w", encoding="utf-8") as f:
            json.dump(self.COURSE, f)

    def teardown_method(self):
        self.cpat.stop()
        self.ppat.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, inputs, eval_return=None, eval_side=None):
        captured = []

        def write(s):
            captured.append(str(s))
            return len(str(s))

        kw = {}
        if eval_side is not None:
            kw["side_effect"] = eval_side
        else:
            kw["return_value"] = eval_return or _eval_ok()
        with patch("shutil.get_terminal_size", return_value=Mock(columns=80, lines=24)), \
             patch("builtins.input", side_effect=inputs), \
             patch.object(yap, "evaluar_actividad", **kw), \
             patch("sys.stdout.write", side_effect=write):
            result = yap.iniciar_ea("TEST101", "EA1")
        return result, "".join(captured), yap.cargar_progreso()

    def test_enter_vacio_no_completa_actividad_evaluable(self):
        _, out, progress = self._run(["", "", "saltar"])
        assert "Escribe tu respuesta" in out
        rec = progress["cursos"]["TEST101"]["EA1"]["actividades"]["1"]
        assert rec.get("aprobado") is False
        assert rec.get("saltada") is True

    def test_aprueba_marca_completada_y_nota(self):
        _, out, progress = self._run(["", "una buena respuesta"], eval_return=_eval_ok(puntaje=90))
        ea = progress["cursos"]["TEST101"]["EA1"]
        assert ea["completada"] is True
        assert ea["actividades"]["1"]["puntaje"] == 90
        assert ea["actividades"]["1"]["fecha_aprobacion"]
        assert ea["nota_final"] == yap.nota_chilena(90)
        assert "APROBADO" in out
        assert "Nota final" in out

    def test_reprobar_permite_reintentar_y_aprobar(self):
        _, _, progress = self._run(
            ["", "mala", "buena"],
            eval_side=[_eval_fail(), _eval_ok(puntaje=80)],
        )
        rec = progress["cursos"]["TEST101"]["EA1"]["actividades"]["1"]
        assert rec["intentos"] == 2
        assert rec["aprobado"] is True
        assert rec["puntaje"] == 80

    def test_maximo_tres_intentos_luego_solo_saltar(self):
        _, out, progress = self._run(
            ["", "a", "b", "c", "d", "saltar"],
            eval_return=_eval_fail(puntaje=10),
        )
        rec = progress["cursos"]["TEST101"]["EA1"]["actividades"]["1"]
        assert rec["intentos"] == 3
        assert rec["saltada"] is True
        assert rec["aprobado"] is False
        assert "Sin intentos" in out

    def test_max_intentos_configurable_por_actividad(self):
        course = json.loads(json.dumps(self.COURSE))
        course["eas"][0]["actividades"][0]["max_intentos"] = 1
        with open(os.path.join(self.tmpdir, "TEST101.json"), "w", encoding="utf-8") as f:
            json.dump(course, f)
        _, out, progress = self._run(
            ["", "unica", "otra", "saltar"],
            eval_return=_eval_fail(),
        )
        rec = progress["cursos"]["TEST101"]["EA1"]["actividades"]["1"]
        assert rec["intentos"] == 1
        assert rec["saltada"] is True

    def test_error_llm_no_consume_intento(self):
        _, _, progress = self._run(
            ["", "ans", "ans2"],
            eval_side=[
                _eval_fail(error=True, puntaje=0, feedback="sin llm"),
                _eval_ok(puntaje=70),
            ],
        )
        rec = progress["cursos"]["TEST101"]["EA1"]["actividades"]["1"]
        assert rec["intentos"] == 1
        assert rec["aprobado"] is True

    def test_pregunta_no_se_evalua(self):
        with patch.object(yap, "cmd_query", return_value="ayuda del tutor") as mock_q:
            _, out, progress = self._run(
                ["", "pregunta que es un algoritmo", "saltar"],
                eval_return=_eval_ok(),
            )
        mock_q.assert_called_once()
        rec = progress["cursos"]["TEST101"]["EA1"]["actividades"]["1"]
        assert rec.get("saltada") is True
        assert rec.get("intentos", 0) == 0
        assert "Tutor" in out

    def test_asocia_sesion_si_existe_hook_21(self):
        called = {}

        def fake_asociar(curso=None, ea=None):
            called["curso"] = curso
            called["ea"] = ea
            return {"id": 1, "curso": curso, "ea": ea}

        with patch.object(yap, "sesion_asociar", fake_asociar, create=True), \
             patch("shutil.get_terminal_size", return_value=Mock(columns=80, lines=24)), \
             patch("builtins.input", side_effect=["salir"]), \
             patch("sys.stdout.write"):
            yap.iniciar_ea("TEST101", "EA1")
        assert called == {"curso": "TEST101", "ea": "EA1"}

    def test_contexto_sesion_incluye_historial(self):
        yap.HISTORY.clear()
        yap.HISTORY.append(("duda previa", "explicacion del tutor"))
        ctx = yap._contexto_sesion_activa()
        assert "duda previa" in ctx
        assert "explicacion del tutor" in ctx
        yap.HISTORY.clear()

    def test_contexto_sesion_usa_sesion_activa_si_existe(self):
        def fake_load():
            return [{"id": 7, "estado": "activa", "curso": "FPY1101", "ea": "EA1"}]

        def fake_activa(sessions):
            return sessions[0]

        with patch.object(yap, "_load_sessions", fake_load, create=True), \
             patch.object(yap, "_sesion_activa", fake_activa, create=True):
            ctx = yap._contexto_sesion_activa()
        assert "Sesion #7" in ctx
        assert "FPY1101" in ctx
        assert "EA1" in ctx


# ============================================================
# 6. yap progreso
# ============================================================

class TestCmdProgresoNotas:
    COURSE = {
        "codigo": "TEST101",
        "nombre": "Curso de Prueba",
        "horas": 10, "semanas": 2,
        "ras": [{"id": "RA1", "descripcion": "RA", "indicadores": ["IL1"]}],
        "eas": [{
            "id": "EA1", "nombre": "EA", "descripcion": "d", "horas": 4,
            "ponderacion": 100,
            "actividades": [
                {"orden": 1, "nombre": "A1", "descripcion": "d"},
                {"orden": 2, "nombre": "A2", "descripcion": "d"},
            ],
            "evaluaciones": [],
        }],
        "evaluaciones": [],
    }

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cpat = patch.object(yap, "CURSOS_DIR", self.tmpdir)
        self.ppat = patch.object(yap, "PROGRESS_FILE", os.path.join(self.tmpdir, "progress.json"))
        self.cpat.start()
        self.ppat.start()
        with open(os.path.join(self.tmpdir, "TEST101.json"), "w", encoding="utf-8") as f:
            json.dump(self.COURSE, f)

    def teardown_method(self):
        self.cpat.stop()
        self.ppat.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("shutil.get_terminal_size", return_value=Mock(columns=80, lines=24))
    def test_muestra_porcentaje_promedio_reprobadas_y_nota(self, _size):
        progress = {
            "cursos": {
                "TEST101": {
                    "EA1": {
                        "completada": True,
                        "actividad_actual": 2,
                        "puntaje_promedio": 50.0,
                        "nota_final": 3.5,
                        "actividades": {
                            "1": {
                                "puntaje": 80, "intentos": 1, "aprobado": True,
                                "fecha_aprobacion": "2026-08-19T10:00:00",
                            },
                            "2": {
                                "puntaje": 20, "intentos": 3, "aprobado": False,
                                "saltada": True,
                            },
                        },
                    }
                }
            }
        }
        yap.guardar_progreso(progress)
        out = yap.cmd_mostrar_progreso()
        assert "TEST101" in out
        assert "2/2" in out
        assert "100%" in out
        assert "promedio 50" in out
        assert "nota 3.5" in out
        assert "Reprobadas" in out
        assert "Act 2" in out
        assert "Nota curso" in out

    @patch("shutil.get_terminal_size", return_value=Mock(columns=80, lines=24))
    def test_sin_progreso(self, _size):
        out = yap.cmd_mostrar_progreso()
        assert "No hay progreso" in out


# ============================================================
# 7. INTEGRACIÓN FPY1101
# ============================================================

class TestIntegracionFPY1101:
    def setup_method(self):
        self.cpat = patch.object(yap, "CURSOS_DIR", os.path.abspath(REPO_CURSOS))
        self.cpat.start()

    def teardown_method(self):
        self.cpat.stop()

    def test_fpy1101_carga_con_schema_de_evaluacion(self):
        curso = yap.cargar_curso("FPY1101")
        assert curso["codigo"] == "FPY1101"
        assert len(curso["eas"]) == 3

    def test_fpy1101_cubre_los_cuatro_tipos(self):
        curso = yap.cargar_curso("FPY1101")
        tipos = {
            act.get("tipo")
            for ea in curso["eas"]
            for act in ea["actividades"]
        }
        for tipo in yap.TIPOS_EVALUACION:
            assert tipo in tipos, f"FPY1101 no incluye tipo {tipo}"

    def test_todas_las_actividades_evaluables_tienen_criterios(self):
        curso = yap.cargar_curso("FPY1101")
        for ea in curso["eas"]:
            for act in ea["actividades"]:
                assert act.get("tipo") in yap.TIPOS_EVALUACION
                assert isinstance(act.get("criterios_evaluacion"), list)
                assert act["criterios_evaluacion"]
                if act["tipo"] == "opcion_multiple":
                    assert act.get("respuesta_correcta")
                    assert act.get("opciones")

    def test_opcion_multiple_de_fpy1101_sin_llm(self):
        curso = yap.cargar_curso("FPY1101")
        act = None
        for ea in curso["eas"]:
            for a in ea["actividades"]:
                if a.get("tipo") == "opcion_multiple":
                    act = a
                    break
            if act:
                break
        assert act is not None
        with patch("subprocess.run") as mock_run:
            r = yap.evaluar_actividad(
                act["respuesta_correcta"],
                act["criterios_evaluacion"],
                tipo="opcion_multiple",
                actividad=act,
            )
        mock_run.assert_not_called()
        assert r["aprobado"] is True

    def test_evaluar_respuesta_libre_de_fpy1101_con_mock(self):
        curso = yap.cargar_curso("FPY1101")
        act = curso["eas"][0]["actividades"][0]
        assert act["tipo"] == "respuesta_libre"
        with patch("subprocess.run", return_value=_llm_stdout({
            "aprobado": True,
            "puntaje": 80,
            "feedback": "Define algoritmo y da ejemplo",
            "criterios_cumplidos": act["criterios_evaluacion"],
            "criterios_fallidos": [],
            "sugerencia": "",
        })):
            r = yap.evaluar_actividad(
                "Un algoritmo es una secuencia de pasos. Entrada, proceso y salida. "
                "Ejemplo: receta de cocina.",
                act["criterios_evaluacion"],
                tipo=act["tipo"],
                actividad=act,
            )
        assert r["aprobado"] is True
        assert r["puntaje"] == 80

    def test_codigo_pseint_de_fpy1101_con_mock(self):
        curso = yap.cargar_curso("FPY1101")
        act = curso["eas"][0]["actividades"][1]
        assert act["tipo"] == "codigo_pseint"
        with patch("subprocess.run", return_value=_llm_stdout({
            "aprobado": False,
            "puntaje": 40,
            "feedback": "Falta FinAlgoritmo",
            "criterios_cumplidos": [],
            "criterios_fallidos": act["criterios_evaluacion"][:1],
            "sugerencia": "Cierra el algoritmo",
        })):
            r = yap.evaluar_actividad(
                "Algoritmo X",
                act["criterios_evaluacion"],
                tipo="codigo_pseint",
                actividad=act,
            )
        assert r["aprobado"] is False
        assert "FinAlgoritmo" in r["feedback"] or r["sugerencia"]


class TestComandosActividad:
    def test_clasifica_comandos(self):
        assert yap._comandos_actividad("") == ("vacio", "")
        assert yap._comandos_actividad("salir")[0] == "salir"
        assert yap._comandos_actividad("saltar")[0] == "saltar"
        assert yap._comandos_actividad("abrir pseint") == ("abrir", "pseint")
        assert yap._comandos_actividad("pregunta que es leer")[0] == "pregunta"
        assert yap._comandos_actividad("? duda")[0] == "pregunta"
        assert yap._comandos_actividad("print('hola')") == ("respuesta", "print('hola')")

    def test_es_evaluable(self):
        assert yap._es_evaluable({"tipo": "completar"}) is True
        assert yap._es_evaluable({"nombre": "x"}) is False

    def test_max_intentos_default_tres(self):
        assert yap._max_intentos_actividad({}) == yap.MAX_INTENTOS_ACTIVIDAD
        assert yap.MAX_INTENTOS_ACTIVIDAD == 3
        assert yap._max_intentos_actividad({"max_intentos": 2}) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
