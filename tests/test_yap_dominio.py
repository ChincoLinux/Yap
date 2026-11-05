"""
test_yap_dominio.py — Consultas fuera del ámbito del curso (#278)

Ante «¿qué es el VAN y el TIR de un proyecto?», sin material en el RAG, el
modelo inventaba una respuesta: el prompt del sistema solo nombraba ChincoLinux
y no acotaba el ámbito.

Pedirle al modelo que decidiera si una pregunta es del curso no funcionó: con
1B siguió inventando, y con 3B empezó a rechazar seguimientos legítimos como
«¿y para qué sirve?». Por eso la decisión la toma el código, igual que las
rutas de teclado de interpret(), y el modelo solo recibe lo que pasa el filtro.

Verifica:
  1. El prompt del sistema delimita el ámbito y ya no se sesga hacia Linux
  2. El filtro rechaza solo cuando nada ata la pregunta al curso
  3. Se inclina por responder: vocabulario, RAG, charla y seguimientos pasan
  4. Se aplica en las entradas de la pregunta libre, y en ninguna otra
  5. El mensaje al estudiante ofrece el curso, cómo reformular y `busca`

Las pruebas no ejecutan el modelo. El comportamiento con el modelo real se
midió aparte y está en la descripción de la PR.

Ejecución: python3 -m pytest tests/test_yap_dominio.py -v
"""

import inspect
import io
import json
import os
import shutil
import sys
import tempfile
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap
import yap_core

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAG = "[Contexto recuperado por RAG local]\n— [FPY1101.json] Una variable guarda un valor."

FUERA_DEL_CURSO = [
    "que es el van y el tir de un proyecto?",
    "quien gano el mundial de futbol de 2010?",
    "como se prepara una cazuela de vacuno?",
    "que medicamento tomo para el dolor de cabeza?",
    "que es la fotosintesis?",
    "que es el ebitda de una empresa?",
]
DEL_CURSO_SIN_RAG = [
    "que es la recursividad?",
    "que diferencia hay entre un for y un while?",
    "que es un bucle infinito?",
    "para que sirve un arreglo?",
    "como saco el factorial de 5?",
    "como hago la tabla de multiplicar del 7?",
]


def catalogo(lang):
    with io.open(os.path.join(RAIZ, "i18n", lang + ".json"), encoding="utf-8") as f:
        return json.load(f)


class BaseDominio:
    """Perfil aislado, español, sin historial y RAG controlado."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.patchers = [
            mock.patch.object(yap, "PROFILE_FILE", os.path.join(self.tmpdir, "profile.json")),
            mock.patch.object(yap, "TELEMETRY_FILE", os.path.join(self.tmpdir, "telemetry.json")),
        ]
        for p in self.patchers:
            p.start()
        yap.set_lang("es", persist=False)
        yap.HISTORY.clear()

    def teardown_method(self):
        yap.HISTORY.clear()
        yap.set_lang("es", persist=False)
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def fuera(self, pregunta, rag=None):
        with mock.patch.object(yap, "_rag_context_for_query", return_value=rag):
            return yap._fuera_de_ambito(pregunta)


# ============================================================
# 1. EL PROMPT DEL SISTEMA
# ============================================================

class TestPromptConAmbito(BaseDominio):
    """Requisito: el prompt acota el ámbito y no sesga hacia Linux."""

    def test_ya_no_nombra_chincolinux(self):
        """Nombrarlo como único tema hacía que todo lo desconocido fuera «Linux»."""
        assert "ChincoLinux" not in yap.SYSTEM_PROMPT
        assert "ChincoLinux" not in catalogo("es")["llm"]["system_prompt"]
        assert "ChincoLinux" not in catalogo("en")["llm"]["system_prompt"]

    def test_declara_el_ambito(self):
        for termino in ("algoritmos", "PSeInt", "Python"):
            assert termino in yap.SYSTEM_PROMPT, termino

    def test_prohibe_inventar(self):
        assert "No inventes" in yap.SYSTEM_PROMPT

    def test_permite_resumir_textos_de_otros_temas(self):
        """`busca fotosintesis` resume Wikipedia: el ámbito no puede impedirlo."""
        assert "resumir" in yap.SYSTEM_PROMPT

    def test_la_constante_coincide_con_el_catalogo(self):
        """El texto vive en dos sitios; si divergen, el selector de idioma falla."""
        assert yap.SYSTEM_PROMPT == catalogo("es")["llm"]["system_prompt"]

    def test_ingles_mantiene_el_ambito(self):
        prompt = catalogo("en")["llm"]["system_prompt"]
        for termino in ("PSeInt", "Python", "Do not make up"):
            assert termino in prompt, termino

    def test_system_prompt_ya_no_lleva_una_copia_literal(self):
        """Antes comparaba contra una copia del texto escrita a mano."""
        fuente = inspect.getsource(yap._system_prompt)
        assert "Eres Yap" not in fuente
        assert "_SYSTEM_PROMPT_POR_DEFECTO" in fuente

    def test_sigue_el_idioma_del_perfil(self):
        yap.set_lang("en", persist=False)
        assert "educational assistant in English" in yap._system_prompt()


# ============================================================
# 2. EL FILTRO RECHAZA LO QUE NO TIENE NADA DEL CURSO
# ============================================================

class TestRechaza(BaseDominio):
    """Requisito: sin vocabulario ni material, no se le pregunta al modelo."""

    def test_el_caso_del_issue(self):
        assert self.fuera("que es el van y el tir de un proyecto?") is True

    def test_preguntas_fuera_del_curso(self):
        for q in FUERA_DEL_CURSO:
            assert self.fuera(q) is True, q

    def test_en_ingles(self):
        yap.set_lang("en", persist=False)
        for q in ("how do I cook a beef stew?", "what is the net present value of a project?"):
            assert self.fuera(q) is True, q

    def test_una_pregunta_nueva_tras_hablar_de_programacion(self):
        """El historial no abre la puerta a cualquier tema."""
        yap.HISTORY.append(("que es la recursividad?", "Una funcion que se llama a si misma."))
        assert self.fuera("que es la fotosintesis?") is True


# ============================================================
# 3. SE INCLINA POR RESPONDER
# ============================================================

class TestDejaPasar(BaseDominio):
    """Requisito: ante la duda, la pregunta va al modelo."""

    def test_preguntas_del_curso_sin_material(self):
        for q in DEL_CURSO_SIN_RAG:
            assert self.fuera(q) is False, q

    def test_con_material_del_rag_aunque_no_haya_vocabulario(self):
        assert self.fuera("como se hace esto?", rag=RAG) is False

    def test_no_consulta_el_rag_si_ya_hay_vocabulario(self):
        with mock.patch.object(yap, "_rag_context_for_query") as rag:
            yap._fuera_de_ambito("que es la recursividad?")
        rag.assert_not_called()

    def test_tildes_mayusculas_y_signos(self):
        """Como escribe un alumno de verdad."""
        for q in ("¿Qué es una función recursiva?", "¿Cómo declaro una VARIABLE en PSeInt?"):
            assert self.fuera(q) is False, q

    def test_mensajes_cortos(self):
        for q in ("hola", "gracias", "como estas?", "ok"):
            assert self.fuera(q) is False, q

    def test_charla_con_yap(self):
        for q in ("quien eres tu?", "que puedes hacer?", "muchas gracias por todo"):
            assert self.fuera(q) is False, q

    def test_seguimientos_con_historial(self):
        """Fue lo que rompió la versión que delegaba en el modelo."""
        yap.HISTORY.append(("que es la recursividad?", "Una funcion que se llama a si misma."))
        for q in ("y para que sirve?", "dame un ejemplo", "no entendi, explicame de nuevo"):
            assert self.fuera(q) is False, q

    def test_sin_historial_un_seguimiento_no_tiene_a_que_referirse(self):
        assert self.fuera("y para que sirve?") is True

    def test_mencionar_el_curso_basta_para_pasar(self):
        """Es la salida que el mensaje le ofrece al alumno."""
        assert self.fuera("como compruebo si una palabra es palindromo?") is True
        assert self.fuera("como compruebo si una palabra es palindromo en pseint?") is False

    def test_mapudungun_queda_sin_filtro(self):
        """El vocabulario es español e inglés: en arn se rechazaría todo."""
        yap.set_lang("arn", persist=False)
        assert self.fuera("Chem ta tami kimün mew ramtun") is False

    def test_el_vocabulario_esta_normalizado(self):
        """Se compara con el texto sin tildes: un término con tilde no coincidiría nunca."""
        for termino in yap._TERMINOS_DEL_CURSO:
            assert termino == yap._normalizar_respuesta(termino), termino


# ============================================================
# 4. DÓNDE SE APLICA
# ============================================================

class TestPuntosDeEntrada(BaseDominio):
    """Requisito: solo la pregunta libre del alumno pasa por el filtro."""

    def test_consulta_libre_rechazada_no_llama_al_modelo(self):
        with mock.patch.object(yap, "_rag_context_for_query", return_value=None), \
                mock.patch.object(yap, "cmd_query") as cq, \
                mock.patch("builtins.print") as imprime:
            yap.handle_action("query", "que es el van?", "que es el van y el tir de un proyecto?")
        cq.assert_not_called()
        assert yap.t("query.fuera_de_ambito") in " ".join(str(c) for c in imprime.call_args_list)

    def test_consulta_local_rechazada_no_llama_al_modelo(self):
        with mock.patch.object(yap, "_rag_context_for_query", return_value=None), \
                mock.patch.object(yap, "cmd_query") as cq, mock.patch("builtins.print"):
            yap.handle_action("query_local", "x", "que es el van y el tir de un proyecto?")
        cq.assert_not_called()

    def test_consulta_del_curso_llega_al_modelo(self):
        with mock.patch.object(yap, "cmd_query", return_value="respuesta") as cq, \
                mock.patch("builtins.print"):
            yap.handle_action("query", "x", "que es la recursividad?")
        cq.assert_called_once()

    def test_la_gui_rechaza_sin_llamar_al_modelo(self):
        with mock.patch.object(yap, "_rag_context_for_query", return_value=None), \
                mock.patch.object(yap_core, "stream_llama") as sl:
            salida = yap_core.execute_action_headless(
                "query", "x", "que es el van y el tir de un proyecto?")
        sl.assert_not_called()
        assert salida == yap.t("query.fuera_de_ambito")

    def test_el_rechazo_no_consume_el_limite_de_consultas(self):
        """El límite (#256) cuenta llamadas al modelo; un rechazo no lo es."""
        with mock.patch.object(yap, "_rag_context_for_query", return_value=None), \
                mock.patch.object(yap, "_rechazo_por_limite") as limite, \
                mock.patch("builtins.print"):
            yap.handle_action("query", "x", "que es el van y el tir de un proyecto?")
        limite.assert_not_called()

    def test_el_rechazo_no_se_guarda_en_el_historial(self):
        """Un turno de rechazo en el historial empuja al modelo a seguir rechazando."""
        with mock.patch.object(yap, "_rag_context_for_query", return_value=None), \
                mock.patch("builtins.print"):
            yap.handle_action("query", "x", "que es el van y el tir de un proyecto?")
        assert yap.HISTORY == []

    def test_cmd_query_no_filtra(self):
        """Las dudas dentro de una actividad llaman a cmd_query directamente."""
        with mock.patch.object(yap, "_rag_context_for_query", return_value=None), \
                mock.patch("subprocess.run",
                           return_value=mock.Mock(stdout="respuesta", stderr="")) as run:
            yap.cmd_query("que es el van y el tir de un proyecto?", store_history=False)
        run.assert_called_once()

    def test_resumen_de_busca_no_filtra(self):
        with mock.patch.object(yap, "_rag_context_for_query", return_value=None), \
                mock.patch("subprocess.run",
                           return_value=mock.Mock(stdout="resumen", stderr="")) as run:
            yap.cmd_query(yap.t("llm.summarize_prompt", query="fotosintesis"),
                          context="La fotosintesis transforma la luz.", store_history=False)
        run.assert_called_once()


# ============================================================
# 5. EL MENSAJE AL ESTUDIANTE
# ============================================================

class TestMensaje(BaseDominio):
    """Requisito: el rechazo explica qué sí puede hacer."""

    def test_ofrece_el_curso(self):
        mensaje = yap.t("query.fuera_de_ambito")
        for termino in ("programación", "PSeInt", "Python"):
            assert termino in mensaje, termino

    def test_explica_como_reformular(self):
        """Ninguna lista de vocabulario es completa: el alumno necesita una salida."""
        assert "en PSeInt" in yap.t("query.fuera_de_ambito")

    def test_ofrece_busca_para_temas_generales(self):
        mensaje = yap.t("query.fuera_de_ambito")
        assert "busca" in mensaje
        assert "Wikipedia" in mensaje

    def test_en_ingles(self):
        yap.set_lang("en", persist=False)
        mensaje = yap.t("query.fuera_de_ambito")
        assert mensaje.startswith("That is outside what I can teach you.")
        assert "in PSeInt" in mensaje

    def test_mapudungun_cae_al_espanol(self):
        """arn es parcial por diseño: la clave nueva usa el español."""
        assert "fuera_de_ambito" not in catalogo("arn").get("query", {})
        yap.set_lang("arn", persist=False)
        assert yap.t("query.fuera_de_ambito") == catalogo("es")["query"]["fuera_de_ambito"]

    def test_el_modelo_no_lo_ve(self):
        """Cuando el modelo leía «busca», fingía haber buscado en Wikipedia."""
        assert "wikipedia" not in yap.SYSTEM_PROMPT.lower()
        assert "busca" not in yap.SYSTEM_PROMPT.lower()
