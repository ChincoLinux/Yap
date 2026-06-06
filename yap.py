#!/usr/bin/env python3
"""Yap — Agente IA local para ChincoLinux."""

import subprocess
import sys
import os
import shutil
import urllib.request
import urllib.parse
import json
import tempfile

CONFIG_DIR = "/etc/yap"
WHITELIST_APPS = f"{CONFIG_DIR}/whitelist/apps.conf"
WHITELIST_WEB = f"{CONFIG_DIR}/whitelist/web.conf"
MODEL_PATH = "/opt/yap/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
MAX_CTX = 4096
SYSTEM_PROMPT = "Eres Yap, un asistente educativo en español para ChincoLinux. Responde de forma clara y breve."


def load_whitelist(path):
    apps = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        apps[parts[0].lower()] = parts[1]
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
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        pass


def cmd_open_app(app_name):
    apps = load_whitelist(WHITELIST_APPS)
    key = app_name.strip().lower()
    if key in apps:
        binary = apps[key]
        path = shutil.which(binary)
        if path:
            subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                result = subprocess.run(
                    [binary, "--version"],
                    capture_output=True, text=True, timeout=5
                )
                version = result.stdout.strip() or result.stderr.strip() or "(sin versión)"
            except Exception:
                version = "(sin versión)"
            app_title = app_name.strip().title()
            notify(f"{app_title} abierta", f"Versión: {version}")
            return f"✅ {app_title} abierta.\nInformación: {version}"
        return f"❌ Binario '{binary}' no encontrado en el sistema"
    return f"❌ '{app_name}' no está en la whitelist de aplicaciones"


def cmd_webfetch(url):
    domains = load_domain_whitelist(WHITELIST_WEB)
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if any(domain.endswith(d) or domain == d for d in domains):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Yap-ChincoLinux/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")[:2000]
            return f"Contenido obtenido ({len(content)} chars):\n{content[:500]}..."
        except Exception as e:
            return f"❌ Error al obtener {url}: {e}"
    return f"❌ Dominio '{domain}' no está en la whitelist"


def cmd_query(prompt):
    full_prompt = f"{SYSTEM_PROMPT}\n\nUsuario: {prompt}\n\nYap:"
    cmd = [
        "llama-cli",
        "-m", MODEL_PATH,
        "-p", full_prompt,
        "-n", "256",
        "--temp", "0.6",
        "--ctx-size", str(MAX_CTX),
        "--no-display-prompt",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.stdout.strip() or "(sin respuesta)"
    except subprocess.TimeoutExpired:
        return "⚠️ Tiempo de espera agotado"
    except FileNotFoundError:
        return "❌ llama-cli no instalado. Ejecuta el setup de Yap."


def interpret(user_input):
    text = user_input.strip().lower()
    for prefix in ["abre ", "abrir ", "open ", "lanzar ", "iniciar "]:
        if text.startswith(prefix):
            rest = user_input[len(prefix):].strip().title()
            return "open_app", rest
    for prefix in ["busca ", "buscar ", "fetch ", "webfetch "]:
        if text.startswith(prefix):
            rest = user_input[len(prefix):].strip()
            if rest.startswith("http"):
                return "webfetch", rest.strip("\"'")
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
        print(cmd_webfetch(param))
    else:
        print("Consultando LLM...")
        print(cmd_query(param))


if __name__ == "__main__":
    main()
