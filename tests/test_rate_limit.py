"""Rate limiting de consultas al LLM (#256).

El modelo corre en el equipo del alumno: un bucle de consultas deja un
Celeron sin CPU durante la clase. Ventana deslizante en memoria, comprobada
antes de invocar al modelo, local o nube.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import yap

RAIZ = Path(__file__).resolve().parent.parent
MAX = yap.RATE_MAX_CONSULTAS
VENTANA = yap.RATE_VENTANA_S


def _llenar(ahora=0.0):
    for _ in range(MAX):
        assert yap._consulta_permitida(ahora) == (True, 0)


class TestVentana:
    def test_dentro_del_limite_se_admite(self):
        _llenar()
        assert len(yap._CONSULTAS_RECIENTES) == MAX

    def test_la_siguiente_se_rechaza_con_la_espera(self):
        _llenar(0.0)
        assert yap._consulta_permitida(0.0) == (False, int(VENTANA))

    def test_la_espera_baja_con_el_tiempo(self):
        _llenar(0.0)
        assert yap._consulta_permitida(VENTANA - 0.5) == (False, 1)

    def test_al_salir_de_la_ventana_se_admite_otra_vez(self):
        _llenar(0.0)
        assert yap._consulta_permitida(VENTANA)[0] is True

    def test_un_rechazo_no_alarga_la_espera(self):
        """Reintentar en bucle no debe castigar mas: el rechazo no cuenta."""
        _llenar(0.0)
        for _ in range(50):
            assert yap._consulta_permitida(VENTANA / 2)[0] is False
        assert len(yap._CONSULTAS_RECIENTES) == MAX
        for _ in range(MAX):
            assert yap._consulta_permitida(VENTANA)[0] is True

    def test_limites_razonables(self):
        assert 10 <= MAX <= 120
        assert VENTANA >= 30


def _resultado_llama():
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="hola", stderr="")


class TestCmdQuery:
    def test_rechaza_antes_de_invocar_al_modelo(self):
        _llenar(yap.time.monotonic())
        with mock.patch.object(yap.subprocess, "run") as run:
            out = yap.cmd_query("pregunta", store_history=False)
        run.assert_not_called()
        assert str(MAX) in out
        assert out.startswith("[WARN]")

    def test_cada_consulta_cuenta_una_vez(self):
        with mock.patch.object(yap.subprocess, "run", return_value=_resultado_llama()):
            yap.cmd_query("uno", store_history=False)
            yap.cmd_query("dos", store_history=False, allow_super_fallback=False)
        assert len(yap._CONSULTAS_RECIENTES) == 2

    def test_query_local_explicita_tambien_cuenta(self):
        """allow_super_fallback=False es la opcion 'solo local' del alumno."""
        _llenar(yap.time.monotonic())
        with mock.patch.object(yap.subprocess, "run") as run:
            yap.cmd_query("x", store_history=False, allow_super_fallback=False)
        run.assert_not_called()

    def test_el_fallback_de_super_no_cuenta_doble(self):
        """Super no disponible -> baja a local: una sola consulta del alumno."""
        with mock.patch.object(yap.subprocess, "run", return_value=_resultado_llama()):
            yap.cmd_query_super("pregunta", store_history=False)
        assert len(yap._CONSULTAS_RECIENTES) == 1

    def test_super_directo_tambien_esta_limitado(self):
        _llenar(yap.time.monotonic())
        with mock.patch.object(yap, "_post_super") as post, mock.patch.object(
            yap.subprocess, "run"
        ) as run:
            out = yap.cmd_query_super("pregunta", store_history=False)
        post.assert_not_called()
        run.assert_not_called()
        assert str(MAX) in out


def test_el_estado_no_persiste_entre_procesos():
    """En memoria: reiniciar Yap resetea el contador, a proposito."""
    r = subprocess.run(
        [sys.executable, "-c", "import yap; print(len(yap._CONSULTAS_RECIENTES))"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        env={**os.environ, "PYTHONPATH": str(RAIZ)},
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().splitlines()[-1] == "0"


def test_mensaje_traducido_en_es_y_en():
    for lang in ("es", "en"):
        cat = json.loads((RAIZ / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        msg = cat["error"]["rate_limited"]
        assert "{max}" in msg and "{segundos}" in msg, lang
