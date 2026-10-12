"""Techos de lectura: #234 (webfetch) y #238 (importar progreso).

Estos tests invocan la funcion. Antes se comprobaba que existiera un literal
en el fuente, lo que dejaba la vulnerabilidad abierta en verde: ver #241.
"""

import json
from unittest import mock

import pytest

import yap


class _Respuesta:
    """Respuesta de urlopen que solo entrega lo que se le pide."""

    def __init__(self, cuerpo, contador):
        self.cuerpo = cuerpo
        self.contador = contador

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, n=-1):
        # Sin limite entrega TODO, que es como se agota la RAM.
        if n is None or n < 0:
            self.contador["n"] += len(self.cuerpo)
            return self.cuerpo
        self.contador["n"] += min(n, len(self.cuerpo))
        return self.cuerpo[:n]


class TestWebfetchTecho:
    """#234 — cmd_webfetch no descarga sin limite."""

    @pytest.fixture
    def web(self, tmp_path):
        f = tmp_path / "web.conf"
        f.write_text("wikipedia.org\n", encoding="utf-8")
        return str(f)

    def _traer(self, web, cuerpo, techo, respuesta=None):
        """Devuelve (resultado, bytes_realmente_descargados)."""
        contador = {"n": 0}
        resp = respuesta if respuesta is not None else _Respuesta(cuerpo, contador)
        with mock.patch.object(yap, "WHITELIST_WEB", web):
            with mock.patch.object(yap, "TECHO_DESCARGA_BYTES", techo):
                with mock.patch("urllib.request.urlopen", return_value=resp):
                    res = yap.cmd_webfetch("https://wikipedia.org/x")
        return res, contador["n"]

    def test_no_descarga_mas_del_tope(self, web):
        """La regresión clave: read() sin argumento baja el cuerpo entero."""
        res, descargado = self._traer(web, b"x" * 200000, 4096)
        assert descargado <= 4096 + 1, (
            f"se descargaron {descargado} bytes con un tope de 4096"
        )
        assert "[ERROR]" in res

    def test_read_recibe_el_tope_como_argumento(self, web):
        """Si read() se llama sin argumento, no hay tope que aplicar."""
        llamada = {}

        class _Espia:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                llamada["n"] = n
                return b"ok"

        self._traer(web, b"", 4096, respuesta=_Espia())
        assert "n" in llamada, "read() no fue llamado"
        assert llamada["n"] >= 0, "read() se llamo sin tope (n por defecto)"
        assert llamada["n"] <= 4096 + 1

    def test_dentro_del_tope_se_acepta(self, web):
        res, _ = self._traer(web, b"<html>ok</html>", 1024)
        assert "[ERROR]" not in res, res
        assert "ok" in res

    def test_recurso_mas_grande_que_el_tope_falla(self, web):
        """#234: debian.org sirve 12 MB y se aceptaba entero."""
        res, _ = self._traer(web, b"x" * 100000, 4096)
        assert "[ERROR]" in res, res
        assert "maximo" in res or "4096" in res

    def test_cuerpo_enorme_no_se_construye(self, web):
        """Un cuerpo de 50 MB explota si se pide entero."""
        class _Enorme:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                if n is None or n < 0:
                    raise AssertionError("read() sin limite expondria 50 MB")
                return b"x" * n

        res, _ = self._traer(web, b"", 4096, respuesta=_Enorme())
        # Debe ser error de tope, no un error generico de descarga: si
        # read() se llama sin limite, la excepcion la traga el except y el
        # mensaje es error.fetch.
        assert "maximo" in res or "4096" in res, res
        assert "Error al obtener" not in res, res

    def test_el_texto_final_sigue_limitado(self, web):
        """El techo de 3000 caracteres se aplica al texto ya obtenido."""
        res, _ = self._traer(web, b"<p>" + b"palabra " * 5000 + b"</p>", 4096)
        assert "[ERROR]" in res, res

    def test_techo_del_proyecto_es_razonable(self):
        """10 MB: suficiente para una pagina, imposible de agotar 4 GB."""
        assert yap.TECHO_DESCARGA_BYTES == 10 * 1024 * 1024


class TestImportarProgresoTecho:
    """#238 — el JSON de un USB no se parsea sin limite."""

    @pytest.fixture
    def aula(self, tmp_path, monkeypatch):
        destino = tmp_path / "aula"
        monkeypatch.setattr(yap, "AULA_DIR", str(destino))
        return destino

    def _fichero(self, tmp_path, peso):
        p = tmp_path / "progress.json"
        datos = {"cursos": {"relleno": "x" * max(0, peso - 32)}}
        p.write_text(json.dumps(datos), encoding="utf-8")
        return str(p)

    def test_fichero_dentro_del_tope_se_importa(self, tmp_path, aula):
        path = self._fichero(tmp_path, 200)
        with mock.patch.object(yap, "TECHO_PROGRESO_BYTES", 4096):
            importados, errores = yap.importar_progreso(path)
        assert errores == [], errores
        assert len(importados) == 1

    def test_fichero_sobre_el_tope_se_rechaza(self, tmp_path, aula):
        path = self._fichero(tmp_path, 40000)
        with mock.patch.object(yap, "TECHO_PROGRESO_BYTES", 4096):
            importados, errores = yap.importar_progreso(path)
        assert importados == []
        assert len(errores) == 1
        assert "supera el maximo" in errores[0]

    def test_no_escribe_nada_si_excede(self, tmp_path, aula):
        path = self._fichero(tmp_path, 40000)
        with mock.patch.object(yap, "TECHO_PROGRESO_BYTES", 4096):
            yap.importar_progreso(path)
        assert not aula.exists() or not list(aula.glob("*.json"))

    def test_no_se_llama_json_load_si_excede(self, tmp_path, aula):
        """La comprobacion es previa: json.load no se llega a invocar."""
        path = self._fichero(tmp_path, 40000)
        with mock.patch.object(yap, "TECHO_PROGRESO_BYTES", 4096):
            with mock.patch("json.load") as cargador:
                yap.importar_progreso(path)
        cargador.assert_not_called()

    def test_getsize_antes_de_json_load(self, tmp_path, aula):
        """Orden estricto: se mide, y solo despues se parsea."""
        orden = []

        original_getsize = yap.os.path.getsize
        original_load = json.load

        def _getsize(p):
            orden.append("getsize")
            return original_getsize(p)

        def _load(f):
            orden.append("load")
            return original_load(f)

        path = self._fichero(tmp_path, 40000)
        with mock.patch.object(yap.os.path, "getsize", side_effect=_getsize):
            with mock.patch("json.load", side_effect=_load):
                with mock.patch.object(yap, "TECHO_PROGRESO_BYTES", 4096):
                    yap.importar_progreso(path)

        assert orden == ["getsize"], f"orden inesperado: {orden}"

    def test_fichero_normal_sigue_funcionando(self, tmp_path, aula):
        """Sin cambio visible: un progress real de decenas de KB pasa."""
        path = str(tmp_path / "progress.json")
        real = {
            "cursos": {f"curso{i}": {"ea": {"a1": {"aprobado": True}}} for i in range(20)}
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(real, f)
        with mock.patch.object(yap, "TECHO_PROGRESO_BYTES", 4 * 1024 * 1024):
            importados, errores = yap.importar_progreso(path)
        assert errores == [], errores
        assert len(importados) == 1

    def test_techo_del_progreso_es_razonable(self):
        """4 MB deja margen sobre el progreso real y evita la DoS."""
        assert yap.TECHO_PROGRESO_BYTES == 4 * 1024 * 1024
