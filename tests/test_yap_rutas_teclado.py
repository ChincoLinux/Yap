"""
test_yap_rutas_teclado.py — Rutas de teclado y pistas del menu (#59)

El menu numerado anuncia ordenes como «Abre [app]» o «Busca [tema]», pero
esas ordenes no estaban enrutadas: dependian del clasificador, que con el
modelo 1B acierta poco. Y elegir su numero solo repetia la etiqueta, sin
decir que escribir.

Verifica:
  1. `abre`, `busca` y `pseint` se resuelven sin invocar al LLM
  2. El parametro conserva las mayusculas del usuario
  3. Una opcion que necesita datos devuelve su pista de uso
  4. Una opcion informativa sigue devolviendo su etiqueta
  5. El menu y su numeracion no se rompen
  6. Las rutas que ya existian siguen igual

Ejecucion: python3 -m pytest tests/test_yap_rutas_teclado.py -v
"""

import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


def _numero_de(fragmento):
    """1-based position of the first menu option whose label matches."""
    for i, (etiqueta, _cmd, _pista) in enumerate(yap._menu_principal(), 1):
        if fragmento.lower() in etiqueta.lower():
            return i
    raise AssertionError(f"no hay opcion de menu para '{fragmento}'")


# ============================================================
# 1. RUTAS DE TECLADO
# ============================================================

class TestRutasDeTeclado:
    """Requisito: las ordenes que el menu anuncia responden siempre."""

    def test_abre(self):
        assert yap.interpret("abre firefox") == ("open_app", "firefox")

    def test_abrir(self):
        assert yap.interpret("abrir libreoffice") == ("open_app", "libreoffice")

    def test_busca(self):
        assert yap.interpret("busca que es un algoritmo") == (
            "search", "que es un algoritmo")

    def test_buscar(self):
        assert yap.interpret("buscar linux") == ("search", "linux")

    def test_pseint(self):
        assert yap.interpret("pseint como hago un ciclo") == (
            "pseint", "como hago un ciclo")

    def test_tutor_pseint(self):
        assert yap.interpret("tutor pseint que es un arreglo") == (
            "pseint", "que es un arreglo")

    def test_tutorial_de_pseint(self):
        for texto in ("aprender pseint", "quiero aprender pseint",
                      "ejercicios pseint", "tutorial pseint"):
            assert yap.interpret(texto) == ("introduccion_pseint", "inicio"), texto

    def test_ninguna_ruta_llama_al_clasificador(self):
        """Es el objetivo del issue: no depender del 1B para esto."""
        with mock.patch.object(yap, "classify_intent") as clasificador:
            for texto in ("abre firefox", "abrir htop", "busca linux",
                          "buscar python", "pseint ciclos",
                          "tutor pseint arreglos", "aprender pseint"):
                yap.interpret(texto)
        clasificador.assert_not_called()

    def test_no_distingue_mayusculas_en_la_orden(self):
        assert yap.interpret("ABRE firefox") == ("open_app", "firefox")

    def test_conserva_las_mayusculas_del_parametro(self):
        """La orden se normaliza; lo que escribe el usuario, no."""
        assert yap.interpret("busca Linus Torvalds") == ("search", "Linus Torvalds")
        assert yap.interpret("abre LibreOffice") == ("open_app", "LibreOffice")

    def test_sin_parametro_sigue_al_clasificador(self):
        """'abre' a secas es ambiguo: que lo resuelva el LLM."""
        for texto in ("abre", "busca", "pseint"):
            with mock.patch.object(yap, "classify_intent",
                                   return_value=("query", texto)) as c:
                yap.interpret(texto)
            c.assert_called_once()

    def test_solo_espacios_tras_la_orden_no_es_ruta(self):
        with mock.patch.object(yap, "classify_intent",
                               return_value=("query", "x")) as c:
            yap.interpret("abre   ")
        c.assert_called_once()

    def test_una_palabra_que_empieza_igual_no_se_enruta(self):
        """'abrelatas' no es 'abre'."""
        with mock.patch.object(yap, "classify_intent",
                               return_value=("query", "x")) as c:
            yap.interpret("abrelatas de cocina")
        c.assert_called_once()


# ============================================================
# 2. PISTAS DE USO
# ============================================================

class TestPistas:
    """Requisito: elegir un numero que pide datos explica como usarse."""

    def test_la_opcion_de_abrir_da_un_ejemplo(self):
        accion, param = yap.interpret(str(_numero_de("Abre [app]")))
        assert accion == "menu_opcion"
        assert "abre" in param.lower()
        assert "firefox" in param.lower()

    def test_la_opcion_de_buscar_da_un_ejemplo(self):
        _accion, param = yap.interpret(str(_numero_de("Busca [tema]")))
        assert "busca" in param.lower()

    def test_la_opcion_de_pseint_da_un_ejemplo(self):
        _accion, param = yap.interpret(str(_numero_de("Tutor PSeInt")))
        assert "pseint" in param.lower()

    def test_la_pista_no_es_solo_la_etiqueta(self):
        """Antes se repetia la etiqueta, que no dice que escribir."""
        numero = _numero_de("Abre [app]")
        etiqueta = yap._menu_principal()[numero - 1][0]
        _accion, param = yap.interpret(str(numero))
        assert param != etiqueta

    def test_toda_opcion_sin_comando_tiene_pista(self):
        for etiqueta, cmd, pista in yap._menu_principal():
            if cmd or etiqueta.startswith("Modelo:"):
                continue
            assert pista.strip(), f"'{etiqueta}' no explica como usarse"

    def test_la_opcion_informativa_devuelve_su_etiqueta(self):
        """«Modelo: …» ya es la respuesta; no necesita pista."""
        _accion, param = yap.interpret(str(_numero_de("Modelo:")))
        assert param.startswith("Modelo:")


# ============================================================
# 3. EL MENU SIGUE SANO
# ============================================================

class TestMenu:
    """Requisito: anadir la pista no puede romper la numeracion."""

    def test_cada_entrada_tiene_tres_campos(self):
        for entrada in yap._menu_principal():
            assert len(entrada) == 3, f"entrada mal formada: {entrada}"

    def test_toda_etiqueta_tiene_texto(self):
        for etiqueta, _cmd, _pista in yap._menu_principal():
            assert etiqueta.strip()

    def test_cmd_menu_lista_todas_las_opciones(self):
        salida = yap.cmd_menu()
        assert "[1]" in salida
        assert f"[{len(yap._menu_principal())}]" in salida

    def test_las_opciones_con_comando_siguen_ejecutandose(self):
        assert yap.interpret(str(_numero_de("Historial — "))) == (
            "historial", "historial")
        assert yap.interpret(str(_numero_de("Ayuda"))) == ("help", "ayuda")

    def test_un_numero_fuera_de_rango_avisa(self):
        accion, param = yap.interpret("99")
        assert accion == "menu_opcion"
        assert "no existe" in param.lower()

    def test_un_numero_con_texto_no_es_seleccion(self):
        with mock.patch.object(yap, "classify_intent",
                               return_value=("query", "x")) as c:
            yap.interpret("5 cursos")
        c.assert_called_once()


# ============================================================
# 4. NO ROMPER LO EXISTENTE
# ============================================================

class TestRutasPrevias:
    """Las rutas que ya funcionaban deben seguir igual."""

    def test_guia(self):
        assert yap.interpret("guia") == ("guia", "guia")

    def test_progreso(self):
        assert yap.interpret("mi progreso") == ("progreso", "progreso")

    def test_historial_ultimo(self):
        assert yap.interpret("historial --ultimo") == ("historial", "--ultimo")

    def test_curso(self):
        assert yap.interpret("curso FPY1101") == ("curso", "FPY1101")

    def test_telemetria(self):
        assert yap.interpret("telemetria exportar") == ("telemetria", "exportar")

    def test_ayuda(self):
        assert yap.interpret("ayuda") == ("help", "ayuda")

    def test_una_pregunta_libre_sigue_yendo_al_llm(self):
        with mock.patch.object(yap, "classify_intent",
                               return_value=("query", "que es debian")) as c:
            yap.interpret("que es debian")
        c.assert_called_once()
