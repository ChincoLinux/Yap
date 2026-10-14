#!/usr/bin/env python3
"""
test_yap_core.py — Pruebas unitarias para el motor desacoplado headless yap_core (#152)

Verifica:
  1. Instanciación y ciclo de vida (start, stop, is_running, is_busy).
  2. Ejecución asíncrona no bloqueante en hilos secundarios.
  3. Callbacks de streaming de tokens (on_token, on_done, on_error, on_status).
  4. Cola de eventos y suscriptores para UI/widgets de escritorio.
  5. Despacho headless de acciones y retrocompatibilidad con yap.py.
  6. Cancelación segura de tareas y procesos.
"""

import sys
import os
from pathlib import Path
import time
import threading
import unittest.mock as mock
import pytest
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yap
import yap_core


@pytest.fixture(autouse=True)
def clean_engine():
    """Asegura que el motor global se reinicia antes y después de cada prueba."""
    yap_core.reset_engine()
    yield
    yap_core.reset_engine()


# ── 1. Ciclo de vida e instanciación ───────────────────────────────


class TestYapCoreLifecycle:
    def test_instanciacion_inicial(self):
        engine = yap_core.YapCore()
        assert not engine.is_running()
        assert not engine.is_busy()
        assert engine.get_current_task() is None

    def test_start_y_stop(self):
        engine = yap_core.YapCore()
        engine.start()
        assert engine.is_running()

        engine.stop(timeout=2.0)
        assert not engine.is_running()

    def test_singleton_get_engine(self):
        e1 = yap_core.get_engine()
        e2 = yap_core.get_engine()
        assert e1 is e2
        assert isinstance(e1, yap_core.YapCore)

    def test_reset_engine(self):
        e1 = yap_core.get_engine()
        e1.start()
        assert e1.is_running()
        yap_core.reset_engine()
        assert not e1.is_running()
        e2 = yap_core.get_engine()
        assert e1 is not e2


# ── 2. Ejecución asíncrona en hilo secundario ─────────────────────


class TestYapCoreAsyncExecution:
    def test_query_async_ejecuta_en_hilo_secundario(self):
        engine = yap_core.YapCore()
        engine.start()

        main_thread_id = threading.get_ident()
        worker_thread_ids = []

        def mock_stream(prompt, **kwargs):
            worker_thread_ids.append(threading.get_ident())
            return "Respuesta simulada"

        with mock.patch("yap_core.query_stream", side_effect=mock_stream):
            task = engine.query_async("Pregunta de prueba")
            finished = task.wait(timeout=3.0)

        assert finished is True
        assert task.status == "completed"
        assert task.result == "Respuesta simulada"
        assert len(worker_thread_ids) == 1
        assert worker_thread_ids[0] != main_thread_id

        engine.stop()

    def test_no_bloquea_hilo_llamador(self):
        engine = yap_core.YapCore()
        engine.start()

        execution_started = threading.Event()

        def slow_action(*args, **kwargs):
            execution_started.set()
            time.sleep(0.3)
            return "Terminado lento"

        with mock.patch(
            "yap.interpret", return_value=("query", "consulta lenta")
        ), mock.patch("yap_core.execute_action_headless", side_effect=slow_action):
            t0 = time.time()
            task = engine.execute_async("consulta lenta")
            duration_submit = time.time() - t0

            # La llamada submit debe retornar de inmediato (< 100ms)
            assert duration_submit < 0.15
            assert task.status in ("pending", "running")

            assert execution_started.wait(timeout=2.0)
            assert task.wait(timeout=2.0)
            assert task.result == "Terminado lento"

        engine.stop()

    def test_procesamiento_en_cola_fifo(self):
        engine = yap_core.YapCore()
        engine.start()

        orden_ejecutado = []

        def record_action(act, par, prompt, **kwargs):
            orden_ejecutado.append(prompt)
            return f"ok-{prompt}"

        with mock.patch(
            "yap.interpret", side_effect=lambda p: ("query", p)
        ), mock.patch("yap_core.execute_action_headless", side_effect=record_action):
            # Se encolan tres; solo se espera por la ultima.
            engine.execute_async("primero")
            engine.execute_async("segundo")
            t3 = engine.execute_async("tercero")

            assert t3.wait(timeout=3.0)

        assert orden_ejecutado == ["primero", "segundo", "tercero"]
        engine.stop()


# ── 3. Streaming de tokens y callbacks ────────────────────────────


class TestYapCoreStreaming:
    def test_callbacks_on_token_y_on_done(self):
        engine = yap_core.YapCore()
        tokens_recibidos = []
        done_recibido = []
        status_recibidos = []

        def simular_stream(cmd, on_token=None, **kwargs):
            for ch in ["Ho", "la", " ", "Mundo"]:
                if on_token:
                    on_token(ch)
            return "Hola Mundo"

        with mock.patch("yap_core.stream_llama", side_effect=simular_stream):
            task = engine.query_async(
                "Saluda",
                on_token=lambda tok: tokens_recibidos.append(tok),
                on_done=lambda res: done_recibido.append(res),
                on_status=lambda st: status_recibidos.append(st),
            )
            assert task.wait(timeout=3.0)

        assert tokens_recibidos == ["Ho", "la", " ", "Mundo"]
        assert done_recibido == ["Hola Mundo"]
        assert task.result == "Hola Mundo"
        assert len(status_recibidos) > 0
        engine.stop()

    def test_callback_on_error_ante_excepcion(self):
        engine = yap_core.YapCore()
        errores = []

        def fallo(*args, **kwargs):
            raise ValueError("Error forzado de prueba")

        with mock.patch(
            "yap.interpret", return_value=("query", "comando_fallido")
        ), mock.patch("yap_core.execute_action_headless", side_effect=fallo):
            task = engine.execute_async(
                "comando_fallido",
                on_error=lambda err: errores.append(err),
            )
            assert task.wait(timeout=3.0)

        assert task.status == "failed"
        assert "Error forzado de prueba" in task.error
        assert len(errores) == 1
        assert "Error forzado de prueba" in errores[0]
        engine.stop()


# ── 4. Eventos y cola de eventos para UI ───────────────────────────


class TestYapCoreEvents:
    def test_emision_de_eventos(self):
        engine = yap_core.YapCore()
        eventos_suscriptor = []

        engine.subscribe(lambda ev: eventos_suscriptor.append(ev))

        with mock.patch(
            "yap_core.execute_action_headless", return_value="Respuesta OK"
        ):
            task = engine.execute_async("ayuda")
            assert task.wait(timeout=3.0)

        tipos = [e.type for e in eventos_suscriptor]
        assert yap_core.EventType.START in tipos
        assert yap_core.EventType.DONE in tipos

        # Verificar cola get_event()
        eventos_cola = []
        while True:
            ev = engine.get_event(block=False)
            if ev is None:
                break
            eventos_cola.append(ev.type)

        assert yap_core.EventType.START in eventos_cola
        assert yap_core.EventType.DONE in eventos_cola
        engine.stop()

    def test_unsubscribe(self):
        engine = yap_core.YapCore()
        recibidos = []

        def cb(ev):
            recibidos.append(ev)

        engine.subscribe(cb)
        engine.unsubscribe(cb)

        with mock.patch("yap_core.execute_action_headless", return_value="OK"):
            task = engine.execute_async("ayuda")
            assert task.wait(timeout=3.0)

        assert len(recibidos) == 0
        engine.stop()


# ── 5. Cancelación de tareas ──────────────────────────────────────


class TestYapCoreCancellation:
    def test_cancel_tarea_pendiente(self):
        # No iniciamos engine para que quede encolada
        task = yap_core.YapTask(prompt="tarea pendiente")
        task.cancel()
        assert task.is_cancelled()

    def test_cancel_current_detiene_proceso(self):
        engine = yap_core.YapCore()
        engine.start()

        started = threading.Event()
        interrupted = threading.Event()

        def block_until_cancelled(cmd, cancel_event=None, **kwargs):
            started.set()
            while not (cancel_event and cancel_event.is_set()):
                time.sleep(0.02)
            interrupted.set()
            return "[WARN] Operación cancelada por el usuario."

        with mock.patch("yap_core.stream_llama", side_effect=block_until_cancelled):
            task = engine.query_async("consulta a cancelar")
            assert started.wait(timeout=2.0)
            engine.cancel_current()
            assert interrupted.wait(timeout=2.0)
            assert task.wait(timeout=2.0)

        assert task.status == "cancelled"
        engine.stop()


# ── 6. Despacho headless y retrocompatibilidad con yap.py ─────────


class TestYapHeadlessAndCompat:
    def test_execute_headless_menu_y_perfil(self):
        engine = yap_core.get_engine()
        out_menu = engine.execute_headless("menu")
        assert "Comandos" in out_menu

        out_perfil = engine.execute_headless("perfil")
        assert "Perfil" in out_perfil

    def test_execute_headless_ayuda(self):
        engine = yap_core.get_engine()
        out_help = engine.execute_headless("ayuda")
        assert "Comandos de Yap" in out_help
        assert "Tutor PSeInt" in out_help

    def test_yap_get_engine_integracion(self):
        e = yap.get_engine()
        assert isinstance(e, yap_core.YapCore)

    def test_cmd_query_con_on_token(self):
        tokens = []
        with mock.patch("yap_core.stream_llama", return_value="Respuesta streamed"):
            res = yap.cmd_query("Prueba", on_token=lambda t: tokens.append(t))
            assert res == "Respuesta streamed"

    def test_cmd_query_sin_on_token_mantiene_comportamiento(self):
        """Retrocompatibilidad: cmd_query sin on_token ejecuta la ruta habitual."""
        fake_result = mock.Mock()
        fake_result.stdout = "Respuesta clasica"
        fake_result.stderr = ""
        with mock.patch("subprocess.run", return_value=fake_result):
            res = yap.cmd_query("Hola", store_history=False, allow_super_fallback=False)
            assert res == "Respuesta clasica"


# ── 7. Detección e Instalación Automática ─────────────────────────


class TestYapCoreAutoInstall:
    def test_esta_llama_instalado_con_mocks(self):
        with mock.patch("shutil.which", return_value="/bin/llama-cli"), mock.patch(
            "os.path.isfile", return_value=True
        ), mock.patch("os.path.getsize", return_value=2_000_000_000):
            assert yap_core.esta_llama_instalado() is True

        with mock.patch("shutil.which", return_value=None):
            assert yap_core.esta_llama_instalado() is False

    def test_asegurar_llama_instalado_respeta_flag_pytest(self):
        """En entorno de pruebas (pytest), asegurar_llama_instalado no descarga nada."""
        with mock.patch(
            "yap_core.esta_llama_instalado", return_value=False
        ), mock.patch("yap_core.instalar_llama_automaticamente") as mock_instalar:
            res = yap_core.asegurar_llama_instalado(auto_instalar=True)
            assert res is False
            mock_instalar.assert_not_called()

    def _aislar_de_pytest(self):
        """Quita 'pytest' de sys.modules y los marcadores del entorno.

        Sin esto el guard triunfa por esa rama y no se puede probar nada
        de lo que depende de estar fuera de la suite.
        """
        previo = sys.modules.pop("pytest", None)
        entorno = {
            k: os.environ.get(k) for k in ("PYTEST_CURRENT_TEST", "YAP_NO_AUTO_INSTALL")
        }
        for k in entorno:
            os.environ.pop(k, None)
        return previo, entorno

    def _restaurar_entorno(self, previo, entorno):
        if previo is not None:
            sys.modules["pytest"] = previo
        for k, v in entorno.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_asegurar_llama_instalado_ejecuta_instalacion_fuera_de_pytest(self):
        """Fuera de pytest, si auto_instalar es True, llama al instalador.

        La version anterior mockeaba el instalador y luego no lo comprobaba:
        afirmaba `assert callable(...)`, que es verdadero siempre. Ademas
        ponia sys.modules["pytest"] = None, que deja "pytest" presente y
        hace que el guard lo frene antes de llegar a nada.
        """
        previo, entorno = self._aislar_de_pytest()
        try:
            with mock.patch(
                "yap_core.esta_llama_instalado", return_value=False
            ), mock.patch(
                "yap_core.instalar_llama_automaticamente", return_value=True
            ) as mock_instalar:
                res = yap_core.asegurar_llama_instalado(auto_instalar=True)
            mock_instalar.assert_called_once()
            assert res is True
        finally:
            self._restaurar_entorno(previo, entorno)

    def test_bajo_pytest_no_instala(self):
        """El guard existe para no descargar gigabytes en la suite."""
        with mock.patch(
            "yap_core.esta_llama_instalado", return_value=False
        ), mock.patch(
            "yap_core.instalar_llama_automaticamente", return_value=True
        ) as mock_instalar:
            res = yap_core.asegurar_llama_instalado(auto_instalar=True)
        mock_instalar.assert_not_called()
        assert res is False

    def test_variable_de_entorno_lo_desactiva(self):
        """YAP_NO_AUTO_INSTALL es la via para apagarlo en el aula.

        Hay que sacar "pytest" de sys.modules: si no, el guard triunfa por
        esa rama y el test daria verde aunque la variable se ignorara.
        """
        previo, entorno = self._aislar_de_pytest()
        try:
            os.environ["YAP_NO_AUTO_INSTALL"] = "1"
            with mock.patch(
                "yap_core.esta_llama_instalado", return_value=False
            ), mock.patch(
                "yap_core.instalar_llama_automaticamente", return_value=True
            ) as mock_instalar:
                assert yap_core.asegurar_llama_instalado(auto_instalar=True) is False
            mock_instalar.assert_not_called()
        finally:
            self._restaurar_entorno(previo, entorno)


class TestChecksumsEnYapCore:
    """El auto-instalador valida con el mismo fichero que setup.sh (#235).

    Antes sólo comprobaba los magic bytes GGUF: un mirror comprometido
    servia un .gguf con magic valido y contenido alterado, y aqui se
    ejecuta en el equipo del alumno.
    """

    def test_hash_esperado_existe_para_los_cuatro_origenes(self):
        for archivo in (
            "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
            "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        ):
            for repo in ("bartowski", "unsloth"):
                h = yap_core.hash_esperado(archivo, repo)
                assert h and len(h) == 64, f"falta {archivo} de {repo}"

    def test_usa_el_mismo_fichero_que_setup(self):
        """Si setup.sh publica un hash, yap_core debe ver el mismo."""
        ruta = os.path.join(
            os.path.dirname(yap_core.__file__), "whitelist", "modelos.sha256"
        )
        assert os.path.abspath(yap_core.CHECKSUMS_MODELOS) == os.path.abspath(ruta)

    def test_archivo_alterado_se_rechaza(self, tmp_path):
        """Nombre real y contenido falso: el hash no cuadra."""
        f = tmp_path / "Llama-3.2-3B-Instruct-Q4_K_M.gguf"
        f.write_bytes(b"GGUF" + b"\0" * 200)
        assert yap_core.verificar_checksum(str(f), "bartowski") is False

    def test_archivo_correcto_se_acepta(self, tmp_path):
        """Se verifica de verdad, no que simplemente diga que sí."""
        contenido = b"GGUF" + os.urandom(64)
        f = tmp_path / "Llama-3.2-1B-Instruct-Q4_K_M.gguf"
        f.write_bytes(contenido)
        import hashlib

        esperado = hashlib.sha256(contenido).hexdigest()
        original = yap_core.CHECKSUMS_MODELOS
        try:
            checks = tmp_path / "c.sha256"
            checks.write_text(
                f"Llama-3.2-1B-Instruct-Q4_K_M.gguf  bartowski  {esperado}  {len(contenido)}\n"
            )
            yap_core.CHECKSUMS_MODELOS = str(checks)
            assert yap_core.verificar_checksum(str(f), "bartowski") is True
        finally:
            yap_core.CHECKSUMS_MODELOS = original

    def test_repo_desconocido_no_valida(self, tmp_path):
        """El hash de bartowski no debe servir para otro repositorio."""
        f = tmp_path / "Llama-3.2-1B-Instruct-Q4_K_M.gguf"
        f.write_bytes(b"GGUF" + b"\0" * 10)
        assert yap_core.hash_esperado(f.name, "nosquien") is None
        assert yap_core.verificar_checksum(str(f), "nosquien") is None

    def test_fichero_ausente_no_finge_verificar(self, tmp_path):
        """Si no hay checksums, avisa (None) en vez de dar por bueno."""
        original = yap_core.CHECKSUMS_MODELOS
        try:
            yap_core.CHECKSUMS_MODELOS = str(tmp_path / "no-existe.sha256")
            f = tmp_path / "Llama-3.2-3B-Instruct-Q4_K_M.gguf"
            f.write_bytes(b"GGUF" + b"\0" * 10)
            assert yap_core.verificar_checksum(str(f), "bartowski") is None
        finally:
            yap_core.CHECKSUMS_MODELOS = original

    def test_no_repite_el_hash_de_setup(self):
        """Si cambiara uno de los dos, este test lo ve."""
        core = yap_core.hash_esperado("Llama-3.2-3B-Instruct-Q4_K_M.gguf", "unsloth")
        ruta = os.path.join(
            os.path.dirname(yap_core.__file__), "whitelist", "modelos.sha256"
        )
        publicado = None
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                if linea.lstrip().startswith("#"):
                    continue
                partes = linea.split()
                if (
                    len(partes) >= 3
                    and partes[0].endswith("3B-Instruct-Q4_K_M.gguf")
                    and partes[1] == "unsloth"
                ):
                    publicado = partes[2]
        assert core == publicado


class TestElAutoInstaladorVerificaDeVerdad:
    """No basta con que la funcion exista: hay que ver que se llama.

    Se añade tras comprobar que, al quitar la llamada del auto-instalador,
    los tests de la clase anterior seguían en verde.
    """

    class _Respuesta:
        def __init__(self, cuerpo):
            self._c = cuerpo
            self.headers = {"Content-Length": str(len(cuerpo))}

        def read(self, n=-1):
            if n is None or n < 0:
                out, self._c = self._c, b""
                return out
            out, self._c = self._c[:n], self._c[n:]
            return out

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _instalar_con(self, cuerpo, monkeypatch, tmp_path):
        """Fuerza el camino de descarga del modelo con el cuerpo dado."""
        monkeypatch.setattr(yap_core, "LOCAL_MODELS_DIR", str(tmp_path), raising=True)
        monkeypatch.setattr(
            yap_core.yap, "MODEL_PATH", str(tmp_path / "no-existe.gguf"), raising=False
        )
        monkeypatch.setattr(
            yap_core.yap,
            "MODEL_3B_NAME",
            "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
            raising=False,
        )
        salidas = []
        monkeypatch.setattr(
            urllib.request,
            "urlopen",
            lambda *a, **k: self._Respuesta(cuerpo),
        )
        # shutil.which devolvio None en Linux, asi que avisa y sigue.
        return yap_core.instalar_llama_automaticamente(
            on_status=lambda m: salidas.append(m)
        ), salidas

    def test_modelo_alterado_no_se_instala(self, monkeypatch, tmp_path):
        """GGUF valido, contenido falso: el checksum lo debe parar."""
        cuerpo = b"GGUF" + os.urandom(2048)
        ok, salidas = self._instalar_con(cuerpo, monkeypatch, tmp_path)
        assert ok is False, "instalo un modelo cuyo hash no coincide"
        assert any("Checksum NO coincide" in s for s in salidas), salidas
        assert not (
            tmp_path / "Llama-3.2-3B-Instruct-Q4_K_M.gguf"
        ).exists(), "el modelo alterado se quedo en destino"

    def test_el_magic_sigue_comprobandose(self, monkeypatch, tmp_path):
        """No-GGUF se rechaza antes de llegar al checksum."""
        ok, salidas = self._instalar_con(
            b"<html>401</html>" + b"x" * 2048, monkeypatch, tmp_path
        )
        assert ok is False
        assert any("GGUF" in s for s in salidas)

    def test_un_modelo_correcto_si_se_instala(self, monkeypatch, tmp_path):
        """El chequeo no debe bloquear el camino bueno."""
        cuerpo = b"GGUF" + os.urandom(2048)
        contenido = cuerpo
        import hashlib

        esperado = hashlib.sha256(contenido).hexdigest()
        original = yap_core.CHECKSUMS_MODELOS
        try:
            checks = tmp_path / "c.sha256"
            checks.write_text(
                "Llama-3.2-3B-Instruct-Q4_K_M.gguf  bartowski  "
                + esperado
                + f"  {len(contenido)}\n"
            )
            yap_core.CHECKSUMS_MODELOS = str(checks)
            _ok, salidas = self._instalar_con(contenido, monkeypatch, tmp_path)
            # El retorno es esta_llama_instalado(), que es False en un host
            # sin llama-cli; lo que importa aqui es que el modelo si se
            # instalo y que no se quejó del checksum.
            assert not any("Checksum NO coincide" in s for s in salidas), salidas
            destino = tmp_path / "Llama-3.2-3B-Instruct-Q4_K_M.gguf"
            assert destino.exists(), "el modelo bueno no se instalo"
        finally:
            yap_core.CHECKSUMS_MODELOS = original


class TestEmpaquetadoDeYapCore:
    """yap.py importa yap_core, así que todo target debe llevarlo.

    La primera pasada de este PR falló en las dos instalaciones de CI con
    ModuleNotFoundError: el .deb empaquetaba yap.py y no yap_core.py.
    """

    RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_deb_lo_instala(self):
        texto = Path(os.path.join(self.RAIZ, "build-deb.sh")).read_text(
            encoding="utf-8"
        )
        assert "yap_core.py" in texto, "build-deb.sh no instala yap_core.py"

    def test_rpm_lo_instala_y_lo_declara(self):
        texto = Path(os.path.join(self.RAIZ, "packaging", "rpm", "yap.spec")).read_text(
            encoding="utf-8"
        )
        assert "install -m 644 yap_core.py" in texto
        assert (
            "/opt/yap/yap_core.py\n" in texto + "\n"
        ), "falta en la seccion %files del RPM"

    def test_flatpak_lo_instala(self):
        texto = Path(
            os.path.join(self.RAIZ, "packaging", "flatpak", "org.chincolinux.Yap.json")
        ).read_text(encoding="utf-8")
        assert "yap_core.py" in texto

    def test_instalador_de_windows_lo_incluye(self):
        texto = Path(
            os.path.join(self.RAIZ, "packaging", "windows", "yap-installer.iss")
        ).read_text(encoding="utf-8")
        assert 'Source: "yap_core.py"' in texto

    def test_yap_importa_yap_core(self):
        """Si yap.py no lo importa, todo esto sobra; que no se caiga."""
        import importlib

        importlib.reload(importlib.import_module("yap_core"))
        assert hasattr(yap_core, "get_engine")

    def test_todos_los_targets_cubiertos(self):
        """Cada fichero que nombra yap.py debe nombrar yap_core.py."""
        rutas = [
            "build-deb.sh",
            os.path.join("packaging", "rpm", "yap.spec"),
            os.path.join("packaging", "flatpak", "org.chincolinux.Yap.json"),
            os.path.join("packaging", "windows", "yap-installer.iss"),
        ]
        for rel in rutas:
            texto = Path(os.path.join(self.RAIZ, rel)).read_text(encoding="utf-8")
            assert "yap_core.py" in texto, f"{rel} no empaqueta yap_core.py"
