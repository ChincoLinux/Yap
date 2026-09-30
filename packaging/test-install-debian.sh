#!/bin/sh
# Instalacion limpia de los .deb de Yap en Debian 12 (CI, issue #31).
# Uso (dentro del contenedor): sh test-install-debian.sh /debs
set -eu

DEBDIR="${1:-/debs}"
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y -qq python3 libnotify-bin apparmor ca-certificates wget

echo "=== Instalando yap_*.deb ==="
# shellcheck disable=SC2086
apt-get install -y $DEBDIR/yap_*.deb

echo "=== Verificacion de archivos ==="
test -x /opt/yap/yap.py
test -L /usr/local/bin/yap
test "$(readlink /usr/local/bin/yap)" = "/opt/yap/yap.py"
test -x /usr/local/bin/llama-cli
test -f /etc/yap/whitelist/apps.conf
test -f /etc/yap/whitelist/web.conf
test -f /etc/yap/pseint/ejercicios.conf
test -f /etc/yap/cursos/FPY1101.json
test -f /etc/apparmor.d/usr.local.bin.yap
test -d /opt/yap/models

echo "=== Comando yap ayuda ==="
/usr/bin/python3 /opt/yap/yap.py ayuda

echo "=== Modelo 1B con wget simulado (sin red) ==="
if [ -x /usr/bin/wget ]; then
    mv /usr/bin/wget /usr/bin/wget.real
fi
printf '%s\n' \
    '#!/bin/sh' \
    'dest=""' \
    'while [ $# -gt 0 ]; do' \
    '  case "$1" in' \
    '    -O) dest="$2"; shift 2 ;;' \
    '    *) shift ;;' \
    '  esac' \
    'done' \
    '[ -n "$dest" ] || exit 1' \
    'mkdir -p "$(dirname "$dest")"' \
    'printf GGUF-STUB > "$dest"' \
    > /usr/bin/wget
chmod 0755 /usr/bin/wget

# shellcheck disable=SC2086
apt-get install -y $DEBDIR/yap-models-1b_*.deb
test -s /opt/yap/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf

echo "PASS: instalacion limpia Debian 12"
