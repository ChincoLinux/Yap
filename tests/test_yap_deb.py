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


# ============================================================
# Simulacion de postinst (copia if-missing)
# ============================================================

class TestPostinstCopySemantics:
    """install_if_missing no debe pisar configs del administrador."""

    def test_copy_only_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "share", "apps.conf")
            dest = os.path.join(tmp, "etc", "apps.conf")
            os.makedirs(os.path.dirname(src))
            os.makedirs(os.path.dirname(dest))
            with open(src, "w", encoding="utf-8") as fh:
                fh.write("DEFAULT\n")
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write("CUSTOM\n")

            # Replica la guarda de postinst
            if not os.path.exists(dest):
                shutil.copy(src, dest)

            with open(dest, encoding="utf-8") as fh:
                assert fh.read() == "CUSTOM\n"

    def test_copy_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "share", "apps.conf")
            dest = os.path.join(tmp, "etc", "apps.conf")
            os.makedirs(os.path.dirname(src))
            os.makedirs(os.path.dirname(dest))
            with open(src, "w", encoding="utf-8") as fh:
                fh.write("DEFAULT\n")

            if not os.path.exists(dest):
                shutil.copy(src, dest)

            with open(dest, encoding="utf-8") as fh:
                assert fh.read() == "DEFAULT\n"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
