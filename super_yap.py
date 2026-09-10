#!/usr/bin/env python3
"""Super Yap — Llama de más parámetros para un host de 8 GB RAM (#91).

El PC del alumno sigue en Yap local (Llama 3.2 1B/3B). Super Yap corre en
el servidor del aula (o en el mismo PC si tiene 8 GB) y habla el contrato
JSON de Yap para no perder el historial de conversación.

Llama 3.2 Instruct en texto solo llega a 3B. Super Yap usa Llama 3.1 8B
Instruct Q4_K_M (misma plantilla de chat: begin_of_text / start_header_id),
que cabe en ~7 GB con contexto 4096 y KV cache Q8_0.

Uso:
  python3 super_yap.py --info
  python3 super_yap.py --serve          # escucha 127.0.0.1:8742
  python3 super_yap.py                  # REPL local con el modelo grande
  python3 super_yap.py "explica while"
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap

BOS = "<|begin_of_text|>"
HEADER = "<|start_header_id|>"
FOOTER = "<|end_header_id|>"
EOT = "<|eot_id|>"

# 8B Q4_K_M ≈ 4.9 GB pesos + ~1 GB KV (4096, Q8) + overhead ≈ 6.5–7.5 GB
SUPER_MODEL_8B = "Llama-3.1-8B-Instruct-Q4_K_M.gguf"
SUPER_MODEL_3B = "Llama-3.2-3B-Instruct-Q4_K_M.gguf"
DEFAULT_MODEL_DIR = "/opt/yap/models"
DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 8742
SUPER_NUBE_HOST = "137.184.146.113"
MAX_CTX = 4096
MAX_HISTORY = 12
N_PREDICT = 512
LLAMA_TIMEOUT = 180
BODY_MAX = 65536
RAM_MIN_MB = 7000

SYSTEM_PROMPT = (
    "Eres Super Yap, el tutor educativo de ChincoLinux en espanol. "
    "Tienes mas capacidad que el Yap local (1B/3B) y debes conservar "
    "el hilo de la conversacion que te envia el alumno. "
    "Responde claro, breve y preciso. Si no sabes, dilo. "
    "No pidas datos personales ni rutas de casa. "
    "No abras aplicaciones, no ejecutes comandos, no instales software. "
    "La nube SUGIERE; el kernel local DECIDE."
)

# session_id -> [(user, assistant), ...]
SESIONES: dict[str, list[tuple[str, str]]] = {}


def _entero_env(nombre, default):
    raw = os.environ.get(nombre, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def directorio_modelos():
    return os.environ.get("YAP_SUPER_MODEL_DIR", DEFAULT_MODEL_DIR)


def modelo_candidato_paths():
    """Rutas en orden: 8B (8 GB) y 3B como respaldo Llama 3.2."""
    explicit = os.environ.get("YAP_SUPER_MODEL_PATH", "").strip()
    if explicit:
        return [explicit]
    d = directorio_modelos()
    return [
        os.path.join(d, SUPER_MODEL_8B),
        os.path.join(d, SUPER_MODEL_3B),
        os.environ.get("YAP_MODEL_PATH", os.path.join(d, SUPER_MODEL_3B)),
    ]


def resolver_modelo():
    """Return (path, etiqueta) of the first GGUF that exists."""
    for path in modelo_candidato_paths():
        if path and os.path.isfile(path):
            nombre = os.path.basename(path)
            if "8B" in nombre:
                etiqueta = "Llama-3.1-8B-Instruct-Q4_K_M"
            elif "3B" in nombre:
                etiqueta = "Llama-3.2-3B-Instruct"
            else:
                etiqueta = nombre
            return path, etiqueta
    return modelo_candidato_paths()[0], "Llama-3.1-8B-Instruct-Q4_K_M"


def _flag(nombre):
    return os.environ.get(nombre, "").strip().lower() in (
        "1", "true", "si", "sí", "yes", "on",
    )


def _parse_meminfo_disponible_mb(texto):
    """MemAvailable (kB) from /proc/meminfo → MB."""
    for line in (texto or "").splitlines():
        if line.startswith("MemAvailable:"):
            try:
                return int(line.split()[1]) // 1024
            except (IndexError, ValueError):
                return None
    return None


def _parse_wmic_free_mb(texto):
    """wmic OS get FreePhysicalMemory /Value → MB."""
    for line in (texto or "").splitlines():
        if line.lower().startswith("freephysicalmemory"):
            try:
                return int(line.split("=", 1)[1].strip()) // 1024
            except (IndexError, ValueError):
                return None
    return None


def _ram_windows_mb():
    """Free physical RAM on Windows. subprocess + timeout, no ctypes."""
    ps = [
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "(Get-CimInstance -ClassName Win32_OperatingSystem).FreePhysicalMemory",
    ]
    try:
        result = subprocess.run(ps, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            raw = (result.stdout or "").strip().split()
            if raw:
                return int(raw[-1]) // 1024
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError):
        pass
    try:
        result = subprocess.run(
            ["wmic", "OS", "get", "FreePhysicalMemory", "/Value"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return _parse_wmic_free_mb(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def ram_disponible_mb():
    """MB de RAM libre. Override: YAP_SUPER_RAM_MB. None si no se puede medir."""
    raw = os.environ.get("YAP_SUPER_RAM_MB", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    try:
        with open("/proc/meminfo") as f:
            mb = _parse_meminfo_disponible_mb(f.read())
        if mb is not None:
            return mb
    except OSError:
        pass
    if os.name == "nt":
        return _ram_windows_mb()
    return None


def ram_suficiente_super():
    """True si hay ≥7 GB libres para cargar el 8B, o YAP_SUPER_FORCE=1."""
    if _flag("YAP_SUPER_FORCE"):
        return True
    # llama-server ya tiene el modelo en RAM: no exigir 7 GB *libres* otra vez.
    if os.environ.get("YAP_SUPER_LLAMA_SERVER", "").strip():
        return True
    ram = ram_disponible_mb()
    if ram is None:
        return False
    return ram >= RAM_MIN_MB


def mensaje_ram_insuficiente():
    ram = ram_disponible_mb()
    if ram is None:
        return (
            f"[ERROR] RAM insuficiente para Super Yap: no se pudo medir la "
            f"memoria libre. Se necesitan ≥{RAM_MIN_MB} MB (7 GB)."
        )
    return (
        f"[ERROR] RAM insuficiente para Super Yap: {ram} MB libres, "
        f"se necesitan ≥{RAM_MIN_MB} MB (7 GB). Usa el Yap local (1B/3B)."
    )


def perfil_ram():
    """Human-readable RAM budget for the 8B Q4_K_M profile."""
    return {
        "pesos_gguf_mb": 4920,
        "kv_cache_q8_ctx4096_mb": 900,
        "runtime_mb": 400,
        "total_estimado_mb": 6220,
        "host_recomendado_mb": 8192,
        "minimo_mb": RAM_MIN_MB,
    }


def _limpiar_salida(result):
    out = (result.stdout or "").strip()
    for tok in (BOS, HEADER, FOOTER, EOT, "[end of text]"):
        out = out.replace(tok, "")
    out = out.strip()
    return out if out else ((result.stderr or "").strip() or "(sin respuesta)")


def historial_a_turnos(historial):
    """Convert [{rol, texto}, ...] into [(user, assistant), ...]."""
    turnos = []
    pendiente = None
    for item in historial or []:
        if not isinstance(item, dict):
            continue
        rol = str(item.get("rol") or item.get("role") or "").strip().lower()
        texto = item.get("texto") or item.get("content") or item.get("text") or ""
        texto = str(texto)
        if rol in ("user", "usuario", "alumno"):
            pendiente = texto
        elif rol in ("assistant", "asistente", "yap", "super") and pendiente is not None:
            turnos.append((pendiente, texto))
            pendiente = None
    return turnos


def _es_sufijo(largo, corto):
    if not corto:
        return True
    if len(corto) > len(largo):
        return False
    return largo[-len(corto):] == corto


def fusionar_historial(session_id, historial_cliente):
    """Keep Super Yap memory across hops without dropping local context.

    The client HISTORY is the source of truth for the turns it sends.
    If those turns are a suffix of the server session, the older server
    prefix is kept (Super Yap remembers more than the local MAX_HISTORY=6).
    On divergence, the local client wins (resume / new session).
    """
    cliente = historial_a_turnos(historial_cliente)
    sid = (session_id or "").strip()
    if not sid:
        return cliente[-MAX_HISTORY:]
    stored = SESIONES.get(sid, [])
    if _es_sufijo(stored, cliente):
        merged = stored
    elif _es_sufijo(cliente, stored):
        merged = cliente
    else:
        merged = cliente
    merged = merged[-MAX_HISTORY:]
    SESIONES[sid] = list(merged)
    return merged


def recordar_turno(session_id, user, assistant):
    sid = (session_id or "").strip()
    if not sid:
        return
    turnos = SESIONES.setdefault(sid, [])
    turnos.append((user, assistant))
    if len(turnos) > MAX_HISTORY:
        del turnos[0:len(turnos) - MAX_HISTORY]


def construir_prompt(prompt, turnos, context=None):
    parts = [BOS]
    parts.append(f"{HEADER}system{FOOTER}\n\n{SYSTEM_PROMPT}{EOT}")
    for user_msg, assistant_msg in turnos:
        parts.append(f"{HEADER}user{FOOTER}\n\n{user_msg}{EOT}")
        parts.append(f"{HEADER}assistant{FOOTER}\n\n{assistant_msg}{EOT}")
    if context:
        parts.append(f"{HEADER}user{FOOTER}\n\nContexto:\n{context}{EOT}")
    parts.append(f"{HEADER}user{FOOTER}\n\n{prompt}{EOT}")
    parts.append(f"{HEADER}assistant{FOOTER}\n\n")
    return "".join(parts)


def _hilos():
    return _entero_env("YAP_SUPER_THREADS", 4)


def llamar_llama_cli(full_prompt, model_path):
    bin_path = shutil.which("llama-cli")
    if not bin_path:
        return "[ERROR] llama-cli no instalado. Ejecuta el setup de Yap."
    if not os.path.isfile(model_path):
        return (
            f"[ERROR] Modelo Super Yap no encontrado: {model_path}\n"
            "Descarga Llama-3.1-8B-Instruct-Q4_K_M.gguf a /opt/yap/models/ "
            "(ver docs/SUPER-YAP.md)."
        )
    cmd = [
        bin_path,
        "-m", model_path,
        "-p", full_prompt,
        "-n", str(N_PREDICT),
        "--temp", os.environ.get("YAP_SUPER_TEMP", "0.7"),
        "--ctx-size", str(_entero_env("YAP_SUPER_CTX", MAX_CTX)),
        "--cache-type-k", "q8_0",
        "--cache-type-v", "q8_0",
        "--flash-attn",
        "--threads", str(_hilos()),
        "-no-cnv",
        "--no-display-prompt",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=LLAMA_TIMEOUT,
        )
        return _limpiar_salida(result)
    except subprocess.TimeoutExpired:
        return f"[WARN] Tiempo de espera agotado ({LLAMA_TIMEOUT}s)"
    except FileNotFoundError:
        return "[ERROR] llama-cli no instalado. Ejecuta el setup de Yap."


def llamar_llama_server(full_prompt, endpoint):
    """POST /completion on a running llama-server (model stays loaded)."""
    import urllib.error
    import urllib.request

    body = json.dumps({
        "prompt": full_prompt,
        "n_predict": N_PREDICT,
        "temperature": float(os.environ.get("YAP_SUPER_TEMP", "0.7")),
        "stop": [EOT, "<|eot_id|>"],
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=LLAMA_TIMEOUT) as resp:
            raw = resp.read(BODY_MAX)
        data = json.loads(raw.decode("utf-8", errors="replace"))
        if isinstance(data, dict):
            texto = data.get("content") or data.get("response") or ""
            if texto:
                return str(texto).strip()
        return "(sin respuesta)"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as err:
        return f"[ERROR] llama-server: {err}"


def generar(prompt, turnos, context=None):
    if not ram_suficiente_super():
        return mensaje_ram_insuficiente()
    full_prompt = construir_prompt(prompt, turnos, context=context)
    server = os.environ.get("YAP_SUPER_LLAMA_SERVER", "").strip()
    if server:
        return llamar_llama_server(full_prompt, server)
    path, _ = resolver_modelo()
    return llamar_llama_cli(full_prompt, path)


def responder_consulta(payload):
    """Apply the Yap contract and return {texto, modelo, session_id, turnos}."""
    if not isinstance(payload, dict):
        return {"texto": "", "error": "JSON invalido", "modelo": ""}
    prompt = (payload.get("prompt") or payload.get("message") or "").strip()
    if not prompt:
        return {"texto": "", "error": "Falta prompt", "modelo": ""}
    context = payload.get("context") or payload.get("contexto")
    session_id = str(payload.get("session_id") or payload.get("sesion") or "")
    turnos = fusionar_historial(session_id, payload.get("historial"))
    texto = generar(prompt, turnos, context=context)
    if texto and not texto.startswith("[ERROR]") and not texto.startswith("[WARN]"):
        recordar_turno(session_id, prompt, texto)
    _, etiqueta = resolver_modelo()
    return {
        "texto": texto,
        "modelo": etiqueta,
        "session_id": session_id,
        "turnos": len(SESIONES.get(session_id, turnos)),
    }


def cmd_info():
    path, etiqueta = resolver_modelo()
    existe = os.path.isfile(path)
    ram = ram_disponible_mb()
    perfil = perfil_ram()
    ram_ok = ram_suficiente_super()
    lines = [
        "Super Yap — modelo grande para host de 8 GB (#91)",
        f"  Modelo:     {etiqueta}",
        f"  Ruta:       {path}",
        f"  Presente:   {'si' if existe else 'no'}",
        f"  Contexto:   {_entero_env('YAP_SUPER_CTX', MAX_CTX)} tokens",
        f"  Hilos:      {_hilos()}",
        f"  Historial:  {MAX_HISTORY} turnos (servidor)",
        f"  Endpoint:   http://{DEFAULT_BIND}:{_entero_env('YAP_SUPER_PORT', DEFAULT_PORT)}/v1/query",
        f"  RAM est.:   {perfil['total_estimado_mb']} MB / {perfil['host_recomendado_mb']} MB",
    ]
    if ram is None:
        lines.append("  RAM libre:  no se pudo medir")
    else:
        lines.append(f"  RAM libre:  {ram} MB ({ram / 1024:.1f} GB)")
    if ram_ok:
        lines.append(f"  Umbral 7 GB: si — Super Yap se puede usar (≥{RAM_MIN_MB} MB)")
    else:
        lines.append(
            f"  Umbral 7 GB: no — Super Yap bloqueado (se necesitan ≥{RAM_MIN_MB} MB libres)"
        )
    lines.append(
        "  Nota: Llama 3.2 texto maximo es 3B; el salto de parametros "
        "que cabe en 8 GB es Llama 3.1 8B Instruct (misma plantilla)."
    )
    return "\n".join(lines)


class SuperYapHandler:
    """HTTP handler extracted so tests do not need to bind a port."""

    def manejar(self, method, path, raw_body):
        if method == "GET" and path in ("/", "/health", "/v1/health"):
            path_modelo, etiqueta = resolver_modelo()
            ram = ram_disponible_mb()
            ram_ok = ram_suficiente_super()
            return 200, {
                "ok": ram_ok,
                "modelo": etiqueta,
                "modelo_presente": os.path.isfile(path_modelo),
                "sesiones": len(SESIONES),
                "ctx": _entero_env("YAP_SUPER_CTX", MAX_CTX),
                "ram_mb": ram,
                "ram_min_mb": RAM_MIN_MB,
                "ram_ok": ram_ok,
            }
        if method != "POST" or path not in ("/v1/query", "/query", "/completion"):
            return 404, {"texto": "", "error": "Ruta no encontrada"}
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 400, {"texto": "", "error": "JSON invalido"}
        data = responder_consulta(payload)
        if data.get("error") and not data.get("texto"):
            code = 400 if data["error"] in ("JSON invalido", "Falta prompt") else 502
            return code, data
        return 200, data


def _hacer_handler():
    from http.server import BaseHTTPRequestHandler

    nucleo = SuperYapHandler()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("[super-yap] " + (fmt % args) + "\n")

        def _send(self, code, obj):
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            code, obj = nucleo.manejar("GET", self.path.split("?", 1)[0], b"")
            self._send(code, obj)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or "0")
            if n > BODY_MAX:
                self._send(413, {"texto": "", "error": "Cuerpo demasiado grande"})
                return
            raw = self.rfile.read(n) if n else b"{}"
            code, obj = nucleo.manejar("POST", self.path.split("?", 1)[0], raw)
            self._send(code, obj)

    return Handler


def servir(bind=None, port=None):
    bind = bind or os.environ.get("YAP_SUPER_BIND", DEFAULT_BIND).strip() or DEFAULT_BIND
    port = port or _entero_env("YAP_SUPER_PORT", DEFAULT_PORT)
    if bind not in ("127.0.0.1", "localhost", "::1", SUPER_NUBE_HOST):
        # LAN del aula: RFC1918, o el host nube pin. Nunca 0.0.0.0.
        partes = bind.split(".")
        ok = False
        if len(partes) == 4:
            try:
                a, b = int(partes[0]), int(partes[1])
                ok = a == 10 or (a == 192 and b == 168) or (a == 172 and 16 <= b <= 31)
            except ValueError:
                ok = False
        if not ok:
            sys.exit(
                "YAP_SUPER_BIND solo admite 127.0.0.1, una IP privada "
                f"(10/8, 172.16/12, 192.168/16) o {SUPER_NUBE_HOST}. "
                "No se escucha en 0.0.0.0."
            )
    if not ram_suficiente_super():
        print(cmd_info())
        sys.exit(mensaje_ram_insuficiente())
    from http.server import ThreadingHTTPServer
    print(cmd_info())
    print()
    print(f"Escuchando http://{bind}:{port}/v1/query")
    print("Deja este proceso abierto. En el Yap local: YAP_SUPER_ENABLED=1")
    Handler = _hacer_handler()
    ThreadingHTTPServer((bind, port), Handler).serve_forever()


def repl():
    if not ram_suficiente_super():
        print(cmd_info())
        print(mensaje_ram_insuficiente())
        return
    print(cmd_info())
    print()
    print("Super Yap REPL. Escribe 'salir' para terminar.")
    turnos = []
    while True:
        try:
            user_input = input("Super Yap > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nChao")
            return
        if not user_input:
            continue
        if user_input.lower() in ("salir", "exit", "quit"):
            print("Chao")
            return
        if user_input.lower() in ("info", "--info"):
            print(cmd_info())
            continue
        texto = generar(user_input, turnos)
        print(texto)
        if texto and not texto.startswith("[ERROR]") and not texto.startswith("[WARN]"):
            turnos.append((user_input, texto))
            if len(turnos) > MAX_HISTORY:
                turnos.pop(0)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        repl()
        return
    if args[0] in ("--serve", "serve", "--servir"):
        servir()
        return
    if args[0] in ("--info", "info", "--estado"):
        print(cmd_info())
        return
    if args[0] in ("-h", "--help", "ayuda"):
        print(textwrap.dedent("""\
            Super Yap (#91) — Llama de mas parametros para 8 GB RAM

              python3 super_yap.py              REPL con el modelo grande
              python3 super_yap.py --serve      HTTP 127.0.0.1:8742
              python3 super_yap.py --info       Modelo, RAM y endpoint
              python3 super_yap.py "pregunta"   Una consulta y sale

            El Yap local envia el historial en cada POST para no perder
            el contexto. Ver docs/SUPER-YAP.md.
        """))
        return
    if not ram_suficiente_super():
        print(cmd_info())
        print(mensaje_ram_insuficiente())
        return
    prompt = " ".join(args)
    print(generar(prompt, []))


if __name__ == "__main__":
    main()
