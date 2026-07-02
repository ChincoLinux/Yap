#!/usr/bin/env python3
"""Yap — Agente IA local para ChincoLinux."""

import subprocess
import sys
import os
import shutil
import textwrap
import json
import glob
import urllib.request
import urllib.parse
import re

CONFIG_DIR = "/etc/yap"
WHITELIST_APPS = f"{CONFIG_DIR}/whitelist/apps.conf"
WHITELIST_WEB = f"{CONFIG_DIR}/whitelist/web.conf"
PSEINT_DIR = f"{CONFIG_DIR}/pseint"
PSEINT_EXERCISES = f"{PSEINT_DIR}/ejercicios.conf"
PSEINT_GUIA_PDF = f"{PSEINT_DIR}/guia_ejercicios.pdf"
CURSOS_DIR = f"{CONFIG_DIR}/cursos"

# ── ChincoLinux TUI ──────────────────────────────────────────
# ponytail: ANSI escape codes, no Rich/Textual dependency

CHINCO_ART = [
    "  ██████╗██╗  ██╗██╗███╗   ██╗ ██████╗██████╗ ",
    " ██╔════╝██║  ██║██║████╗  ██║██╔════╝██╔══██╗",
    " ██║     ███████║██║██╔██╗ ██║██║     ██║  ██║",
    " ██║     ██╔══██║██║██║╚██╗██║██║     ██║  ██║",
    " ╚██████╗██║  ██║██║██║ ╚████║╚██████╗╚██████╔╝",
    "  ╚═════╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ",
]

def render_art(art_lines, color=""):
    """Join art lines with optional ANSI color wrapping."""
    s = "\n".join(art_lines)
    return f"{color}{s}{C['RESET']}" if color else s

C = {
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "GREEN": "\033[92m",
    "CYAN": "\033[96m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "BLUE": "\033[94m",
    "GRAY": "\033[90m",
}

def display_header(title):
    """Return a colored header string with the given title."""
    w = shutil.get_terminal_size().columns
    line = f"{C['CYAN']}{'═' * w}{C['RESET']}"
    padded = f"  {C['BOLD']}{C['GREEN']}{title}{C['RESET']}  "
    return f"\n{line}\n{padded}\n{line}\n"

def display_menu(title, options):
    """Return a numbered menu string. Returns string, does not print."""
    lines = [f"\n{C['BOLD']}{C['YELLOW']}  {title}{C['RESET']}"]
    lines.append(f"  {C['GRAY']}{'─' * 50}{C['RESET']}")
    for i, opt in enumerate(options, 1):
        lines.append(f"  {C['GREEN']}[{i}]{C['RESET']} {opt}")
    return "\n".join(lines) + "\n"

def display_box(text, color="CYAN"):
    """Return text wrapped in a colored box. Returns string."""
    w = max(3, min(shutil.get_terminal_size().columns - 2, 78))  # ponytail: min 3 avoids textwrap crash on narrow/non-TTY
    c = C.get(color.upper(), C["CYAN"])
    lines = []
    lines.append(f"{c}┌{'─' * w}┐{C['RESET']}")
    for para in text.split("\n"):
        for wrapped in textwrap.wrap(para, width=w - 2) or [""]:
            lines.append(f"{c}│{C['RESET']} {wrapped:<{w - 2}} {c}│{C['RESET']}")
    lines.append(f"{c}└{'─' * w}┘{C['RESET']}")
    return "\n".join(lines)

MODEL_PATH = "/opt/yap/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf"
MAX_CTX = 2048
MAX_HISTORY = 6

BOS = "<|begin_of_text|>"
HEADER = "<|start_header_id|>"
FOOTER = "<|end_header_id|>"
EOT = "<|eot_id|>"

SYSTEM_PROMPT = (
    "Eres Yap, un asistente educativo en espanol para ChincoLinux. "
    "Responde de forma clara, breve y precisa. Si no sabes algo, dilo."
)

HISTORY = []


def load_whitelist(path):
    apps = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        apps[parts[0].lower()] = [c.strip() for c in parts[1].split(",")]
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


def cargar_ejercicios():
    """Carga ejercicios PSeInt desde archivo de configuracion.
    Formato: Titulo:Descripcion|GuiaSolucion
    Retorna lista de (titulo, descripcion, solucion) o lista vacia si no existe.
    """
    ejercicios = []
    if os.path.exists(PSEINT_EXERCISES):
        with open(PSEINT_EXERCISES, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Formato: Titulo:Descripcion|Solucion
                    rest = line.split(":", 1)
                    if len(rest) >= 2:
                        titulo = rest[0].strip()
                        sub = rest[1].split("|", 1)
                        desc = sub[0].strip()
                        sol = sub[1].strip() if len(sub) > 1 else ""
                        ejercicios.append((titulo, desc, sol))
    return ejercicios


def cargar_curso(codigo):
    """Load a course by code from CURSOS_DIR. Validates required keys."""
    path = os.path.join(CURSOS_DIR, f"{codigo}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Curso '{codigo}' no encontrado en {CURSOS_DIR}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _validar_curso(codigo, data)
    return data


REQUIRED_CURSO_KEYS = {"codigo", "nombre", "horas", "semanas", "ras", "eas", "evaluaciones"}
REQUIRED_RA_KEYS = {"id", "descripcion", "indicadores"}
REQUIRED_EA_KEYS = {"id", "nombre", "descripcion", "horas", "actividades", "evaluaciones"}

def _validar_curso(codigo, data):
    """Validate course structure has required keys. Raises ValueError if not."""
    # ponytail: plain dict key checks, no JSON Schema dependency
    missing = REQUIRED_CURSO_KEYS - data.keys()
    if missing:
        raise ValueError(
            f"Curso '{codigo}': faltan claves requeridas: {', '.join(sorted(missing))}")
    for i, ra in enumerate(data.get("ras", [])):
        m = REQUIRED_RA_KEYS - ra.keys()
        if m:
            raise ValueError(
                f"Curso '{codigo}', RA#{i}: faltan {', '.join(sorted(m))}")
    for i, ea in enumerate(data.get("eas", [])):
        m = REQUIRED_EA_KEYS - ea.keys()
        if m:
            raise ValueError(
                f"Curso '{codigo}', EA#{i}: faltan {', '.join(sorted(m))}")


def listar_cursos():
    """Discover available courses by scanning CURSOS_DIR for *.json files."""
    if not os.path.isdir(CURSOS_DIR):
        return []
    pattern = os.path.join(CURSOS_DIR, "*.json")
    files = sorted(glob.glob(pattern))
    cursos = []
    for f in files:
        name = os.path.basename(f).replace(".json", "")
        try:
            data = cargar_curso(name)
            cursos.append((name, data.get("nombre", name)))
        except (json.JSONDecodeError, ValueError, FileNotFoundError):
            pass  # skip malformed files
    return cursos


# ── Progreso del estudiante ─────────────────────────────────
PROGRESS_FILE = os.path.expanduser("~/.config/yap/progress.json")

def cargar_progreso():
    """Load student progress. Returns default empty dict if no file."""
    path = PROGRESS_FILE
    if not os.path.exists(path):
        return {"cursos": {}}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"cursos": {}}

def guardar_progreso(progress):
    """Save student progress atomically to avoid corruption."""
    path = PROGRESS_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)  # atomic on Linux


# ── Comandos de curso ───────────────────────────────────────

def cmd_curso(codigo):
    """Enter a course: show overview with RAs and EAs."""
    try:
        curso = cargar_curso(codigo)
    except FileNotFoundError as e:
        return f"[ERROR] {e}"
    except (ValueError, json.JSONDecodeError) as e:
        return f"[ERROR] Curso corrupto: {e}"

    lines = [display_header(f"{curso['codigo']} — {curso['nombre']}")]
    lines.append(f"  Horas: {curso['horas']} | Semanas: {curso['semanas']}")
    lines.append(f"  Ambiente: {curso.get('ambiente', 'N/A')}")
    lines.append(f"  Herramientas: {', '.join(curso.get('herramientas', []))}")
    lines.append("")
    lines.append(display_menu("Resultados de Aprendizaje", [
        f"{ra['id']}: {ra['descripcion'][:70]}..." for ra in curso.get("ras", [])
    ]))
    lines.append(display_menu("Experiencias de Aprendizaje", [
        f"{ea['id']}: {ea['nombre']} ({ea['horas']}h, {ea.get('ponderacion', '?')}%)"
        for ea in curso.get("eas", [])
    ]))
    lines.append(f"\n  {C['GRAY']}iniciar EA1 | iniciar EA2 | iniciar EA3 | salir{C['RESET']}")
    return "\n".join(lines)


def iniciar_ea(curso_codigo, ea_id):
    """Data-driven interactive guided session for a learning experience.
    
    Displays activities one by one. Student can advance, ask the AI, open tools,
    or quit. Progress is saved atomically after each step.
    """
    try:
        curso = cargar_curso(curso_codigo)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        return f"[ERROR] {e}"

    ea = None
    for e in curso.get("eas", []):
        if e["id"].lower() == ea_id.lower():
            ea = e
            break
    if not ea:
        return f"[ERROR] Experiencia '{ea_id}' no encontrada en {curso_codigo}"

    # Load progress and determine starting point
    progress = cargar_progreso()
    curso_prog = progress.setdefault("cursos", {}).setdefault(curso_codigo, {})
    ea_prog = curso_prog.setdefault(ea_id, {"completada": False, "actividad_actual": 0})

    actividades = ea["actividades"]
    current = ea_prog["actividad_actual"]

    # Show overview
    sys.stdout.write(display_header(f"{ea['id']}: {ea['nombre']}"))
    sys.stdout.write(f"  {ea['descripcion']}\n")
    sys.stdout.write(f"  Herramientas: {', '.join(ea.get('herramientas', []))}\n")
    sys.stdout.write(f"  Actividades: {len(actividades)} | Horas: {ea['horas']}\n\n")

    for act in actividades:
        done = act["orden"] <= current
        status = f"{C['GREEN']}✓{C['RESET']}" if done else f"{C['GRAY']}·{C['RESET']}"
        sys.stdout.write(f"  {status} {act['orden']}. {act['nombre']}\n")
        sys.stdout.write(f"     {act['descripcion'][:70]}...\n")

    sys.stdout.write(f"\n  {C['GRAY']}[Enter = empezar] [salir]{C['RESET']}\n")
    try:
        resp = input().strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    if resp.lower() == "salir":
        return ""

    # Interactive activity loop
    t = len(actividades)

    while 0 <= current < t:
        act = actividades[current]
        tool = act.get("tool_hint") or (ea["herramientas"][0] if ea.get("herramientas") else None)

        sys.stdout.write(display_box(
            f"ACTIVIDAD {act['orden']}/{t}: {act['nombre']}\n\n{act['descripcion']}",
            color="CYAN"
        ))
        if tool:
            tool_key = tool.split(" ")[0].lower()  # first word only for 'abrir' command
            sys.stdout.write(f"\n  {C['GRAY']}Tool sugerida: {tool}  —  escribe 'abrir {tool_key}' para lanzarla{C['RESET']}\n")

        activity_done = False
        while not activity_done:
            try:
                resp = input(f"  {C['GRAY']}[Enter=hecho] [pregunta] [abrir X] [salir]{C['RESET']}\n  {C['GREEN']}> {C['RESET']}").strip()
            except (EOFError, KeyboardInterrupt):
                sys.stdout.write("\n")
                guardar_progreso(progress)
                return ""

            if not resp:
                # Mark as done, save, advance
                current += 1
                progress["cursos"][curso_codigo][ea_id]["actividad_actual"] = current
                if current >= t:
                    progress["cursos"][curso_codigo][ea_id]["completada"] = True
                guardar_progreso(progress)
                activity_done = True

            elif resp.lower() == "salir":
                sys.stdout.write(f"\n  {C['YELLOW']}Progreso guardado. Retoma con 'iniciar {ea_id}'.{C['RESET']}\n")
                return ""

            elif resp.lower().startswith("abrir "):
                app_key = resp[5:].strip().lower()
                # Only whitelisted tools, or delegate to cmd_open_app whitelist
                sys.stdout.write(cmd_open_app(app_key) + "\n")

            else:
                # Student question — AI with full context
                contexto = (
                    f"Curso: {curso['codigo']} - {curso['nombre']}\n"
                    f"EA: {ea['id']} - {ea['nombre']}\n"
                    f"Actividad {act['orden']}/{t}: {act['nombre']}\n"
                    f"Descripcion: {act['descripcion']}\n"
                )
                sys.stdout.write(f"\n{C['CYAN']}Tutor:{C['RESET']}\n")
                sys.stdout.write(cmd_query(contexto + f"\nDuda del estudiante: {resp}", store_history=False) + "\n")

    sys.stdout.write(display_box(f"✓ Has completado {ea['id']}: {ea['nombre']}\n\n"
                                 f"Revisa las evaluaciones de esta EA con 'yap curso {curso_codigo}'.", color="GREEN"))
    return ""


def cmd_guia():
    """Interactive onboarding tutorial — step-by-step walkthrough of all features."""
    pasos = [
        ("Bienvenida a ChincoLinux",
         "Yap es el asistente IA educativa de ChincoLinux. Funciona 100% local sin internet.\n"
         "Desde el modo interactivo (escribe 'yap') puedes hacer preguntas, abrir apps,\n"
         "buscar en Wikipedia, aprender a programar y seguir cursos completos."),
        ("Abrir herramientas",
         "Escribe 'Abre Firefox' o 'Abre LibreOffice' para lanzar aplicaciones de la whitelist.\n"
         "Usa 'abrir pseint' o 'abrir vscode' dentro de una sesion de curso."),
        ("Buscar informacion",
         "Escribe 'Busca [tema]' para buscar en Wikipedia. El LLM resume el resultado.\n"
         "Ejemplo: 'Busca que es una variable en programacion'"),
        ("Tutor PSeInt",
         "Escribe 'como hago un ciclo mientras' para consultar al tutor de programacion.\n"
         "El tutor responde con pseudocodigo PSeInt paso a paso."),
        ("Tutorial PSeInt interactivo",
         "Escribe 'quiero aprender pseint' para iniciar el tutorial completo.\n"
         "Abre PSeInt, guia PDF, y presenta ejercicios con asistencia IA en tiempo real."),
        ("Sistema de Cursos",
         "Escribe 'curso FPY1101' para ver el plan de Fundamentos de Programacion.\n"
         "Escribe 'iniciar EA1' para empezar la primera experiencia de aprendizaje.\n"
         "Progreso se guarda automaticamente. Retoma donde quedaste."),
        ("Comandos esenciales",
         "  ayuda        — esta lista de comandos\n"
         "  guia         — tutorial interactivo (este)\n"
         "  curso CODIGO — ver plan de un curso\n"
         "  iniciar EA1  — empezar sesion guiada\n"
         "  mi progreso  — ver tu avance\n"
         "  salir / Ctrl+C — terminar"),
    ]

    lines = [display_header("Guia Rapida")]
    for i, (titulo, contenido) in enumerate(pasos, 1):
        lines.append(display_box(f"PASO {i}: {titulo}\n\n{contenido}", color="CYAN"))
        lines.append(f"\n  {C['GRAY']}[Enter = siguiente] [salir]{C['RESET']}\n")
    return "\n".join(lines)


def cmd_mostrar_progreso():
    """Display student progress across all courses."""
    progress = cargar_progreso()
    cursos_prog = progress.get("cursos", {})

    if not cursos_prog:
        return display_box("No hay progreso registrado. Inicia un curso con 'yap curso FPY1101'.", color="YELLOW")

    lines = [display_header("Mi Progreso")]
    for codigo, eas in cursos_prog.items():
        lines.append(f"\n  {C['BOLD']}{C['GREEN']}{codigo}{C['RESET']}")
        for ea_id, estado in eas.items():
            status = f"{C['GREEN']}✓{C['RESET']}" if estado.get("completada") else f"{C['YELLOW']}▶{C['RESET']}"
            act = estado.get("actividad_actual", 0)
            lines.append(f"    {status} {ea_id}: {act} actividad(es) completada(s)")
    lines.append(f"\n  {C['GRAY']}Progreso guardado en ~/.config/yap/progress.json{C['RESET']}")
    return "\n".join(lines)


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
        available = ", ".join(sorted(apps.keys(), key=str.title))
        return f"[ERROR] '{app_name.strip().title()}' no disponible.\nApps permitidas: {available}"

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
        allowed = ", ".join(domains)
        return f"[ERROR] Dominio '{domain}' bloqueado.\nDominios permitidos: {allowed}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Yap-ChincoLinux/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"[ERROR] Error al obtener {url}: {e}"

    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    text = text[:3000]

    if feed_to_llm:
        return text, True

    return f"Contenido obtenido ({len(text)} chars):\n{text[:1000]}..."


def _clean_output(result):
    """Strip BOS/EOT/header tokens from llama-cli stdout. Falls back to stderr."""
    out = result.stdout.strip()
    for tok in [BOS, HEADER, FOOTER, EOT, "[end of text]"]:
        out = out.replace(tok, "")
    out = out.strip()
    return out if out else (result.stderr.strip() or "(sin respuesta)")


def cmd_query(prompt, context=None, store_history=True):
    parts = [BOS]
    parts.append(f"{HEADER}system{FOOTER}\n\n{SYSTEM_PROMPT}{EOT}")

    # Add conversation history (store original user prompt, not fabricated ones)
    for user_msg, assistant_msg in HISTORY:
        parts.append(f"{HEADER}user{FOOTER}\n\n{user_msg}{EOT}")
        parts.append(f"{HEADER}assistant{FOOTER}\n\n{assistant_msg}{EOT}")

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
        "--cache-type-k", "q8_0",
        "--cache-type-v", "q8_0",
        "--flash-attn",
        "--threads", "2",
        "-no-cnv",
        "--no-display-prompt",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        out = _clean_output(result)
        if store_history and out not in ("(sin respuesta)", ""):
            HISTORY.append((prompt, out))
            if len(HISTORY) > MAX_HISTORY:
                HISTORY.pop(0)
        return out
    except subprocess.TimeoutExpired:
        return "[WARN] Tiempo de espera agotado (120s)"
    except FileNotFoundError:
        return "[ERROR] llama-cli no instalado. Ejecuta el setup de Yap."


def cmd_pseint(query):
    """Tutor de PSeInt: responde paso a paso sin historial de contexto."""
    pseint_prompt = (
        "Eres un tutor de programacion que ensena con PSeInt en espanol. "
        "Cuando un estudiante te pregunte sobre un problema o concepto: "
        "1) Explica el concepto de forma sencilla. "
        "2) Muestra el pseudocodigo PSeInt completo paso a paso. "
        "3) Incluye las palabras clave: Algoritmo, Definir, Escribir, Leer, "
        "Si-Entonces-Sino, Mientras, Repetir, Para, Segun, Arreglo. "
        "4) Usa indentacion clara en el pseudocodigo. "
        "5) Responde SOLO con la guia, sin divagaciones."
    )
    parts = [BOS]
    parts.append(f"{HEADER}system{FOOTER}\n\n{pseint_prompt}{EOT}")
    parts.append(f"{HEADER}user{FOOTER}\n\n{query}{EOT}")
    parts.append(f"{HEADER}assistant{FOOTER}\n\n")

    full_prompt = "".join(parts)

    cmd = [
        "llama-cli", "-m", MODEL_PATH,
        "-p", full_prompt,
        "-n", "512",
        "--temp", "0.5",
        "--ctx-size", "1024",
        "--cache-type-k", "q8_0",
        "--cache-type-v", "q8_0",
        "--flash-attn",
        "--threads", "2",
        "-no-cnv",
        "--no-display-prompt",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return _clean_output(result)
    except subprocess.TimeoutExpired:
        return "[WARN] Tiempo de espera agotado (120s)"
    except FileNotFoundError:
        return "[ERROR] llama-cli no instalado. Ejecuta el setup de Yap."


def cmd_intro_pseint():
    """Tutorial interactivo de PSeInt: abre PDF estatico con guia, abre PSeInt y enseña paso a paso."""
    ejercicios = cargar_ejercicios()
    if not ejercicios:
        print("[ERROR] No hay ejercicios configurados en", PSEINT_EXERCISES)
        return

    total = len(ejercicios)

    # 1. Abrir PDF estatico con la guia de ejercicios
    if os.path.exists(PSEINT_GUIA_PDF):
        try:
            subprocess.Popen(["xdg-open", PSEINT_GUIA_PDF],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[OK] Guia de ejercicios abierta")
        except FileNotFoundError:
            print(f"[INFO] PDF disponible en: {PSEINT_GUIA_PDF}")
    else:
        print(f"[INFO] Guia PDF no encontrada en {PSEINT_GUIA_PDF}")

    # 2. Abrir PSeInt (si esta instalado)
    print(cmd_open_app("pseint"))

    # 3. Tutorial interactivo paso a paso
    print("\n" + "=" * 56)
    print("  TUTOR INTERACTIVO PSEINT — PASO A PASO")
    print("=" * 56)

    idx = 0
    while 0 <= idx < total:
        titulo, desc, solucion = ejercicios[idx]
        print(f"\n┌── EJERCICIO {idx + 1}/{total}: {titulo}")
        print(f"│   {desc}")
        print(f"└{'─' * 50}")

        if not solucion:
            print("\n(Sin guia de resolucion. Pregunta al tutor.)")
            while True:
                try:
                    resp = input("  > ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nTutorial interrumpido.")
                    return
                if resp.lower() == "siguiente":
                    idx += 1
                    break
                elif resp.lower() == "salir":
                    print("\nTutorial finalizado.")
                    return
                elif resp:
                    print("\n[ASISTENCIA]")
                    print(cmd_pseint(
                        f"Ejercicio: '{titulo}' - {desc}.\n"
                        f"Duda del estudiante: {resp}"
                    ))
            continue

        # Mostrar guia de resolucion paso a paso
        pasos_guia = [p.strip() for p in solucion.split(";") if p.strip()]
        paso_actual = 0
        while paso_actual < len(pasos_guia):
            paso = pasos_guia[paso_actual]
            print(f"\n  >> {paso}")

            while True:
                try:
                    resp = input(
                        "  [Enter = continuar] [pregunta] [siguiente] [salir]\n  > "
                    ).strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n\nTutorial interrumpido.")
                    return

                if not resp:
                    paso_actual += 1
                    break

                lower = resp.lower()

                if lower == "salir":
                    print("\nTutorial finalizado. ¡Sigue practicando!")
                    return

                if lower == "siguiente":
                    paso_actual = len(pasos_guia)
                    idx += 1
                    break

                # El estudiante tiene una duda - la IA responde con contexto completo
                guia_completa = " ; ".join(pasos_guia)
                print("\n[ASISTENCIA]")
                print(cmd_pseint(
                    f"EJERCICIO: {titulo}\n"
                    f"Descripcion: {desc}\n"
                    f"Guia de resolucion paso a paso: {guia_completa}\n\n"
                    f"El estudiante esta en el {paso}.\n"
                    f"Duda del estudiante: {resp}"
                ))

            if paso_actual >= len(pasos_guia) and lower != "siguiente":
                print(f"\n  ✓ Completaste el ejercicio '{titulo}'")
                while True:
                    try:
                        resp = input("  [siguiente] [salir]\n  > ").strip()
                    except (EOFError, KeyboardInterrupt):
                        return
                    if resp.lower() == "siguiente":
                        idx += 1
                        break
                    elif resp.lower() == "salir":
                        print("\nTutorial finalizado.")
                        return
                break

    print(f"\n✓ ¡Felicidades! Completaste los {total} ejercicios.")
    print("Para mas ayuda, escribe tu pregunta sobre PSeInt en cualquier momento.")


def classify_intent(user_input):
    """Use the LLM to determine user intent and extract parameters."""
    prompt = (
        f"{BOS}{HEADER}system{FOOTER}\n\n"
        "Eres un clasificador de comandos. Responde SOLO con ACCION|PARAMETRO.\n"
        "ACCION: open_app (abrir app), search (buscar en Wikipedia),\n"
        "webfetch (obtener URL), pseint (tutor PSeInt/programacion),\n"
        "introduccion_pseint (tutorial interactivo con ejercicios),\n"
        "curso (ver o iniciar curso), guia (tutorial interactivo),\n"
        "progreso (ver avance), help (mostrar ayuda/opciones),\n"
        "query (preguntar al AI).\n"
        "Ejemplo: 'abre firefox' -> open_app|firefox\n"
        "Ejemplo: 'busca quien es vegetta777 en wikipedia' -> search|vegetta777\n"
        "Ejemplo: 'busca linus torvalds' -> search|linus torvalds\n"
        "Ejemplo: 'fetch https://ejemplo.com' -> webfetch|https://ejemplo.com\n"
        "Ejemplo: 'como hago un ciclo mientras' -> pseint|como hago un ciclo mientras\n"
        "Ejemplo: 'explica los arreglos en pseint' -> pseint|explica los arreglos en pseint\n"
        "Ejemplo: 'quiero aprender pseint' -> introduccion_pseint|inicio\n"
        "Ejemplo: 'ejercicios pseint' -> introduccion_pseint|inicio\n"
        "Ejemplo: 'ayuda' -> help|ayuda\n"
        "Ejemplo: 'como usar yap' -> help|como usar yap\n"
        "Ejemplo: 'que es debian?' -> query|que es debian?\n"
        "Ejemplo: 'curso fpy1101' -> curso|FPY1101\n"
        "Ejemplo: 'iniciar ea1' -> curso|FPY1101:EA1\n"
        "Ejemplo: 'ver mi curso' -> curso|FPY1101\n"
        "Ejemplo: 'guia' -> guia|guia\n"
        "Ejemplo: 'como usar yap' -> guia|guia\n"
        "Ejemplo: 'mi progreso' -> progreso|progreso\n"
        "Ejemplo: 'avance' -> progreso|progreso\n"
        f"{EOT}"
        f"{HEADER}user{FOOTER}\n\n{user_input}{EOT}"
        f"{HEADER}assistant{FOOTER}\n\n"
    )

    cmd = [
        "llama-cli", "-m", MODEL_PATH,
        "-p", prompt, "-n", "15", "--temp", "0.1",
        "--ctx-size", "512",
        "--cache-type-k", "q8_0",
        "--cache-type-v", "q8_0",
        "--flash-attn",
        "--threads", "2",
        "-no-cnv", "--no-display-prompt",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        out = result.stdout.strip()
        for tok in [BOS, HEADER, FOOTER, EOT, "[end of text]"]:
            out = out.replace(tok, "")
        out = out.strip().split("\n")[0]

        if "|" in out:
            action, param = out.split("|", 1)
            action = action.strip().lower()
            param = param.strip()
            if action in ("open_app", "search", "webfetch", "pseint", "introduccion_pseint", "curso", "guia", "progreso", "help", "query"):
                return action, param
    except subprocess.TimeoutExpired:
        pass

    return "query", user_input.strip()

def interpret(user_input):
    """Keyword router before LLM classifier for known commands."""
    stripped = user_input.strip().lower()

    # Exact/prefix keyword routing (bypasses LLM for speed & reliability)
    if stripped in ("guia", "guia rapida", "tutorial", "como usar"):
        return "guia", "guia"
    if stripped in ("progreso", "avance", "mi progreso", "mi avance", "avance curso"):
        return "progreso", "progreso"
    if stripped in ("ayuda", "help", "--help", "-h", "comandos", "ayuda yap"):
        return "help", "ayuda"
    if stripped in ("salir", "exit", "quit", "q"):
        sys.exit(0)

    # curso FPY1101 → ("curso", "FPY1101")
    # iniciar EA1   → ("curso", "FPY1101:EA1")  — needs context, hands to LLM
    if stripped.startswith("curso "):
        param = user_input[6:].strip().upper()
        if param:
            return "curso", param

    if stripped.startswith("iniciar "):
        param = user_input[8:].strip().upper()
        if param and param.startswith("EA"):
            return "curso", f"FPY1101:{param}"  # ponytail: assumes active course

    return classify_intent(user_input)


def tui_run():
    """TUI curses: split-view, Chinco prompt, historial, scroll."""
    import curses
    import curses.textpad
    import io
    import traceback

    def _run(stdscr):
        curses.use_default_colors()
        curses.curs_set(1)
        # colores: 1=cyan, 2=green, 3=yellow, 4=red, 5=gray
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_RED, -1)
        curses.init_pair(5, curses.COLOR_BLACK, -1)

        buf = []       # lineas de output
        scroll = 0
        inp = ""
        pos = 0        # cursor dentro de inp
        hist = []      # historial de comandos
        hist_idx = -1

        def add_out(text, color=0):
            for line in text.rstrip("\n").split("\n"):
                buf.append((line, color))

        def _show_chinco_info(add_out):
            add_out("")
            for line in CHINCO_ART:
                add_out(line, 4)
            add_out("")
            add_out(f"  {'═' * 50}", 5)
            add_out("  Comandos disponibles:", 0)
            for line in [
                "  guia            Tutorial interactivo",
                "  curso N         Plan de estudio (ej: curso FPY1101)",
                "  ayuda           Lista completa de comandos",
                "  abre [app]      Abrir aplicacion permitida",
                "  busca [tema]    Buscar en Wikipedia",
                "  progreso        Ver progreso del curso activo",
                "  iniciar EA[N]   Iniciar sesion de ejercicios",
                "  salir           Terminar sesion",
            ]:
                add_out(line, 3)
            add_out("")
            add_out(f"  {'─' * 50}", 5)
            add_out("  Atajos de teclado:", 0)
            for line in [
                "  Tab/Ctrl+I  Esta ayuda (prompt vacio) / autocompletar",
                "  F1          Esta ayuda",
                "  ?           Esta ayuda (prompt vacio)",
                "  ↑ ↓         Navegar historial de comandos",
                "  RePág AvPág Desplazar salida",
                "  Ctrl+C/D    Salir",
            ]:
                add_out(line, 0)
            add_out("")

        def refresh_view():
            curses.curs_set(0)  # ocultar cursor durante redibujo
            h, w = stdscr.getmaxyx()
            ih = h - 2  # output height: 2 lines for separator + prompt

            # ── Separador ──
            stdscr.move(ih, 0)
            stdscr.clrtoeol()
            stdscr.hline(ih, 0, curses.ACS_HLINE, w, curses.color_pair(5))

            # ── Input line ──
            prompt = " Chinco > "
            stdscr.attrset(curses.color_pair(2))
            stdscr.addstr(ih + 1, 0, prompt)
            stdscr.attrset(0)
            max_inp = w - len(prompt) - 2
            visible = inp if len(inp) <= max_inp else inp[-(max_inp):]
            stdscr.addstr(ih + 1, len(prompt), visible + " ")

            # ── Output area ──
            max_scroll = max(0, len(buf) - ih)
            scroll_clamped = min(scroll, max_scroll)
            for y in range(ih):
                idx = scroll_clamped + y
                if idx < len(buf):
                    text, color = buf[idx]
                    text = text[:w]
                    if color:
                        style = curses.color_pair(color)
                        if text.startswith("> "):
                            style |= curses.A_BOLD
                        stdscr.addstr(y, 0, text, style)
                        stdscr.clrtoeol()
                    else:
                        stdscr.addstr(y, 0, text[:w])
                        stdscr.clrtoeol()
                else:
                    stdscr.addstr(y, 0, " ")
                    stdscr.clrtoeol()
            # mostrar cursor en la posicion del prompt
            stdscr.move(ih + 1, min(len(prompt) + pos, w - 2))
            curses.curs_set(1)
            return scroll_clamped

        # ── Pantalla de bienvenida ──
        add_out("")
        for line in CHINCO_ART:
            add_out(line, 1)
        add_out("")
        add_out(f"  {'═' * 50}", 5)
        add_out("  Escribe comandos o preguntas:", 0)
        for line in [
            "    guia            Tutorial interactivo",
            "    ayuda           Lista completa de comandos",
            "    curso N         Plan de estudio",
            "    abre [app]      Abrir aplicacion",
            "    busca [tema]    Buscar en Wikipedia",
            "    salir           Terminar sesion",
        ]:
            add_out(line, 3)
        add_out("")
        add_out("", 0)

        while True:
            h, w = stdscr.getmaxyx()
            if h < 10 or w < 30:
                stdscr.addstr(0, 0, "Terminal demasiado pequena (min 30x10)")
                stdscr.refresh()
                curses.napms(2000)
                return

            scroll = refresh_view()
            stdscr.refresh()

            key = stdscr.getch()

            # ── Manejo de teclas ──
            if key in (curses.KEY_ENTER, 10, 13):
                # Enter → ejecutar comando
                cmd = inp.strip()
                inp = ""
                pos = 0
                hist_idx = -1
                if cmd:
                    hist.append(cmd)
                    add_out(f"> {cmd}", 2)
                    if cmd.lower() in ("salir", "exit", "quit"):
                        break

                    # Capturar output de handle_action
                    old_out, old_err = sys.stdout, sys.stderr
                    cap = io.StringIO()
                    sys.stdout = cap
                    sys.stderr = cap
                    try:
                        action, param = interpret(cmd)
                        handle_action(action, param, cmd)
                    except Exception:
                        traceback.print_exc(file=cap)
                    sys.stdout = old_out
                    sys.stderr = old_err
                    text = cap.getvalue()
                    if text:
                        add_out(re.sub(r"\033\[[0-9;]*m", "", text).rstrip())
                    add_out("")

            elif key == curses.KEY_BACKSPACE or key == 127:
                if pos > 0:
                    inp = inp[:pos-1] + inp[pos:]
                    pos -= 1
            elif key == curses.KEY_DC:  # Delete
                if pos < len(inp):
                    inp = inp[:pos] + inp[pos+1:]
            elif key == curses.KEY_LEFT:
                pos = max(0, pos - 1)
            elif key == curses.KEY_RIGHT:
                pos = min(len(inp), pos + 1)
            elif key == curses.KEY_HOME:
                pos = 0
            elif key == curses.KEY_END:
                pos = len(inp)
            elif key == curses.KEY_UP:
                if hist:
                    if hist_idx == -1:
                        hist_idx = len(hist) - 1
                    else:
                        hist_idx = max(0, hist_idx - 1)
                    inp = hist[hist_idx]
                    pos = len(inp)
            elif key == curses.KEY_DOWN:
                if hist_idx >= 0:
                    hist_idx += 1
                    if hist_idx >= len(hist):
                        hist_idx = -1
                        inp = ""
                    else:
                        inp = hist[hist_idx]
                    pos = len(inp)
            elif key == curses.KEY_PPAGE:  # Page Up
                scroll = max(0, scroll - (h - 2))
            elif key == curses.KEY_NPAGE:  # Page Down
                scroll = min(len(buf), scroll + (h - 2))
            elif key == curses.KEY_RESIZE:
                pass  # ponytail: proximo ciclo recoge nuevo tamano via getmaxyx()
            elif key == curses.KEY_F1:
                _show_chinco_info(add_out)
            elif key == 9:  # Tab/Ctrl+I — info si prompt vacio, completar si no
                # ponytail: first-match completion, no cycle/fuzzy
                conocidos = ["curso ", "iniciar ea", "guia", "ayuda", "progreso",
                             "abre ", "busca ", "salir"]
                if inp:
                    matches = [c for c in conocidos if c.startswith(inp)]
                    if matches:
                        inp = matches[0]
                        pos = len(inp)
                else:
                    _show_chinco_info(add_out)
            elif key in (3, 4):  # Ctrl+C, Ctrl+D
                break
            elif key == ord("?") and not inp:
                _show_chinco_info(add_out)
            elif 32 <= key <= 126:
                inp = inp[:pos] + chr(key) + inp[pos:]
                pos += 1

    curses.wrapper(_run)


def main():
    # `yap` sin argumentos → TUI curses (Chinco)
    if len(sys.argv) == 1:
        if sys.stdout.isatty() and sys.stdin.isatty():
            try:
                tui_run()
                return  # curses TUI salio limpiamente
            except Exception:
                pass  # fallback si curses falla
        sys.stdout.write(render_art(CHINCO_ART, C['CYAN']) + "\n")
        sys.stdout.write(display_menu("Comandos disponibles", [
            "Preguntar al AI (escribe tu consulta)",
            "Abre [app] — abrir aplicacion permitida",
            "Busca [tema] — buscar en Wikipedia",
            "Tutor PSeInt — preguntas de programacion",
            "Quiero aprender PSeInt — tutorial interactivo",
            "Curso: 'curso FPY1101' — acceder al plan de estudio",
            "Ayuda — mostrar esta lista",
            "Salir — Ctrl+C o 'salir'",
        ]))
        print()
        while True:
            try:
                user_input = input(f"{C['GREEN']}Chinco{C['RESET']} > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                sys.exit(0)
            if not user_input:
                continue
            action, param = interpret(user_input)
            handle_action(action, param, user_input)

    # `yap <comando>` → keyword router + LLM classifier
    else:
        user_input = " ".join(sys.argv[1:])
        action, param = interpret(user_input)
        handle_action(action, param, user_input)


def handle_action(action, param, original_input):
    if action == "open_app":
        print(cmd_open_app(param))

    elif action == "search":
        query = param
        wikipedia_api = (
            "https://es.wikipedia.org/w/api.php?action=query"
            "&prop=extracts&exintro=&explaintext=&exchars=2000"
            "&titles=" + urllib.parse.quote(query) + "&format=json"
        )
        print(f"Buscando '{query}' en Wikipedia...")
        content = cmd_webfetch(wikipedia_api, feed_to_llm=True)
        if isinstance(content, tuple):
            text, _ = content
            print(f"Contenido obtenido ({len(text)} chars). Resumiendo con LLM...")
            response = cmd_query(
                f"Resume el siguiente contenido sobre '{query}':",
                context=text,
                store_history=False,
            )
            print(response)
            source = "https://es.wikipedia.org/wiki/" + query.replace(" ", "_")
            print(f"\nFuente: {source}")
            if not response.startswith("[WARN]") and not response.startswith("[ERROR]"):
                HISTORY.append((query, response))
                if len(HISTORY) > MAX_HISTORY:
                    HISTORY.pop(0)
        else:
            print(content)

    elif action == "webfetch":
        print("Obteniendo contenido web...")
        content = cmd_webfetch(param, feed_to_llm=True)
        if isinstance(content, tuple):
            text, _ = content
            print(f"Contenido obtenido ({len(text)} chars). Resumiendo con LLM...")
            response = cmd_query(
                f"Resume el siguiente contenido sobre '{param}':",
                context=text,
                store_history=False,
            )
            print(response)
            if not response.startswith("[WARN]") and not response.startswith("[ERROR]"):
                HISTORY.append((param, response))
                if len(HISTORY) > MAX_HISTORY:
                    HISTORY.pop(0)
        else:
            print(content)

    elif action == "pseint":
        print("Consultando tutor PSeInt...")
        print(cmd_pseint(param))

    elif action == "introduccion_pseint":
        cmd_intro_pseint()

    elif action == "curso":
        parts = [p.strip() for p in param.split(":", 1)]
        codigo = parts[0].upper()
        if len(parts) > 1 and parts[1].lower().startswith("ea"):
            print(iniciar_ea(codigo, parts[1]))
        else:
            print(cmd_curso(codigo))

    elif action == "guia":
        print(cmd_guia())

    elif action == "progreso":
        print(cmd_mostrar_progreso())

    elif action == "help":
        print()
        print("  Preguntar:     Cualquier pregunta directa al AI")
        print("  Abrir app:     'Abre [aplicacion]' (Firefox, Terminal, etc.)")
        print("  Wikipedia:     'Busca [tema]' (resumen desde Wikipedia)")
        print("  Tutor PSeInt:  Preguntas sobre programacion con PSeInt")
        print("  Introduccion:  'Quiero aprender PSeInt' — tutorial interactivo")
        print("  Curso:         'curso FPY1101' — acceder al plan de estudio")
        print("  Iniciar EA:    'iniciar EA1' — comenzar experiencia de aprendizaje")
        print()

    else:
        print("Consultando LLM...")
        print(cmd_query(original_input))


if __name__ == "__main__":
    main()
