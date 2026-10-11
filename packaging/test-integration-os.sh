#!/bin/sh
# Verificacion de integracion en un sistema ChincoLinux OS real (#34).
#
# Pensado para correr dentro de una Live USB, una VM o una laptop educativa
# con Yap ya instalado (.deb o ISO). No instala nada: sólo comprueba.
#
# Uso:
#   sh packaging/test-integration-os.sh           # todas las comprobaciones
#   sh packaging/test-integration-os.sh --help    # esta ayuda
#
# Sale con 0 si todo pasa, 1 si algo falla (los SKIP no cuentan).

set -u

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    cat <<'EOF'
Verificacion de integracion de Yap en ChincoLinux OS (#34)

Comprueba en un sistema real:
  1. yap esta en el PATH
  2. yap --apparmor-status informa enforce
  3. yap ayuda lista comandos
  4. yap curso FPY1101 muestra el curso
  5. whitelists en /etc/yap/
  6. modelo en /opt/yap/models/
  7. AppArmor deniega accesos fuera del perfil
  8. yap --daemon-status responde

Uso: sh packaging/test-integration-os.sh
EOF
    exit 0
fi

FALLAS=0
TOTALES=0

ok()   { printf '  [OK]    %s\n' "$1"; }
fail() { printf '  [FALLA] %s\n' "$1"; FALLAS=$((FALLAS + 1)); }
skip() { printf '  [SKIP]  %s\n' "$1"; }
seccion() { printf '\n=== %s ===\n' "$1"; TOTALES=$((TOTALES + 1)); }

seccion "1. yap en el PATH"
if command -v yap >/dev/null 2>&1; then
    ok "$(command -v yap)"
else
    fail "no se encontro 'yap' en el PATH"
fi

seccion "2. AppArmor en enforce"
if command -v yap >/dev/null 2>&1; then
    # El comando se llama --apparmor-status y tambien --postinstall-check
    SALIDA=$(yap --apparmor-status 2>&1 || true)
    case "$SALIDA" in
        *enforce*|*ACTIVO*|*Activo*) ok "yap --apparmor-status: enforce" ;;
        *) fail "yap --apparmor-status no informa enforce: $SALIDA" ;;
    esac
else
    skip "sin 'yap' en el PATH"
fi

seccion "3. yap ayuda"
if command -v yap >/dev/null 2>&1; then
    AYUDA=$(yap ayuda 2>&1 || true)
    if [ -n "$AYUDA" ]; then
        ok "la ayuda imprime $(printf '%s' "$AYUDA" | wc -l) lineas"
    else
        fail "yap ayuda no imprime nada"
    fi
else
    skip "sin 'yap' en el PATH"
fi

seccion "4. yap curso FPY1101"
if command -v yap >/dev/null 2>&1; then
    CURSO=$(yap curso FPY1101 2>&1 || true)
    case "$CURSO" in
        *FPY1101*) ok "el curso se muestra" ;;
        *) fail "no aparece FPY1101 en la salida" ;;
    esac
else
    skip "sin 'yap' en el PATH"
fi

seccion "5. whitelists en /etc/yap/"
if [ -f /etc/yap/whitelist/apps.conf ] && [ -f /etc/yap/whitelist/web.conf ]; then
    ok "apps.conf y web.conf presentes"
else
    fail "faltan /etc/yap/whitelist/{apps,web}.conf"
fi

seccion "6. modelo en /opt/yap/models/"
MODELO=$(ls /opt/yap/models/*.gguf 2>/dev/null | head -n 1)
if [ -n "$MODELO" ]; then
    ok "$MODELO ($(wc -c < "$MODELO") bytes)"
else
    fail "no hay ningun .gguf en /opt/yap/models/"
fi

seccion "7. AppArmor deniega fuera del perfil"
if command -v aa-exec >/dev/null 2>&1 && [ -f /etc/apparmor.d/usr.local.bin.yap ]; then
    # Bajo el perfil, leer /etc/shadow debe ser denegado.
    if aa-exec -p usr_local.bin_yap -- cat /etc/shadow >/dev/null 2>&1; then
        fail "aa-exec pudo leer /etc/shadow: el perfil no restringe"
    else
        ok "lectura denegada por el perfil"
    fi
else
    skip "sin aa-exec o sin el perfil instalado"
fi

seccion "8. yap --daemon-status"
if command -v yap >/dev/null 2>&1; then
    ESTADO=$(yap --daemon-status 2>&1 || true)
    if [ -n "$ESTADO" ]; then
        ok "$ESTADO"
    else
        fail "yap --daemon-status no responde"
    fi
else
    skip "sin 'yap' en el PATH"
fi

printf '\n=== Resumen: %s comprobaciones, %s fallas ===\n' "$TOTALES" "$FALLAS"
if [ "$FALLAS" -gt 0 ]; then
    exit 1
fi
exit 0
