Name:           yap
Version:        1.0.1
Release:        1%{?dist}
Summary:        Asistente IA local CPU-only para entornos educativos
License:        MIT
URL:            https://github.com/ChincoLinux/Yap
Source0:        %{name}-%{version}.tar.gz

# llama-cli static binary is provided separately or built from source
# For CI/stub builds, a fake llama-cli can be used
BuildArch:      x86_64
BuildRequires:  python3

Requires:       python3 >= 3.11
Requires:       libnotify
Requires:       python3-gobject
Suggests:       yap-models-1b
Suggests:       yap-models-3b
Suggests:       firefox
Suggests:       libreoffice
Suggests:       evince

%description
Yap es un agente conversacional basado en Llama 3.2 Instruct (GGUF Q4_K_M),
ejecución CPU-only con llama.cpp de enlace estático, diseñado para entornos
educativos con recursos limitados (ChincoLinux / Debian 13).

Incluye el agente (yap.py), el binario llama-cli, whitelists educativas y el
perfil AppArmor. El modelo GGUF se instala por separado: dnf install yap-models-1b
o yap-models-3b.

# ─── yap-models-1b subpackage ───────────────────────────────────────────────
%package models-1b
Summary:        Modelo Llama 3.2 1B Instruct Q4_K_M para Yap
BuildArch:      noarch
Requires:       yap

%description models-1b
Modelo Llama 3.2 1B Instruct (GGUF Q4_K_M, ~0.81 GB).
Recomendado para equipos con 2–4 GB de RAM (ultra-lowmem).

# ─── yap-models-3b subpackage ───────────────────────────────────────────────
%package models-3b
Summary:        Modelo Llama 3.2 3B Instruct Q4_K_M para Yap
BuildArch:      noarch
Requires:       yap

%description models-3b
Modelo Llama 3.2 3B Instruct (GGUF Q4_K_M, ~2.0 GB).
Recomendado para equipos con 6–8 GB de RAM (main/lowmem).

# ─── prep ────────────────────────────────────────────────────────────────────
%prep
%autosetup

# ─── build ───────────────────────────────────────────────────────────────────
%build
# No compilation needed for yap.py (pure Python, stdlib-only)
# llama-cli is a pre-compiled static binary included in the source tarball

# ─── install ─────────────────────────────────────────────────────────────────
%install
install -d %{buildroot}/opt/yap/models
install -d %{buildroot}/usr/local/bin
install -d %{buildroot}/usr/share/yap/whitelist
install -d %{buildroot}/usr/share/yap/whitelist/pseint
install -d %{buildroot}/usr/share/yap/cursos
install -d %{buildroot}/usr/share/yap/apparmor
install -d %{buildroot}/usr/share/applications
install -d %{buildroot}/usr/share/doc/yap
install -d %{buildroot}/etc/yap
install -d %{buildroot}/etc/apparmor.d
install -d %{buildroot}/usr/share/user-tmpfiles.d

# Agent and runtime
install -m 755 yap.py %{buildroot}/opt/yap/yap.py
install -m 644 yap_core.py %{buildroot}/opt/yap/yap_core.py
install -m 755 llama-cli %{buildroot}/usr/local/bin/llama-cli

# Symlink: /usr/local/bin/yap -> /opt/yap/yap.py
ln -sf /opt/yap/yap.py %{buildroot}/usr/local/bin/yap

# Whitelists (defaults)
install -m 644 whitelist/apps.conf    %{buildroot}/usr/share/yap/whitelist/apps.conf
install -m 644 whitelist/web.conf     %{buildroot}/usr/share/yap/whitelist/web.conf
install -m 644 whitelist/pseint/ejercicios.conf \
    %{buildroot}/usr/share/yap/whitelist/pseint/ejercicios.conf
# PDF guide (optional, may not exist in all builds)
test -f whitelist/pseint/guia_ejercicios.pdf && \
    install -m 644 whitelist/pseint/guia_ejercicios.pdf \
    %{buildroot}/usr/share/yap/whitelist/pseint/guia_ejercicios.pdf || true

# Courses
for f in cursos/*.json; do
    install -m 644 "$f" %{buildroot}/usr/share/yap/cursos/
done

# AppArmor profile
install -m 644 apparmor/usr.local.bin.yap \
    %{buildroot}/etc/apparmor.d/usr.local.bin.yap

# Desktop integration
install -m 644 packaging/desktop/yap.desktop \
    %{buildroot}/usr/share/applications/yap.desktop

# User tmpfiles rule
install -m 644 packaging/yap/user-tmpfiles.d/yap.conf \
    %{buildroot}/usr/share/user-tmpfiles.d/yap.conf

# Systemd service
mkdir -p %{buildroot}%{_unitdir}
install -m 644 packaging/systemd/yap-daemon.service \
    %{buildroot}%{_unitdir}/yap-daemon.service

# Agent specification
if [ -f yap-agent.md ]; then
    install -m 644 yap-agent.md %{buildroot}/usr/share/yap/agent/yap.md
fi

# Documentation
install -m 644 README.md  %{buildroot}/usr/share/doc/yap/README.md
install -m 644 LICENSE    %{buildroot}/usr/share/doc/yap/LICENSE
install -m 644 USAGE.md   %{buildroot}/usr/share/doc/yap/USAGE.md

# ─── post ────────────────────────────────────────────────────────────────────
%post
# Copy default whitelists to /etc/yap/ only if they don't exist (preserves admin changes)
for f in apps.conf web.conf; do
    if [ ! -f /etc/yap/$f ]; then
        cp /usr/share/yap/whitelist/$f /etc/yap/$f
    fi
done
if [ ! -d /etc/yap/pseint ]; then
    mkdir -p /etc/yap/pseint
    cp -r /usr/share/yap/whitelist/pseint/* /etc/yap/pseint/ 2>/dev/null || true
fi
if [ ! -d /etc/yap/cursos ]; then
    mkdir -p /etc/yap/cursos
    cp /usr/share/yap/cursos/*.json /etc/yap/cursos/ 2>/dev/null || true
fi

# Load AppArmor profile if available
if command -v apparmor_parser &>/dev/null && [ -d /sys/kernel/security/apparmor ]; then
    apparmor_parser -r /etc/apparmor.d/usr.local.bin.yap 2>/dev/null && \
        echo "yap: perfil AppArmor cargado (enforce)." || \
        echo "yap: aviso — AppArmor disponible pero el perfil no se pudo cargar."
else
    echo "yap: AppArmor no disponible en este kernel. Perfil instalado sin confinamiento activo."
fi

# Update desktop database
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database /usr/share/applications &>/dev/null || true
fi

# ─── preun ───────────────────────────────────────────────────────────────────
%preun
# Unload AppArmor profile on full removal (not on upgrade)
if [ $1 -eq 0 ]; then
    if command -v apparmor_parser &>/dev/null && [ -d /sys/kernel/security/apparmor ]; then
        apparmor_parser -R /etc/apparmor.d/usr.local.bin.yap 2>/dev/null || true
    fi
fi

# ─── postun ──────────────────────────────────────────────────────────────────
%postun
if [ $1 -eq 0 ]; then
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database /usr/share/applications &>/dev/null || true
    fi
fi

# ─── post (models-1b) ────────────────────────────────────────────────────────
%post models-1b
MODEL_DIR=/opt/yap/models
MODEL_FILE="$MODEL_DIR/Llama-3.2-1B-Instruct-Q4_K_M.gguf"
MODEL_URL="https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf"

mkdir -p "$MODEL_DIR"
if [ ! -f "$MODEL_FILE" ]; then
    echo "yap-models-1b: descargando modelo 1B (~0.81 GB)..."
    if command -v wget &>/dev/null; then
        wget -q --show-progress -O "$MODEL_FILE" "$MODEL_URL" || \
            { echo "ERROR: fallo en la descarga. Descarga manual: $MODEL_URL"; rm -f "$MODEL_FILE"; }
    elif command -v curl &>/dev/null; then
        curl -L --progress-bar -o "$MODEL_FILE" "$MODEL_URL" || \
            { echo "ERROR: fallo en la descarga. Descarga manual: $MODEL_URL"; rm -f "$MODEL_FILE"; }
    else
        echo "ERROR: wget o curl requeridos para descargar el modelo."
    fi
else
    echo "yap-models-1b: modelo ya presente en $MODEL_FILE"
fi

# ─── post (models-3b) ────────────────────────────────────────────────────────
%post models-3b
MODEL_DIR=/opt/yap/models
MODEL_FILE="$MODEL_DIR/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
MODEL_URL="https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"

mkdir -p "$MODEL_DIR"
if [ ! -f "$MODEL_FILE" ]; then
    echo "yap-models-3b: descargando modelo 3B (~2.0 GB)..."
    if command -v wget &>/dev/null; then
        wget -q --show-progress -O "$MODEL_FILE" "$MODEL_URL" || \
            { echo "ERROR: fallo en la descarga. Descarga manual: $MODEL_URL"; rm -f "$MODEL_FILE"; }
    elif command -v curl &>/dev/null; then
        curl -L --progress-bar -o "$MODEL_FILE" "$MODEL_URL" || \
            { echo "ERROR: fallo en la descarga. Descarga manual: $MODEL_URL"; rm -f "$MODEL_FILE"; }
    else
        echo "ERROR: wget o curl requeridos para descargar el modelo."
    fi
else
    echo "yap-models-3b: modelo ya presente en $MODEL_FILE"
fi

# ─── files ───────────────────────────────────────────────────────────────────
%files
/opt/yap/yap.py
/opt/yap/yap_core.py
/usr/local/bin/yap
/usr/local/bin/llama-cli
/usr/share/yap/whitelist/
/usr/share/yap/cursos/
%config(noreplace) /etc/apparmor.d/usr.local.bin.yap
/usr/share/applications/yap.desktop
/usr/share/user-tmpfiles.d/yap.conf
%{_unitdir}/yap-daemon.service
%doc /usr/share/doc/yap/README.md
%doc /usr/share/doc/yap/LICENSE
%doc /usr/share/doc/yap/USAGE.md

%files models-1b
# The model file is downloaded in %post, not in the package itself
%dir /opt/yap/models

%files models-3b
%dir /opt/yap/models

# ─── changelog ───────────────────────────────────────────────────────────────
%changelog
* Sun Oct 11 2026 ChincoLinux <chincolinux@users.noreply.github.com> - 1.0.1-1
- Initial Fedora RPM packaging (issue #161)
- Mirrors the existing Debian .deb structure
- Adds AppArmor support with apparmor_parser
- Desktop integration via .desktop file
