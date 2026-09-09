"""
test_yap_super.py — Super Yap (#91): Llama 8B en host de 8 GB + contexto

Sin Internet, sin LLM, sin llama-cli. Todo mockeado.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap
import super_yap


class SuperTestBase:
    def setup_method(self):
        yap.HISTORY.clear()
        yap._SUPER_ESTADO = "local"
        super_yap.SESIONES.clear()
        self._env_backup = {
            k: os.environ.get(k)
            for k in list(os.environ)
            if k.startswith("YAP_SUPER")
        }
        for k in list(os.environ):
            if k.startswith("YAP_SUPER"):
                del os.environ[k]

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
        super_yap.SESIONES.clear()

    def habilitar(self, endpoint=None, token=""):
        os.environ["YAP_SUPER_ENABLED"] = "1"
        os.environ["YAP_SUPER_ENDPOINT"] = endpoint or yap.SUPER_DEFAULT_ENDPOINT
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


class TestHostSuperPermitido(SuperTestBase):
    def test_loopback_permitido(self):
        assert yap._host_super_permitido(yap.SUPER_DEFAULT_ENDPOINT) is True
        assert yap._host_super_permitido("http://localhost:8742/v1/query") is True

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
        assert payload["model"] == "Llama-3.1-8B-Instruct-Q4_K_M"
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
        assert yap.debe_delegar_super("explica la diferencia entre while y for") is False

    def test_habilitada_y_compleja_delega(self):
        self.habilitar()
        assert yap.debe_delegar_super("explica la diferencia entre while y for") is True

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


class TestCmdQuerySuper(SuperTestBase):
    @patch("yap.cmd_query", return_value="local-ok")
    def test_sin_super_usa_local_sin_red(self, mock_local):
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
            "modelo": "Llama-3.1-8B-Instruct-Q4_K_M",
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

    def test_super_pregunta_fuerza_super_query(self):
        action, param = yap.interpret("super explica while")
        assert action == "super_query"
        assert "explica while" in param

    @patch.object(yap, "classify_intent", return_value=("query", "explica while"))
    def test_query_compleja_se_reescribe_si_hay_super(self, _cls):
        self.habilitar()
        action, param = yap.interpret("explica la diferencia entre while y for")
        assert action == "super_query"

    @patch.object(yap, "classify_intent", return_value=("open_app", "firefox"))
    def test_open_app_nunca_se_va_a_super(self, _cls):
        self.habilitar()
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


class TestCmdSuperStatus(SuperTestBase):
    def test_status_no_imprime_el_token(self):
        self.habilitar(token="supersecreto")
        out = yap.cmd_super_status()
        assert "supersecreto" not in out
        assert "Llama-3.1-8B" in out
        assert "presente" in out


class TestFusionarContextoSuperYap(SuperTestBase):
    def test_cliente_sufijo_conserva_prefijo_del_servidor(self):
        super_yap.SESIONES["S1"] = [
            ("t0", "a0"),
            ("t1", "a1"),
            ("t2", "a2"),
        ]
        payload = [
            {"rol": "user", "texto": "t1"},
            {"rol": "assistant", "texto": "a1"},
            {"rol": "user", "texto": "t2"},
            {"rol": "assistant", "texto": "a2"},
        ]
        merged = super_yap.fusionar_historial("S1", payload)
        assert merged[0] == ("t0", "a0")
        assert merged[-1] == ("t2", "a2")
        assert len(merged) == 3

    def test_divergencia_gana_el_cliente_local(self):
        super_yap.SESIONES["S1"] = [("viejo", "resp")]
        payload = [
            {"rol": "user", "texto": "nuevo"},
            {"rol": "assistant", "texto": "otra"},
        ]
        merged = super_yap.fusionar_historial("S1", payload)
        assert merged == [("nuevo", "otra")]

    def test_recordar_turno_no_pierde_el_hilo(self):
        super_yap.fusionar_historial("S3", [
            {"rol": "user", "texto": "hola"},
            {"rol": "assistant", "texto": "hola de vuelta"},
        ])
        super_yap.recordar_turno("S3", "y un ejemplo", "Aqui va")
        assert super_yap.SESIONES["S3"][-1] == ("y un ejemplo", "Aqui va")
        assert super_yap.SESIONES["S3"][0][0] == "hola"


class TestModeloOchoGigas(SuperTestBase):
    def test_perfil_ram_cabe_en_8gb(self):
        perfil = super_yap.perfil_ram()
        assert perfil["total_estimado_mb"] < 8192
        assert perfil["host_recomendado_mb"] == 8192
        assert perfil["pesos_gguf_mb"] > 4000

    def test_candidatos_empiezan_por_8b(self):
        paths = super_yap.modelo_candidato_paths()
        assert any("8B" in p for p in paths)
        assert any("Llama-3.2-3B" in p for p in paths)

    def test_handler_health_sin_llm(self):
        handler = super_yap.SuperYapHandler()
        code, body = handler.manejar("GET", "/health", b"")
        assert code == 200
        assert body["ok"] is True
        assert "8B" in body["modelo"] or "3B" in body["modelo"]

    def test_handler_post_sin_prompt_es_400(self):
        handler = super_yap.SuperYapHandler()
        code, body = handler.manejar("POST", "/v1/query", b"{}")
        assert code == 400
        assert body.get("error") == "Falta prompt"

    @patch.object(super_yap, "generar", return_value="While itera con condicion.")
    def test_handler_post_devuelve_texto_y_modelo(self, _gen):
        handler = super_yap.SuperYapHandler()
        payload = json.dumps({
            "prompt": "explica while",
            "historial": [
                {"rol": "user", "texto": "hola"},
                {"rol": "assistant", "texto": "hola"},
            ],
            "session_id": "S9",
        }).encode("utf-8")
        code, body = handler.manejar("POST", "/v1/query", payload)
        assert code == 200
        assert "While itera" in body["texto"]
        assert body["session_id"] == "S9"
        assert super_yap.SESIONES["S9"][-1][0] == "explica while"


class TestNoImportsPeligrososSuper:
    def test_yap_sigue_sin_imports_prohibidos(self):
        with open(yap.__file__, encoding="utf-8") as f:
            source = f.read()
        for line in source.split("\n"):
            if line.startswith("import ") or line.startswith("from "):
                for peligroso in ("socket", "ctypes", "pickle", "base64", "codecs"):
                    assert peligroso not in line

    def test_super_yap_sin_shell_eval_system(self):
        with open(super_yap.__file__, encoding="utf-8") as f:
            source = f.read()
        assert "shell=True" not in source
        assert "os.system(" not in source
        assert "eval(" not in source
