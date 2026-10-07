#!/usr/bin/env python3
"""
scripts/download_windows.py — Descarga de modelo GGUF y llama-cli para Windows
"""

import sys
import os
import urllib.request
import zipfile
import shutil
import time

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BIN_DIR = os.path.join(BASE_DIR, "bin")
MODELS_DIR = os.path.join(BASE_DIR, "models")

LLAMA_ZIP_URL = "https://github.com/ggerganov/llama.cpp/releases/download/b5097/llama-b5097-bin-win-avx2-x64.zip"
MODEL_3B_URL = "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf?download=true"
MODEL_3B_FILENAME = "Llama-3.2-3B-Instruct-Q4_K_M.gguf"


def download_with_progress(url: str, dest_path: str, desc: str = "Descargando"):
    print(f"\n[+] {desc}...")
    print(f"    URL: {url}")
    print(f"    Destino: {dest_path}")

    start_time = time.time()
    last_print = 0

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Yap-Windows-Downloader/1.0"}
    )

    with urllib.request.urlopen(req) as response, open(dest_path, "wb") as out_file:
        total_size = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024  # 1MB chunks

        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            out_file.write(chunk)
            downloaded += len(chunk)

            now = time.time()
            if now - last_print > 1.0 or downloaded == total_size:
                last_print = now
                elapsed = max(0.1, now - start_time)
                speed_mb = (downloaded / (1024 * 1024)) / elapsed
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    mb_down = downloaded / (1024 * 1024)
                    mb_tot = total_size / (1024 * 1024)
                    sys.stdout.write(
                        f"\r    [{percent:5.1f}%] {mb_down:.1f} MB / {mb_tot:.1f} MB  ({speed_mb:.2f} MB/s)    "
                    )
                else:
                    mb_down = downloaded / (1024 * 1024)
                    sys.stdout.write(f"\r    {mb_down:.1f} MB descargados ({speed_mb:.2f} MB/s)    ")
                sys.stdout.flush()

    print("\n    ✓ Descarga completada.")


def setup_llama_binaries():
    os.makedirs(BIN_DIR, exist_ok=True)
    llama_exe = os.path.join(BIN_DIR, "llama-cli.exe")
    if os.path.isfile(llama_exe):
        print(f"\n[✓] llama-cli.exe ya existe en: {llama_exe}")
        return

    zip_path = os.path.join(BIN_DIR, "llama-win.zip")
    download_with_progress(LLAMA_ZIP_URL, zip_path, "Descargando llama-cli precompilado para Windows")

    print("[+] Extrayendo binarios...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(BIN_DIR)
    os.remove(zip_path)
    print(f"[✓] Binarios extraídos exitosamente en: {BIN_DIR}")


def setup_model():
    os.makedirs(MODELS_DIR, exist_ok=True)
    target_path = os.path.join(MODELS_DIR, MODEL_3B_FILENAME)
    if os.path.isfile(target_path) and os.path.getsize(target_path) > 1_500_000_000:
        print(f"\n[✓] El modelo {MODEL_3B_FILENAME} ya existe ({os.path.getsize(target_path) / (1024*1024):.1f} MB).")
        return

    part_path = target_path + ".part"
    download_with_progress(MODEL_3B_URL, part_path, f"Descargando {MODEL_3B_FILENAME} desde Hugging Face")

    # Verificar magic GGUF
    with open(part_path, "rb") as f:
        magic = f.read(4)
    if magic != b"GGUF":
        raise ValueError(f"El archivo descargado no es un GGUF válido (magic: {magic!r})")

    if os.path.exists(target_path):
        os.remove(target_path)
    os.rename(part_path, target_path)
    print(f"\n[✓] Modelo guardado y verificado en: {target_path}")


def main():
    print("=" * 65)
    print("  Yap — Instalador de Componentes Locales para Windows")
    print("=" * 65)
    setup_llama_binaries()
    setup_model()
    print("\n" + "=" * 65)
    print("  ¡Instalación completada exitosamente!")
    print("=" * 65)
    print("\nPara ejecutar Yap en Windows con tu nuevo modelo:")
    print(f'  $env:Path += ";{BIN_DIR}"')
    print(f'  $env:YAP_MODEL_PATH = "{os.path.join(MODELS_DIR, MODEL_3B_FILENAME)}"')
    print('  python yap.py "que es un algoritmo?"\n')


if __name__ == "__main__":
    main()
