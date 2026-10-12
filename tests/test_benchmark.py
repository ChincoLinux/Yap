"""tests/test_benchmark.py — Harness de benchmark (#40)."""

import json
import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import benchmark


CPUINFO = (
    "processor\t: 0\n"
    "model name\t: Intel(R) Celeron(R) N4000 CPU @ 1.10GHz\n"
    "cpu cores\t: 2\n"
)
MEMINFO = "MemTotal:        3840000 kB\nSwapTotal:       0 kB\n"

STDERR = (
    "llama_print_timing: prompt eval time = 2345.67 ms / 128 tokens "
    "(18.33 ms per token, 54.55 tokens per second)\n"
    "llama_print_timing:        eval time = 1234.56 ms / 64 tokens "
    "(19.29 ms per token, 51.85 tokens per second)\n"
)


class TestPerfilHardware:
    def test_parsea_cpu_y_ram(self, tmp_path):
        cpuinfo = tmp_path / "cpuinfo"
        meminfo = tmp_path / "meminfo"
        cpuinfo.write_text(CPUINFO, encoding="utf-8")
        meminfo.write_text(MEMINFO, encoding="utf-8")
        perfil = benchmark.perfil_hardware(str(cpuinfo), str(meminfo))
        assert "Celeron" in perfil["cpu"]
        assert perfil["ram_gb"] == 3.7
        assert perfil["nucleos"] >= 1

    def test_archivos_inexistentes_no_tumban_el_script(self, tmp_path):
        perfil = benchmark.perfil_hardware(
            str(tmp_path / "no-existe"), str(tmp_path / "tampoco")
        )
        assert perfil["cpu"] == "desconocido"
        assert perfil["ram_gb"] is None


class TestParseoTimings:
    def test_extrae_tokens_y_ms(self):
        t = benchmark.parsear_timings(STDERR)
        assert t["prompt"] == 128
        assert t["generados"] == 64
        assert abs(t["ms"] - 3580.23) < 0.01

    def test_sin_timings_devuelve_none(self):
        assert benchmark.parsear_timings("") is None
        assert benchmark.parsear_timings(None) is None
        assert benchmark.parsear_timings("algo sin numeros") is None


class TestResumen:
    def test_mediana_y_tok_s(self):
        corridas = [
            {"ms": 1000.0, "generados": 50},
            {"ms": 2000.0, "generados": 100},
            {"ms": 1500.0, "generados": 75},
        ]
        r = benchmark.resumen(corridas)
        assert r["corridas"] == 3
        assert r["ms_mediana"] == 1500.0
        assert r["ms_max"] == 2000.0
        # 75 tokens en 1.5 s -> 50 tok/s
        assert r["tok_s"] == 50.0

    def test_sin_corridas_devuelve_none(self):
        assert benchmark.resumen([]) is None


class TestCLI:
    def test_sin_llama_cli_sale_con_codigo_2(self, capsys):
        with mock.patch.object(benchmark.shutil, "which", return_value=None):
            assert benchmark.main([]) == 2
        assert "llama-cli" in capsys.readouterr().err

    def test_sin_modelo_sale_con_codigo_2(self, tmp_path, capsys):
        modelo = tmp_path / "no-existe.gguf"
        with mock.patch.object(benchmark.shutil, "which", return_value="/bin/true"):
            assert benchmark.main(["--modelo", str(modelo)]) == 2
        assert "modelo" in capsys.readouterr().err.lower()

    def test_escribe_json_de_resultados(self, tmp_path, monkeypatch):
        modelo = tmp_path / "m.gguf"
        modelo.write_text("x", encoding="utf-8")
        salida = tmp_path / "res.json"

        def correr_falso(*args, **kwargs):
            return {"prompt": 10, "generados": 5, "ms": 1000.0, "ms_pared": 1100.0}

        with mock.patch.object(
            benchmark.shutil, "which", return_value="/bin/true"
        ), mock.patch.object(benchmark, "correr_llama", side_effect=correr_falso):
            assert (
                benchmark.main(
                    ["--modelo", str(modelo), "--quick", "--json", str(salida)]
                )
                == 0
            )

        datos = json.loads(salida.read_text(encoding="utf-8"))
        assert datos["resultados"]["caliente"]["corridas"] == 2
        assert datos["hardware"]["nucleos"] >= 1
