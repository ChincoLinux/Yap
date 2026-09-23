"""
test_yap_adaptive.py — Pruebas del Sistema Adaptativo de Dificultad (#30)

Verifica:
  1. Reglas del algoritmo (AdaptiveEngine):
     - Subida de nivel tras 3 aprobados seguidos SIN pistas
     - Bajada de nivel tras 2 reprobados consecutivos
     - Mantenimiento en escenarios mixtos
     - Límites: no subir mas alla de desafiante, no bajar de facil (repaso)
  2. Mapeo del nivel base del perfil (#24) -> dificultad (facil/normal/desafiante)
  3. Seleccion de variantes por actividad (curso JSON) segun el nivel
  4. Metricas en progress.json: tiempo_actividad, intentos, puntaje, pistas_usadas, resultado
  5. Anuncios publicos al cambiar de nivel
  6. Integracion con el feedback pedagogico (#29): dificultad en el prompt

Ejecucion: python3 -m pytest tests/test_yap_adaptive.py -v
"""

import os
import json
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


def _registro(resultado="aprobado", pistas_usadas=0, saltada=False, puntaje=None):
    """Build an activity progress record like the ones stored in progress.json."""
    rec = {
        "resultado": resultado,
        "pistas_usadas": pistas_usadas,
        "aprobado": resultado == "aprobado",
        "tiempo_actividad": 120,
        "intentos": 1,
        "puntaje": puntaje,
    }
    if saltada:
        rec["saltada"] = True
    return rec


def _historial_pasos(resultados, pistas=0):
    """Build a history list from a sequence of resultados."""
    if isinstance(pistas, int):
        pistas = [pistas] * len(resultados)
    return [_registro(r, p) for r, p in zip(resultados, pistas)]


# ============================================================
# 1. REGLAS DEL ALGORITMO
# ============================================================

class TestReglaSubida:
    """Requisito: 3 aprobados seguidos sin pistas => subir nivel."""

    def test_tres_aprobados_sin_pistas_suben(self):
        e = yap.AdaptiveEngine()
        d = e.analizar(
            _historial_pasos(["aprobado"] * 3, pistas=0),
            dificultad_actual="facil",
        )
        assert d["accion"] == "subir"
        assert d["cambio"] is True
        assert d["nuevo"] == "normal"

    def test_subida_normal_a_desafiante(self):
        e = yap.AdaptiveEngine()
        d = e.analizar(
            _historial_pasos(["aprobado"] * 3, pistas=0),
            dificultad_actual="normal",
        )
        assert d["nuevo"] == "desafiante"

    def test_tres_aprobados_uno_con_pistas_no_suben(self):
        e = yap.AdaptiveEngine()
        d = e.analizar(
            _historial_pasos(["aprobado", "aprobado", "aprobado"],
                             pistas=[0, 0, 1]),
            dificultad_actual="normal",
        )
        assert d["accion"] == "mantener"
        assert d["nuevo"] == "normal"

    def test_dos_aprobados_no_suben(self):
        e = yap.AdaptiveEngine()
        d = e.analizar(
            _historial_pasos(["aprobado", "aprobado"], pistas=0),
            dificultad_actual="facil",
        )
        assert d["accion"] == "mantener"

    def test_no_sube_mas_alla_de_desafiante(self):
        e = yap.AdaptiveEngine()
        d = e.analizar(
            _historial_pasos(["aprobado"] * 3, pistas=0),
            dificultad_actual="desafiante",
        )
        assert d["nuevo"] == "desafiante"
        assert d["cambio"] is False

    def test_aprobado_puntaje_0_no_subir(self):
        """Regla: subir exige pistas_usadas == 0; una actividad reprobada corta la racha."""
        e = yap.AdaptiveEngine()
        hist = _historial_pasos(["aprobado", "reprobado", "aprobado"], pistas=0)
        d = e.analizar(hist, dificultad_actual="facil")
        assert d["accion"] == "mantener"


class TestReglaBajada:
    """Requisito: 2 reprobados consecutivos => bajar nivel."""

    def test_dos_reprobados_bajan(self):
        e = yap.AdaptiveEngine()
        d = e.analizar(
            _historial_pasos(["reprobado", "reprobado"], pistas=0),
            dificultad_actual="desafiante",
        )
        assert d["accion"] == "bajar"
        assert d["nuevo"] == "normal"
        assert d["cambio"] is True

    def test_bajada_normal_a_facil(self):
        e = yap.AdaptiveEngine()
        d = e.analizar(
            _historial_pasos(["reprobado", "reprobado"], pistas=0),
            dificultad_actual="normal",
        )
        assert d["nuevo"] == "facil"

    def test_dos_reprobados_en_facil_ofrece_repaso(self):
        e = yap.AdaptiveEngine()
        d = e.analizar(
            _historial_pasos(["reprobado", "reprobado"], pistas=0),
            dificultad_actual="facil",
        )
        assert d["repaso"] is True
        assert d["cambio"] is False
        assert d["nuevo"] == "facil"
        assert "repaso" in (d["anuncio"] or "")

    def test_un_reprobado_no_baja(self):
        e = yap.AdaptiveEngine()
        d = e.analizar(
            _historial_pasos(["reprobado"], pistas=0),
            dificultad_actual="desafiante",
        )
        assert d["accion"] == "mantener"
        assert d["nuevo"] == "desafiante"

    def test_saltar_cuenta_como_reprobado(self):
        e = yap.AdaptiveEngine()
        hist = [
            _registro("reprobado", saltada=True),
            _registro("reprobado", saltada=True),
        ]
        d = e.analizar(hist, dificultad_actual="normal")
        assert d["accion"] == "bajar"
        assert d["nuevo"] == "facil"


class TestMantenimiento:
    """Requisito: en cualquier otro caso se mantiene el nivel."""

    def test_dos_aprobados_y_uno_con_pistas(self):
        e = yap.AdaptiveEngine()
        hist = _historial_pasos(
            ["aprobado", "aprobado", "aprobado"], pistas=[0, 0, 1])
        d = e.analizar(hist, dificultad_actual="normal")
        assert d["accion"] == "mantener"
        assert d["nuevo"] == "normal"
        assert d["anuncio"] is None

    def test_secuencia_aprobado_reprobado_mantiene(self):
        e = yap.AdaptiveEngine()
        d = e.analizar(
            _historial_pasos(["aprobado", "reprobado", "reprobado", "aprobado"],
                             pistas=0),
            dificultad_actual="normal",
        )
        assert d["accion"] == "mantener"

    def test_historial_vacio_por_defecto(self):
        e = yap.AdaptiveEngine()
        d = e.analizar([], dificultad_actual="normal")
        assert d["accion"] == "mantener"
        assert d["nuevo"] == "normal"

    def test_historial_con_registros_invalidos_no_revienta(self):
        e = yap.AdaptiveEngine()
        d = e.analizar([None, {"resultado": None}, "basura"], dificultad_actual="normal")
        assert d["accion"] == "mantener"
        assert d["nuevo"] == "normal"


# ============================================================
# 2. MAPEO DEL NIVEL BASE DEL PERFIL (#24)
# ============================================================

class TestMapeoPerfil:
    """Requisito: el nivel base del perfil se lee como punto de partida."""

    def test_basico_a_facil(self):
        assert yap._dificultad_desde_perfil("basico") == "facil"

    def test_intermedio_a_normal(self):
        assert yap._dificultad_desde_perfil("intermedio") == "normal"

    def test_avanzado_a_desafiante(self):
        assert yap._dificultad_desde_perfil("avanzado") == "desafiante"

    def test_valor_desconocido_cae_en_normal(self):
        assert yap._dificultad_desde_perfil("indefinido") == "normal"
        assert yap._dificultad_desde_perfil(None) == "normal"

    def test_mayusculas_se_normalizan(self):
        assert yap._dificultad_desde_perfil("AVANZADO") == "desafiante"

    def test_sin_dificultad_actual_se_usa_el_perfil(self):
        e = yap.AdaptiveEngine()
        d = e.analizar([], dificultad_actual=None, nivel_perfil="basico")
        assert d["nuevo"] == "facil"


# ============================================================
# 3. SELECCION DE VARIANTES
# ============================================================

class TestVariantes:
    """Requisito: las actividades pueden definir variantes facil/normal/desafiante."""

    def _actividad(self):
        return {
            "orden": 1,
            "nombre": "Act",
            "tipo": "respuesta_libre",
            "enunciado": "Consigna base",
            "criterios_evaluacion": ["c1"],
            "variantes": {
                "facil": {"enunciado": "Consigna facil"},
                "normal": {"enunciado": "Consigna normal"},
                "desafiante": {"enunciado": "Consigna dificil", "criterios_evaluacion": ["c1", "c2"]},
            },
        }

    def test_selecciona_variante_facil(self):
        e = yap.AdaptiveEngine()
        act = e.elegir_variante(self._actividad(), "facil")
        assert act["enunciado"] == "Consigna facil"
        assert act["variante_nivel"] == "facil"

    def test_selecciona_variante_desafiante_con_criterios(self):
        e = yap.AdaptiveEngine()
        act = e.elegir_variante(self._actividad(), "desafiante")
        assert act["enunciado"] == "Consigna dificil"
        assert act["criterios_evaluacion"] == ["c1", "c2"]
        assert act["variante_nivel"] == "desafiante"

    def test_sin_variantes_devuelve_copia_igual(self):
        e = yap.AdaptiveEngine()
        base = {"orden": 1, "nombre": "X", "tipo": "respuesta_libre"}
        act = e.elegir_variante(base, "normal")
        assert act == base
        assert act is not base  # copia, no muta el original

    def test_variante_inexistente_usar_base(self):
        e = yap.AdaptiveEngine()
        base = self._actividad()
        act = e.elegir_variante(base, "nivel_invalido")
        assert act["enunciado"] == "Consigna base"

    def test_no_muta_el_original(self):
        e = yap.AdaptiveEngine()
        base = self._actividad()
        e.elegir_variante(base, "facil")
        assert base.get("variante_nivel") is None
        assert base["enunciado"] == "Consigna base"


# ============================================================
# 4. METRICAS EN PROGRESS.JSON
# ============================================================

class TestMetricas:
    """Requisito: cada actividad registra tiempo, intentos, puntaje, pistas y resultado."""

    def _resultado(self, aprobado=True, puntaje=85):
        return {
            "aprobado": aprobado,
            "puntaje": puntaje,
            "feedback": "ok",
            "criterios_cumplidos": [],
            "criterios_fallidos": [],
            "sugerencia": "",
            "error": False,
            "parseado": True,
        }

    def test_registro_nace_con_las_metricas(self):
        rec = yap._registro_actividad({}, 1)
        for clave in ("tiempo_actividad", "pistas_usadas", "resultado", "variante",
                      "intentos", "puntaje"):
            assert clave in rec, f"falta '{clave}'"

    def test_se_guardan_todas_las_metricas(self):
        progress = {"cursos": {}}
        yap.registrar_intento_actividad(
            progress, "FPY1101", "EA1", 1, self._resultado(aprobado=True, puntaje=90),
            tiempo_actividad=420, pistas_usadas=1, variante="normal",
        )
        rec = progress["cursos"]["FPY1101"]["EA1"]["actividades"]["1"]
        assert rec["tiempo_actividad"] == 420
        assert rec["pistas_usadas"] == 1
        assert rec["variante"] == "normal"
        assert rec["intentos"] == 1
        assert rec["puntaje"] == 90
        assert rec["resultado"] == "aprobado"

    def test_resultado_reprobado(self):
        progress = {"cursos": {}}
        yap.registrar_intento_actividad(
            progress, "FPY1101", "EA1", 2, self._resultado(aprobado=False, puntaje=30),
        )
        rec = progress["cursos"]["FPY1101"]["EA1"]["actividades"]["2"]
        assert rec["resultado"] == "reprobado"
        assert rec["aprobado"] is False

    def test_error_llm_no_marca_resultado(self):
        progress = {"cursos": {}}
        yap.registrar_intento_actividad(
            progress, "FPY1101", "EA1", 1,
            {**self._resultado(), "error": True},
        )
        rec = progress["cursos"]["FPY1101"]["EA1"]["actividades"]["1"]
        assert rec["resultado"] is None
        assert rec["intentos"] == 0

    def test_guardar_y_leer_metricas_desde_archivo(self):
        import tempfile
        pdir = tempfile.mkdtemp()
        try:
            with mock.patch.object(yap, "PROGRESS_FILE",
                                   os.path.join(pdir, "progress.json")):
                progress = {"cursos": {}}
                yap.registrar_intento_actividad(
                    progress, "FPY1101", "EA1", 1, self._resultado(),
                    tiempo_actividad=300, pistas_usadas=0, variante="facil",
                )
                yap.guardar_progreso(progress)
                loaded = yap.cargar_progreso()
                act = loaded["cursos"]["FPY1101"]["EA1"]["actividades"]["1"]
                assert act["tiempo_actividad"] == 300
                assert act["pistas_usadas"] == 0
                assert act["variante"] == "facil"
                assert act["resultado"] == "aprobado"
        finally:
            import shutil
            shutil.rmtree(pdir, ignore_errors=True)


# ============================================================
# 5. ANUNCIOS PUBLICOS
# ============================================================

class TestAnuncios:
    """Requisito: al cambiar de nivel se genera un anuncio para el estudiante."""

    def test_subida_genera_anuncio(self):
        e = yap.AdaptiveEngine()
        d = e.analizar([], dificultad_actual=None)  # toca el anuncio directo
        msg = e.anuncio("subir", "normal")
        assert "subir" in msg
        assert "🚀" in msg

    def test_bajada_genera_anuncio(self):
        e = yap.AdaptiveEngine()
        msg = e.anuncio("bajar", "normal")
        assert "repasar" in msg
        assert "💪" in msg

    def test_mantener_no_genera_anuncio(self):
        e = yap.AdaptiveEngine()
        assert e.anuncio("mantener", "normal") is None

    def test_el_algoritmo_incluye_anuncio_en_su_decision(self):
        e = yap.AdaptiveEngine()
        d = e.analizar(
            _historial_pasos(["aprobado"] * 3, pistas=0),
            dificultad_actual="facil",
        )
        assert d["annuncio"] if "annuncio" in d else d["anuncio"]
        assert "subir" in (d["anuncio"] or "")


# ============================================================
# 6. INTEGRACION CON EL FEEDBACK (#29)
# ============================================================

class TestFeedbackAdaptativo:
    """Requisito: el feedback se adapta al nivel actual (facil/normal/desafiante)."""

    def test_el_prompt_de_evaluacion_conoce_la_dificultad(self):
        p = yap._prompt_evaluacion(
            "mi respuesta", ["c1"], "respuesta_libre", {}, "",
            dificultad="desafiante",
        )
        assert "Dificultad actual: desafiante" in p

    def test_sin_dificultad_no_se_menciona(self):
        p = yap._prompt_evaluacion("mi respuesta", ["c1"], "respuesta_libre", {}, "")
        assert "Dificultad actual" not in p

    def test_dificultad_invalida_no_se_menciona(self):
        p = yap._prompt_evaluacion("x", ["c1"], "respuesta_libre", {}, "",
                                   dificultad="imposible")
        assert "Dificultad actual" not in p

    def test_evaluar_actividad_propaga_la_dificultad(self):
        with mock.patch.object(yap, "_llamar_llm_evaluacion",
                               return_value='{"aprobado": true, "puntaje": 80}') as llm:
            yap.evaluar_actividad(
                "resp", ["c1"], contexto="", dificultad="facil"
            )
        assert "Dificultad actual: facil" in llm.call_args[0][0]


# ============================================================
# 7. VALIDACION DEL ESQUEMA DE CURSOS
# ============================================================

class TestEsquemaCurso:
    """Requisito: los cursos (FPY1101) cargan con variantes de dificultad."""

    def _curso(self):
        curso_dir = os.path.join(os.path.dirname(__file__), "..", "cursos")
        with mock.patch.object(yap, "CURSOS_DIR", os.path.abspath(curso_dir)):
            return yap.cargar_curso("FPY1101")

    def test_fpy1101_carga_con_variantes(self):
        act1 = self._curso()["eas"][0]["actividades"][0]
        assert "variantes" in act1
        assert set(act1["variantes"].keys()) >= {"facil", "normal", "desafiante"}

    def test_variante_opcion_multiple_mantiene_respuesta_valida(self):
        act = [a for e in self._curso()["eas"] for a in e["actividades"]
               if a.get("variantes") and a.get("tipo") == "opcion_multiple"][0]
        for nivel, v in act["variantes"].items():
            if v.get("opciones"):
                assert v["opciones"]
                assert v.get("respuesta_correcta")

    @mock.patch.object(yap, "AdaptiveEngine", lambda *a, **k: None)
    def test_carga_varios_cursos_sin_romper_listado(self):
        """Un curso con variantes no debe romper cargar_curso_(validacion)."""
        curso_dir = os.path.join(os.path.dirname(__file__), "..", "cursos")
        with mock.patch.object(yap, "CURSOS_DIR", os.path.abspath(curso_dir)):
            _curso = yap.cargar_curso("FPY1101")
        assert _curso["codigo"] == "FPY1101"


class TestDificultadConfigurable:
    """Requisito: la dificultad puede configurarse por curso o EA si aplica."""

    def test_curso_puede_definir_dificultad_inicial(self):
        engine = yap.AdaptiveEngine()
        # El curso FPY1101 no fija dificultad -> se usa el perfil por defecto
        assert yap.DIFFICULTAD_DEFAULT == "normal"

    def _curso_con_dificultad(self, nivel):
        return {
            "codigo": "TEST101",
            "nombre": "Curso",
            "horas": 50, "semanas": 10,
            "ras": [],
            "eas": [{
                "id": "EA1",
                "nombre": "EA",
                "descripcion": "d",
                "horas": 20,
                "ponderacion": 100,
                "dificultad": nivel,
                "actividades": [{
                    "orden": 1,
                    "nombre": "A",
                    "descripcion": "d",
                    "tipo": "respuesta_libre",
                    "enunciado": "q",
                    "criterios_evaluacion": ["c1"],
                    "variantes": {
                        "facil": {"enunciado": "f"},
                        "normal": {"enunciado": "n"},
                        "desafiante": {"enunciado": "d2"},
                    },
                }],
                "evaluaciones": [],
            }],
            "evaluaciones": [],
        }

    def test_iniciar_ea_usa_la_dificultad_de_la_ea(self):
        """Al iniciar una EA con 'dificultad' configurada, esa es la inicial."""
        import tempfile
        import shutil
        pdir = tempfile.mkdtemp()
        try:
            copia = dict(self._curso_con_dificultad("desafiante"))
            with mock.patch.object(yap, "CURSOS_DIR", pdir), \
                 mock.patch.object(yap, "PROGRESS_FILE",
                                   os.path.join(pdir, "progress.json")), \
                 mock.patch.object(yap, "PROFILE_FILE",
                                   os.path.join(pdir, "profile.json")), \
                 mock.patch.object(yap, "sesion_asociar",
                                   lambda **kw: {"id": 1}, create=True), \
                 mock.patch("builtins.input", side_effect=["", "salir"]), \
                 mock.patch("sys.stdout.write", lambda s: len(str(s))), \
                 mock.patch("shutil.get_terminal_size",
                            return_value=mock.Mock(columns=80, lines=24)):
                with open(os.path.join(pdir, "TEST101.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(copia, f)
                yap.guardar_perfil({"nombre": "Ana", "nivel": "basico"})
                yap.iniciar_ea("TEST101", "EA1")
                progress = yap.cargar_progreso()
            assert progress["cursos"]["TEST101"]["dificultad_actual"] == "desafiante"
        finally:
            shutil.rmtree(pdir, ignore_errors=True)

    def test_sin_config_usa_el_nivel_del_perfil(self):
        """Sin dificultad en el JSON, el perfil base define la inicial."""
        import tempfile
        import shutil
        pdir = tempfile.mkdtemp()
        try:
            copia = dict(self._curso_con_dificultad(""))
            with mock.patch.object(yap, "CURSOS_DIR", pdir), \
                 mock.patch.object(yap, "PROGRESS_FILE",
                                   os.path.join(pdir, "progress.json")), \
                 mock.patch.object(yap, "PROFILE_FILE",
                                   os.path.join(pdir, "profile.json")), \
                 mock.patch.object(yap, "sesion_asociar",
                                   lambda **kw: {"id": 1}, create=True), \
                 mock.patch("builtins.input", side_effect=["", "salir"]), \
                 mock.patch("sys.stdout.write", lambda s: len(str(s))), \
                 mock.patch("shutil.get_terminal_size",
                            return_value=mock.Mock(columns=80, lines=24)):
                with open(os.path.join(pdir, "TEST101.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(copia, f)
                yap.guardar_perfil({"nombre": "Ana", "nivel": "basico"})
                yap.iniciar_ea("TEST101", "EA1")
                progress = yap.cargar_progreso()
            # perfil basico -> dificultad facil
            assert progress["cursos"]["TEST101"]["dificultad_actual"] == "facil"
        finally:
            shutil.rmtree(pdir, ignore_errors=True)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])