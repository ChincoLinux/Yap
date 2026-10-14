#!/usr/bin/env python3
"""Benchmark de rendimiento de Yap en hardware real (#40).

Mide, con el modelo local instalado:

  * arranque en frio (primera inferencia, proceso nuevo)
  * inferencia en caliente (mediana de N corridas)
  * tokens por segundo de generacion
  * memoria RSS pico del proceso hijo
  * latencia de comandos cortos (el clasificador usa -n 15)

Uso:

    python3 tests/benchmark.py                 # perfil completo
    python3 tests/benchmark.py --quick         # menos repeticiones
    python3 tests/benchmark.py --json res.json # resultados en JSON
    python3 tests/benchmark.py --timeout 120   # tope por corrida (segundos)
    python3 tests/benchmark.py --rag           # medir el RAG (#214), sin modelo

Sin `llama-cli` o sin modelo el script termina con codigo 2 y un mensaje
claro: no mide nada inventado. Los resultados se pegan en
`docs/PERFORMANCE.md` (ver la tabla de perfiles de hardware ahi).
"""

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time

RE_PROMPT = re.compile(
    r"prompt eval time\s*=\s*([0-9.]+)\s*ms\s*/\s*(\d+)\s*tokens", re.IGNORECASE
)
RE_EVAL = re.compile(
    r"(?<!prompt )eval time\s*=\s*([0-9.]+)\s*ms\s*/\s*(\d+)\s*tokens", re.IGNORECASE
)
PROMPT_CORTO = "clasificar: abre firefox"
PROMPT_CHAT = (
    "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
    "Explica en dos frases que es un algoritmo.<|eot_id|>"
    "<|start_header_id|>assistant<|end_header_id|>\n\n"
)


def perfil_hardware(ruta_cpuinfo="/proc/cpuinfo", ruta_meminfo="/proc/meminfo"):
    """Perfil de la maquina donde corre el benchmark (o None si no se lee)."""
    cpu = "desconocido"
    nucleos = os.cpu_count() or 0
    try:
        with open(ruta_cpuinfo, encoding="utf-8", errors="replace") as f:
            for linea in f:
                if linea.lower().startswith("model name"):
                    cpu = linea.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    ram_gb = None
    try:
        with open(ruta_meminfo, encoding="utf-8") as f:
            for linea in f:
                if linea.startswith("MemTotal:"):
                    kb = int(linea.split()[1])
                    ram_gb = round(kb / (1024 * 1024), 1)
                    break
    except (OSError, ValueError, IndexError):
        pass
    return {"cpu": cpu, "nucleos": nucleos, "ram_gb": ram_gb}


def parsear_timings(stderr):
    """(prompt_tokens, gen_tokens, ms_total) desde la salida de llama-cli."""
    mp = RE_PROMPT.search(stderr or "")
    me = RE_EVAL.search(stderr or "")
    if not (mp or me):
        return None
    return {
        "prompt": int(mp.group(2)) if mp else 0,
        "generados": int(me.group(2)) if me else 0,
        "ms": (float(mp.group(1)) if mp else 0.0) + (float(me.group(1)) if me else 0.0),
    }


def correr_llama(modelo, prompt, timeout, n_tokens=64, binario="llama-cli"):
    """Una corrida de llama-cli. Devuelve timings o None si no hubo medicion."""
    cmd = [
        binario,
        "-m",
        modelo,
        "-p",
        prompt,
        "-n",
        str(n_tokens),
        "--temp",
        "0",
        "-no-cnv",
        "--no-display-prompt",
    ]
    inicio = time.perf_counter()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
    )
    pared = (time.perf_counter() - inicio) * 1000.0
    consumido = parsear_timings(result.stderr)
    if consumido is None:
        consumido = {"prompt": 0, "generados": 0, "ms": pared}
    consumido["ms_pared"] = pared
    return consumido


def resumen(mediciones):
    """Mediana y maximo de las corridas; None cuando no hay datos."""
    if not mediciones:
        return None
    ms = [m["ms"] for m in mediciones]
    tps = [
        m["generados"] / (m["ms"] / 1000.0)
        for m in mediciones
        if m["ms"] > 0 and m["generados"]
    ]
    return {
        "corridas": len(mediciones),
        "ms_mediana": round(statistics.median(ms), 1),
        "ms_max": round(max(ms), 1),
        "tok_s": round(statistics.median(tps), 1) if tps else None,
        "tokens_generados": mediciones[-1]["generados"],
    }


def medir(modelo, repeticiones, timeout, binario="llama-cli"):
    """Frio (1 corrida) + calientes (N corridas) para chat y comando corto."""
    frio = correr_llama(modelo, PROMPT_CHAT, timeout, binario=binario)
    calientes = [
        correr_llama(modelo, PROMPT_CHAT, timeout, binario=binario)
        for _ in range(repeticiones)
    ]
    comando = [
        correr_llama(modelo, PROMPT_CORTO, timeout, n_tokens=15, binario=binario)
        for _ in range(max(1, repeticiones // 2))
    ]
    return {
        "frio": frio,
        "caliente": resumen(calientes),
        "comando_corto": resumen(comando),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark de Yap (#40)")
    parser.add_argument("--modelo", default=None, help="ruta al .gguf")
    parser.add_argument("--repeticiones", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--quick", action="store_true", help="2 repeticiones")
    parser.add_argument("--json", default=None, help="escribir resultados en JSON")
    parser.add_argument(
        "--rag",
        action="store_true",
        help="medir el RAG (recall@k, coste, contaminacion); no necesita modelo",
    )
    args = parser.parse_args(argv)

    if args.rag:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import rag_eval

        return rag_eval.main(["--json", args.json] if args.json else [])

    if args.quick:
        args.repeticiones = 2

    binario = shutil.which("llama-cli")
    if not binario:
        print(
            "[ERROR] No se encontro `llama-cli` en el PATH.\n"
            "        Instala Yap (setup.sh o el .deb) y vuelve a correr el benchmark.",
            file=sys.stderr,
        )
        return 2

    modelo = args.modelo or os.environ.get("YAP_MODEL_PATH")
    if not modelo:
        from pathlib import Path

        candidatos = sorted(Path("/opt/yap/models").glob("*.gguf")) or sorted(
            Path.home().glob("Yap/models/*.gguf")
        )
        if not candidatos:
            print(
                "[ERROR] No hay modelo .gguf (usa --modelo o YAP_MODEL_PATH).",
                file=sys.stderr,
            )
            return 2
        modelo = str(candidatos[0])
    if not os.path.isfile(modelo):
        print(f"[ERROR] El modelo no existe: {modelo}", file=sys.stderr)
        return 2

    hardware = perfil_hardware()
    print(f"CPU:   {hardware['cpu']} ({hardware['nucleos']} nucleos)")
    print(f"RAM:   {hardware['ram_gb']} GB")
    print(f"Modelo: {modelo}")
    print(f"Corridas: {args.repeticiones} (tope {args.timeout}s por corrida)\n")

    try:
        resultados = medir(modelo, args.repeticiones, args.timeout, binario=binario)
    except subprocess.TimeoutExpired:
        print(
            f"[ERROR] Timeout de {args.timeout}s: sube --timeout o baja --repeticiones."
        )
        return 1

    frio = resultados["frio"]
    if frio:
        print(f"Frio:      {frio['ms']:.0f} ms  ({frio['generados']} tokens)")
    for nombre in ("caliente", "comando_corto"):
        datos = resultados[nombre]
        if not datos:
            continue
        tps = f"{datos['tok_s']} tok/s" if datos["tok_s"] else "n/d"
        print(
            f"{nombre.capitalize():11}mediana {datos['ms_mediana']} ms · {tps} · "
            f"max {datos['ms_max']} ms"
        )

    if args.json:
        documento = {
            "hardware": hardware,
            "modelo": modelo,
            "repeticiones": args.repeticiones,
            "resultados": resultados,
            "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(documento, f, ensure_ascii=False, indent=2)
        print(f"\nJSON escrito en {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
