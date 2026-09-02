#!/usr/bin/env bash
# Conecta Yap (Linux) a Gemini Enterprise Agent Platform.
# Uso:
#   export PROJECT_ID=yap-nube-xxx
#   export ENGINE_ID=1234567890
#   ./agent-platform/conectar-linux.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

die() { echo "ERROR: $*" >&2; exit 1; }

command -v python3 >/dev/null || die "Instala python3"
command -v gcloud >/dev/null || die "Instala gcloud: https://cloud.google.com/sdk/docs/install"

PROJECT_ID="${PROJECT_ID:-${YAP_CLOUD_PROJECT:-}}"
LOCATION="${LOCATION:-${YAP_CLOUD_LOCATION:-southamerica-west1}}"
ENGINE_ID="${ENGINE_ID:-${YAP_CLOUD_ENGINE_ID:-}}"
BACKEND="${YAP_CLOUD_BACKEND:-agent_platform}"

[[ -n "$PROJECT_ID" ]] || die "Falta PROJECT_ID (ejemplo: export PROJECT_ID=yap-nube-kirto)"
if [[ "$BACKEND" == "agent_platform" || "$BACKEND" == "agent" || "$BACKEND" == "adk" ]]; then
  [[ -n "$ENGINE_ID" ]] || die "Falta ENGINE_ID (el numero que imprimio _deploy.py)"
fi

gcloud config set project "$PROJECT_ID" >/dev/null
TOKEN="$(gcloud auth print-access-token 2>/dev/null || true)"
[[ -n "$TOKEN" ]] || die "gcloud auth login  (y luego gcloud auth application-default login)"

export YAP_CLOUD_ENABLED=1
export YAP_CLOUD_BACKEND="$BACKEND"
export YAP_CLOUD_PROJECT="$PROJECT_ID"
export YAP_CLOUD_LOCATION="$LOCATION"
export YAP_CLOUD_ENGINE_ID="$ENGINE_ID"
export YAP_CLOUD_MODEL="${YAP_CLOUD_MODEL:-gemini-3.7-flash}"
export YAP_CLOUD_TOKEN="$TOKEN"
export YAP_CLOUD_TIMEOUT="${YAP_CLOUD_TIMEOUT:-20}"

echo "Yap -> Agent Platform"
echo "  project  = $PROJECT_ID"
echo "  location = $LOCATION"
echo "  backend  = $BACKEND"
echo "  engine   = ${ENGINE_ID:-(generate)}"
echo
python3 "$ROOT/yap.py" nube
echo
echo "Prueba:"
echo "  python3 yap.py nube explica la diferencia entre while y for"
echo
if [[ "${1:-}" == "--query" ]]; then
  shift
  python3 "$ROOT/yap.py" nube "${*:-explica while en una frase}"
fi
