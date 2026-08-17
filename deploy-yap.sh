#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# deploy-yap.sh — Despliegue masivo de Yap por SSH
# ============================================================
# Orquesta la instalación de Yap en varios equipos de un laboratorio
# escolar desde un equipo administrador con acceso SSH.
#
# Uso:
#   sudo ./deploy-yap.sh --hosts /etc/yap/lab1.txt [opciones]
#
# Opciones:
#   --hosts FILE        Archivo con un host por línea (IP o DNS). Obligatorio.
#   --mirror PATH       Usar mirror local (NFS/HTTP) en lugar de clonar de GitHub.
#   --branch BRANCH     Rama/modelo a desplegar (default: ultra-lowmem).
#   --whitelist DIR     Empujar whitelists centralizadas tras instalar.
#   --user USER         Usuario SSH remoto (default: alumno).
#   --parallel N        Equipos simultáneos (default: 4).
#   --dry-run           Solo mostrar qué se haría, sin ejecutar.
#   -h, --help          Mostrar esta ayuda.
#
# Requisitos:
#   - ssh, scp, rsync instalados en el administrador.
#   - Usuario remoto con sudo NOPASSWD para setup.sh (ver docs/DEPLOY.md §Apéndice A).
#   - Mirror accesible por los hosts (si se usa --mirror).
# ============================================================

# Valores por defecto
HOSTS_FILE=""
MIRROR=""
BRANCH="ultra-lowmem"
WHITELIST_DIR=""
REMOTE_USER="alumno"
PARALLEL=4
DRY_RUN=false

# Colores mínimos (sin dependencias)
if [ -t 1 ]; then
  C_GREEN=$'\033[92m'; C_YELLOW=$'\033[93m'; C_RED=$'\033[91m'
  C_CYAN=$'\033[96m'; C_GRAY=$'\033[90m'; C_RESET=$'\033[0m'
else
  C_GREEN=""; C_YELLOW=""; C_RED=""; C_CYAN=""; C_GRAY=""; C_RESET=""
fi

usage() {
  cat <<'EOF'
deploy-yap.sh — Despliegue masivo de Yap por SSH

Orquesta la instalación de Yap en varios equipos de un laboratorio
escolar desde un equipo administrador con acceso SSH.

Uso:
  sudo ./deploy-yap.sh --hosts /etc/yap/lab1.txt [opciones]

Opciones:
  --hosts FILE        Archivo con un host por línea (IP o DNS). Obligatorio.
  --mirror PATH       Usar mirror local (NFS/HTTP) en lugar de clonar de GitHub.
  --branch BRANCH     Rama/modelo a desplegar (default: ultra-lowmem).
  --whitelist DIR     Empujar whitelists centralizadas tras instalar.
  --user USER         Usuario SSH remoto (default: alumno).
  --parallel N        Equipos simultáneos (default: 4).
  --dry-run           Solo mostrar qué se haría, sin ejecutar.
  -h, --help          Mostrar esta ayuda.

Requisitos:
  - ssh, scp, rsync instalados en el administrador.
  - Usuario remoto con sudo NOPASSWD para setup.sh (ver docs/DEPLOY.md §Apéndice A).
  - Mirror accesible por los hosts (si se usa --mirror).
EOF
  exit 0
}

# ── Parseo de argumentos ──────────────────────────────────────
while [ $# -gt 0 ]; do
  case "$1" in
    --hosts)    HOSTS_FILE="$2"; shift 2 ;;
    --mirror)   MIRROR="$2"; shift 2 ;;
    --branch)   BRANCH="$2"; shift 2 ;;
    --whitelist) WHITELIST_DIR="$2"; shift 2 ;;
    --user)     REMOTE_USER="$2"; shift 2 ;;
    --parallel) PARALLEL="$2"; shift 2 ;;
    --dry-run)  DRY_RUN=true; shift ;;
    -h|--help)  usage ;;
    *) echo "${C_RED}Error:${C_RESET} opción desconocida: $1" >&2; exit 2 ;;
  esac
done

# ── Validaciones ──────────────────────────────────────────────
if [ -z "$HOSTS_FILE" ]; then
  echo "${C_RED}Error:${C_RESET} --hosts es obligatorio. Usa -h para ayuda." >&2
  exit 2
fi

if [ ! -f "$HOSTS_FILE" ]; then
  echo "${C_RED}Error:${C_RESET} archivo de hosts no encontrado: $HOSTS_FILE" >&2
  exit 2
fi

if ! command -v ssh >/dev/null 2>&1; then
  echo "${C_RED}Error:${C_RESET} 'ssh' no está instalado en el administrador." >&2
  exit 3
fi

if [ -n "$MIRROR" ] && [ ! -d "$MIRROR" ]; then
  echo "${C_RED}Error:${C_RESET} mirror no encontrado: $MIRROR" >&2
  exit 2
fi

if [ -n "$WHITELIST_DIR" ] && [ ! -d "$WHITELIST_DIR" ]; then
  echo "${C_RED}Error:${C_RESET} directorio de whitelists no encontrado: $WHITELIST_DIR" >&2
  exit 2
fi

# Validar que PARALLEL sea entero positivo
if ! [[ "$PARALLEL" =~ ^[1-9][0-9]*$ ]]; then
  echo "${C_RED}Error:${C_RESET} --parallel debe ser un entero positivo." >&2
  exit 2
fi

# Leer hosts (ignorar líneas vacías y comentarios)
mapfile -t HOSTS < <(grep -vE '^\s*(#|$)' "$HOSTS_FILE" || true)

if [ ${#HOSTS[@]} -eq 0 ]; then
  echo "${C_RED}Error:${C_RESET} no se encontraron hosts en $HOSTS_FILE" >&2
  exit 2
fi

# ── Resumen del despliegue ────────────────────────────────────
echo "${C_CYAN}═══════════════════════════════════════════════════════════════${C_RESET}"
echo "${C_CYAN}  deploy-yap.sh — Despliegue masivo de Yap${C_RESET}"
echo "${C_CYAN}═══════════════════════════════════════════════════════════════${C_RESET}"
echo "  Hosts:        ${#HOSTS[@]} equipo(s) desde $HOSTS_FILE"
echo "  Rama:         $BRANCH"
echo "  Usuario SSH:  $REMOTE_USER"
echo "  Paralelismo:  $PARALLEL"
[ -n "$MIRROR" ]       && echo "  Mirror:       $MIRROR"       || echo "  Mirror:       (clonar desde GitHub)"
[ -n "$WHITELIST_DIR" ] && echo "  Whitelists:   $WHITELIST_DIR" || echo "  Whitelists:   (no se empujan)"
$DRY_RUN && echo "  ${C_YELLOW}Modo:${C_RESET}          DRY-RUN (sin ejecutar)" || echo "  Modo:         ejecución real"
echo ""

# ── Función de despliegue por host ────────────────────────────
# Imprime a stdout: "HOST|OK" o "HOST|FAIL|mensaje"
deploy_one() {
  local host="$1"
  local ssh_target="${REMOTE_USER}@${host}"
  local remote_dir="/opt/Yap"

  # 0. Dry-run: reportar sin tocar la red
  if $DRY_RUN; then
    echo "${host}|OK|dry-run: se instalaría rama $BRANCH"
    return 0
  fi

  # 1. Verificar conectividad SSH (timeout 10s)
  if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$ssh_target" 'echo ok' >/dev/null 2>&1; then
    echo "${host}|FAIL|sin conexión SSH"
    return 0
  fi

  # 2. Asegurar /opt/Yap en el remoto (clonar o sincronizar desde mirror)
  if [ -n "$MIRROR" ]; then
    # Sincronizar mirror local al remoto por rsync (reutiliza modelo ya descargado)
    if ! rsync -a --delete --exclude='.git' "$MIRROR/" \
         "${ssh_target}:${remote_dir}/" 2>/dev/null; then
      echo "${host}|FAIL|rsync desde mirror falló"
      return 0
    fi
  else
    # Clonar desde GitHub en el remoto (requiere internet en el host)
    if ! ssh -o BatchMode=yes "$ssh_target" \
         "sudo git clone --branch $BRANCH --depth 1 https://github.com/ChincoLinux/Yap.git ${remote_dir} 2>/dev/null || true" 2>/dev/null; then
      echo "${host}|FAIL|git clone falló"
      return 0
    fi
  fi

  # 3. Asegurar la rama correcta
  ssh -o BatchMode=yes "$ssh_target" \
      "sudo git -C ${remote_dir} checkout $BRANCH 2>/dev/null || true" >/dev/null 2>&1

  # 4. Ejecutar setup.sh en el remoto
  if ssh -o BatchMode=yes "$ssh_target" "sudo ${remote_dir}/setup.sh" >/dev/null 2>&1; then
    # 5. Empujar whitelists centralizadas si se solicitó
    if [ -n "$WHITELIST_DIR" ]; then
      scp -q "${WHITELIST_DIR}/apps.conf" "${WHITELIST_DIR}/web.conf" \
          "${ssh_target}:/tmp/" 2>/dev/null && \
        ssh -o BatchMode=yes "$ssh_target" \
            "sudo mv /tmp/apps.conf /etc/yap/whitelist/apps.conf && sudo mv /tmp/web.conf /etc/yap/whitelist/web.conf" \
            >/dev/null 2>&1 || true
    fi
    echo "${host}|OK|instalado rama $BRANCH"
  else
    echo "${host}|FAIL|setup.sh falló"
  fi
}

# ── Ejecución con paralelismo controlado ──────────────────────
export -f deploy_one
export REMOTE_USER BRANCH MIRROR WHITELIST_DIR DRY_RUN
export C_GREEN C_YELLOW C_RED C_CYAN C_GRAY C_RESET

RESULTS_FILE=$(mktemp)
trap 'rm -f "$RESULTS_FILE"' EXIT

# xargs controla el paralelismo; deploy_one es seguro para concurrencia
printf '%s\n' "${HOSTS[@]}" | xargs -I{} -P "$PARALLEL" bash -c 'deploy_one "$@"' _ {} \
  > "$RESULTS_FILE"

# ── Reporte final ─────────────────────────────────────────────
echo ""
echo "${C_CYAN}═══════════════════════════════════════════════════════════════${C_RESET}"
echo "${C_CYAN}  Reporte de despliegue${C_RESET}"
echo "${C_CYAN}═══════════════════════════════════════════════════════════════${C_RESET}"

OK=0; FAIL=0
while IFS='|' read -r host status detail; do
  if [ "$status" = "OK" ]; then
    echo "  ${C_GREEN}✓${C_RESET} ${host}  ${C_GRAY}${detail}${C_RESET}"
    OK=$((OK+1))
  else
    echo "  ${C_RED}✗${C_RESET} ${host}  ${C_YELLOW}${detail}${C_RESET}"
    FAIL=$((FAIL+1))
  fi
done < "$RESULTS_FILE"

echo ""
echo "  ${C_GREEN}OK:${C_RESET} $OK   ${C_RED}FALLARON:${C_RESET} $FAIL   Total: $((OK+FAIL))"

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "${C_YELLOW}Revisa los hosts fallidos y vuelve a ejecutar solo para ellos${C_RESET}"
  echo "${C_GRAY}  grep '|FAIL|' \"$RESULTS_FILE\" | cut -d'|' -f1 > hosts-retry.txt${C_RESET}"
  exit 1
fi

echo ""
echo "${C_GREEN}✓ Despliegue completado en los $OK equipos.${C_RESET}"
echo "${C_GRAY}Verifica con: ssh ${REMOTE_USER}@<host> 'yap --apparmor-status && yap ayuda'${C_RESET}"
