"""Tests para los comandos y servicios de post-instalación de Yap (#129)."""

import os
from unittest.mock import patch

import pytest

import yap


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SYSTEMD_DIR = os.path.join(REPO_ROOT, "packaging", "systemd")


class TestSystemdUnits:
    """Verifica que las unidades systemd existan y tengan las directivas requeridas."""

    def test_daemon_service_unit_exists_and_configured(self):
        path = os.path.join(SYSTEMD_DIR, "yap-daemon.service")
        assert os.path.isfile(path)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "ExecStart=/usr/local/bin/yap --daemon" in content
        assert "Restart=on-failure" in content
        assert "MemoryMax=4G" in content
        assert "WantedBy=multi-user.target" in content

    def test_sync_service_and_timer_exist(self):
        service_path = os.path.join(SYSTEMD_DIR, "yap-sync.service")
        timer_path = os.path.join(SYSTEMD_DIR, "yap-sync.timer")
        assert os.path.isfile(service_path)
        assert os.path.isfile(timer_path)

        with open(service_path, encoding="utf-8") as f:
            service_content = f.read()
        assert "ExecStart=/usr/local/bin/yap --sync" in service_content
        assert "ConditionEnvironment=!YAP_OFFLINE=1" in service_content

        with open(timer_path, encoding="utf-8") as f:
            timer_content = f.read()
        assert "OnCalendar=daily" in timer_content
        assert "WantedBy=timers.target" in timer_content


class TestInterpretPostinstall:
    """Verifica el enrutamiento de comandos en interpret()."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "--postinstall-check",
            "postinstall-check",
            "postinstall check",
            "--check",
            "postinstall",
        ],
    )
    def test_interpret_postinstall_check(self, cmd):
        action, param = yap.interpret(cmd)
        assert action == "postinstall_check"
        assert param == "check"

    @pytest.mark.parametrize("cmd", ["--daemon", "daemon", "-d"])
    def test_interpret_daemon(self, cmd):
        action, param = yap.interpret(cmd)
        assert action == "daemon"
        assert param == "daemon"

    @pytest.mark.parametrize(
        "cmd", ["--daemon-status", "daemon-status", "daemon status"]
    )
    def test_interpret_daemon_status(self, cmd):
        action, param = yap.interpret(cmd)
        assert action == "daemon_status"
        assert param == "status"

    @pytest.mark.parametrize("cmd", ["--sync", "sync"])
    def test_interpret_sync(self, cmd):
        action, param = yap.interpret(cmd)
        assert action == "sync"
        assert param == "sync"


class TestPostinstallCheckCommand:
    """Verifica el comando cmd_postinstall_check()."""

    def test_postinstall_check_output_structure(self):
        out = yap.cmd_postinstall_check()
        assert "Verificación Post-Instalación" in out
        assert "AppArmor" in out
        assert "Whitelist Apps" in out
        assert "Whitelist Web" in out
        assert "Agent Contract" in out
        assert "Modelo Local" in out
        assert "Daemon Service" in out

    def test_postinstall_check_detects_existing_components(self, tmp_path):
        apps = tmp_path / "apps.conf"
        apps.write_text("LibreOffice:libreoffice\n", encoding="utf-8")
        web = tmp_path / "web.conf"
        web.write_text("wikipedia.org\n", encoding="utf-8")
        agent = tmp_path / "yap.md"
        agent.write_text("# Yap Agent\n", encoding="utf-8")
        model = tmp_path / "test-model.gguf"
        model.write_bytes(b"dummy" * 1024)

        with patch.object(yap, "WHITELIST_APPS", str(apps)), patch.object(
            yap, "WHITELIST_WEB", str(web)
        ), patch.object(yap, "MODEL_PATH", str(model)), patch.object(
            yap,
            "apparmor_status",
            return_value={"installed": True, "profile_loaded": True, "mode": "enforce"},
        ):
            out = yap.cmd_postinstall_check()
            assert "Modo enforce activo" in out
            assert "1 aplicaciones permitidas" in out
            assert "1 dominios permitidos" in out
            assert "test-model.gguf" in out


class TestDaemonAndSyncCommands:
    """Verifica los comandos daemon y sync."""

    def test_daemon_once_runs_and_exits(self, monkeypatch):
        monkeypatch.setenv("YAP_DAEMON_ONCE", "1")
        yap.cmd_daemon()

    def test_check_daemon_active_with_pidfile(self):
        pidfile = "/tmp/yap-daemon.pid"
        try:
            with open(pidfile, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
            active, detail = yap._check_daemon_active()
            assert active is True
            assert f"PID {os.getpid()}" in detail
        finally:
            if os.path.exists(pidfile):
                os.remove(pidfile)

    def test_sync_offline_mode(self, monkeypatch):
        monkeypatch.setenv("YAP_OFFLINE", "1")
        res = yap.cmd_sync()
        assert "Modo offline activo" in res
        assert "omitida" in res

    def test_sync_online_mode(self, monkeypatch, tmp_path):
        monkeypatch.delenv("YAP_OFFLINE", raising=False)
        with patch.object(yap, "CONFIG_DIR", str(tmp_path)):
            res = yap.cmd_sync()
            assert "[YAP SYNC]" in res
            assert os.path.isdir(str(tmp_path / "whitelist"))
            assert os.path.isdir(str(tmp_path / "agent"))

    def test_handle_action_dispatch(self, capsys):
        yap.handle_action("daemon_status", "status", "daemon-status")
        captured = capsys.readouterr()
        assert "Yap daemon:" in captured.out
