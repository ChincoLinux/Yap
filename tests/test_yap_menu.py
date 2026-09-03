"""
test_yap_menu.py — Pruebas del menú numerado y las rutas de teclado (#59)

Verifica:
  1. El menú es la fuente única de la numeración mostrada y la enrutada
  2. Escribir un número ejecuta la acción correspondiente
  3. Las opciones que necesitan parámetro muestran su pista de uso
  4. Los números fuera de rango se tratan como consulta normal
  5. `abre`, `busca` y `pseint` se enrutan sin invocar al LLM
  6. Las rutas nuevas no rompen las que ya existían

Ejecucion: python3 -m pytest tests/test_yap_menu.py -v
"""

import sys
import os
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


# ============================================================
# 1. FUENTE ÚNICA
# ============================================================

class TestFuenteUnica:
    """Requisito: la numeración mostrada y la enrutada no pueden divergir."""

    def test_el_menu_no_esta_vacio(self):
        assert len(yap.MENU_INTERACTIVO) > 0

    def test_cada_entrada_tiene_cuatro_campos(self):
        for entrada in yap.MENU_INTERACTIVO:
            assert len(entrada) == 4, f"entrada mal formada: {entrada}"

    def test_las_etiquetas_salen_del_mismo_sitio(self):
        etiquetas = yap._etiquetas_menu()
        assert len(etiquetas) == len(yap.MENU_INTERACTIVO)
        for i, entrada in enumerate(yap.MENU_INTERACTIVO):
            assert etiquetas[i] == entrada[0]

    def test_toda_etiqueta_tiene_texto(self):
        for etiqueta in yap._etiquetas_menu():
            assert etiqueta.strip(), "hay una opcion sin texto"

    def test_las_opciones_sin_parametro_traen_pista(self):
        """Si el número no puede ejecutarse solo, debe explicar cómo usarlo."""
        for etiqueta, accion, param, pista in yap.MENU_INTERACTIVO:
            if param is None:
                assert pista.strip(), f"'{etiqueta}' no explica como usarse"

    def test_las_acciones_declaradas_existen(self):
        """Una opción no puede apuntar a una acción que handle_action ignora."""
        conocidas = set(yap.ACCIONES_CONOCIDAS) | {"salir", None}
        for etiqueta, accion, _, _ in yap.MENU_INTERACTIVO:
            assert accion in conocidas, f"'{etiqueta}' apunta a '{accion}'"


    def test_toda_accion_despachada_es_conocida_por_la_telemetria(self):
        """Si handle_action despacha una acción que ACCIONES_CONOCIDAS ignora,
        la telemetría la contabiliza como `query` y la da por nunca usada."""
        import re
        fuente = open(yap.__file__, encoding="utf-8").read()
        despachadas = set(re.findall(r'action == "([a-z_]+)"', fuente))
        faltan = despachadas - set(yap.ACCIONES_CONOCIDAS)
        assert not faltan, f"acciones sin registrar en la telemetria: {faltan}"

    def test_toda_accion_conocida_tiene_nombre_legible(self):
        faltan = [a for a in yap.ACCIONES_CONOCIDAS if a not in yap.ACCIONES_NOMBRES]
        assert not faltan, f"sin nombre para el resumen: {faltan}"


# ============================================================
# 2. SELECCIÓN POR NÚMERO
# ============================================================

class TestSeleccionPorNumero:
    """Requisito: escribir el número ejecuta la acción correspondiente."""

    def test_opcion_de_curso(self):
        n = self._numero_de("curso")
        assert yap.interpret(str(n)) == ("curso", "FPY1101")

    def test_opcion_de_historial(self):
        n = self._numero_de("historial", param="historial")
        assert yap.interpret(str(n)) == ("historial", "historial")

    def test_opcion_de_sesion(self):
        n = self._numero_de("sesion")
        assert yap.interpret(str(n)) == ("sesion", "")

    def test_opcion_de_telemetria(self):
        n = self._numero_de("telemetria")
        assert yap.interpret(str(n)) == ("telemetria", "")

    def test_opcion_de_ayuda(self):
        n = self._numero_de("help")
        assert yap.interpret(str(n)) == ("help", "ayuda")

    def test_la_opcion_de_salir_termina_el_programa(self):
        n = self._numero_de("salir")
        with mock.patch.object(yap.sys, "exit", side_effect=SystemExit) as salir:
            try:
                yap.interpret(str(n))
            except SystemExit:
                pass
        salir.assert_called_once_with(0)

    def test_ningun_numero_valido_llega_al_llm(self):
        """Es el objetivo del issue: dejar de depender del clasificador."""
        with mock.patch.object(yap, "classify_intent") as clasificador:
            for i in range(1, len(yap.MENU_INTERACTIVO) + 1):
                entrada = yap._opcion_menu(i)
                if entrada[1] == "salir":
                    continue
                yap.interpret(str(i))
            clasificador.assert_not_called()

    def _numero_de(self, accion, param=None):
        for i, entrada in enumerate(yap.MENU_INTERACTIVO, 1):
            if entrada[1] == accion and (param is None or entrada[2] == param):
                return i
        raise AssertionError(f"no hay opcion para '{accion}'")


# ============================================================
# 3. PISTAS DE USO
# ============================================================

class TestPistas:
    """Requisito: las opciones que piden datos explican cómo usarse."""

    def test_devuelve_la_pista_en_vez_de_ejecutar(self):
        for i, (_, _, param, pista) in enumerate(yap.MENU_INTERACTIVO, 1):
            if param is None:
                assert yap.interpret(str(i)) == ("menu_pista", pista)

    def test_la_pista_de_abrir_muestra_un_ejemplo(self):
        for i, (_, accion, param, pista) in enumerate(yap.MENU_INTERACTIVO, 1):
            if accion == "open_app" and param is None:
                assert "abre" in pista.lower()
                return
        raise AssertionError("no hay opcion de abrir app sin parametro")

    def test_handle_action_muestra_la_pista(self):
        with mock.patch("builtins.print") as escribir:
            yap.handle_action("menu_pista", "Escribe 'abre' y el nombre.", "2")
        salida = " ".join(str(c) for c in escribir.call_args_list)
        assert "abre" in salida

    def test_pista_vacia_no_revienta(self):
        with mock.patch("builtins.print") as escribir:
            yap.handle_action("menu_pista", "", "1")
        escribir.assert_called()


# ============================================================
# 4. NÚMEROS FUERA DE RANGO
# ============================================================

class TestFueraDeRango:
    """Requisito: un número fuera de rango es una consulta normal."""

    def test_cero_va_al_clasificador(self):
        with mock.patch.object(yap, "classify_intent", return_value=("query", "0")) as c:
            yap.interpret("0")
        c.assert_called_once()

    def test_un_numero_alto_va_al_clasificador(self):
        """'cuanto es 7 por 8' -> 56 no debe ejecutar la opcion 56."""
        with mock.patch.object(yap, "classify_intent", return_value=("query", "56")) as c:
            yap.interpret("56")
        c.assert_called_once()

    def test_justo_encima_del_ultimo_va_al_clasificador(self):
        fuera = str(len(yap.MENU_INTERACTIVO) + 1)
        with mock.patch.object(yap, "classify_intent", return_value=("query", fuera)) as c:
            yap.interpret(fuera)
        c.assert_called_once()

    def test_un_numero_con_texto_no_es_seleccion(self):
        with mock.patch.object(yap, "classify_intent", return_value=("query", "x")) as c:
            yap.interpret("5 cursos")
        c.assert_called_once()

    def test_opcion_menu_rechaza_valores_invalidos(self):
        assert yap._opcion_menu(0) is None
        assert yap._opcion_menu(-1) is None
        assert yap._opcion_menu(999) is None
        assert yap._opcion_menu("2") is None


# ============================================================
# 5. RUTAS DE TECLADO NUEVAS
# ============================================================

class TestRutasDeTeclado:
    """Requisito: abre, busca y pseint no dependen del clasificador."""

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
            assert yap.interpret(texto) == ("introduccion_pseint", "inicio")

    def test_conserva_mayusculas_del_parametro(self):
        """El parámetro es del usuario; solo la orden se normaliza."""
        assert yap.interpret("busca Linus Torvalds") == ("search", "Linus Torvalds")

    def test_ninguna_ruta_nueva_llama_al_llm(self):
        with mock.patch.object(yap, "classify_intent") as clasificador:
            for texto in ("abre firefox", "abrir htop", "busca linux",
                          "buscar python", "pseint ciclos",
                          "tutor pseint arreglos", "aprender pseint"):
                yap.interpret(texto)
            clasificador.assert_not_called()

    def test_sin_parametro_sigue_al_clasificador(self):
        """'abre' a secas es ambiguo: que lo resuelva el LLM."""
        with mock.patch.object(yap, "classify_intent", return_value=("query", "abre")) as c:
            yap.interpret("abre")
        c.assert_called_once()


# ============================================================
# 6. NO ROMPER LO EXISTENTE
# ============================================================

class TestRutasPrevias:
    """Las rutas que ya funcionaban deben seguir igual."""

    def test_guia(self):
        assert yap.interpret("guia") == ("guia", "guia")

    def test_progreso(self):
        assert yap.interpret("mi progreso") == ("progreso", "progreso")

    def test_historial_ultimo(self):
        assert yap.interpret("historial --ultimo") == ("historial", "--ultimo")

    def test_sesion(self):
        assert yap.interpret("sesion pausar") == ("sesion", "pausar")

    def test_telemetria(self):
        assert yap.interpret("telemetria exportar") == ("telemetria", "exportar")

    def test_curso(self):
        assert yap.interpret("curso FPY1101") == ("curso", "FPY1101")

    def test_ayuda(self):
        assert yap.interpret("ayuda") == ("help", "ayuda")

    def test_una_pregunta_libre_sigue_yendo_al_llm(self):
        with mock.patch.object(yap, "classify_intent",
                               return_value=("query", "que es debian")) as c:
            yap.interpret("que es debian")
        c.assert_called_once()
