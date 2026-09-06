"""
test_yap_feedback.py — Pruebas del feedback pedagógico estructurado (#29)

Verifica:
  1. Distinción entre feedback formativo y sumativo
  2. Pautas diferenciadas en el prompt del evaluador
  3. Persistencia de criterios por actividad
  4. Composición del feedback sumativo al cerrar una EA
  5. Línea de avance entre intentos
  6. Integración con la evaluación automática (#23)

Ejecucion: python3 -m pytest tests/test_yap_feedback.py -v
"""

import sys
import os
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


def _resultado(aprobado=True, puntaje=80, cumplidos=None, fallidos=None, error=False):
    """Build an evaluation result like the ones evaluar_actividad returns."""
    return {
        "aprobado": aprobado,
        "puntaje": puntaje,
        "feedback": "texto",
        "criterios_cumplidos": cumplidos or [],
        "criterios_fallidos": fallidos or [],
        "sugerencia": "",
        "error": error,
        "parseado": True,
    }


# ============================================================
# 1. TIPO DE FEEDBACK
# ============================================================

class TestTipoFeedback:
    """Requisito: distinguir feedback formativo de sumativo."""

    def test_las_constantes_existen(self):
        assert yap.FEEDBACK_FORMATIVO == "formativo"
        assert yap.FEEDBACK_SUMATIVO == "sumativo"
        assert set(yap.TIPOS_FEEDBACK) == {"formativo", "sumativo"}

    def test_por_defecto_es_formativo(self):
        """Durante la EA el feedback acompaña, no califica."""
        r = yap.evaluar_actividad("", ["c1"])
        assert r["tipo_feedback"] == yap.FEEDBACK_FORMATIVO

    def test_se_puede_pedir_sumativo(self):
        r = yap.evaluar_actividad("", ["c1"], tipo_feedback=yap.FEEDBACK_SUMATIVO)
        assert r["tipo_feedback"] == yap.FEEDBACK_SUMATIVO

    def test_un_tipo_invalido_cae_en_formativo(self):
        r = yap.evaluar_actividad("", ["c1"], tipo_feedback="inventado")
        assert r["tipo_feedback"] == yap.FEEDBACK_FORMATIVO

    def test_el_sello_alcanza_a_la_ruta_de_opcion_multiple(self):
        """Todas las rutas de evaluación deben sellar el tipo, no solo la del LLM."""
        act = {"opciones": ["a", "b"], "respuesta_correcta": "a"}
        r = yap.evaluar_actividad("a", [], tipo="opcion_multiple", actividad=act,
                                  tipo_feedback=yap.FEEDBACK_SUMATIVO)
        assert r["tipo_feedback"] == yap.FEEDBACK_SUMATIVO


# ============================================================
# 2. PAUTAS EN EL PROMPT
# ============================================================

class TestPautasDelPrompt:
    """Requisito: system prompt diferenciado por tipo de feedback."""

    def test_la_pauta_formativa_reconoce_antes_de_corregir(self):
        assert "FORMATIVO" in yap.PAUTA_FORMATIVA
        assert "hizo bien" in yap.PAUTA_FORMATIVA
        assert "reintentar" in yap.PAUTA_FORMATIVA

    def test_la_pauta_sumativa_no_invita_a_reintentar(self):
        assert "SUMATIVO" in yap.PAUTA_SUMATIVA
        assert "sin invitar a reintentar" in yap.PAUTA_SUMATIVA

    def test_el_prompt_formativo_lleva_su_pauta(self):
        p = yap._prompt_evaluacion("resp", ["c1"], "respuesta_libre", {}, "",
                                   tipo_feedback=yap.FEEDBACK_FORMATIVO)
        assert "FORMATIVO" in p
        assert "SUMATIVO" not in p

    def test_el_prompt_sumativo_lleva_su_pauta(self):
        p = yap._prompt_evaluacion("resp", ["c1"], "respuesta_libre", {}, "",
                                   tipo_feedback=yap.FEEDBACK_SUMATIVO)
        assert "SUMATIVO" in p
        assert "FORMATIVO" not in p

    def test_el_tipo_llega_hasta_el_prompt(self):
        """El parámetro debe propagarse por toda la cadena, no perderse."""
        with mock.patch.object(yap, "_llamar_llm_evaluacion", return_value="{}") as llm:
            yap.evaluar_actividad("resp", ["c1"], contexto="",
                                  tipo_feedback=yap.FEEDBACK_SUMATIVO)
        assert "SUMATIVO" in llm.call_args[0][0]


# ============================================================
# 3. PERSISTENCIA DE CRITERIOS
# ============================================================

class TestPersistenciaDeCriterios:
    """Requisito: guardar los criterios para poder componer el sumativo."""

    def test_el_registro_nace_con_los_campos_nuevos(self):
        rec = yap._registro_actividad({}, 1)
        for clave in ("criterios_cumplidos", "criterios_fallidos", "puntaje_anterior"):
            assert clave in rec, f"falta '{clave}'"

    def test_se_guardan_los_criterios_del_intento(self):
        prog = {}
        yap.registrar_intento_actividad(
            prog, "C1", "EA1", 1,
            _resultado(cumplidos=["ciclos"], fallidos=["arreglos"]),
        )
        rec = prog["cursos"]["C1"]["EA1"]["actividades"]["1"]
        assert rec["criterios_cumplidos"] == ["ciclos"]
        assert rec["criterios_fallidos"] == ["arreglos"]

    def test_se_conserva_el_puntaje_anterior(self):
        prog = {}
        yap.registrar_intento_actividad(prog, "C1", "EA1", 1, _resultado(puntaje=40))
        yap.registrar_intento_actividad(prog, "C1", "EA1", 1, _resultado(puntaje=90))
        rec = prog["cursos"]["C1"]["EA1"]["actividades"]["1"]
        assert rec["puntaje_anterior"] == 40
        assert rec["puntaje"] == 90

    def test_un_error_del_llm_no_pisa_los_criterios(self):
        """Un fallo de red no debe borrar lo que ya se había evaluado."""
        prog = {}
        yap.registrar_intento_actividad(
            prog, "C1", "EA1", 1, _resultado(cumplidos=["ciclos"]))
        yap.registrar_intento_actividad(
            prog, "C1", "EA1", 1, _resultado(error=True, cumplidos=[]))
        rec = prog["cursos"]["C1"]["EA1"]["actividades"]["1"]
        assert rec["criterios_cumplidos"] == ["ciclos"]


# ============================================================
# 4. FEEDBACK SUMATIVO
# ============================================================

class TestFeedbackSumativo:
    """Requisito: nota final con fortalezas y áreas por mejorar."""

    def _progreso(self):
        prog = {}
        yap.registrar_intento_actividad(
            prog, "C1", "EA1", 1,
            _resultado(True, 90, cumplidos=["ciclos", "variables"]))
        yap.registrar_intento_actividad(
            prog, "C1", "EA1", 2,
            _resultado(False, 40, cumplidos=["variables"], fallidos=["arreglos"]))
        return prog

    def test_sin_actividades_evaluadas(self):
        r = yap.feedback_sumativo_ea({}, "C1", "EA1")
        assert r["promedio"] is None
        assert "No hay actividades" in r["texto"]

    def test_calcula_promedio_y_nota(self):
        r = yap.feedback_sumativo_ea(self._progreso(), "C1", "EA1")
        assert r["promedio"] == 65.0
        assert r["nota"] == yap.nota_chilena(65.0)

    def test_marca_el_tipo_sumativo(self):
        r = yap.feedback_sumativo_ea(self._progreso(), "C1", "EA1")
        assert r["tipo_feedback"] == yap.FEEDBACK_SUMATIVO

    def test_separa_fortalezas_de_areas_por_mejorar(self):
        r = yap.feedback_sumativo_ea(self._progreso(), "C1", "EA1")
        assert "ciclos" in r["fortalezas"]
        assert "arreglos" in r["por_mejorar"]

    def test_un_criterio_fallado_no_cuenta_como_fortaleza(self):
        """Aprobar 'variables' una vez no borra haberlo fallado en otra actividad."""
        prog = {}
        yap.registrar_intento_actividad(
            prog, "C1", "EA1", 1, _resultado(True, 80, cumplidos=["variables"]))
        yap.registrar_intento_actividad(
            prog, "C1", "EA1", 2, _resultado(False, 30, fallidos=["variables"]))
        r = yap.feedback_sumativo_ea(prog, "C1", "EA1")
        assert "variables" not in r["fortalezas"]
        assert "variables" in r["por_mejorar"]

    def test_lista_las_actividades_no_aprobadas(self):
        r = yap.feedback_sumativo_ea(self._progreso(), "C1", "EA1")
        assert r["actividades_reprobadas"] == [2]

    def test_el_texto_resume_lo_esencial(self):
        r = yap.feedback_sumativo_ea(self._progreso(), "C1", "EA1")
        assert "Nota:" in r["texto"]
        assert "Fortalezas:" in r["texto"]
        assert "A mejorar:" in r["texto"]

    def test_no_llama_al_llm(self):
        """El cierre se compone de lo registrado: en 3-8 GB una llamada extra no se justifica."""
        with mock.patch.object(yap, "_llamar_llm_evaluacion") as llm:
            yap.feedback_sumativo_ea(self._progreso(), "C1", "EA1")
        llm.assert_not_called()

    def test_finalizar_ea_guarda_el_balance(self):
        prog = self._progreso()
        ea_prog = yap._finalizar_ea(prog, "C1", "EA1")
        assert "fortalezas" in ea_prog
        assert "por_mejorar" in ea_prog
        assert ea_prog["completada"] is True


# ============================================================
# 5. AVANCE ENTRE INTENTOS
# ============================================================

class TestLineaDeAvance:
    """Requisito: feedback de progreso comparado con intentos anteriores."""

    def test_sin_intento_previo_no_hay_linea(self):
        assert yap._linea_avance({"puntaje": 70, "puntaje_anterior": None}) == ""

    def test_mejora(self):
        linea = yap._linea_avance({"puntaje": 80, "puntaje_anterior": 50})
        assert "Avance" in linea and "+30" in linea

    def test_retroceso(self):
        linea = yap._linea_avance({"puntaje": 40, "puntaje_anterior": 70})
        assert "Retroceso" in linea

    def test_sin_cambio(self):
        assert "Sin cambio" in yap._linea_avance({"puntaje": 60, "puntaje_anterior": 60})

    def test_registro_invalido_no_revienta(self):
        assert yap._linea_avance(None) == ""
        assert yap._linea_avance({"puntaje": "x", "puntaje_anterior": 10}) == ""


# ============================================================
# 6. PRESENTACIÓN
# ============================================================

class TestPresentacion:
    """Requisito: plantillas pedagógicas legibles para el estudiante."""

    def test_el_resultado_formativo_muestra_el_avance(self):
        salida = yap._mostrar_resultado_evaluacion(
            _resultado(False, 60), 2, 3,
            registro={"puntaje": 60, "puntaje_anterior": 30},
        )
        assert "Avance" in salida

    def test_sin_registro_no_muestra_avance(self):
        salida = yap._mostrar_resultado_evaluacion(_resultado(False, 60), 1, 3)
        assert "Avance" not in salida

    def test_el_sumativo_muestra_nota_y_balance(self):
        prog = {}
        yap.registrar_intento_actividad(
            prog, "C1", "EA1", 1,
            _resultado(True, 90, cumplidos=["ciclos"], fallidos=["arreglos"]))
        salida = yap._mostrar_feedback_sumativo(
            yap.feedback_sumativo_ea(prog, "C1", "EA1"), "EA1: Algoritmos")
        assert "Nota final" in salida
        assert "ciclos" in salida
        assert "arreglos" in salida

    def test_el_sumativo_sin_datos_no_revienta(self):
        salida = yap._mostrar_feedback_sumativo(
            yap.feedback_sumativo_ea({}, "C1", "EA1"))
        assert "No hay actividades" in salida
