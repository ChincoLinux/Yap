"""Tests del reporte de consumo de tokens del LLM local (#85)."""

import yap


SAMPLE = (
    "llama_print_timing:        load time = 100.00 ms\n"
    "llama_print_timing: prompt eval time = 2345.67 ms / 128 tokens "
    "(18.33 ms per token, 54.55 tokens per second)\n"
    "llama_print_timing:        eval time = 1234.56 ms / 64 tokens "
    "(19.29 ms per token, 51.85 tokens per second)\n"
    "llama_print_timing:        total time = 3580.23 ms / 192 tokens\n"
)


class TestConsumoTokens:
    """Parseo, acumulacion y presentacion del consumo (#85)."""

    def setup_method(self):
        yap._CONSUMO_SESION.update(
            {"prompt": 0, "generados": 0, "ms": 0.0, "llamadas": 0}
        )
        yap._CONSUMO_ULTIMO.clear()

    def test_parsea_prompt_y_eval(self):
        yap._registrar_consumo(SAMPLE)
        assert yap._CONSUMO_ULTIMO["prompt"] == 128
        assert yap._CONSUMO_ULTIMO["generados"] == 64
        assert abs(yap._CONSUMO_ULTIMO["ms"] - 3580.23) < 0.01

    def test_acumula_entre_llamadas(self):
        yap._registrar_consumo(SAMPLE)
        yap._registrar_consumo(SAMPLE)
        assert yap._CONSUMO_SESION["llamadas"] == 2
        assert yap._CONSUMO_SESION["prompt"] == 256
        assert yap._CONSUMO_SESION["generados"] == 128

    def test_stderr_vacio_no_acumula(self):
        yap._registrar_consumo("")
        yap._registrar_consumo(None)
        yap._registrar_consumo("otro texto sin timings")
        assert yap._CONSUMO_SESION["llamadas"] == 0
        assert yap._CONSUMO_ULTIMO == {}

    def test_velocidad_de_generacion(self):
        yap._registrar_consumo(SAMPLE)
        tps = yap._velocidad_tokens(yap._CONSUMO_ULTIMO)
        # 64 tokens en 1.23456 s -> 51.85 tok/s (el numero que imprime llama-cli)
        assert 51.0 < tps < 52.5

    def test_velocidad_sin_tiempo_es_cero(self):
        assert yap._velocidad_tokens({"generados": 10, "ms": 0.0}) == 0.0

    def test_linea_tras_consulta(self):
        yap._registrar_consumo(SAMPLE)
        linea = yap.linea_consumo()
        assert linea is not None
        assert "128" in linea and "64" in linea
        assert "CONSUMO" in linea

    def test_linea_se_puede_desactivar(self, monkeypatch):
        monkeypatch.setenv("YAP_CONSUMO", "0")
        yap._registrar_consumo(SAMPLE)
        assert yap.linea_consumo() is None

    def test_linea_sin_consumo_es_none(self):
        assert yap.linea_consumo() is None

    def test_cmd_consumo_sin_consultas(self):
        salida = yap.cmd_consumo()
        assert "CONSUMO" in salida

    def test_cmd_consumo_acumulado(self):
        yap._registrar_consumo(SAMPLE)
        salida = yap.cmd_consumo()
        assert "192" in salida  # 128 prompt + 64 generados

    def test_interpret_mapea_consumo(self):
        assert yap.interpret("consumo") == ("consumo", "")
        assert yap.interpret("--consumo") == ("consumo", "")
        assert yap.interpret("tokens") == ("consumo", "")
