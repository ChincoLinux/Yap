#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Yap — Instalación del Agente IA local para ChincoLinux
# ============================================================

YAP_VERSION="1.0.0"
YAP_DIR="/opt/yap"
MODEL_DIR="$YAP_DIR/models"
CONFIG_DIR="/etc/yap"
WHITELIST_DIR="$CONFIG_DIR/whitelist"
BIN_DIR="/usr/local/bin"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_URL="https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
LLAMACPP_REPO="https://github.com/ggerganov/llama.cpp.git"
LLAMACPP_BRANCH="b5097"

echo "=============================================="
echo "  YAP v$YAP_VERSION — ChincoLinux AI Agent"
echo "=============================================="
echo ""

# --- 1. Dependencias del sistema ---
echo "[1/6] Instalando dependencias del sistema..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
  build-essential cmake curl wget git pkg-config \
  python3 python3-pip \
  libnotify-bin notify-osd \
  libcurl4-openssl-dev \
  --no-install-recommends

# --- 2. Compilar llama.cpp ---
echo "[2/6] Compilando llama.cpp..."
LLAMA_BUILD=$(mktemp -d)
cd "$LLAMA_BUILD"
git clone --depth 1 --branch "$LLAMACPP_BRANCH" "$LLAMACPP_REPO" 2>/dev/null
cd llama.cpp
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DLLAMA_CUDA=OFF -DLLAMA_BLAS=OFF -DLLAMA_METAL=OFF -DLLAMA_CURL=OFF -DLLAMA_STATIC=ON
cmake --build . --config Release -j"$(nproc)" 2>&1
sudo cp bin/llama-cli /usr/local/bin/llama-cli
rm -rf "$LLAMA_BUILD"

# --- 3. Descargar modelo ---
echo "[3/6] Descargando modelo Llama 3.2 3B Instruct (GGUF Q4_K_M)..."
sudo mkdir -p "$MODEL_DIR"
MODEL_FILE="$MODEL_DIR/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
if [ ! -f "$MODEL_FILE" ]; then
  sudo wget --progress=bar:force -O "$MODEL_FILE" "$MODEL_URL"
else
  echo "  Modelo ya existe, saltando descarga."
fi

# --- 4. Instalar agente Yap y whitelist ---
echo "[4/6] Instalando agente Yap..."
sudo mkdir -p "$WHITELIST_DIR"
sudo cp "$SCRIPT_DIR/whitelist/apps.conf" "$WHITELIST_DIR/"
sudo cp "$SCRIPT_DIR/whitelist/web.conf" "$WHITELIST_DIR/"
sudo cp "$SCRIPT_DIR/yap.py" "$YAP_DIR/yap.py"
sudo chmod +x "$YAP_DIR/yap.py"
sudo ln -sf "$YAP_DIR/yap.py" "$BIN_DIR/yap"

# --- 5. Instalar aplicaciones recomendadas ---
echo "[5/6] Instalando aplicaciones sugeridas..."
sudo apt-get install -y -qq \
  libreoffice evince firefox-esr micro htop \
  --no-install-recommends 2>/dev/null || true

# --- 6. Verificación ---
echo "[6/6] Verificando instalación..."
echo ""
echo "=============================================="
echo "  YAP v$YAP_VERSION — Instalación completa"
echo "=============================================="
echo ""
echo "  Componente        Estado"
echo "  ----------------- -------"
echo "  llama-cli         $(command -v llama-cli && echo '[OK]' || echo '[FAIL]')"
echo "  Modelo            $(ls -lh $MODEL_FILE 2>/dev/null | awk '{print $5}')"
echo "  yap               $(command -v yap && echo '[OK]' || echo '[FAIL]')"
echo "  notify-send       $(command -v notify-send && echo '[OK]' || echo '[FAIL]')"
echo ""
echo "  Whitelist apps:  $WHITELIST_DIR/apps.conf"
echo "  Whitelist web:   $WHITELIST_DIR/web.conf"
echo ""
echo "  Uso:"
echo "    yap Abre LibreOffice"
echo "    yap Busca https://es.wikipedia.org/wiki/Linux"
echo "    yap ¿Qué es Debian?"
echo ""
