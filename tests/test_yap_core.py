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
import time
import threading
import queue
import unittest.mock as mock
import pytest

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

        with mock.patch("yap_core.execute_action_headless", side_effect=slow_action):
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

        with mock.patch("yap_core.execute_action_headless", side_effect=record_action):
            t1 = engine.execute_async("primero")
            t2 = engine.execute_async("segundo")
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

        with mock.patch("yap_core.execute_action_headless", side_effect=fallo):
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

        with mock.patch("yap_core.execute_action_headless", return_value="Respuesta OK"):
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
        cb = lambda ev: recibidos.append(ev)

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
        engine = yap_core.YapCore()
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
