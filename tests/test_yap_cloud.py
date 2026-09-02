"""
test_yap_cloud.py — Delegación a Gemini 3.7 Flash en Agent Platform

Sin Internet, sin LLM, sin GCP. Todo mockeado.
"""

import json
import os
import shutil
import sys
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


class CloudTestBase:
    def setup_method(self):
        yap.HISTORY.clear()
        yap._NUBE_ESTADO = "local"
        yap._ULTIMO_CONSUMO = None
        yap._CONSUMO_SESION = {"prompt": 0, "respuesta": 0, "total": 0}
        self._consumo_dir = tempfile.mkdtemp()
        self._consumo_file = os.path.join(self._consumo_dir, "consumo.json")
        self._consumo_patch = patch.object(yap, "CONSUMO_FILE", self._consumo_file)
        self._consumo_patch.start()
        self._env_backup = {
            k: os.environ.get(k)
            for k in list(os.environ)
            if k.startswith("YAP_CLOUD")
        }
        for k in list(os.environ):
            if k.startswith("YAP_CLOUD"):
                del os.environ[k]

    def teardown_method(self):
        self._consumo_patch.stop()
        shutil.rmtree(self._consumo_dir, ignore_errors=True)
        for k in list(os.environ):
            if k.startswith("YAP_CLOUD"):
                del os.environ[k]
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yap.HISTORY.clear()
        yap._NUBE_ESTADO = "local"
        yap._ULTIMO_CONSUMO = None
        yap._CONSUMO_SESION = {"prompt": 0, "respuesta": 0, "total": 0}

    def habilitar(self, token="token-flota", endpoint=None):
        os.environ["YAP_CLOUD_ENABLED"] = "1"
        os.environ["YAP_CLOUD_TOKEN"] = token
        os.environ["YAP_CLOUD_ENDPOINT"] = endpoint or yap.CLOUD_DEFAULT_ENDPOINT


def _auth_header(req):
    items = []
    if hasattr(req, "header_items"):
        items.extend(req.header_items())
    items.extend(getattr(req, "unredirected_hdrs", {}).items())
    items.extend(getattr(req, "headers", {}).items())
    for key, val in items:
        if str(key).lower() == "authorization":
            return val
    return None


def _urlopen_json(payload, status=200):
    raw = json.dumps(payload).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = raw
    resp.status = status
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


class TestConsultaCompleja(CloudTestBase):
    def test_corta_sin_pistas_no_es_compleja(self):
        assert yap.consulta_compleja("hola") is False
        assert yap.consulta_compleja("que hora es") is False

    def test_pista_explica_es_compleja(self):
        assert yap.consulta_compleja("explica la diferencia entre while y for") is True

    def test_texto_largo_es_compleja(self):
        assert yap.consulta_compleja("x" * 80) is True


class TestHostPermitido(CloudTestBase):
    def test_psc_por_defecto_permitido(self):
        assert yap._host_nube_permitido(yap.CLOUD_DEFAULT_ENDPOINT) is True

    def test_ip_publica_bloqueada(self):
        assert yap._host_nube_permitido("https://8.8.8.8/v1/query") is False

    def test_googleapis_bloqueado_sin_allowlist(self):
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        assert yap._host_nube_permitido(url) is False

    def test_hostname_en_allowlist(self):
        os.environ["YAP_CLOUD_HOSTS"] = "agent.yap.lab"
        assert yap._host_nube_permitido("https://agent.yap.lab/v1/query") is True

    def test_scheme_file_bloqueado(self):
        assert yap._host_nube_permitido("file:///etc/passwd") is False

    def test_cidr_configurable(self):
        os.environ["YAP_CLOUD_CIDR"] = "192.168.10.0/24"
        assert yap._host_nube_permitido("https://192.168.10.5/v1") is True
        assert yap._host_nube_permitido("https://10.40.0.10/v1") is False


class TestSanitizarYPayload(CloudTestBase):
    def test_oculta_home_y_correo(self):
        texto = "mira /home/alumno/tarea.py y escribe a a@b.cl"
        out = yap._sanitizar_texto_nube(texto)
        assert "/home/alumno" not in out
        assert "a@b.cl" not in out
        assert "[correo]" in out

    def test_payload_no_lleva_token_ni_ruta_home(self):
        self.habilitar()
        yap.HISTORY.append(("/home/juan/secretos.py", "ok"))
        payload = yap._payload_nube("explica listas con /home/juan/x.py")
        blob = json.dumps(payload)
        assert "token-flota" not in blob
        assert "/home/juan" not in blob
        assert payload["model"] == "gemini-3.7-flash"
        assert payload["intent"] == "query"
        assert "request_id" in payload
        assert payload["request_id"].startswith("yap-")

    def test_historial_acotado_a_cuatro_turnos(self):
        for i in range(8):
            yap.HISTORY.append((f"u{i}", f"a{i}"))
        payload = yap._payload_nube("explica")
        users = [h for h in payload["historial"] if h["rol"] == "user"]
        assert len(users) == yap.CLOUD_HISTORY_MAX


class TestDelegacion(CloudTestBase):
    def test_deshabilitada_no_delega(self):
        assert yap.debe_delegar_nube("explica la diferencia entre while y for") is False

    def test_habilitada_y_compleja_delega(self):
        self.habilitar()
        assert yap.debe_delegar_nube("explica la diferencia entre while y for") is True

    def test_habilitada_corta_no_delega(self):
        self.habilitar()
        assert yap.debe_delegar_nube("hola") is False

    def test_sin_token_no_delega(self):
        os.environ["YAP_CLOUD_ENABLED"] = "1"
        os.environ["YAP_CLOUD_ENDPOINT"] = yap.CLOUD_DEFAULT_ENDPOINT
        assert yap.nube_configurada() is False


class TestCmdQueryCloud(CloudTestBase):
    @patch("yap.cmd_query", return_value="local-ok")
    def test_sin_nube_usa_local_sin_red(self, mock_local):
        with patch("urllib.request.urlopen") as red:
            out = yap.cmd_query_cloud("explica listas", store_history=False)
        red.assert_not_called()
        mock_local.assert_called_once()
        assert out == "local-ok"
        assert yap.etiqueta_motor() == "LOCAL"

    @patch("yap.cmd_query", return_value="local-ok")
    def test_endpoint_publico_no_abre_conexion(self, mock_local):
        self.habilitar(endpoint="https://8.8.8.8/v1/query")
        with patch("urllib.request.urlopen") as red:
            out = yap.cmd_query_cloud("explica listas", store_history=False)
        red.assert_not_called()
        assert "local-ok" in out

    @patch("urllib.request.urlopen")
    def test_respuesta_contrato_yap(self, mock_urlopen):
        self.habilitar()
        mock_urlopen.return_value = _urlopen_json({"texto": "While itera con condicion."})
        out = yap.cmd_query_cloud("explica while", store_history=True)
        assert "While itera" in out
        assert "[WARN]" not in out
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.get_method() == "POST"
        assert _auth_header(req) == "Bearer token-flota"
        body = json.loads(req.data.decode("utf-8"))
        assert body["model"] == "gemini-3.7-flash"
        assert yap.HISTORY[-1][1] == out
        assert yap.etiqueta_motor() == "NUBE"

    @patch("urllib.request.urlopen")
    def test_respuesta_gemini_candidates(self, mock_urlopen):
        self.habilitar()
        mock_urlopen.return_value = _urlopen_json({
            "candidates": [{"content": {"parts": [{"text": "ok gemini"}]}}],
        })
        out = yap.cmd_query_cloud("explica", store_history=False)
        assert out == "ok gemini"

    @patch("yap.cmd_query", return_value="fallback-local")
    @patch("urllib.request.urlopen", side_effect=TimeoutError("timeout"))
    def test_timeout_cae_a_local(self, _red, mock_local):
        self.habilitar()
        out = yap.cmd_query_cloud("explica listas", store_history=False)
        assert "[WARN] Nube no disponible" in out
        assert "fallback-local" in out
        mock_local.assert_called_once()
        assert yap.etiqueta_motor() == "DEGRADADO"

    @patch("urllib.request.urlopen")
    def test_peticion_sin_timeout(self, mock_urlopen):
        self.habilitar()
        mock_urlopen.return_value = _urlopen_json({"texto": "ok"})
        yap.cmd_query_cloud("explica listas", store_history=False)
        _args, kwargs = mock_urlopen.call_args
        assert kwargs.get("timeout") is None

    @patch("yap.cmd_query", return_value="fallback-local")
    def test_token_desde_archivo(self, mock_local):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("secreto-archivo\n")
            os.environ["YAP_CLOUD_ENABLED"] = "1"
            os.environ["YAP_CLOUD_TOKEN_FILE"] = path
            os.environ["YAP_CLOUD_ENDPOINT"] = yap.CLOUD_DEFAULT_ENDPOINT
            with patch("urllib.request.urlopen") as red:
                red.return_value = _urlopen_json({"texto": "desde archivo"})
                out = yap.cmd_query_cloud("explica", store_history=False)
            assert out == "desde archivo"
            req = red.call_args[0][0]
            assert _auth_header(req) == "Bearer secreto-archivo"
        finally:
            os.remove(path)


class TestInterpretNube(CloudTestBase):
    def test_nube_pelada_es_status(self):
        assert yap.interpret("nube") == ("nube", "")

    def test_nube_pregunta_fuerza_cloud_query(self):
        action, param = yap.interpret("nube explica while")
        assert action == "cloud_query"
        assert "explica while" in param

    @patch.object(yap, "classify_intent", return_value=("query", "explica while"))
    def test_query_compleja_se_reescribe_si_hay_nube(self, _cls):
        self.habilitar()
        action, param = yap.interpret("explica la diferencia entre while y for")
        assert action == "cloud_query"

    @patch.object(yap, "classify_intent", return_value=("open_app", "firefox"))
    def test_open_app_nunca_se_va_a_la_nube(self, _cls):
        self.habilitar()
        action, param = yap.interpret("abre firefox")
        assert action == "open_app"
        assert param == "firefox"

    @patch.object(yap, "classify_intent")
    def test_status_no_pasa_por_el_llm(self, mock_cls):
        yap.interpret("nube")
        mock_cls.assert_not_called()


class TestHandleActionNube(CloudTestBase):
    def test_status_no_abre_red(self):
        with patch("urllib.request.urlopen") as red:
            with patch("builtins.print"):
                yap.handle_action("nube", "", "nube")
        red.assert_not_called()

    def test_cloud_query_despacha_cmd_query_cloud(self):
        with patch.object(yap, "cmd_query_cloud", return_value="ok-nube") as cmd:
            with patch("builtins.print"):
                yap.handle_action("cloud_query", "explica", "nube explica")
        cmd.assert_called_once()


class TestCmdNubeStatus(CloudTestBase):
    def test_status_no_imprime_el_token(self):
        self.habilitar(token="supersecreto")
        out = yap.cmd_nube_status()
        assert "supersecreto" not in out
        assert "gemini-3.7-flash" in out
        assert "presente" in out


class TestAgentPlatformArtifact:
    def test_modelo_fijado_a_gemini_37_flash(self):
        root = os.path.join(os.path.dirname(__file__), "..", "agent-platform", "yap_nube")
        agent_py = os.path.join(root, "agent.py")
        with open(agent_py, encoding="utf-8") as f:
            fuente = f.read()
        assert 'MODEL = "gemini-3.7-flash"' in fuente
        assert "kernel local DECIDE" in fuente or "kernel local decide" in fuente.lower()
        assert "google.adk.agents" in fuente

    def test_importar_agente_sin_adk_no_rompe(self):
        root = os.path.join(os.path.dirname(__file__), "..", "agent-platform")
        sys.path.insert(0, root)
        try:
            import yap_nube.agent as agent
            assert agent.MODEL == "gemini-3.7-flash"
        finally:
            sys.path.pop(0)


class TestConsumoTokens(CloudTestBase):
    def test_usage_metadata_gemini_se_registra(self):
        self.habilitar()
        with patch("urllib.request.urlopen") as red:
            red.return_value = _urlopen_json({
                "candidates": [{"content": {"parts": [{"text": "ok gemini"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 20,
                    "totalTokenCount": 30,
                },
            })
            out = yap.cmd_query_cloud("explica", store_history=False)
        assert out == "ok gemini"
        assert yap._ULTIMO_CONSUMO == {"prompt": 10, "respuesta": 20, "total": 30}
        assert yap._load_consumo()["total"] == 30

    def test_contrato_uso_se_registra(self):
        self.habilitar()
        with patch("urllib.request.urlopen") as red:
            red.return_value = _urlopen_json({
                "texto": "While itera con condicion.",
                "uso": {"prompt": 8, "respuesta": 12, "total": 20},
            })
            out = yap.cmd_query_cloud("explica while", store_history=False)
        assert "While itera" in out
        assert yap._ULTIMO_CONSUMO["total"] == 20

    def test_banner_muestra_tokens_acumulados(self):
        yap._write_consumo_file({"prompt": 10, "respuesta": 20, "total": 42})
        linea = yap._linea_consumo_total()
        assert "42" in linea
        assert "Tokens gastados" in linea

    def test_banner_cero_si_no_hay_datos(self):
        linea = yap._linea_consumo_total()
        assert "Tokens gastados: 0" in linea

    def test_llama_stderr_se_parsea(self):
        stderr = (
            "llama_perf_context_print: prompt eval time =   12.00 ms /    15 tokens\n"
            "llama_perf_context_print:        eval time =  120.00 ms /    40 tokens\n"
        )
        uso = yap._uso_tokens_llama(stderr)
        assert uso == {"prompt": 15, "respuesta": 40, "total": 55}

    def test_imprime_consumo_al_final_de_la_consulta(self):
        self.habilitar()
        with patch("urllib.request.urlopen") as red:
            red.return_value = _urlopen_json({
                "texto": "respuesta",
                "uso": {"prompt": 3, "respuesta": 7, "total": 10},
            })
            with patch("builtins.print") as mock_print:
                yap.handle_action("cloud_query", "explica", "nube explica")
        printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
        assert "respuesta" in printed
        assert "Tokens de esta consulta: 10" in printed
        assert "entrada 3" in printed
        assert "salida 7" in printed


class TestNoImportsPeligrososCloud:
    def test_yap_sigue_sin_imports_prohibidos(self):
        with open(yap.__file__, encoding="utf-8") as f:
            source = f.read()
        for line in source.split("\n"):
            if line.startswith("import ") or line.startswith("from "):
                for peligroso in ("socket", "ctypes", "pickle", "base64", "codecs"):
                    assert peligroso not in line
