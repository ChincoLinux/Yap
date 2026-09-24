"""
test_yap_profesor.py — Pruebas del modo profesor (#25)

Verifica:
  1. El rol en el perfil: valores validos, persistencia y saneado
  2. El PIN: derivacion con sal, verificacion y validacion de formato
  3. La autorizacion: sin rol, sin PIN, PIN erroneo y sin terminal
  4. La importacion de progreso desde archivo, carpeta plana o carpeta por alumno
  5. Las metricas agregadas y sus filtros
  6. El panel, la ficha individual y la exportacion a CSV
  7. El enrutado en interpret() y el despacho en handle_action()

Ejecucion: python3 -m pytest tests/test_yap_profesor.py -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


PROGRESO_MEDIO = {
    "cursos": {
        "FPY1101": {
            "EA1": {
                "completada": False,
                "total_actividades": 4,
                "actividades": {
                    "1": {"puntaje": 80, "aprobado": True,
                          "fecha_aprobacion": "2026-09-10T10:00:00"},
                    "2": {"puntaje": 40, "aprobado": False},
                },
            }
        }
    }
}

PROGRESO_BAJO = {
    "cursos": {
        "FPY1101": {
            "EA1": {
                "completada": False,
                "total_actividades": 4,
                "actividades": {"1": {"puntaje": 20, "aprobado": False}},
            }
        }
    }
}

PROGRESO_VACIO = {"cursos": {}}


class ProfesorTestBase:
    """Aisla perfil, progreso, aula y telemetria en un directorio temporal."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.aula = os.path.join(self.tmpdir, "aula")
        self.patchers = [
            mock.patch.object(yap, "PROFILE_FILE",
                              os.path.join(self.tmpdir, "profile.json")),
            mock.patch.object(yap, "PROGRESS_FILE",
                              os.path.join(self.tmpdir, "progress.json")),
            mock.patch.object(yap, "AULA_DIR", self.aula),
            mock.patch.object(yap, "TELEMETRY_FILE",
                              os.path.join(self.tmpdir, "telemetry.json")),
            mock.patch.object(yap, "CURSOS_DIR",
                              os.path.join(self.tmpdir, "cursos")),
        ]
        for p in self.patchers:
            p.start()

    def teardown_method(self):
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def hacer_profesor(self, pin="1234"):
        yap.actualizar_rol("profesor")
        yap.definir_pin(pin)

    def escribir_progreso(self, nombre, datos, subcarpeta=None, perfil=None):
        """Write a progress.json the way a USB copy would carry it."""
        base = self.tmpdir if subcarpeta is None else os.path.join(self.tmpdir, subcarpeta)
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, nombre)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(datos, f)
        if perfil is not None:
            with open(os.path.join(base, "profile.json"), "w", encoding="utf-8") as f:
                json.dump(perfil, f)
        return path

    def importar(self, nombre, datos):
        """Shortcut: leave one student already imported into the aula."""
        os.makedirs(self.aula, exist_ok=True)
        registro = {"nombre": nombre, "origen": "/tmp/x.json",
                    "importado": "2026-09-15T08:00:00", "progreso": datos}
        with open(os.path.join(self.aula, yap._slug(nombre) + ".json"),
                  "w", encoding="utf-8") as f:
            json.dump(registro, f)
        return registro


# ============================================================
# 1. EL ROL EN EL PERFIL
# ============================================================

class TestRol(ProfesorTestBase):
    """Requisito: el panel exige un perfil con rol de profesor."""

    def test_por_defecto_es_estudiante(self):
        assert yap.cargar_perfil()["rol"] == "estudiante"

    def test_nadie_es_profesor_por_defecto(self):
        assert yap.es_profesor() is False

    def test_actualizar_rol(self):
        yap.actualizar_rol("profesor")
        assert yap.cargar_perfil()["rol"] == "profesor"
        assert yap.es_profesor() is True

    def test_rol_invalido_se_rechaza(self):
        for rol in ("director", "admin", "", "root"):
            try:
                yap.actualizar_rol(rol)
            except ValueError:
                continue
            raise AssertionError(f"se acepto el rol '{rol}'")

    def test_rol_corrupto_en_disco_vuelve_a_estudiante(self):
        with open(yap.PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump({"rol": "superusuario"}, f)
        assert yap.cargar_perfil()["rol"] == "estudiante"

    def test_cmd_perfil_actualiza_el_rol(self):
        assert "[OK]" in yap.cmd_perfil("rol profesor")
        assert yap.es_profesor() is True

    def test_cmd_perfil_muestra_el_rol(self):
        assert "Rol:" in yap.cmd_perfil()

    def test_cmd_perfil_rechaza_un_rol_invalido(self):
        assert "[ERROR]" in yap.cmd_perfil("rol director")


# ============================================================
# 2. EL PIN
# ============================================================

class TestPin(ProfesorTestBase):
    """Requisito: autenticacion simple con PIN."""

    def test_sin_configurar(self):
        assert yap.pin_configurado() is False

    def test_definir_y_verificar(self):
        yap.definir_pin("4821")
        assert yap.pin_configurado() is True
        assert yap.verificar_pin("4821") is True

    def test_pin_incorrecto(self):
        yap.definir_pin("4821")
        assert yap.verificar_pin("0000") is False

    def test_el_pin_no_se_guarda_en_claro(self):
        yap.definir_pin("4821")
        contenido = open(yap.PROFILE_FILE, encoding="utf-8").read()
        assert "4821" not in contenido

    def test_dos_perfiles_con_el_mismo_pin_no_comparten_hash(self):
        """Sal distinta por perfil: un hash no delata al otro."""
        yap.definir_pin("4821")
        primero = yap.cargar_perfil()["profesor"]["pin_hash"]
        yap.definir_pin("4821")
        assert yap.cargar_perfil()["profesor"]["pin_hash"] != primero

    def test_formato_invalido(self):
        for pin in ("abc", "12", "1" * 20, "", "12 34", "12a4"):
            try:
                yap.definir_pin(pin)
            except ValueError:
                continue
            raise AssertionError(f"se acepto el PIN '{pin}'")

    def test_verificar_sin_pin_configurado(self):
        assert yap.verificar_pin("1234") is False

    def test_el_pin_sobrevive_a_una_recarga_del_perfil(self):
        """_normalizar_perfil no puede descartar el bloque del docente."""
        self.hacer_profesor("5678")
        yap.actualizar_nivel("avanzado")
        assert yap.verificar_pin("5678") is True


# ============================================================
# 3. AUTORIZACION
# ============================================================

class TestAutorizacion(ProfesorTestBase):
    """Requisito: el panel no se abre sin rol y sin PIN correcto."""

    def test_sin_rol_no_entra(self):
        salida = yap.cmd_profesor()
        assert "rol" in salida.lower()

    def test_sin_pin_no_entra(self):
        yap.actualizar_rol("profesor")
        assert "PIN" in yap.cmd_profesor()

    def test_pin_incorrecto_no_entra(self):
        self.hacer_profesor("1234")
        with mock.patch.object(yap, "_pedir_pin", return_value="9999"):
            assert "incorrecto" in yap.cmd_profesor().lower()

    def test_pin_correcto_entra(self):
        self.hacer_profesor("1234")
        self.importar("Maria", PROGRESO_MEDIO)
        with mock.patch.object(yap, "_pedir_pin", return_value="1234"):
            assert "Panel del docente" in yap.cmd_profesor()

    def test_pin_correcto_sin_alumnos_explica_como_importar(self):
        self.hacer_profesor("1234")
        with mock.patch.object(yap, "_pedir_pin", return_value="1234"):
            assert "importar" in yap.cmd_profesor()

    def test_sin_terminal_se_deniega(self):
        """Mismo criterio que confirm_action del #12."""
        self.hacer_profesor("1234")
        stdin = mock.Mock()
        stdin.isatty.return_value = False
        with mock.patch.object(yap.sys, "stdin", stdin):
            assert yap._pedir_pin() == ""

    def test_la_ayuda_no_exige_pin(self):
        assert "importar" in yap.cmd_profesor("ayuda")


# ============================================================
# 4. IMPORTACION
# ============================================================

class TestImportacion(ProfesorTestBase):
    """Requisito: importar progress.json desde un directorio o USB."""

    def test_un_archivo_suelto(self):
        path = self.escribir_progreso("maria.json", PROGRESO_MEDIO)
        importados, errores = yap.importar_progreso(path)
        assert importados == ["maria"]
        assert not errores

    def test_una_carpeta_plana(self):
        self.escribir_progreso("maria.json", PROGRESO_MEDIO, subcarpeta="usb")
        self.escribir_progreso("pedro.json", PROGRESO_BAJO, subcarpeta="usb")
        importados, _ = yap.importar_progreso(os.path.join(self.tmpdir, "usb"))
        assert sorted(importados) == ["maria", "pedro"]

    def test_una_carpeta_por_estudiante(self):
        """Copiar ~/.config/yap/ entero es lo que pasa en la practica."""
        self.escribir_progreso("progress.json", PROGRESO_MEDIO, subcarpeta="usb/ana")
        importados, _ = yap.importar_progreso(os.path.join(self.tmpdir, "usb"))
        assert importados == ["ana"]

    def test_el_nombre_sale_del_profile_vecino(self):
        self.escribir_progreso("progress.json", PROGRESO_MEDIO, subcarpeta="usb/eq1",
                               perfil={"nombre": "María González"})
        importados, _ = yap.importar_progreso(os.path.join(self.tmpdir, "usb"))
        assert importados == ["María González"]

    def test_el_profile_vecino_no_se_importa_como_progreso(self):
        self.escribir_progreso("progress.json", PROGRESO_MEDIO, subcarpeta="usb",
                               perfil={"nombre": "Ana"})
        importados, _ = yap.importar_progreso(os.path.join(self.tmpdir, "usb"))
        assert importados == ["Ana"]
        assert len(yap.cargar_alumnos()) == 1

    def test_json_invalido_no_revienta(self):
        os.makedirs(os.path.join(self.tmpdir, "usb"), exist_ok=True)
        with open(os.path.join(self.tmpdir, "usb", "roto.json"), "w") as f:
            f.write("{ no es json")
        importados, errores = yap.importar_progreso(os.path.join(self.tmpdir, "usb"))
        assert not importados
        assert errores

    def test_un_json_que_no_es_progreso_se_descarta(self):
        self.escribir_progreso("otro.json", {"algo": "distinto"}, subcarpeta="usb")
        importados, errores = yap.importar_progreso(os.path.join(self.tmpdir, "usb"))
        assert not importados
        assert "no parece" in errores[0]

    def test_ruta_inexistente(self):
        importados, errores = yap.importar_progreso(os.path.join(self.tmpdir, "nada"))
        assert not importados
        assert errores

    def test_la_escritura_es_atomica(self):
        path = self.escribir_progreso("maria.json", PROGRESO_MEDIO)
        yap.importar_progreso(path)
        sobrantes = [f for f in os.listdir(self.aula) if f.endswith(".tmp")]
        assert not sobrantes

    def test_reimportar_actualiza_en_vez_de_duplicar(self):
        path = self.escribir_progreso("maria.json", PROGRESO_MEDIO)
        yap.importar_progreso(path)
        yap.importar_progreso(path)
        assert len(yap.cargar_alumnos()) == 1

    def test_el_nombre_no_puede_escapar_del_directorio(self):
        """El nombre viene de un archivo ajeno: no puede componer una ruta."""
        assert yap._slug("../../etc/passwd") == "etc-passwd"
        assert "/" not in yap._slug("a/b")
        assert "\\" not in yap._slug("a\\b")
        assert yap._slug("..") == "sin-nombre"


# ============================================================
# 5. METRICAS
# ============================================================

class TestMetricas(ProfesorTestBase):
    """Requisito: % completado, nota promedio y ultima sesion."""

    def test_avance_y_porcentaje(self):
        m = yap.metricas_alumno(self.importar("Maria", PROGRESO_MEDIO))
        assert m["evaluadas"] == 2
        assert m["total"] == 4
        assert m["porcentaje"] == 50.0

    def test_nota_promedio(self):
        """80 y 40 promedian 60, que en la escala chilena es exactamente 4.0."""
        m = yap.metricas_alumno(self.importar("Maria", PROGRESO_MEDIO))
        assert m["nota"] == 4.0
        assert m["aprobado"] is True

    def test_bajo_la_aprobacion(self):
        m = yap.metricas_alumno(self.importar("Pedro", PROGRESO_BAJO))
        assert m["nota"] < yap.NOTA_APROBACION
        assert m["aprobado"] is False

    def test_sin_actividades(self):
        m = yap.metricas_alumno(self.importar("Nuevo", PROGRESO_VACIO))
        assert m["nota"] is None
        assert m["porcentaje"] == 0.0
        assert m["aprobado"] is False

    def test_ultima_actividad(self):
        m = yap.metricas_alumno(self.importar("Maria", PROGRESO_MEDIO))
        assert m["ultima"].startswith("2026-09-10")

    def test_sin_fechas_la_ultima_es_none(self):
        assert yap.metricas_alumno(self.importar("Pedro", PROGRESO_BAJO))["ultima"] is None

    def test_filtro_por_curso(self):
        registro = self.importar("Maria", PROGRESO_MEDIO)
        assert yap.metricas_alumno(registro, curso="FPY1101")["evaluadas"] == 2
        assert yap.metricas_alumno(registro, curso="OTRO")["evaluadas"] == 0

    def test_filtro_por_ea(self):
        registro = self.importar("Maria", PROGRESO_MEDIO)
        assert yap.metricas_alumno(registro, ea="EA1")["evaluadas"] == 2
        assert yap.metricas_alumno(registro, ea="EA9")["evaluadas"] == 0

    def test_progreso_corrupto_no_revienta(self):
        registro = {"nombre": "X", "progreso": {"cursos": {"FPY1101": "no es dict"}}}
        assert yap.metricas_alumno(registro)["nota"] is None


# ============================================================
# 6. PANEL, FICHA Y CSV
# ============================================================

class TestPanel(ProfesorTestBase):
    """Requisito: panel TUI con la lista de estudiantes."""

    def test_sin_alumnos_explica_como_importar(self):
        assert "importar" in yap.panel_aula()

    def test_lista_a_los_alumnos(self):
        self.importar("Maria", PROGRESO_MEDIO)
        self.importar("Pedro", PROGRESO_BAJO)
        salida = yap.panel_aula()
        assert "Maria" in salida
        assert "Pedro" in salida
        assert "2 estudiante(s)" in salida

    def test_muestra_el_promedio_y_los_reprobados(self):
        self.importar("Maria", PROGRESO_MEDIO)
        self.importar("Pedro", PROGRESO_BAJO)
        salida = yap.panel_aula()
        assert "Promedio del curso" in salida
        assert "1 de 2" in salida

    def test_cuenta_a_los_que_no_tienen_datos(self):
        self.importar("Nuevo", PROGRESO_VACIO)
        assert "Sin actividades evaluadas: 1" in yap.panel_aula()

    def test_el_archivo_corrupto_del_aula_se_ignora(self):
        self.importar("Maria", PROGRESO_MEDIO)
        with open(os.path.join(self.aula, "roto.json"), "w") as f:
            f.write("{ roto")
        assert len(yap.cargar_alumnos()) == 1


class TestFicha(ProfesorTestBase):
    """Requisito: reporte individual detallado."""

    def test_ficha_de_un_alumno(self):
        self.importar("Maria", PROGRESO_MEDIO)
        salida = yap.ficha_alumno("Maria")
        assert "Maria" in salida
        assert "FPY1101" in salida
        assert "EA1" in salida

    def test_el_nombre_no_distingue_mayusculas(self):
        self.importar("María González", PROGRESO_MEDIO)
        assert "[ERROR]" not in yap.ficha_alumno("maría gonzález")

    def test_alumno_inexistente(self):
        assert "[ERROR]" in yap.ficha_alumno("Nadie")


class TestExportacionCSV(ProfesorTestBase):
    """Requisito: exportacion a CSV."""

    def test_sin_alumnos_no_exporta(self):
        assert "[ERROR]" in yap.exportar_csv()

    def test_escribe_cabecera_y_filas(self):
        self.importar("Maria", PROGRESO_MEDIO)
        self.importar("Pedro", PROGRESO_BAJO)
        destino = yap.exportar_csv(os.path.join(self.tmpdir, "reporte.csv"))
        filas = open(destino, encoding="utf-8").read().strip().splitlines()
        assert filas[0].startswith("nombre,")
        assert len(filas) == 3

    def test_la_exportacion_es_atomica(self):
        self.importar("Maria", PROGRESO_MEDIO)
        destino = yap.exportar_csv(os.path.join(self.tmpdir, "reporte.csv"))
        assert not os.path.exists(destino + ".tmp")

    def test_los_datos_van_en_el_csv(self):
        self.importar("Maria", PROGRESO_MEDIO)
        destino = yap.exportar_csv(os.path.join(self.tmpdir, "reporte.csv"))
        contenido = open(destino, encoding="utf-8").read()
        assert "Maria" in contenido
        assert "4.0" in contenido

    def test_un_nombre_con_coma_no_rompe_el_csv(self):
        self.importar("González, María", PROGRESO_MEDIO)
        destino = yap.exportar_csv(os.path.join(self.tmpdir, "reporte.csv"))
        import csv as _csv
        with open(destino, encoding="utf-8", newline="") as f:
            filas = list(_csv.reader(f))
        assert filas[1][0] == "González, María"


# ============================================================
# 7. ENRUTADO Y DESPACHO
# ============================================================

class TestEnrutado(ProfesorTestBase):
    """Requisito: 'profesor' no depende del clasificador."""

    def test_profesor_pelado(self):
        assert yap.interpret("profesor") == ("profesor", "")

    def test_subcomando(self):
        assert yap.interpret("profesor listar") == ("profesor", "listar")

    def test_conserva_mayusculas_del_nombre(self):
        """El nombre del estudiante es un parametro, no una orden."""
        assert yap.interpret("profesor estudiante María González") == (
            "profesor", "estudiante María González")

    def test_no_llama_al_clasificador(self):
        with mock.patch.object(yap, "classify_intent") as clasificador:
            for texto in ("profesor", "profesor listar", "docente exportar"):
                yap.interpret(texto)
        clasificador.assert_not_called()

    def test_una_pregunta_sobre_profesores_sigue_al_llm(self):
        with mock.patch.object(yap, "classify_intent",
                               return_value=("query", "x")) as clasificador:
            yap.interpret("que hace un profesor de matematicas")
        clasificador.assert_called_once()


class TestDespacho(ProfesorTestBase):
    """Requisito: handle_action ejecuta y contabiliza la accion."""

    def test_despacha_el_subcomando(self):
        with mock.patch.object(yap, "cmd_profesor", return_value="ok") as cmd:
            yap.handle_action("profesor", "estudiante María", "profesor estudiante María")
        cmd.assert_called_once_with("estudiante", "María")

    def test_despacha_sin_subcomando(self):
        with mock.patch.object(yap, "cmd_profesor", return_value="ok") as cmd:
            yap.handle_action("profesor", "", "profesor")
        cmd.assert_called_once_with("", "")

    def test_la_telemetria_conoce_la_accion(self):
        assert "profesor" in yap.ACCIONES_CONOCIDAS
        assert "profesor" in yap.ACCIONES_NOMBRES

    def test_se_registra_por_separado(self):
        with mock.patch.object(yap, "cmd_profesor", return_value="ok"):
            yap.handle_action("profesor", "listar", "profesor listar")
        with open(yap.TELEMETRY_FILE, encoding="utf-8") as f:
            assert json.load(f)["comandos"]["profesor"] == 1


class TestMenu(ProfesorTestBase):
    """Requisito: la opcion no ensucia el menu del estudiante."""

    def test_el_estudiante_no_ve_la_opcion(self):
        etiquetas = [e for e, _ in yap._menu_principal()]
        assert not any("Profesor" in e for e in etiquetas)

    def test_el_profesor_si_la_ve(self):
        yap.actualizar_rol("profesor")
        etiquetas = [e for e, _ in yap._menu_principal()]
        assert any("Profesor" in e for e in etiquetas)

    def test_la_numeracion_del_estudiante_no_cambia(self):
        """Anadir la opcion no puede mover los numeros que ya usa el alumno."""
        base = [c for _, c in yap._menu_principal()]
        yap.actualizar_rol("profesor")
        con_rol = [c for _, c in yap._menu_principal()]
        assert con_rol[:len(base) - 3] == base[:len(base) - 3]

    def test_el_numero_del_profesor_enruta(self):
        yap.actualizar_rol("profesor")
        opciones = yap._menu_principal()
        numero = next(i for i, (e, _) in enumerate(opciones, 1) if "Profesor" in e)
        assert yap.interpret(str(numero)) == ("profesor", "")
