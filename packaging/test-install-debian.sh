#!/bin/sh
# Instalacion, reinstalacion y purga en Debian 12/13 (CI, issues #31 y #33).
# Uso (dentro del contenedor): sh test-install-debian.sh /debs
set -eu

DEBDIR="${1:-/debs}"
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y -qq python3 libnotify-bin apparmor ca-certificates wget systemd

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
test -f /usr/share/user-tmpfiles.d/yap.conf
test -d /opt/yap/models
dpkg-query -W -f='${Conffiles}\n' yap | grep /etc/apparmor.d/usr.local.bin.yap

echo "=== AppArmor: compilacion real sin cargar politicas en el host ==="
apparmor_parser --skip-kernel-load --skip-cache /etc/apparmor.d/usr.local.bin.yap

echo "=== Configuracion de usuario con tmpfiles ==="
useradd --create-home --shell /bin/sh yap-student
test ! -e /home/yap-student/.config/yap
# El contenedor no inicia sesiones; ejecutar la misma operacion del servicio de usuario.
runuser -u yap-student -- systemd-tmpfiles --user --create yap.conf
test "$(stat -c %U /home/yap-student/.config/yap)" = yap-student
test "$(stat -c %a /home/yap-student/.config/yap)" = 700
runuser -u yap-student -- sh -c 'printf "%s\n" "{\"progress\": 1}" > "$HOME/.config/yap/progress.json"'
runuser -u yap-student -- systemd-tmpfiles --user --create yap.conf
grep -q '"progress": 1' /home/yap-student/.config/yap/progress.json

echo "=== Reconfiguracion y reinstalacion conservan personalizaciones ==="
printf '\n# Configuracion del aula\n' >> /etc/yap/whitelist/apps.conf
printf '\n# Perfil del administrador\n' >> /etc/apparmor.d/usr.local.bin.yap
cp /etc/yap/whitelist/apps.conf /tmp/yap-apps.expected
cp /etc/apparmor.d/usr.local.bin.yap /tmp/yap-apparmor.expected
chmod 0640 /etc/yap/whitelist/apps.conf
dpkg-reconfigure -f noninteractive yap
# shellcheck disable=SC2086
apt-get install -y --reinstall $DEBDIR/yap_*.deb
cmp /tmp/yap-apps.expected /etc/yap/whitelist/apps.conf
cmp /tmp/yap-apparmor.expected /etc/apparmor.d/usr.local.bin.yap
test "$(stat -c %a /etc/yap/whitelist/apps.conf)" = 640

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

echo "=== Remove conserva configuracion; purge conserva progreso ==="
apt-get remove -y yap-models-1b yap
test -f /etc/yap/whitelist/apps.conf
test -f /etc/apparmor.d/usr.local.bin.yap
test ! -e /usr/share/user-tmpfiles.d/yap.conf
apt-get purge -y yap-models-1b yap
test ! -e /etc/yap
test ! -e /etc/apparmor.d/usr.local.bin.yap
grep -q '"progress": 1' /home/yap-student/.config/yap/progress.json

echo "PASS: instalacion, reinstalacion, tmpfiles y purga en Debian"
