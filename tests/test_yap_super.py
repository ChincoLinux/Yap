"""
test_yap_super.py — Super Yap (#91): Gradio Cloud Run + contexto

Sin Internet, sin LLM, sin llama-cli. Todo mockeado.
El 8B local (super_yap.py / hiperparametros llama.cpp) ya no existe:
si el modelo local tarda 3 min, Yap consulta Gradio en Cloud Run.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap


def _json_endpoint():
    return (
        f"http://{yap.SUPER_NUBE_HOST_LEGACY}:{yap.SUPER_NUBE_PORT_LEGACY}/v1/query"
    )


class SuperTestBase:
    def setup_method(self):
        yap.HISTORY.clear()
        yap._SUPER_ESTADO = "local"
        yap._SUPER_MODO = "auto"
        yap._gradio_reset_cache()
        self._env_backup = {
            k: os.environ.get(k)
            for k in list(os.environ)
            if k.startswith("YAP_SUPER")
        }
        for k in list(os.environ):
            if k.startswith("YAP_SUPER"):
                del os.environ[k]
        os.environ["YAP_SUPER_INTERNET"] = "0"

    def teardown_method(self):
        for k in list(os.environ):
            if k.startswith("YAP_SUPER"):
                del os.environ[k]
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yap.HISTORY.clear()
        yap._SUPER_ESTADO = "local"
        yap._SUPER_MODO = "auto"
        yap._gradio_reset_cache()

    def habilitar(self, endpoint=None, token=""):
        os.environ["YAP_SUPER_ENABLED"] = "1"
        os.environ["YAP_SUPER_ENDPOINT"] = endpoint or _json_endpoint()
        if token:
            os.environ["YAP_SUPER_TOKEN"] = token


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


class TestConsultaParaSuper(SuperTestBase):
    def test_corta_sin_pistas_no_delega(self):
        assert yap.consulta_para_super("hola") is False
        assert yap.consulta_para_super("que hora es") is False

    def test_pista_explica_delega(self):
        assert yap.consulta_para_super("explica la diferencia entre while y for") is True

    def test_texto_largo_delega(self):
        assert yap.consulta_para_super("x" * 80) is True

    def test_historial_largo_excede_tokens(self):
        yap.HISTORY.extend([("u" * 400, "a" * 400) for _ in range(6)])
        assert yap._excede_tokens_local("sigue") is True
        assert yap.consulta_para_super("sigue") is True


class TestHostSuperPermitido(SuperTestBase):
    def test_loopback_permitido(self):
        assert yap._host_super_permitido("http://127.0.0.1:8742/v1/query") is True
        assert yap._host_super_permitido("http://localhost:8742/v1/query") is True

    def test_host_nube_pin_permitido(self):
        assert yap._host_es_super_nube(yap.SUPER_DEFAULT_ENDPOINT) is True
        assert yap._host_es_super_gradio(yap.SUPER_DEFAULT_ENDPOINT) is True
        assert yap._host_super_permitido(yap.SUPER_DEFAULT_ENDPOINT) is True
        assert yap._host_super_permitido("http://137.184.146.113:8742/v1/query") is True
        assert yap._host_super_permitido("http://137.184.146.113:80/v1/query") is True

    def test_run_app_ajeno_bloqueado(self):
        assert yap._host_super_permitido("https://otro.southamerica-west1.run.app") is False

    def test_rfc1918_permitido(self):
        assert yap._host_super_permitido("http://10.40.0.10:8742/v1/query") is True
        assert yap._host_super_permitido("http://192.168.1.5/v1") is True
        assert yap._host_super_permitido("http://172.16.0.2/v1") is True

    def test_ip_publica_bloqueada(self):
        assert yap._host_super_permitido("https://8.8.8.8/v1/query") is False

    def test_hostname_publico_bloqueado(self):
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        assert yap._host_super_permitido(url) is False

    def test_hostname_en_allowlist(self):
        os.environ["YAP_SUPER_HOSTS"] = "super.yap.lab"
        assert yap._host_super_permitido("http://super.yap.lab/v1/query") is True

    def test_scheme_file_bloqueado(self):
        assert yap._host_super_permitido("file:///etc/passwd") is False

    def test_notwikipedia_no_cuela_como_host(self):
        os.environ["YAP_SUPER_HOSTS"] = "yap.lab"
        assert yap._host_super_permitido("http://notyap.lab/v1") is False


class TestSanitizarYPayload(SuperTestBase):
    def test_oculta_home_y_correo(self):
        texto = "mira /home/alumno/tarea.py y escribe a a@b.cl"
        out = yap._sanitizar_texto_super(texto)
        assert "/home/alumno" not in out
        assert "a@b.cl" not in out
        assert "[correo]" in out

    def test_payload_lleva_historial_y_no_el_token(self):
        self.habilitar(token="token-aula")
        yap.HISTORY.append(("/home/juan/secretos.py", "ok"))
        payload = yap._payload_super("explica listas con /home/juan/x.py")
        blob = json.dumps(payload)
        assert "token-aula" not in blob
        assert "/home/juan" not in blob
        assert "Llama-3.1-8B" not in blob
        assert "model" not in payload
        assert payload["intent"] == "query"
        assert payload["request_id"].startswith("yap-")
        assert payload["historial"][0]["rol"] == "user"

    def test_historial_acotado(self):
        for i in range(12):
            yap.HISTORY.append((f"u{i}", f"a{i}"))
        payload = yap._payload_super("explica")
        users = [h for h in payload["historial"] if h["rol"] == "user"]
        assert len(users) == min(len(yap.HISTORY), yap.SUPER_HISTORY_MAX)


class TestDelegacion(SuperTestBase):
    def test_deshabilitada_no_delega(self):
        os.environ["YAP_SUPER_ENABLED"] = "0"
        assert yap.debe_delegar_super("explica la diferencia entre while y for") is False

    def test_auto_sin_internet_no_delega(self):
        """Sin red, auto se queda en el Llama local."""
        assert yap._super_habilitado() is True
        assert yap.super_configurada() is True
        assert yap._hay_internet() is False
        assert yap.debe_delegar_super("explica la diferencia entre while y for") is False
        assert yap.debe_delegar_super("hola") is False

    def test_auto_con_internet_delega_a_la_nube(self):
        os.environ["YAP_SUPER_INTERNET"] = "1"
        assert yap._hay_internet() is True
        assert yap.debe_delegar_super("hola") is True
        assert yap.debe_delegar_super("explica la diferencia entre while y for") is True
        assert yap.etiqueta_familia_modelo() == "otro modelo"

    def test_auto_ip_legacy_sin_env_no_delega(self):
        os.environ["YAP_SUPER_ENDPOINT"] = _json_endpoint()
        assert yap._super_habilitado() is False
        assert yap.debe_delegar_super("explica la diferencia entre while y for") is False

    def test_auto_loopback_sin_env_no_delega(self):
        os.environ["YAP_SUPER_ENDPOINT"] = "http://127.0.0.1:8742/v1/query"
        assert yap._super_habilitado() is False
        assert yap.debe_delegar_super("explica la diferencia entre while y for") is False

    def test_habilitada_compleja_tampoco_adelanta(self):
        self.habilitar()
        assert yap.debe_delegar_super("explica la diferencia entre while y for") is False

    def test_habilitada_corta_no_delega(self):
        self.habilitar()
        assert yap.debe_delegar_super("hola") is False

    def test_lan_sin_token_no_configurada(self):
        os.environ["YAP_SUPER_ENABLED"] = "1"
        os.environ["YAP_SUPER_ENDPOINT"] = "http://10.40.0.10:8742/v1/query"
        assert yap.super_configurada() is False

    def test_lan_con_token_si_configurada(self):
        os.environ["YAP_SUPER_ENABLED"] = "1"
        os.environ["YAP_SUPER_ENDPOINT"] = "http://10.40.0.10:8742/v1/query"
        os.environ["YAP_SUPER_TOKEN"] = "aula"
        assert yap.super_configurada() is True

    def test_loopback_sin_token_si_configurada(self):
        self.habilitar()
        assert yap.super_configurada() is True

    def test_loopback_no_exige_7gb(self):
        """Ya no hay 8B local: loopback no pide 7 GB de RAM."""
        self.habilitar(endpoint="http://127.0.0.1:8742/v1/query")
        assert yap.super_configurada() is True

    def test_gradio_configurada_sin_env(self):
        assert yap._host_es_super_gradio(yap._super_endpoint()) is True
        assert yap.super_configurada() is True


class TestCmdQuerySuper(SuperTestBase):
    @patch("yap.cmd_query", return_value="local-ok")
    def test_sin_super_usa_local_sin_red(self, mock_local):
        os.environ["YAP_SUPER_ENABLED"] = "0"
        with patch("urllib.request.urlopen") as red:
            out = yap.cmd_query_super("explica listas", store_history=False)
        red.assert_not_called()
        mock_local.assert_called_once()
        assert out == "local-ok"
        assert yap.etiqueta_motor() == "LOCAL"

    @patch("yap.cmd_query", return_value="local-ok")
    def test_endpoint_publico_no_abre_conexion(self, mock_local):
        self.habilitar(endpoint="https://8.8.8.8/v1/query")
        with patch("urllib.request.urlopen") as red:
            out = yap.cmd_query_super("explica listas", store_history=False)
        red.assert_not_called()
        assert "local-ok" in out

    @patch("urllib.request.urlopen")
    def test_respuesta_contrato_yap_conserva_historial(self, mock_urlopen):
        self.habilitar()
        yap.HISTORY.append(("que es un mientras", "Un ciclo con condicion."))
        mock_urlopen.return_value = _urlopen_json({
            "texto": "Algoritmo Ejemplo...",
        })
        out = yap.cmd_query_super("ahora un ejemplo", store_history=True)
        assert "Algoritmo Ejemplo" in out
        assert "[WARN]" not in out
        req = mock_urlopen.call_args[0][0]
        assert req.get_method() == "POST"
        body = json.loads(req.data.decode("utf-8"))
        assert body["historial"][0]["texto"] == "que es un mientras"
        assert yap.HISTORY[-1] == ("ahora un ejemplo", out)
        assert yap.HISTORY[0][0] == "que es un mientras"
        assert yap.etiqueta_motor() == "SUPER"

    @patch("yap.cmd_query", return_value="fallback-local")
    @patch("urllib.request.urlopen", side_effect=TimeoutError("timeout"))
    def test_timeout_cae_a_local(self, _red, mock_local):
        self.habilitar()
        out = yap.cmd_query_super("explica listas", store_history=False)
        assert "[WARN] Super Yap no disponible" in out
        assert "fallback-local" in out
        mock_local.assert_called_once()
        assert yap.etiqueta_motor() == "DEGRADADO"

    @patch("urllib.request.urlopen")
    def test_token_en_header_no_en_json(self, mock_urlopen):
        self.habilitar(token="secreto-aula")
        mock_urlopen.return_value = _urlopen_json({"texto": "ok"})
        yap.cmd_query_super("explica", store_history=False)
        req = mock_urlopen.call_args[0][0]
        assert _auth_header(req) == "Bearer secreto-aula"
        body = json.loads(req.data.decode("utf-8"))
        assert "secreto-aula" not in json.dumps(body)


class TestInterpretSuper(SuperTestBase):
    def test_super_pelado_es_status(self):
        assert yap.interpret("super") == ("super", "")
        assert yap.interpret("nube") == ("super", "")

    def test_super_on_off_cambia_modo(self):
        assert yap.interpret("super on") == ("super_modo", "on")
        assert yap.interpret("super off") == ("super_modo", "off")
        assert yap.interpret("usar super") == ("super_modo", "on")
        assert yap.interpret("cambiar a local") == ("super_modo", "off")

    def test_super_pregunta_fuerza_super_query(self):
        action, param = yap.interpret("super explica while")
        assert action == "super_query"
        assert "explica while" in param

    @patch.object(yap, "classify_intent", return_value=("query", "explica while"))
    def test_query_compleja_en_auto_sigue_local(self, _cls):
        self.habilitar()
        action, param = yap.interpret("explica la diferencia entre while y for")
        assert action == "query"

    @patch.object(yap, "classify_intent", return_value=("query", "hola"))
    def test_con_internet_la_consulta_va_a_la_nube(self, _cls):
        self.habilitar()
        os.environ["YAP_SUPER_INTERNET"] = "1"
        action, param = yap.interpret("hola")
        assert action == "super_query"

    @patch.object(yap, "classify_intent", return_value=("open_app", "firefox"))
    def test_open_app_nunca_se_va_a_super(self, _cls):
        self.habilitar()
        os.environ["YAP_SUPER_INTERNET"] = "1"
        action, param = yap.interpret("abre firefox")
        assert action == "open_app"
        assert param == "firefox"

    @patch.object(yap, "classify_intent")
    def test_status_no_pasa_por_el_llm(self, mock_cls):
        yap.interpret("super")
        mock_cls.assert_not_called()


class TestHandleActionSuper(SuperTestBase):
    def test_status_no_abre_red(self):
        with patch("urllib.request.urlopen") as red:
            with patch("builtins.print"):
                yap.handle_action("super", "", "super")
        red.assert_not_called()

    def test_super_query_despacha_cmd_query_super(self):
        with patch.object(yap, "cmd_query_super", return_value="ok-super") as cmd:
            with patch("builtins.print"):
                yap.handle_action("super_query", "explica", "super explica")
        cmd.assert_called_once()

    def test_super_modo_on_off(self):
        self.habilitar()
        with patch("builtins.print"):
            yap.handle_action("super_modo", "on", "super on")
        assert yap._SUPER_MODO == "super"
        with patch("builtins.print"):
            yap.handle_action("super_modo", "off", "super off")
        assert yap._SUPER_MODO == "auto"


class TestCmdSuperStatus(SuperTestBase):
    def test_status_no_imprime_el_token(self):
        self.habilitar(token="supersecreto")
        out = yap.cmd_super_status()
        assert "supersecreto" not in out
        assert "Llama-3.1-8B" not in out
        assert "presente" in out
        assert "Timeout:" in out
        assert "180" in out
        assert "Modo:" in out
        assert "Internet:" in out
        assert "Modelo:" not in out

    def test_timeout_local_es_3_min(self):
        assert yap.SUPER_LOCAL_TIMEOUT == 180
        assert yap.SUPER_GRADIO_SSE_TIMEOUT == 180
        assert yap._local_llama_timeout() == 180

    def test_familia_modelo_llama_u_otro(self):
        assert yap.etiqueta_familia_modelo() == "Llama"
        self.habilitar()
        yap._SUPER_ESTADO = "super"
        assert yap.etiqueta_familia_modelo() == "otro modelo"


def _gradio_html():
    host = yap.SUPER_GRADIO_HOST
    return (
        "<html><script>window.gradio_config = {"
        f'"root": "https://{host}", "api_prefix": "/gradio_api"'
        '}; var x = {"id": 6, "api_name": "chat"};'
        "</script></html>"
    )


def _urlopen_html(html, status=200):
    resp = MagicMock()
    resp.read.return_value = html.encode("utf-8")
    resp.status = status
    resp.readline.return_value = b""
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def _urlopen_sse(texto="Hola desde Super Yap"):
    payload = json.dumps({
        "msg": "process_completed",
        "output": {"data": [texto]},
    })
    lines = [
        f"data: {payload}\n".encode("utf-8"),
        b"",
    ]
    resp = MagicMock()
    resp.read.return_value = b""
    resp.readline.side_effect = lines
    resp.status = 200
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


class TestGradioNube(SuperTestBase):
    def test_extraer_texto_plano(self):
        assert yap._extraer_texto_gradio(["Hola nube"]) == "Hola nube"

    def test_extraer_texto_add_tuples(self):
        data = [[["add", [], "parte1"], ["add", [], "parte2"]]]
        assert yap._extraer_texto_gradio(data) == "parte1parte2"

    def test_descubrir_fn_index_chat(self):
        root, prefix, fn, err = yap._descubrir_gradio(_gradio_html(), "https://x")
        assert err is None
        assert prefix == "/gradio_api"
        assert fn == 6
        assert yap.SUPER_GRADIO_HOST in root

    @patch("yap._gradio_urlopen")
    def test_chat_gradio_join_y_sse(self, mock_urlopen):
        self.habilitar(endpoint=yap.SUPER_DEFAULT_ENDPOINT)
        mock_urlopen.side_effect = [
            _urlopen_html(_gradio_html()),
            _urlopen_json({"event_id": "e1"}),
            _urlopen_sse("Algoritmo EnLaNube"),
        ]
        out = yap.cmd_query_super("explica while", store_history=True)
        assert "Algoritmo EnLaNube" in out
        assert "[WARN]" not in out
        assert mock_urlopen.call_count == 3
        join_req = mock_urlopen.call_args_list[1][0][0]
        assert "/queue/join" in join_req.full_url
        assert "key=" in join_req.full_url
        body = json.loads(join_req.data.decode("utf-8"))
        assert body["data"][0]["text"] == "explica while"
        assert "files" in body["data"][0]
        sse_req = mock_urlopen.call_args_list[2][0][0]
        assert "/queue/data" in sse_req.full_url
        assert "session_hash=" in sse_req.full_url
        assert yap.etiqueta_motor() == "SUPER"
        assert yap.HISTORY[-1][0] == "explica while"

    @patch("yap._gradio_urlopen")
    def test_clave_no_va_en_json_ni_en_historial(self, mock_urlopen):
        self.habilitar(endpoint=yap.SUPER_DEFAULT_ENDPOINT)
        mock_urlopen.side_effect = [
            _urlopen_html(_gradio_html()),
            _urlopen_json({"event_id": "e1"}),
            _urlopen_sse("ok"),
        ]
        yap.cmd_query_super("explica", store_history=True)
        join_req = mock_urlopen.call_args_list[1][0][0]
        body = json.loads(join_req.data.decode("utf-8"))
        blob = json.dumps(body)
        assert yap.SUPER_NUBE_KEY_DEFAULT not in blob
        assert yap.SUPER_NUBE_KEY_DEFAULT not in yap.HISTORY[-1][1]

    def test_status_no_imprime_clave_gradio(self):
        out = yap.cmd_super_status()
        assert yap.SUPER_NUBE_KEY_DEFAULT not in out
        assert "Gradio" in out or "gradio" in out.lower() or "chat" in out.lower()


class TestFallbackLocalASuper(SuperTestBase):
    @patch("yap.cmd_query_super", return_value="desde-nube")
    @patch("subprocess.run")
    def test_timeout_local_usa_super(self, mock_run, mock_super):
        self.habilitar()
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired("llama-cli", 180)
        out = yap.cmd_query("hola", store_history=False)
        mock_super.assert_called_once()
        assert "desde-nube" in out
        assert "modelo local tardo demasiado" in out.lower() or "tardo demasiado" in out
        assert mock_run.call_args.kwargs.get("timeout") == 180

    @patch("yap.cmd_query_super", return_value="desde-nube")
    @patch("subprocess.run")
    def test_tokens_de_mas_van_a_super(self, mock_run, mock_super):
        self.habilitar()
        yap.HISTORY.extend([("u" * 400, "a" * 400) for _ in range(6)])
        out = yap.cmd_query("sigue", store_history=False)
        mock_run.assert_not_called()
        mock_super.assert_called_once()
        assert "desde-nube" in out

    @patch.object(yap, "classify_intent", return_value=("query", "hola"))
    def test_modo_super_delega_aunque_sea_corta(self, _cls):
        self.habilitar()
        yap._SUPER_MODO = "super"
        action, param = yap.interpret("hola")
        assert action == "super_query"

    @patch.object(yap, "classify_intent", return_value=("query", "explica while"))
    def test_modo_local_no_delega_auto(self, _cls):
        self.habilitar()
        yap._SUPER_MODO = "local"
        action, param = yap.interpret("explica la diferencia entre while y for")
        assert action == "query"


class TestNoImportsPeligrososSuper:
    def test_yap_sigue_sin_imports_prohibidos(self):
        with open(yap.__file__, encoding="utf-8") as f:
            source = f.read()
        assert "import requests" not in source
        assert "super_yap.py" not in source
        assert "Llama-3.1-8B" not in source
        assert "SUPER_MODEL_NAME" not in source
        for line in source.split("\n"):
            if line.startswith("import ") or line.startswith("from "):
                for peligroso in ("socket", "ctypes", "pickle", "base64", "codecs"):
                    assert peligroso not in line

    def test_no_existe_super_yap_local(self):
        ruta = os.path.join(os.path.dirname(yap.__file__), "super_yap.py")
        assert not os.path.isfile(ruta)
