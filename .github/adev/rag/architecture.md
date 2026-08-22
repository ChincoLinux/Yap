# RAG: Arquitectura de Yap (ChincoLinux)

> Contexto recuperable para agentes. Fuente de verdad: `yap.py`, `CLAUDE.md`, `README.md`.

---

## Capas del sistema

```
Usuario → CLI yap → Interprete (classify_intent)
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
        Whitelist    Whitelist    LLM local
        apps         web          llama.cpp
              │           │           │
              ▼           ▼           ▼
        Lanzar app   Webfetch    Respuesta
        + alerta     + límite    educativa
                   3000 chars
```

---

## Flujo de una consulta

1. **Entrada**: Usuario escribe comando (directo o interactivo)
2. **Clasificación**: `classify_intent(texto)` → envía a LLM con prompt de clasificación
3. **Respuesta LLM**: `ACCIÓN|PARÁMETRO` donde ACCIÓN ∈ {`open_app`, `search`, `webfetch`, `query`, `pseint`}
4. **Ejecución**: `handle_action(acción, parámetro)` despacha a `cmd_*()`
5. **Salida**: Resultado mostrado en terminal / notificación gráfica

---

## Componentes clave (yap.py)

| Componente | Función | Líneas aprox |
|---|---|---|
| **CLI** | `main()` — loop interactivo + modo directo | 222–236 |
| **Intérprete** | `classify_intent()` — LLM clasifica intención | 178–216 |
| **Whitelist apps** | `load_whitelist()` + `cmd_open_app()` | 96–106, 67–101 |
| **Whitelist web** | `load_domain_whitelist()` + `cmd_webfetch()` | 109–117, 104–133 |
| **LLM local** | `cmd_query()` — prompt Llama 3.2 + historial | 136–178 |
| **Notificador** | `notify()` — `notify-send` 3 urgencias | 56–64 |
| **Cursos** | `cargar_curso()`, `listar_cursos()`, progreso | 142–190, 193+ |
| **PSeInt** | `cargar_ejercicios()`, `cmd_pseint()`, tutorial | 120–139, 240+ |

---

## Ramas de configuración (modelos)

| Rama | MODEL_PATH | MAX_CTX | KV Cache | Threads | RAM |
|---|---|---|---|---|---|
| `master` | Llama-3.2-3B-Instruct-Q4_K_M.gguf | 4096 | FP16 | 4 | ~3.5GB |
| `lowmem` | Llama-3.2-3B-Instruct-Q4_K_M.gguf | 2048 | Q8_0 | 2 | ~3.1GB |
| `ultra-lowmem` | Llama-3.2-1B-Instruct-Q4_K_M.gguf | 2048 | Q8_0 | 2 | ~1.8GB |

**Hook post-checkout** (`.githooks/post-checkout`): informa modelo anterior/nuevo, estado descarga, siguiente paso.

---

## Constantes críticas

```python
CONFIG_DIR = "/etc/yap"
WHITELIST_APPS = "/etc/yap/whitelist/apps.conf"
WHITELIST_WEB = "/etc/yap/whitelist/web.conf"
PSEINT_DIR = "/etc/yap/pseint"
CURSOS_DIR = "/etc/yap/cursos"
PROGRESS_FILE = "~/.config/yap/progress.json"
MODEL_PATH = "/opt/yap/models/..."  # cambia por rama
MAX_CTX = 2048  # o 4096 en master
MAX_HISTORY = 6
```

---

## Formato de prompts Llama 3.2

```python
BOS = "<|begin_of_text|>"
HEADER = "<|start_header_id|>"
FOOTER = "<|end_header_id|>"
EOT = "<|eot_id|>"

# Sistema
SYSTEM_PROMPT = "Eres Yap, un asistente educativo en español..."

# Historial: hasta 6 turnos (user/assistant alternados)
# Contexto PSeInt: reducido a 1024 tokens
```

---

## Intenciones y handlers

| Intención | Handler | Validación |
|---|---|---|
| `open_app` | `cmd_open_app()` | `shutil.which()` contra whitelist apps.conf |
| `search` | `cmd_search()` | Wikipedia API REST, dominio `wikipedia.org` |
| `webfetch` | `cmd_webfetch()` | Dominio en web.conf, límite 3000 chars, strip HTML |
| `query` | `cmd_query()` | LLM directo, historial si interactivo |
| `pseint` | `cmd_pseint()` | Contexto ejercicio + guía completa, sin historial |

---

## Seguridad por diseño

- **Sin shell=True** — `subprocess.Popen([binario, args...])`
- **Sin eval/os.system** — verificado en CI (grep)
- **Whitelist apps** — nombre visible → [binarios], fallback ordenado
- **Whitelist web** — match exacto o subdominio directo (`domain.endswith("."+d)`)
- **Timeouts** — todo `subprocess.run(timeout=...)`
- **Límites** — webfetch 3000 chars, contexto 2048/4096 tokens

---

## Tests (81 totales)

| Archivo | Clases | Pruebas | Enfoque |
|---|---|---|---|
| `test_yap_security.py` | 10 | 25 | Whitelist, inyección, límites, código |
| `test_yap_functional.py` | 11 | 56 | Apps, webfetch, LLM, historial, PSeInt, cursos, TUI |
| `run_tests.py` | — | — | Ejecutor + reporte TXT/VM |

**Mocking total:** `subprocess.run`, `urllib.request`, `shutil.which` — sin LLM/GPU/Internet.

---

## Instalación (setup.sh)

1. Dependencias: `build-essential`, `cmake`, `libcurl4-openssl-dev`, `python3-pip`, `libnotify-bin`
2. Compila `llama.cpp` estático (`-DBUILD_SHARED_LIBS=OFF`)
3. Descarga modelo según `MODEL_PATH` en `yap.py`
4. Instala en `/etc/yap/` + symlink `/usr/local/bin/yap` → repo
5. Configura git hooks (`.githooks/post-checkout`)

---

## Referencias de código

- `yap.py:29-43` — `load_whitelist`
- `yap.py:45-53` — `load_domain_whitelist`
- `yap.py:56-64` — `notify`
- `yap.py:67-101` — `cmd_open_app`
- `yap.py:104-133` — `cmd_webfetch`
- `yap.py:136-178` — `cmd_query`
- `yap.py:178-216` — `classify_intent`
- `yap.py:222-236` — `main`
- `yap.py:240-270` — `handle_action`