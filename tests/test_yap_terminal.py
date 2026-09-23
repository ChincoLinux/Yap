"""
test_yap_terminal.py — La terminal del estudiante no se hereda (#99)

Sintoma reportado: a partir de la segunda consulta, lo que se escribe deja de
verse en pantalla, aunque Enter sigue enviando la pregunta.

Causa: los procesos hijos heredaban stdin. `llama-cli` hace tcsetattr sobre la
terminal que recibe y apaga el eco; si no termina limpiamente, el eco se queda
apagado y el estudiante escribe a ciegas. Las aplicaciones de la whitelist,
que viven mas que la llamada, competian ademas por la misma terminal.

Verifica:
  1. Ninguna llamada a subprocess hereda stdin (revision estatica del fuente)
  2. Las tres rutas de llama-cli pasan stdin=DEVNULL
  3. El lanzador de aplicaciones tampoco se queda con la terminal

Ejecucion: python3 -m pytest tests/test_yap_terminal.py -v
"""

import ast
import os
import subprocess
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap

LLAMADAS = ("run", "Popen", "call", "check_call", "check_output")


def _fuente():
    with open(yap.__file__, encoding="utf-8") as f:
        return f.read()


def _llamadas_subprocess(fuente):
    """Return every subprocess.<run|Popen|...> call found in the source."""
    encontradas = []
    for nodo in ast.walk(ast.parse(fuente)):
        if not isinstance(nodo, ast.Call):
            continue
        f = nodo.func
        if (isinstance(f, ast.Attribute)
                and isinstance(f.value, ast.Name)
                and f.value.id == "subprocess"
                and f.attr in LLAMADAS):
            encontradas.append((f.attr, nodo))
    return encontradas


def _kwarg(nodo, nombre):
    for kw in nodo.keywords:
        if kw.arg == nombre:
            return kw.value
    return None


# ============================================================
# 1. REVISION ESTATICA
# ============================================================

class TestNingunProcesoHeredaLaTerminal:
    """Requisito: ningun hijo recibe la terminal del estudiante."""

    def test_hay_llamadas_que_revisar(self):
        """Si el parser deja de encontrarlas, el resto no prueba nada."""
        assert len(_llamadas_subprocess(_fuente())) >= 5

    def test_toda_llamada_pasa_stdin(self):
        faltan = [
            f"{attr}() en la linea {nodo.lineno}"
            for attr, nodo in _llamadas_subprocess(_fuente())
            if _kwarg(nodo, "stdin") is None
        ]
        assert not faltan, (
            "estas llamadas heredan la terminal del estudiante: " + ", ".join(faltan))

    def test_el_stdin_es_devnull(self):
        """Un pipe abierto dejaria al hijo esperando entrada que nunca llega."""
        malas = []
        for attr, nodo in _llamadas_subprocess(_fuente()):
            valor = _kwarg(nodo, "stdin")
            if valor is None:
                continue
            es_devnull = (isinstance(valor, ast.Attribute)
                          and valor.attr == "DEVNULL")
            if not es_devnull:
                malas.append(f"{attr}() en la linea {nodo.lineno}")
        assert not malas, "stdin deberia ser subprocess.DEVNULL en: " + ", ".join(malas)


# ============================================================
# 2. LAS RUTAS DE llama-cli
# ============================================================

class TestRutasDeLlamaCli:
    """Requisito: las tres llamadas al modelo local sueltan la terminal."""

    def _resultado(self, salida="Una respuesta suficientemente larga."):
        return mock.Mock(stdout=salida, stderr="", returncode=0)

    def test_cmd_query(self):
        with mock.patch("subprocess.run", return_value=self._resultado()) as run:
            yap.cmd_query("que es un algoritmo", store_history=False)
        assert run.call_args.kwargs["stdin"] is subprocess.DEVNULL

    def test_cmd_pseint(self):
        with mock.patch("subprocess.run", return_value=self._resultado()) as run:
            yap.cmd_pseint("como hago un ciclo")
        assert run.call_args.kwargs["stdin"] is subprocess.DEVNULL

    def test_classify_intent(self):
        with mock.patch("subprocess.run",
                        return_value=self._resultado("query|hola")) as run:
            yap.classify_intent("hola")
        assert run.call_args.kwargs["stdin"] is subprocess.DEVNULL

    def test_la_segunda_consulta_sigue_teniendo_terminal(self):
        """Es el sintoma del #99: fallaba a partir de la segunda."""
        with mock.patch("subprocess.run", return_value=self._resultado()) as run:
            yap.cmd_query("primera pregunta", store_history=False)
            yap.cmd_query("segunda pregunta", store_history=False)
        assert run.call_count == 2
        for llamada in run.call_args_list:
            assert llamada.kwargs["stdin"] is subprocess.DEVNULL


# ============================================================
# 3. LANZADOR DE APLICACIONES
# ============================================================

class TestLanzadorDeAplicaciones:
    """Requisito: la aplicacion vive mas que la llamada; no puede quedarse
    con la terminal del REPL."""

    def test_popen_de_la_app_no_hereda_stdin(self):
        with mock.patch.object(yap, "load_whitelist",
                               return_value={"firefox": ["firefox"]}):
            with mock.patch.object(yap.shutil, "which",
                                   return_value="/usr/bin/firefox"):
                with mock.patch("subprocess.Popen") as popen:
                    with mock.patch("subprocess.run",
                                    return_value=mock.Mock(stdout="1.0", stderr="")):
                        yap.cmd_open_app("firefox")
        popen.assert_called_once()
        assert popen.call_args.kwargs["stdin"] is subprocess.DEVNULL

    def test_la_app_bloqueada_sigue_sin_lanzarse(self):
        """El arreglo no puede relajar la whitelist."""
        with mock.patch.object(yap, "load_whitelist",
                               return_value={"firefox": ["firefox"]}):
            with mock.patch("subprocess.Popen") as popen:
                salida = yap.cmd_open_app("chrome")
        popen.assert_not_called()
        assert "[ERROR]" in salida
