"""
test_yap_deb.py — Empaquetado .deb de Yap (#31)

Verifica (sin dpkg, sin LLM, sin red):
  1. Plantillas DEBIAN (control, postinst, prerm, postrm)
  2. Depends: python3, libnotify-bin, apparmor
  3. postinst copia whitelists, instala AppArmor y crea el symlink
  4. postrm no toca ~/.config/yap/
  5. Paquetes de modelo descargan el GGUF en postinst
  6. build-deb.sh genera .deb con dpkg-deb y llama.cpp estatico

Si bash + dpkg-deb estan disponibles, construye un .deb con --stub-llama
y comprueba que el archivo existe.

Ejecucion: python3 -m pytest tests/test_yap_deb.py -v
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PACKAGING = os.path.join(REPO_ROOT, "packaging")
BUILD_DEB = os.path.join(REPO_ROOT, "build-deb.sh")
VERSION_FILE = os.path.join(REPO_ROOT, "VERSION")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def parse_control(text):
    fields = {}
    key = None
    for line in text.splitlines():
        if not line:
            continue
        if line[:1] in " \t" and key:
            fields[key] += " " + line.strip()
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            fields[key] = val.strip()
    return fields


# ============================================================
# Plantillas del paquete yap
# ============================================================

class TestYapDebianTemplates:
    """Requisito: DEBIAN/control, postinst, prerm, postrm existen y son validos."""

    def test_control_exists(self):
        path = os.path.join(PACKAGING, "yap", "DEBIAN", "control")
        assert os.path.isfile(path)

    def test_control_required_fields(self):
        text = _read(os.path.join(PACKAGING, "yap", "DEBIAN", "control"))
        fields = parse_control(text)
        assert fields.get("Package") == "yap"
        assert fields.get("Architecture") == "amd64"
        assert "@VERSION@" in fields.get("Version", "")
        assert "python3" in fields.get("Depends", "")
        assert "libnotify-bin" in fields.get("Depends", "")
        assert "apparmor" in fields.get("Depends", "")
        assert "yap-models-1b" in fields.get("Recommends", "")
        assert "yap-models-3b" in fields.get("Recommends", "")

    def test_maintainer_scripts_exist(self):
        for name in ("postinst", "prerm", "postrm"):
            path = os.path.join(PACKAGING, "yap", "DEBIAN", name)
            assert os.path.isfile(path), f"falta {name}"
            text = _read(path)
            assert text.startswith("#!/bin/sh")
            assert "set -e" in text

    def test_postinst_copies_whitelists(self):
        text = _read(os.path.join(PACKAGING, "yap", "DEBIAN", "postinst"))
        assert 'YAP_ETC="/etc/yap"' in text
        assert "$YAP_ETC/whitelist" in text
        assert "apps.conf" in text
        assert "web.conf" in text
        assert "ejercicios.conf" in text
        assert "install_if_missing" in text

    def test_postinst_installs_apparmor(self):
        text = _read(os.path.join(PACKAGING, "yap", "DEBIAN", "postinst"))
        assert "/etc/apparmor.d/usr.local.bin.yap" in text
        assert "apparmor_parser" in text

    def test_postinst_creates_symlink(self):
        text = _read(os.path.join(PACKAGING, "yap", "DEBIAN", "postinst"))
        assert "ln -sf /opt/yap/yap.py /usr/local/bin/yap" in text

    def test_postinst_does_not_overwrite_existing_configs(self):
        text = _read(os.path.join(PACKAGING, "yap", "DEBIAN", "postinst"))
        assert '[ ! -e "$dest" ]' in text

    def test_prerm_unloads_apparmor(self):
        text = _read(os.path.join(PACKAGING, "yap", "DEBIAN", "prerm"))
        assert "apparmor_parser -R" in text

    def test_postrm_purge_removes_etc_yap(self):
        text = _read(os.path.join(PACKAGING, "yap", "DEBIAN", "postrm"))
        assert "rm -rf /etc/yap" in text
        assert "purge" in text

    def test_postrm_preserves_user_config(self):
        text = _read(os.path.join(PACKAGING, "yap", "DEBIAN", "postrm"))
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            assert ".config/yap" not in stripped
            assert "/home/" not in stripped
            assert "rm -rf ~/" not in stripped

    def test_copyright_is_mit(self):
        text = _read(os.path.join(PACKAGING, "yap", "copyright"))
        assert "MIT" in text
        assert "ChincoLinux" in text


# ============================================================
# Paquetes de modelo
# ============================================================

class TestModelPackages:
    """Requisito: yap-models-1b / yap-models-3b descargan el GGUF."""

    @pytest.mark.parametrize("pkg,filename", [
        ("yap-models-1b", "Llama-3.2-1B-Instruct-Q4_K_M.gguf"),
        ("yap-models-3b", "Llama-3.2-3B-Instruct-Q4_K_M.gguf"),
    ])
    def test_control_depends_on_yap(self, pkg, filename):
        text = _read(os.path.join(PACKAGING, pkg, "DEBIAN", "control"))
        fields = parse_control(text)
        assert fields.get("Package") == pkg
        assert fields.get("Architecture") == "all"
        assert "yap" in fields.get("Depends", "")
        assert "wget" in fields.get("Depends", "")

    @pytest.mark.parametrize("pkg,filename", [
        ("yap-models-1b", "Llama-3.2-1B-Instruct-Q4_K_M.gguf"),
        ("yap-models-3b", "Llama-3.2-3B-Instruct-Q4_K_M.gguf"),
    ])
    def test_postinst_downloads_huggingface(self, pkg, filename):
        text = _read(os.path.join(PACKAGING, pkg, "DEBIAN", "postinst"))
        assert text.startswith("#!/bin/sh")
        assert "set -e" in text
        assert filename in text
        assert "huggingface.co" in text
        assert "/opt/yap/models" in text
        assert "wget" in text
        assert "curl" in text

    @pytest.mark.parametrize("pkg", ["yap-models-1b", "yap-models-3b"])
    def test_postinst_skips_if_embedded(self, pkg):
        text = _read(os.path.join(PACKAGING, pkg, "DEBIAN", "postinst"))
        assert "ya existe, no se descarga" in text

    @pytest.mark.parametrize("pkg", ["yap-models-1b", "yap-models-3b"])
    def test_postrm_purge_only_own_gguf(self, pkg):
        text = _read(os.path.join(PACKAGING, pkg, "DEBIAN", "postrm"))
        assert "purge" in text
        assert "rm -rf /etc/yap" not in text
        assert "/.config/yap" not in text or "Conserva" in text


# ============================================================
# build-deb.sh
# ============================================================

class TestBuildDebScript:
    """Requisito: build-deb.sh funcional, dpkg-deb, llama.cpp estatico."""

    def test_script_exists(self):
        assert os.path.isfile(BUILD_DEB)
        assert os.path.isfile(os.path.join(PACKAGING, "test-install-debian.sh"))

    def test_script_is_strict_bash(self):
        text = _read(BUILD_DEB)
        assert text.startswith("#!/usr/bin/env bash")
        assert "set -euo pipefail" in text

    def test_uses_dpkg_deb(self):
        text = _read(BUILD_DEB)
        assert "dpkg-deb" in text
        assert "--root-owner-group" in text

    def test_static_cpu_only_flags(self):
        text = _read(BUILD_DEB)
        assert "-DBUILD_SHARED_LIBS=OFF" in text
        assert "-DLLAMA_CUDA=OFF" in text
        assert "-DLLAMA_METAL=OFF" in text
        assert "-DLLAMA_CURL=OFF" in text

    def test_cli_flags(self):
        text = _read(BUILD_DEB)
        for flag in ("--stub-llama", "--skip-llama", "--llama-cli",
                     "--embed-models", "--no-models", "--outdir"):
            assert flag in text

    def test_packages_payload_paths(self):
        text = _read(BUILD_DEB)
        assert "/opt/yap/yap.py" in text
        assert "/usr/local/bin/yap" in text
        assert "/usr/local/bin/llama-cli" in text
        assert "usr/share/yap/whitelist" in text
        assert "usr/share/doc/yap" in text

    def test_reads_version_file(self):
        text = _read(BUILD_DEB)
        assert "VERSION" in text
        assert os.path.isfile(VERSION_FILE)
        version = _read(VERSION_FILE).strip()
        assert version, "VERSION vacio"


# ============================================================
# Layout de fuentes empaquetadas
# ============================================================

class TestSourcePayload:
    """Los archivos que el .deb debe incluir existen en el repo."""

    def test_whitelist_files(self):
        assert os.path.isfile(os.path.join(REPO_ROOT, "whitelist", "apps.conf"))
        assert os.path.isfile(os.path.join(REPO_ROOT, "whitelist", "web.conf"))
        assert os.path.isfile(os.path.join(REPO_ROOT, "whitelist", "pseint", "ejercicios.conf"))

    def test_apparmor_profile(self):
        assert os.path.isfile(os.path.join(REPO_ROOT, "apparmor", "usr.local.bin.yap"))

    def test_curso_fpy1101(self):
        assert os.path.isfile(os.path.join(REPO_ROOT, "cursos", "FPY1101.json"))

    def test_yap_py_exists(self):
        assert os.path.isfile(os.path.join(REPO_ROOT, "yap.py"))


# ============================================================
# Build real (solo si hay dpkg-deb + bash)
# ============================================================

def _have_deb_toolchain():
    return shutil.which("bash") and shutil.which("dpkg-deb")


@pytest.mark.skipif(not _have_deb_toolchain(), reason="requiere bash y dpkg-deb (Linux)")
class TestBuildDebSmoke:
    """Construye yap_*.deb con llama-cli stub y verifica el archivo."""

    def test_build_stub_produces_debs(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                ["bash", BUILD_DEB, "--stub-llama", "--outdir", tmp],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            assert result.returncode == 0, result.stderr + "\n" + result.stdout
            version = _read(VERSION_FILE).strip()
            yap_deb = os.path.join(tmp, f"yap_{version}_amd64.deb")
            m1 = os.path.join(tmp, f"yap-models-1b_{version}_all.deb")
            m3 = os.path.join(tmp, f"yap-models-3b_{version}_all.deb")
            assert os.path.isfile(yap_deb), os.listdir(tmp)
            assert os.path.isfile(m1)
            assert os.path.isfile(m3)
            assert os.path.getsize(yap_deb) > 1024

    def test_contents_include_agent_and_whitelists(self):
        dpkg_deb = shutil.which("dpkg-deb")
        if not dpkg_deb:
            pytest.skip("dpkg-deb no disponible")
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                ["bash", BUILD_DEB, "--stub-llama", "--no-models", "--outdir", tmp],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            assert result.returncode == 0, result.stderr
            version = _read(VERSION_FILE).strip()
            yap_deb = os.path.join(tmp, f"yap_{version}_amd64.deb")
            listing = subprocess.run(
                [dpkg_deb, "-c", yap_deb],
                capture_output=True, text=True, timeout=30,
            )
            assert listing.returncode == 0
            out = listing.stdout
            assert "opt/yap/yap.py" in out
            assert "usr/local/bin/llama-cli" in out
            assert "usr/share/yap/whitelist/apps.conf" in out
            assert "usr/share/yap/apparmor/usr.local.bin.yap" in out
            assert "etc/apparmor.d/usr.local.bin.yap" in out
            assert "usr/share/user-tmpfiles.d/yap.conf" in out
            conffiles = subprocess.run(
                [dpkg_deb, "-I", yap_deb, "conffiles"],
                capture_output=True, text=True, timeout=30,
            )
            assert conffiles.returncode == 0, conffiles.stderr
            assert conffiles.stdout.strip() == "/etc/apparmor.d/usr.local.bin.yap"


# ============================================================
# Ejecucion de maintainer scripts con rutas aisladas (sin root ni red)
# ============================================================

@pytest.fixture
def maintainer_env(tmp_path):
    """Run the actual shell scripts; relocate only absolute installation paths."""
    if os.name != "posix" or not shutil.which("sh"):
        pytest.skip("requiere shell POSIX")
    root = tmp_path / "root"
    share = root / "usr/share/yap"
    for dirname, source in (
        ("whitelist", "whitelist"), ("cursos", "cursos"),
        ("pseint", "whitelist/pseint"),
    ):
        shutil.copytree(Path(REPO_ROOT) / source, share / dirname)
    profile = root / "etc/apparmor.d/usr.local.bin.yap"
    profile.parent.mkdir(parents=True)
    shutil.copyfile(Path(REPO_ROOT) / "apparmor/usr.local.bin.yap", profile)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    parser = fake_bin / "apparmor_parser"
    parser.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$YAP_TEST_PARSER_LOG"\n'
        'case "$1" in\n'
        '  -r) exit "${YAP_TEST_LOAD_RC:-0}" ;;\n'
        '  --skip-kernel-load) exit "${YAP_TEST_PARSE_RC:-0}" ;;\n'
        'esac\n', encoding="utf-8",
    )
    parser.chmod(0o755)
    log = tmp_path / "parser.log"
    env = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}",
               YAP_TEST_PARSER_LOG=str(log))

    def run(name="postinst", action="configure"):
        script = _read(os.path.join(PACKAGING, "yap", "DEBIAN", name))
        for path in ("/usr/share/yap", "/etc/yap", "/opt/yap",
                     "/usr/local/bin", "/etc/apparmor.d",
                     "/sys/kernel/security/apparmor"):
            script = script.replace(path, str(root) + path)
        target = tmp_path / name
        target.write_text(script, encoding="utf-8")
        return subprocess.run(["sh", str(target), action], env=env,
                              capture_output=True, text=True, timeout=15)

    return root, env, log, run


class TestMaintainerScripts:
    def test_install_and_reconfigure_preserve_admin_configs(self, maintainer_env):
        root, _, log, run = maintainer_env
        result = run()
        assert result.returncode == 0, result.stderr
        etc = root / "etc/yap"
        apps = etc / "whitelist/apps.conf"
        web = etc / "whitelist/web.conf"
        assert apps.read_bytes() == (Path(REPO_ROOT) / "whitelist/apps.conf").read_bytes()
        assert web.is_file()
        assert (etc / "cursos/FPY1101.json").is_file()
        assert (etc / "pseint/ejercicios.conf").is_file()
        assert (root / "usr/local/bin/yap").is_symlink()
        apps.write_text("CUSTOM\n", encoding="utf-8")
        apps.chmod(0o640)
        # Even intentionally empty whitelists must remain empty.
        web.write_text("", encoding="utf-8")
        result = run()
        assert result.returncode == 0, result.stderr
        assert apps.read_text() == "CUSTOM\n"
        assert apps.stat().st_mode & 0o777 == 0o640
        assert web.read_text() == ""
        assert len(log.read_text().splitlines()) == 2  # parse only; no kernel
        assert "sin confinamiento activo" in result.stderr

    def test_dangling_config_symlink_is_not_followed(self, maintainer_env):
        root, _, _, run = maintainer_env
        apps = root / "etc/yap/whitelist/apps.conf"
        apps.parent.mkdir(parents=True)
        target = root / "admin-missing.conf"
        apps.symlink_to(target)
        assert run().returncode == 0
        assert apps.is_symlink()
        assert not target.exists()

    def test_loads_valid_profile_when_kernel_is_available(self, maintainer_env):
        root, _, log, run = maintainer_env
        (root / "sys/kernel/security/apparmor").mkdir(parents=True)
        result = run()
        assert result.returncode == 0, result.stderr
        calls = log.read_text().splitlines()
        assert calls[0].startswith("--skip-kernel-load --skip-cache ")
        assert calls[1].startswith("-r ")

    @pytest.mark.parametrize("failure", ["YAP_TEST_PARSE_RC", "YAP_TEST_LOAD_RC"])
    def test_parser_errors_fail_configuration(self, maintainer_env, failure):
        root, env, _, run = maintainer_env
        (root / "sys/kernel/security/apparmor").mkdir(parents=True)
        env[failure] = "1"
        assert run().returncode != 0

    def test_respects_admin_disabled_profile(self, maintainer_env):
        root, _, log, run = maintainer_env
        (root / "sys/kernel/security/apparmor").mkdir(parents=True)
        disabled = root / "etc/apparmor.d/disable/usr.local.bin.yap"
        disabled.parent.mkdir()
        disabled.symlink_to("../usr.local.bin.yap")
        result = run()
        assert result.returncode == 0, result.stderr
        assert "deshabilitado" in result.stderr
        assert len(log.read_text().splitlines()) == 1

    def test_postinst_preserves_dpkg_managed_profile(self, maintainer_env):
        root, _, _, run = maintainer_env
        profile = root / "etc/apparmor.d/usr.local.bin.yap"
        custom = profile.read_text() + "\n# Administrator customization\n"
        profile.write_text(custom, encoding="utf-8")
        assert run().returncode == 0
        assert profile.read_text() == custom
        profile.unlink()  # An admin deletion is also a conffile choice.
        assert run().returncode == 0
        assert not profile.exists()

    def test_upgrade_does_not_unload_profile(self, maintainer_env):
        _, _, log, run = maintainer_env
        assert run("prerm", "upgrade").returncode == 0
        assert not log.exists()
        assert run("prerm", "remove").returncode == 0
        assert log.read_text().startswith("-R ")

    def test_remove_preserves_configs_and_purge_cleans_etc_only(self, maintainer_env):
        root, _, _, run = maintainer_env
        assert run().returncode == 0
        etc = root / "etc/yap"
        student = root / "home/student/.config/yap/progress.json"
        student.parent.mkdir(parents=True)
        student.write_text('{"progress": 1}', encoding="utf-8")
        assert run("postrm", "remove").returncode == 0
        assert etc.is_dir()
        assert (root / "etc/apparmor.d/usr.local.bin.yap").is_file()
        assert run("postrm", "purge").returncode == 0
        assert not etc.exists()
        assert student.read_text() == '{"progress": 1}'

    def test_other_postinst_actions_do_nothing(self, maintainer_env):
        root, _, log, run = maintainer_env
        assert run(action="abort-upgrade").returncode == 0
        assert not (root / "etc/yap").exists()
        assert not log.exists()


@pytest.mark.skipif(not shutil.which("apparmor_parser"), reason="requiere apparmor_parser")
def test_apparmor_profile_compiles_without_kernel():
    result = subprocess.run(
        ["apparmor_parser", "--skip-kernel-load", "--skip-cache",
         os.path.join(REPO_ROOT, "apparmor", "usr.local.bin.yap")],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(not shutil.which("systemd-tmpfiles"), reason="requiere systemd-tmpfiles")
def test_user_tmpfiles_creates_private_directory_without_deleting_progress(tmp_path):
    user_home = tmp_path / "student"
    user_home.mkdir()
    env = dict(os.environ, HOME=str(user_home))
    command = ["systemd-tmpfiles", "--user", "--create",
               os.path.join(PACKAGING, "yap", "user-tmpfiles.d", "yap.conf")]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    config = user_home / ".config/yap"
    assert config.is_dir()
    assert config.stat().st_mode & 0o777 == 0o700
    assert config.stat().st_uid == os.getuid()
    progress = config / "progress.json"
    progress.write_text('{"progress": 1}', encoding="utf-8")
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert progress.read_text() == '{"progress": 1}'


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
