#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Yap — Generador de paquetes .deb (issue #31)
# ============================================================
# Uso:
#   ./build-deb.sh                  # yap + paquetes de modelo (meta)
#   ./build-deb.sh --stub-llama     # llama-cli de prueba (CI)
#   ./build-deb.sh --skip-llama     # usa llama-cli del PATH
#   ./build-deb.sh --llama-cli PATH
#   ./build-deb.sh --no-models      # solo yap_*.deb
#   ./build-deb.sh --embed-models 1b|3b|all
#   ./build-deb.sh --outdir dist
#
# Requiere Linux con dpkg-deb. Compilar llama.cpp pide cmake/g++.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGING_DIR="$SCRIPT_DIR/packaging"
VERSION="$(tr -d '[:space:]' < "$SCRIPT_DIR/VERSION" 2>/dev/null || true)"
VERSION="${VERSION:-1.0.0}"

LLAMACPP_REPO="https://github.com/ggerganov/llama.cpp.git"
LLAMACPP_BRANCH="b5097"

OUTDIR="$SCRIPT_DIR/dist"
STUB_LLAMA=false
SKIP_LLAMA=false
LLAMA_CLI_SRC=""
BUILD_MODELS=true
EMBED_MODELS=""   # vacio | 1b | 3b | all

usage() {
  cat <<'EOF'
Uso: ./build-deb.sh [opciones]

  --outdir DIR            Directorio de salida (default: ./dist)
  --stub-llama            Binario llama-cli de prueba (no compila)
  --skip-llama            Usar llama-cli existente en PATH
  --llama-cli PATH        Copiar este binario al paquete
  --no-models             No generar yap-models-*.deb
  --embed-models 1b|3b|all
                          Descargar GGUF y embeberlo en el .deb (offline)
  -h, --help              Esta ayuda

Paquetes generados:
  yap_<ver>_amd64.deb           agente + llama-cli + configs
  yap-models-1b_<ver>_all.deb   modelo 1B (~0.81 GB)
  yap-models-3b_<ver>_all.deb   modelo 3B (~1.9 GB)
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --outdir) OUTDIR="$2"; shift 2 ;;
    --stub-llama) STUB_LLAMA=true; shift ;;
    --skip-llama) SKIP_LLAMA=true; shift ;;
    --llama-cli) LLAMA_CLI_SRC="$2"; shift 2 ;;
    --no-models) BUILD_MODELS=false; shift ;;
    --embed-models)
      EMBED_MODELS="$2"
      case "$EMBED_MODELS" in
        1b|3b|all) ;;
        *) echo "ERROR: --embed-models debe ser 1b, 3b o all" >&2; exit 2 ;;
      esac
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: opcion desconocida: $1" >&2; usage; exit 2 ;;
  esac
done

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "ERROR: dpkg-deb no esta instalado. Este script se ejecuta en Debian/Ubuntu." >&2
  exit 1
fi

mkdir -p "$OUTDIR"
OUTDIR="$(cd "$OUTDIR" && pwd)"
WORKDIR="$(mktemp -d)"
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT

echo "================================================================"
echo "  YAP v$VERSION — build de paquetes .deb"
echo "================================================================"
echo "  Salida: $OUTDIR"
echo ""

# --- helpers --------------------------------------------------------

subst_control() {
  local src="$1"
  local dest="$2"
  local size_kb="$3"
  sed -e "s/@VERSION@/${VERSION}/g" \
      -e "s/@INSTALLED_SIZE@/${size_kb}/g" \
      "$src" > "$dest"
}

installed_size_kb() {
  local root="$1"
  du -sk "$root" | awk '{print $1}'
}

install_file() {
  local mode="$1" src="$2" dest="$3"
  mkdir -p "$(dirname "$dest")"
  cp "$src" "$dest"
  chmod "$mode" "$dest"
}

ensure_llama_cli() {
  local dest="$1"
  if [ -n "$LLAMA_CLI_SRC" ]; then
    if [ ! -f "$LLAMA_CLI_SRC" ]; then
      echo "ERROR: --llama-cli no existe: $LLAMA_CLI_SRC" >&2
      exit 1
    fi
    cp "$LLAMA_CLI_SRC" "$dest"
    chmod 0755 "$dest"
    echo "  llama-cli copiado desde $LLAMA_CLI_SRC"
    return
  fi

  if $STUB_LLAMA; then
    cat > "$dest" <<'STUB'
#!/bin/sh
echo "llama-cli stub (paquete de prueba, no es el runtime real)"
exit 0
STUB
    chmod 0755 "$dest"
    echo "  llama-cli STUB generado (solo para tests/CI)"
    return
  fi

  if $SKIP_LLAMA; then
    local found
    found="$(command -v llama-cli || true)"
    if [ -z "$found" ]; then
      echo "ERROR: --skip-llama pero llama-cli no esta en PATH" >&2
      exit 1
    fi
    cp "$found" "$dest"
    chmod 0755 "$dest"
    echo "  llama-cli copiado desde $found"
    return
  fi

  echo "  Compilando llama.cpp (estatico, CPU-only, tag $LLAMACPP_BRANCH)..."
  if ! command -v cmake >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
    echo "ERROR: se necesita git y cmake para compilar llama.cpp" >&2
    echo "       Use --stub-llama, --skip-llama o --llama-cli PATH" >&2
    exit 1
  fi

  local build
  build="$(mktemp -d)"
  git clone --depth 1 --branch "$LLAMACPP_BRANCH" "$LLAMACPP_REPO" "$build/llama.cpp"
  cmake -S "$build/llama.cpp" -B "$build/build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF \
    -DLLAMA_CUDA=OFF \
    -DLLAMA_METAL=OFF \
    -DLLAMA_CURL=OFF
  cmake --build "$build/build" --config Release -j"$(nproc 2>/dev/null || echo 2)"

  local bin=""
  if [ -f "$build/build/bin/llama-cli" ]; then
    bin="$build/build/bin/llama-cli"
  elif [ -f "$build/build/llama-cli" ]; then
    bin="$build/build/llama-cli"
  fi
  if [ -z "$bin" ]; then
    echo "ERROR: cmake no produjo llama-cli" >&2
    rm -rf "$build"
    exit 1
  fi
  cp "$bin" "$dest"
  chmod 0755 "$dest"
  rm -rf "$build"
  echo "  llama-cli compilado (enlace estatico)"
}

download_gguf() {
  local url="$1"
  local dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [ -s "$dest" ]; then
    echo "  GGUF ya existe: $dest"
    return
  fi
  echo "  Descargando $(basename "$dest")..."
  if command -v wget >/dev/null 2>&1; then
    wget --progress=bar:force -O "$dest.part" "$url"
  elif command -v curl >/dev/null 2>&1; then
    curl -L --fail -o "$dest.part" "$url"
  else
    echo "ERROR: se necesita wget o curl para --embed-models" >&2
    exit 1
  fi
  mv "$dest.part" "$dest"
}

build_deb_from_staging() {
  local staging="$1"
  local outfile="$2"
  # Forzar root:root para que el .deb no herede UID del builder
  dpkg-deb --root-owner-group --build "$staging" "$outfile"
  echo "  ✓ $(basename "$outfile")  ($(du -h "$outfile" | awk '{print $1}'))"
}

# --- paquete yap ----------------------------------------------------

stage_yap() {
  local staging="$WORKDIR/yap"
  rm -rf "$staging"
  mkdir -p "$staging"

  # Payload
  mkdir -p \
    "$staging/opt/yap/models" \
    "$staging/opt/yap/agent" \
    "$staging/usr/local/bin" \
    "$staging/usr/share/yap/whitelist" \
    "$staging/usr/share/yap/pseint" \
    "$staging/usr/share/yap/cursos" \
    "$staging/usr/share/yap/apparmor" \
    "$staging/usr/share/doc/yap"

  install_file 0755 "$SCRIPT_DIR/yap.py" "$staging/opt/yap/yap.py"
  ln -sf /opt/yap/yap.py "$staging/usr/local/bin/yap"

  ensure_llama_cli "$staging/usr/local/bin/llama-cli"

  install_file 0644 "$SCRIPT_DIR/whitelist/apps.conf" \
    "$staging/usr/share/yap/whitelist/apps.conf"
  install_file 0644 "$SCRIPT_DIR/whitelist/web.conf" \
    "$staging/usr/share/yap/whitelist/web.conf"
  install_file 0644 "$SCRIPT_DIR/whitelist/pseint/ejercicios.conf" \
    "$staging/usr/share/yap/pseint/ejercicios.conf"
  if [ -f "$SCRIPT_DIR/whitelist/pseint/guia_ejercicios.pdf" ]; then
    install_file 0644 "$SCRIPT_DIR/whitelist/pseint/guia_ejercicios.pdf" \
      "$staging/usr/share/yap/pseint/guia_ejercicios.pdf"
  fi

  if ls "$SCRIPT_DIR/cursos/"*.json >/dev/null 2>&1; then
    cp "$SCRIPT_DIR/cursos/"*.json "$staging/usr/share/yap/cursos/"
    chmod 0644 "$staging/usr/share/yap/cursos/"*.json
  fi

  install_file 0644 "$SCRIPT_DIR/apparmor/usr.local.bin.yap" \
    "$staging/usr/share/yap/apparmor/usr.local.bin.yap"

  if [ -f "$SCRIPT_DIR/yap-agent.md" ]; then
    install_file 0644 "$SCRIPT_DIR/yap-agent.md" "$staging/opt/yap/agent/yap.md"
    install_file 0644 "$SCRIPT_DIR/yap-agent.md" "$staging/usr/share/yap/agent/yap.md"
  fi

  for doc in README.md USAGE.md CHANGELOG.md LICENSE; do
    if [ -f "$SCRIPT_DIR/$doc" ]; then
      install_file 0644 "$SCRIPT_DIR/$doc" "$staging/usr/share/doc/yap/$doc"
    fi
  done
  install_file 0644 "$PACKAGING_DIR/yap/copyright" \
    "$staging/usr/share/doc/yap/copyright"

  # DEBIAN
  mkdir -p "$staging/DEBIAN"
  local size
  size="$(installed_size_kb "$staging")"
  subst_control "$PACKAGING_DIR/yap/DEBIAN/control" "$staging/DEBIAN/control" "$size"
  install_file 0755 "$PACKAGING_DIR/yap/DEBIAN/postinst" "$staging/DEBIAN/postinst"
  install_file 0755 "$PACKAGING_DIR/yap/DEBIAN/prerm" "$staging/DEBIAN/prerm"
  install_file 0755 "$PACKAGING_DIR/yap/DEBIAN/postrm" "$staging/DEBIAN/postrm"

  local out="$OUTDIR/yap_${VERSION}_amd64.deb"
  build_deb_from_staging "$staging" "$out"
}

# --- paquetes de modelo --------------------------------------------

stage_model() {
  local variant="$1"   # 1b | 3b
  local pkg="yap-models-${variant}"
  local arch_file="all"
  local filename size_hint url
  case "$variant" in
    1b)
      filename="Llama-3.2-1B-Instruct-Q4_K_M.gguf"
      size_hint="0.81 GB"
      url="https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/${filename}"
      ;;
    3b)
      filename="Llama-3.2-3B-Instruct-Q4_K_M.gguf"
      size_hint="1.9 GB"
      url="https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/${filename}"
      ;;
    *) echo "ERROR: variante de modelo desconocida: $variant" >&2; exit 1 ;;
  esac

  local staging="$WORKDIR/$pkg"
  rm -rf "$staging"
  mkdir -p "$staging/opt/yap/models" "$staging/DEBIAN" "$staging/usr/share/doc/$pkg"

  local should_embed=false
  case "$EMBED_MODELS" in
    all) should_embed=true ;;
    "$variant") should_embed=true ;;
  esac
  if $should_embed; then
    echo "  Embebiendo modelo $variant ($size_hint)..."
    download_gguf "$url" "$staging/opt/yap/models/$filename"
    chmod 0644 "$staging/opt/yap/models/$filename"
  else
    # Placeholder para que dpkg cree el directorio; postinst descarga
    : > "$staging/opt/yap/models/.keep"
  fi

  if [ -f "$SCRIPT_DIR/LICENSE" ]; then
    install_file 0644 "$SCRIPT_DIR/LICENSE" "$staging/usr/share/doc/$pkg/copyright"
  fi

  local size
  size="$(installed_size_kb "$staging")"
  subst_control "$PACKAGING_DIR/$pkg/DEBIAN/control" "$staging/DEBIAN/control" "$size"
  install_file 0755 "$PACKAGING_DIR/$pkg/DEBIAN/postinst" "$staging/DEBIAN/postinst"
  install_file 0755 "$PACKAGING_DIR/$pkg/DEBIAN/postrm" "$staging/DEBIAN/postrm"

  local out="$OUTDIR/${pkg}_${VERSION}_${arch_file}.deb"
  build_deb_from_staging "$staging" "$out"
}

# --- main -----------------------------------------------------------

echo "  PASO 1 — paquete yap"
stage_yap
echo ""

if $BUILD_MODELS; then
  echo "  PASO 2 — paquetes de modelo"
  stage_model 1b
  stage_model 3b
  echo ""
fi

echo "================================================================"
echo "  Paquetes en $OUTDIR:"
ls -lh "$OUTDIR"/*.deb 2>/dev/null || true
echo "================================================================"
echo ""
echo "  Instalacion local:"
echo "    sudo apt install ./yap_${VERSION}_amd64.deb"
echo "    sudo apt install ./yap-models-1b_${VERSION}_all.deb   # o yap-models-3b"
echo ""
