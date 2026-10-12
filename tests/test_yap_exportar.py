"""test_yap_exportar.py — Exportación de progreso para el docente (#30).

Verifica:
  1. El filtro por estudiante en el CSV y el HTML
  2. El reporte HTML imprimible (tabla, filtros y escape de HTML)
  3. El parser de `yap exportar` (formato, filtros, ruta y errores)
  4. El gate del modo profesor y el enrutado en interpret()

Ejecucion: python3 -m pytest tests/test_yap_exportar.py -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


PROGRESO = {
    "cursos": {
        "FPY1101": {
            "EA1": {
                "completada": False,
                "total_actividades": 4,
                "actividades": {
                    "1": {
                        "puntaje": 80,
                        "aprobado": True,
                        "fecha_aprobacion": "2026-09-10T10:00:00",
                    },
                    "2": {"puntaje": 40, "aprobado": False},
                },
            }
        }
    }
}


class ExportarBase:
    """Aisla perfil, aula y cursos en un directorio temporal."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.aula = os.path.join(self.tmpdir, "aula")
        self.patchers = [
            mock.patch.object(
                yap, "PROFILE_FILE", os.path.join(self.tmpdir, "profile.json")
            ),
            mock.patch.object(yap, "AULA_DIR", self.aula),
            mock.patch.object(
                yap, "PROGRESS_FILE", os.path.join(self.tmpdir, "progress.json")
            ),
            mock.patch.object(yap, "CURSOS_DIR", os.path.join(self.tmpdir, "cursos")),
        ]
        for p in self.patchers:
            p.start()

    def teardown_method(self):
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def importar(self, nombre, datos=PROGRESO):
        os.makedirs(self.aula, exist_ok=True)
        registro = {
            "nombre": nombre,
            "origen": "/tmp/x.json",
            "importado": "2026-09-15T08:00:00",
            "progreso": datos,
        }
        with open(
            os.path.join(self.aula, yap._slug(nombre) + ".json"), "w", encoding="utf-8"
        ) as f:
            json.dump(registro, f)
        return registro

    def ruta(self, nombre):
        return os.path.join(self.tmpdir, nombre)


# ============================================================
# 1. FILTRO POR ESTUDIANTE
# ============================================================


class TestFiltroEstudiante(ExportarBase):
    def test_csv_sin_filtro_incluye_a_todos(self):
        self.importar("Maria")
        self.importar("Pedro")
        destino = self.ruta("todos.csv")
        assert yap.exportar_csv(destino) == destino
        with open(destino, encoding="utf-8") as f:
            contenido = f.read()
        assert "Maria" in contenido and "Pedro" in contenido

    def test_csv_con_filtro_deja_solo_a_ese_estudiante(self):
        self.importar("Maria")
        self.importar("Pedro")
        destino = self.ruta("maria.csv")
        assert yap.exportar_csv(destino, estudiante="MARIA") == destino
        with open(destino, encoding="utf-8") as f:
            contenido = f.read()
        assert "Maria" in contenido
        assert "Pedro" not in contenido

    def test_filtro_sin_coincidencia_es_error(self):
        self.importar("Maria")
        salida = yap.exportar_csv(self.ruta("x.csv"), estudiante="Zaira")
        assert salida.startswith("[ERROR]")
        assert "Zaira" in salida

    def test_sin_alumnos_sigue_siendo_error(self):
        salida = yap.exportar_csv(self.ruta("x.csv"))
        assert salida.startswith("[ERROR]")


# ============================================================
# 2. REPORTE HTML
# ============================================================


class TestReporteHTML(ExportarBase):
    def test_genera_tabla_con_los_estudiantes(self):
        self.importar("Maria")
        destino = self.ruta("reporte.html")
        assert yap.exportar_html(destino) == destino
        with open(destino, encoding="utf-8") as f:
            contenido = f.read()
        assert "<table>" in contenido
        assert "Maria" in contenido
        assert "Actividades totales" in contenido
        # documento autocontenido: sin recursos externos
        assert "http://" not in contenido and "https://" not in contenido

    def test_escape_html_en_los_nombres(self):
        self.importar("Ana <script>alert(1)</script>")
        destino = self.ruta("peligro.html")
        yap.exportar_html(destino)
        with open(destino, encoding="utf-8") as f:
            contenido = f.read()
        assert "<script>" not in contenido
        assert "&lt;script&gt;" in contenido

    def test_filtro_de_curso_aparece_en_el_reporte(self):
        self.importar("Maria")
        destino = self.ruta("por-curso.html")
        yap.exportar_html(destino, curso="FPY1101")
        with open(destino, encoding="utf-8") as f:
            contenido = f.read()
        assert "Filtros: curso FPY1101" in contenido

    def test_filtro_por_estudiante_en_html(self):
        self.importar("Maria")
        self.importar("Pedro")
        destino = self.ruta("uno.html")
        yap.exportar_html(destino, estudiante="pedro")
        with open(destino, encoding="utf-8") as f:
            contenido = f.read()
        assert "Pedro" in contenido
        assert "Maria" not in contenido


# ============================================================
# 3. PARSER DEL COMANDO
# ============================================================


class TestParserExportar(ExportarBase):
    def setup_method(self):
        super().setup_method()
        self.importar("Maria")

    def test_csv_por_defecto_con_ruta(self):
        destino = self.ruta("salida.csv")
        salida = yap._exportar(destino)
        assert salida.startswith("[OK]")
        assert destino in salida
        assert os.path.exists(destino)

    def test_flag_curso_y_ruta(self):
        destino = self.ruta("c.csv")
        salida = yap._exportar(f"--csv --curso FPY1101 {destino}")
        assert salida.startswith("[OK]")
        with open(destino, encoding="utf-8") as f:
            assert "Maria" in f.read()

    def test_flag_curso_con_igual(self):
        destino = self.ruta("c2.csv")
        assert yap._exportar(f"--curso=FPY1101 {destino}").startswith("[OK]")
        assert os.path.exists(destino)

    def test_pdf_es_alias_del_html(self):
        salida = yap._exportar(f"--pdf {self.ruta('informe.pdf.html')}")
        assert salida.startswith("[OK]")
        assert "Imprimir" in salida

    def test_html_con_estudiante(self):
        self.importar("Pedro")
        destino = self.ruta("f.html")
        assert yap._exportar(f"--html --estudiante maria {destino}").startswith("[OK]")
        with open(destino, encoding="utf-8") as f:
            contenido = f.read()
        assert "Maria" in contenido and "Pedro" not in contenido

    def test_flag_desconocido(self):
        assert "[ERROR] Opcion desconocida: --zzz" in yap._exportar("--zzz")

    def test_curso_sin_valor(self):
        assert "[ERROR] Falta el valor de --curso" in yap._exportar("--curso")


# ============================================================
# 4. GATE Y ENRUTADO
# ============================================================


class TestGateYEnrutado(ExportarBase):
    def test_sin_rol_profesor_no_exporta(self):
        self.importar("Maria")
        salida = yap.cmd_exportar("")
        assert "profesor" in salida.lower()

    def test_interpret_mapea_exportar(self):
        assert yap.interpret("exportar") == ("exportar", "")
        assert yap.interpret("exportar --html") == ("exportar", "--html")
        assert yap.interpret("export --csv --curso FPY1101") == (
            "exportar",
            "--csv --curso FPY1101",
        )
