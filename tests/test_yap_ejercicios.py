"""
test_yap_ejercicios.py — Ejercicios interactivos con validacion (#27)

Cubre parser v1/v2, los 4 tipos, pistas, progress.json, CLI y el hook EA.
El LLM se mockea; nunca se invoca llama-cli.
"""

import json
import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


REPO_CONF = os.path.join(
    os.path.dirname(__file__), "..", "whitelist", "pseint", "ejercicios.conf"
)


def _v2_block(eid, tipo, extra=""):
    return (
        f"[{eid}]\n"
        f"titulo=Titulo {eid}\n"
        f"tipo={tipo}\n"
        f"enunciado=Enunciado de {eid}\n"
        "pista1=concepto\n"
        "pista2=parcial\n"
        "pista3=casi solucion\n"
        f"{extra}"
    )


class _EjerciciosBase:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.exercises_path = os.path.join(self.tmpdir, "ejercicios.conf")
        self.progress_path = os.path.join(self.tmpdir, "progress.json")
        self.cursos_dir = os.path.join(self.tmpdir, "cursos")
        os.makedirs(self.cursos_dir, exist_ok=True)
        self._p_ex = patch.object(yap, "PSEINT_EXERCISES", self.exercises_path)
        self._p_pr = patch.object(yap, "PROGRESS_FILE", self.progress_path)
        self._p_cu = patch.object(yap, "CURSOS_DIR", self.cursos_dir)
        self._p_ex.start()
        self._p_pr.start()
        self._p_cu.start()

    def teardown_method(self):
        self._p_ex.stop()
        self._p_pr.stop()
        self._p_cu.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, content):
        with open(self.exercises_path, "w", encoding="utf-8") as f:
            f.write(content)


# ============================================================
# Parser v1 + v2
# ============================================================

class TestParserEjercicios(_EjerciciosBase):
    def test_v2_bloque_completo(self):
        self._write(_v2_block(
            "hola_mundo", "codigo_pseint",
            "solucion=Algoritmo X\ncriterio=Usa Algoritmo\nvalidacion=llm\n",
        ))
        ej = yap.cargar_ejercicios()
        assert len(ej) == 1
        assert ej[0]["id"] == "hola_mundo"
        assert ej[0]["tipo"] == "codigo_pseint"
        assert ej[0]["formato"] == "v2"
        assert ej[0]["pistas"] == ["concepto", "parcial", "casi solucion"]
        assert ej[0]["criterios"] == ["Usa Algoritmo"]
        assert "Algoritmo X" in ej[0]["solucion"]

    def test_v1_oneliner(self):
        self._write("Hola Mundo:Escribe un programa\nSuma:Suma dos|Paso 1; Paso 2\n")
        ej = yap.cargar_ejercicios()
        assert len(ej) == 2
        assert ej[0]["formato"] == "v1"
        assert ej[0]["id"] == "hola_mundo"
        assert ej[0]["solucion"] == ""
        assert ej[1]["solucion"] == "Paso 1; Paso 2"
        assert not yap._es_ejercicio_evaluable(ej[0])

    def test_mixto_v1_y_v2(self):
        self._write(
            "Legacy:desc v1|guia\n"
            + _v2_block("nuevo", "completar", "solucion=a|b\nvalidacion=exacta\n")
        )
        ej = yap.cargar_ejercicios()
        ids = [e["id"] for e in ej]
        assert ids == ["legacy", "nuevo"]
        assert ej[0]["formato"] == "v1"
        assert ej[1]["formato"] == "v2"

    def test_ignora_comentarios(self):
        self._write("# comentario\n" + _v2_block(
            "x", "completar", "solucion=a|b\nvalidacion=exacta\n"
        ))
        assert len(yap.cargar_ejercicios()) == 1

    def test_id_duplicado_gana_el_primero(self):
        self._write(
            _v2_block("dup", "completar", "solucion=uno\nvalidacion=exacta\ntitulo=Primero\n")
            + _v2_block("dup", "completar", "solucion=dos\nvalidacion=exacta\ntitulo=Segundo\n")
        )
        # titulo= after the block start overwrites within the same block;
        # two [dup] blocks: first wins
        ej = yap.cargar_ejercicios()
        assert len(ej) == 1
        assert ej[0]["solucion"] == "uno"

    def test_opcion_multiple_sin_respuesta_se_omite(self):
        self._write(_v2_block("bad", "opcion_multiple", "opcion=A\nopcion=B\n"))
        assert yap.cargar_ejercicios() == []

    def test_v2_sin_pista3_se_omite(self):
        self._write(
            "[incompleto]\ntitulo=X\ntipo=completar\nenunciado=Y\n"
            "pista1=a\npista2=b\nsolucion=z\nvalidacion=exacta\n"
        )
        assert yap.cargar_ejercicios() == []

    def test_archivo_inexistente(self):
        os.remove(self.exercises_path) if os.path.exists(self.exercises_path) else None
        self.exercises_path = os.path.join(self.tmpdir, "no_existe.conf")
        self._p_ex.stop()
        self._p_ex = patch.object(yap, "PSEINT_EXERCISES", self.exercises_path)
        self._p_ex.start()
        assert yap.cargar_ejercicios() == []

    def test_ejercicio_por_id_rechaza_path_traversal(self):
        self._write(_v2_block(
            "hola_mundo", "completar", "solucion=a\nvalidacion=exacta\n"
        ))
        assert yap.ejercicio_por_id("../etc") is None
        assert yap.ejercicio_por_id("hola_mundo/../../passwd") is None
        assert yap.ejercicio_por_id("hola_mundo") is not None

    def test_alias_respuesta_texto(self):
        self._write(_v2_block(
            "libre", "respuesta_texto",
            "criterio=Define algo\nvalidacion=llm\n",
        ))
        ej = yap.cargar_ejercicios()
        assert ej[0]["tipo"] == "respuesta_libre"

    def test_catalogo_repo_cubre_cuatro_tipos(self):
        with patch.object(yap, "PSEINT_EXERCISES", os.path.abspath(REPO_CONF)):
            ej = yap.cargar_ejercicios()
        tipos = {_alias for _alias in (yap._alias_tipo(e["tipo"]) for e in ej)}
        for t in ("codigo_pseint", "respuesta_libre", "opcion_multiple", "completar"):
            assert t in tipos, f"falta tipo {t} en el catalogo"


# ============================================================
# Validacion exacta y LLM (mock)
# ============================================================

class TestEvaluarEjercicio(_EjerciciosBase):
    def test_opcion_multiple_correcta_sin_llm(self):
        ej = {
            "tipo": "opcion_multiple",
            "opciones": ["A", "B", "C", "A y B"],
            "respuesta_correcta": "A",
            "criterios": ["primera condicion"],
            "validacion": "exacta",
        }
        with patch.object(yap, "_llamar_llm_evaluacion") as mock_llm:
            r = yap.evaluar_ejercicio(ej, "A")
            mock_llm.assert_not_called()
        assert r["aprobado"] is True
        assert r["puntaje"] == 100

    def test_opcion_multiple_incorrecta(self):
        ej = {
            "tipo": "opcion_multiple",
            "opciones": ["A", "B", "C"],
            "respuesta_correcta": "A",
            "validacion": "exacta",
        }
        r = yap.evaluar_ejercicio(ej, "B")
        assert r["aprobado"] is False
        assert r["puntaje"] == 0

    def test_opcion_multiple_letra_y_indice(self):
        ej = {
            "tipo": "opcion_multiple",
            "opciones": ["A", "B", "C"],
            "respuesta_correcta": "A",
            "validacion": "exacta",
        }
        assert yap.evaluar_ejercicio(ej, "a")["aprobado"] is True
        assert yap.evaluar_ejercicio(ej, "1")["aprobado"] is True
        assert yap.evaluar_ejercicio(ej, "A)")["aprobado"] is True

    def test_completar_huecos_orden_y_tildes(self):
        ej = {
            "tipo": "completar",
            "solucion": "entrada|proceso|salida",
            "validacion": "exacta",
            "criterios": ["entrada", "proceso", "salida"],
        }
        with patch.object(yap, "_llamar_llm_evaluacion") as mock_llm:
            r = yap.evaluar_ejercicio(ej, "Salida, Proceso y Entrada")
            mock_llm.assert_not_called()
        assert r["aprobado"] is True
        r2 = yap.evaluar_ejercicio(ej, "solo entrada")
        assert r2["aprobado"] is False

    def test_codigo_pseint_exacta_normalizada(self):
        ej = {
            "tipo": "codigo_pseint",
            "solucion": "Algoritmo X\n  Escribir 1\nFinAlgoritmo",
            "validacion": "exacta",
        }
        r = yap.evaluar_ejercicio(ej, "algoritmo x escribir 1 finalgoritmo")
        assert r["aprobado"] is True

    def test_respuesta_libre_usa_llm(self):
        ej = {
            "tipo": "respuesta_libre",
            "enunciado": "Que es un algoritmo",
            "criterios": ["Define algoritmo"],
            "titulo": "Algo",
            "validacion": "llm",
        }
        payload = (
            '{"aprobado": true, "puntaje": 90, "feedback": "Bien",'
            ' "criterios_cumplidos": ["Define algoritmo"],'
            ' "criterios_fallidos": [], "sugerencia": ""}'
        )
        with patch.object(yap, "_llamar_llm_evaluacion", return_value=payload) as mock_llm:
            r = yap.evaluar_ejercicio(ej, "Un algoritmo es una secuencia de pasos")
            mock_llm.assert_called_once()
        assert r["aprobado"] is True
        assert r["puntaje"] == 90

    def test_codigo_pseint_llm(self):
        ej = {
            "tipo": "codigo_pseint",
            "enunciado": "Hola mundo",
            "criterios": ["Usa Escribir"],
            "titulo": "Hola",
            "validacion": "llm",
        }
        payload = (
            '{"aprobado": false, "puntaje": 40, "feedback": "Falta Escribir",'
            ' "criterios_cumplidos": [],'
            ' "criterios_fallidos": ["Usa Escribir"], "sugerencia": "Usa Escribir"}'
        )
        with patch.object(yap, "_llamar_llm_evaluacion", return_value=payload):
            r = yap.evaluar_ejercicio(ej, "print hola")
        assert r["aprobado"] is False
        assert "Escribir" in r["feedback"]

    def test_respuesta_vacia(self):
        r = yap.evaluar_ejercicio({"tipo": "completar", "solucion": "a"}, "")
        assert r["aprobado"] is False
        assert r["error"] is False


# ============================================================
# Pistas
# ============================================================

class TestPistas(_EjerciciosBase):
    def test_tres_niveles(self):
        ej = {"pistas": ["concepto", "parcial", "casi solucion"]}
        assert yap.pista_siguiente(ej, 0) == (1, "concepto")
        assert yap.pista_siguiente(ej, 1) == (2, "parcial")
        assert yap.pista_siguiente(ej, 2) == (3, "casi solucion")
        assert yap.pista_siguiente(ej, 3) is None

    def test_pista_no_evalua_ni_gasta_intento(self):
        self._write(_v2_block(
            "x", "completar", "solucion=entrada|proceso|salida\nvalidacion=exacta\n"
        ))
        with patch("builtins.input", side_effect=["pista", "pista", "pista", "pista", "salir"]):
            yap.cmd_ejercicios("x")
        prog = yap.cargar_progreso()
        rec = prog["ejercicios"]["x"]
        assert rec["pistas_usadas"] == 3
        assert rec["intentos"] == 0
        assert rec.get("aprobado") is False


# ============================================================
# Flujo interactivo
# ============================================================

class TestFlujoEjercicio(_EjerciciosBase):
    def test_correcto_felicita_y_completa(self):
        self._write(_v2_block(
            "x", "completar", "solucion=entrada|proceso|salida\nvalidacion=exacta\n"
        ))
        with patch("builtins.input", side_effect=["entrada proceso salida"]):
            yap.cmd_ejercicios("x")
        rec = yap.cargar_progreso()["ejercicios"]["x"]
        assert rec["aprobado"] is True
        assert rec["completado"] is True
        assert rec["intentos"] == 1

    def test_incorrecto_permite_reintento(self):
        self._write(_v2_block(
            "x", "completar", "solucion=ok\nvalidacion=exacta\n"
        ))
        with patch("builtins.input", side_effect=["malo", "ok"]):
            yap.cmd_ejercicios("x")
        rec = yap.cargar_progreso()["ejercicios"]["x"]
        assert rec["aprobado"] is True
        assert rec["intentos"] == 2

    def test_tres_fallos_solo_saltar(self):
        self._write(_v2_block(
            "x", "completar", "solucion=ok\nvalidacion=exacta\nmax_intentos=3\n"
        ))
        with patch("builtins.input", side_effect=["a", "b", "c", "ok", "saltar"]):
            yap.cmd_ejercicios("x")
        rec = yap.cargar_progreso()["ejercicios"]["x"]
        assert rec["aprobado"] is False
        assert rec["saltado"] is True
        assert rec["intentos"] == 3

    def test_error_llm_no_incrementa_intentos(self):
        self._write(_v2_block(
            "lib", "respuesta_libre",
            "criterio=Define\nvalidacion=llm\n",
        ))
        with patch.object(yap, "_llamar_llm_evaluacion", return_value="[ERROR] llama-cli"):
            with patch("builtins.input", side_effect=["una respuesta", "salir"]):
                yap.cmd_ejercicios("lib")
        rec = yap.cargar_progreso()["ejercicios"]["lib"]
        assert rec["intentos"] == 0
        assert rec.get("aprobado") is False

    def test_saltar_puntaje_cero(self):
        self._write(_v2_block(
            "x", "completar", "solucion=ok\nvalidacion=exacta\n"
        ))
        with patch("builtins.input", side_effect=["saltar"]):
            yap.cmd_ejercicios("x")
        rec = yap.cargar_progreso()["ejercicios"]["x"]
        assert rec["saltado"] is True
        assert rec["puntaje"] == 0
        assert rec["completado"] is True


# ============================================================
# Progreso
# ============================================================

class TestProgresoEjercicios(_EjerciciosBase):
    def test_persiste_campos(self):
        progress = {"cursos": {}}
        yap.registrar_intento_ejercicio(
            progress, "hola",
            {"aprobado": True, "puntaje": 90, "error": False},
            pistas_usadas=1, origen="standalone", curso="FPY1101", ea="EA1",
        )
        yap.guardar_progreso(progress)
        loaded = yap.cargar_progreso()
        rec = loaded["ejercicios"]["hola"]
        assert rec["intentos"] == 1
        assert rec["pistas_usadas"] == 1
        assert rec["puntaje"] == 90
        assert rec["fecha"]
        assert rec["curso"] == "FPY1101"

    def test_progreso_viejo_solo_cursos(self):
        yap.guardar_progreso({"cursos": {"FPY1101": {"EA1": {"completada": False}}}})
        loaded = yap.cargar_progreso()
        assert "cursos" in loaded
        r = yap.resumen_ejercicios(loaded)
        assert r["total"] == 0 or isinstance(r["aprobados"], int)

    def test_escritura_atomica(self):
        yap.guardar_progreso({"cursos": {}, "ejercicios": {}})
        assert os.path.exists(self.progress_path)
        assert not os.path.exists(self.progress_path + ".tmp")

    def test_cmd_progreso_incluye_ejercicios(self, monkeypatch=None):
        self._write(_v2_block(
            "x", "completar", "solucion=ok\nvalidacion=exacta\n"
        ))
        progress = {"cursos": {}, "ejercicios": {}}
        yap.registrar_intento_ejercicio(
            progress, "x", {"aprobado": True, "puntaje": 80, "error": False}
        )
        yap.guardar_progreso(progress)
        with patch("shutil.get_terminal_size") as mock_size:
            mock_size.return_value.columns = 80
            mock_size.return_value.lines = 24
            out = yap.cmd_mostrar_progreso()
        assert "Ejercicios" in out
        assert "aprobados" in out


# ============================================================
# CLI
# ============================================================

class TestCliEjercicios(_EjerciciosBase):
    def test_lista_incluye_cuatro_tipos(self):
        self._write(
            _v2_block("a", "codigo_pseint", "criterio=x\nvalidacion=llm\n")
            + _v2_block("b", "respuesta_libre", "criterio=x\nvalidacion=llm\n")
            + _v2_block(
                "c", "opcion_multiple",
                "opcion=A\nopcion=B\nrespuesta_correcta=A\nvalidacion=exacta\n",
            )
            + _v2_block("d", "completar", "solucion=z\nvalidacion=exacta\n")
        )
        with patch("shutil.get_terminal_size") as mock_size:
            mock_size.return_value.columns = 80
            mock_size.return_value.lines = 24
            out = yap.cmd_ejercicios("lista")
        assert "codigo_pseint" in out
        assert "respuesta_libre" in out
        assert "opcion_multiple" in out
        assert "completar" in out
        assert "a" in out and "d" in out

    def test_interpret_ejercicios(self):
        assert yap.interpret("ejercicios") == ("ejercicios", "")
        assert yap.interpret("ejercicios lista") == ("ejercicios", "lista")
        assert yap.interpret("ejercicios hola_mundo") == ("ejercicios", "hola_mundo")
        assert yap.interpret("lista de ejercicios") == ("ejercicios", "lista")

    def test_id_inexistente(self):
        self._write(_v2_block("x", "completar", "solucion=z\nvalidacion=exacta\n"))
        out = yap.cmd_ejercicios("no_existe")
        assert "[ERROR]" in out


# ============================================================
# Hook EA
# ============================================================

class TestHookEA(_EjerciciosBase):
    def test_actividad_con_ejercicio_id(self):
        self._write(_v2_block(
            "partes_algoritmo", "completar",
            "solucion=entrada|proceso|salida\nvalidacion=exacta\n",
        ))
        curso = {
            "codigo": "TEST101",
            "nombre": "Curso de Prueba",
            "horas": 10, "semanas": 1,
            "ras": [{"id": "RA1", "descripcion": "RA", "indicadores": ["IL1"]}],
            "eas": [{
                "id": "EA1", "nombre": "EA", "descripcion": "desc",
                "horas": 5, "ponderacion": 100,
                "herramientas": ["PSeInt"],
                "actividades": [{
                    "orden": 1, "nombre": "Act1", "descripcion": "desc",
                    "ejercicio_id": "partes_algoritmo",
                }],
                "evaluaciones": [],
            }],
            "evaluaciones": [],
        }
        with open(os.path.join(self.cursos_dir, "TEST101.json"), "w", encoding="utf-8") as f:
            json.dump(curso, f)
        with patch("shutil.get_terminal_size") as mock_size:
            mock_size.return_value.columns = 80
            mock_size.return_value.lines = 24
            with patch("builtins.input", side_effect=["", "entrada proceso salida"]):
                yap.iniciar_ea("TEST101", "EA1")
        prog = yap.cargar_progreso()
        assert prog["ejercicios"]["partes_algoritmo"]["aprobado"] is True
        assert prog["cursos"]["TEST101"]["EA1"]["actividad_actual"] == 1
        assert prog["cursos"]["TEST101"]["EA1"]["completada"] is True


# ============================================================
# Arquitectura
# ============================================================

class TestArquitecturaEjercicios:
    def test_api_publica(self):
        for name in (
            "cargar_ejercicios", "ejercicio_por_id", "listar_ejercicios",
            "evaluar_ejercicio", "pista_siguiente", "cmd_ejercicios",
            "registrar_intento_ejercicio", "resumen_ejercicios",
        ):
            assert hasattr(yap, name) and callable(getattr(yap, name))
