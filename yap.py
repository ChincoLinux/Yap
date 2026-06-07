#!/usr/bin/env python3
"""Yap — Agente IA local para ChincoLinux."""

import subprocess
import sys
import os
import shutil
import urllib.request
import urllib.parse

CONFIG_DIR = "/etc/yap"
WHITELIST_APPS = f"{CONFIG_DIR}/whitelist/apps.conf"
WHITELIST_WEB = f"{CONFIG_DIR}/whitelist/web.conf"
MODEL_PATH = "/opt/yap/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
MAX_CTX = 4096

BOS = "<|begin_of_text|>"
HEADER = "<|start_header_id|>"
FOOTER = "<|end_header_id|>"
EOT = "<|eot_id|>"

SYSTEM_PROMPT = (
    "Eres Yap, un asistente educativo en espanol para ChincoLinux. "
    "Responde de forma clara, breve y precisa. Si no sabes algo, dilo."
)


def load_whitelist(path):
    apps = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        apps[parts[0].lower()] = parts[1].split(",")
    return apps


def load_domain_whitelist(path):
    domains = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    domains.append(line.lower())
    return domains


def notify(title, msg, urgency="normal"):
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, title, msg],
            check=False, timeout=3,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


def cmd_open_app(app_name):
    apps = load_whitelist(WHITELIST_APPS)
    key = app_name.strip().lower()
    if key not in apps:
        return f"[ERROR] '{app_name.strip().title()}' no esta en la whitelist de aplicaciones"

    candidates = apps[key]
    bin_path = None
    chosen = None
    for candidate in candidates:
        candidate = candidate.strip()
        path = shutil.which(candidate)
        if path:
            bin_path = path
            chosen = candidate
            break

    if not bin_path:
        candidates_str = ", ".join(candidates)
        return f"[ERROR] Ningun binario encontrado: {candidates_str}"

    subprocess.Popen([bin_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        result = subprocess.run(
            [chosen, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        version = result.stdout.strip() or result.stderr.strip() or "(sin version)"
    except Exception:
        version = "(sin version)"

    app_title = app_name.strip().title()
    notify(f"{app_title} abierta", f"Version: {version}")
    return f"[OK] {app_title} abierta.\nInformacion: {version}"


def cmd_webfetch(url, feed_to_llm=False):
    domains = load_domain_whitelist(WHITELIST_WEB)
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]

    if not (domain in domains or any(domain == d or domain.endswith("." + d) for d in domains)):
        return f"[ERROR] Dominio '{domain}' no esta en la whitelist"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Yap-ChincoLinux/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"[ERROR] Error al obtener {url}: {e}"

    # Strip HTML tags (basic)
    import re
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    text = text[:3000]

    if feed_to_llm:
        return text, True

    return f"Contenido obtenido ({len(text)} chars):\n{text[:1000]}..."


def cmd_query(prompt, context=None):
    parts = [BOS]
    parts.append(f"{HEADER}system{FOOTER}\n\n{SYSTEM_PROMPT}{EOT}")
    if context:
        parts.append(f"{HEADER}user{FOOTER}\n\nContexto:\n{context}{EOT}")
    parts.append(f"{HEADER}user{FOOTER}\n\n{prompt}{EOT}")
    parts.append(f"{HEADER}assistant{FOOTER}\n\n")

    full_prompt = "".join(parts)

    cmd = [
        "llama-cli",
        "-m", MODEL_PATH,
        "-p", full_prompt,
        "-n", "384",
        "--temp", "0.7",
        "--ctx-size", str(MAX_CTX),
        "-no-cnv",
        "--no-display-prompt",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        out = result.stdout.strip()
        # Strip special tokens that might leak into output
        for tok in [BOS, HEADER, FOOTER, EOT, "[end of text]"]:
            out = out.replace(tok, "")
        out = out.strip()
        if not out:
            out = result.stderr.strip() or "(sin respuesta)"
        return out
    except subprocess.TimeoutExpired:
        return "[WARN] Tiempo de espera agotado (120s)"
    except FileNotFoundError:
        return "[ERROR] llama-cli no instalado. Ejecuta el setup de Yap."


def interpret(user_input):
    text = user_input.strip().lower()

    for prefix in ["abre ", "abrir ", "open ", "lanzar ", "iniciar "]:
        if text.startswith(prefix):
            rest = user_input[len(prefix):].strip()
            return "open_app", rest

    for prefix in ["busca ", "buscar ", "fetch ", "webfetch "]:
        if text.startswith(prefix):
            rest = user_input[len(prefix):].strip().strip("\"'")
            if rest.startswith("http"):
                return "webfetch", rest

    return "query", user_input


def main():
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        try:
            user_input = input("Yap > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if not user_input:
            return

    action, param = interpret(user_input)

    if action == "open_app":
        print(cmd_open_app(param))

    elif action == "webfetch":
        print("Obteniendo contenido web...")
        content = cmd_webfetch(param, feed_to_llm=True)
        if isinstance(content, tuple):
            text, _ = content
            print(f"Contenido obtenido ({len(text)} chars). Resumiendo con LLM...")
            response = cmd_query(
                f"Resume el siguiente contenido sobre '{param}':",
                context=text,
            )
            print(response)
        else:
            print(content)

    else:
        print("Consultando LLM...")
        print(cmd_query(user_input))


if __name__ == "__main__":
    main()
