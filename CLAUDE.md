# CLAUDE.md — Yap (ChincoLinux)

> **Marco A-Dev:** Este proyecto opera bajo la doctrina de [A-Dev](https://github.com/scanalesespinoza/adev). Lee `ADEV.md` (doctrina) y `.github/adev/` (políticas locales) antes de cualquier cambio.

---

## 1. Identidad del proyecto

**Yap** es un asistente IA local, CPU-only, para entornos educativos con recursos limitados (ChincoLinux / Debian 13).

| Atributo | Valor |
|---|---|
| Versión | `1.0.0-beta` |
| Modelo | Llama 3.2 Instruct (GGUF Q4_K_M / 1B) |
| Runtime | llama.cpp (enlace estático, CPU-only) |
| Idioma | Español |
| RAM | 1.8 GB – 3.5 GB (según rama) |
| SO | Debian 13 (64-bit) |
| Licencia | MIT |

---

## 2. Arquitectura (yap.py)

Flujo principal: `entrada → classify_intent() → handle_action() → cmd_*()`.

### Funciones clave

| Función | Líneas | Rol |
|---|---|---|
| `load_whitelist()` | 96–106 | Carga `apps.conf` → `{nombre: [binarios]}` |
| `load_domain_whitelist()` | 109–117 | Carga `web.conf` → `[dominios]` |
| `cargar_ejercicios()` | 120–139 | Lee `ejercicios.conf` PSeInt |
| `cargar_curso()` / `listar_cursos()` | 142–190 | Descubre cursos JSON en `CURSOS_DIR` |
| `cmd_open_app()` | 67–101 (ref README) | Lanza app de whitelist con `shutil.which()` |
| `cmd_webfetch()` | 104–133 | Valida dominio, limpia HTML, limita 3000 chars |
| `cmd_query()` | 136–178 | Prompt Llama 3.2 + historial |
| `classify_intent()` | 178–216 | Clasifica: `open_app`\|`search`\|`webfetch`\|`query`\|`pseint` |
| `handle_action()` | 240–270 | Centraliza acciones + historial |
| `main()` | 222–236 | Loop interactivo `while True` |

### Constantes críticas

```python
MODEL_PATH = "/opt/yap/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf"  # cambia por rama
MAX_CTX = 2048          # master=4096, lowmem/ultra=2048
MAX_HISTORY = 6
CONFIG_DIR = "/etc/yap"
CURSOS_DIR = "/etc/yap/cursos"
PROGRESS_FILE = ~/.config/yap/progress.json
```

### Intenciones soportadas

`open_app` (abrir app whitelist) · `search` (Wikipedia API) · `webfetch` (URL directa) · `query` (LLM directo) · `cloud_query` (Gemini 3.7 Flash en Agent Platform, opt-in) · `pseint` (tutor PSeInt).

La nube está **apagada por defecto**. Quienes clonan el repo despliegan `agent-platform/yap_nube/` (modelo `gemini-3.7-flash`) y activan `YAP_CLOUD_ENABLED=1` en la imagen del laboratorio. El alumno no usa GCP. Si el POST privado falla, Yap cae al LLM local. Ver `docs/CLOUD.md`.

---

## 3. Seguridad (no negociable)

### Whitelists
- **`whitelist/apps.conf`** — `Nombre:bin1,bin2` (multi-binario con fallback)
- **`whitelist/web.conf`** — dominios exactos o subdominio directo (`d == domain or domain.endswith("."+d)`)

### Reglas de código (CI verifica)
- ❌ `shell=True`, `eval()`, `os.system()` — prohibidos
- ❌ `open()` en modo escritura fuera de paths permitidos
- ❌ `os.remove`, `shutil.rmtree` en código fuente
- ✅ Todo `subprocess.run()` debe tener `timeout=`
- ✅ Contenido webfetch limitado a 3000 chars
- ✅ Sin imports: `socket`, `ctypes`, `pickle`, `base64`

### Acciones bloqueadas por diseño
Comandos arbitrarios · red fuera de whitelist · instalar/eliminar software · modificar archivos del sistema.

---

## 4. Ramas de configuración

| Rama | Modelo | Ctx | KV Cache | RAM | Threads |
|---|---|---|---|---|---|
| `master` | 3B Q4_K_M | 4096 | FP16 | ~3.5GB | 4 |
| `lowmem` | 3B Q4_K_M | 2048 | Q8_0 | ~3.1GB | 2 |
| `ultra-lowmem` | 1B Q4_K_M | 2048 | Q8_0 | ~1.8GB | 2 |

El hook `.githooks/post-checkout` informa del cambio de modelo al hacer `git checkout`.

---

## 5. Estructura del repo

```
Yap/
├── yap.py                 # Agente principal (36KB, ~640 líneas)
├── setup.sh               # Instalador (compila llama.cpp, descarga modelo)
├── whitelist/
│   ├── apps.conf          # Apps permitidas
│   └── web.conf           # Dominios permitidos
├── cursos/                # JSON de cursos (FPY1101, etc.)
├── tests/
│   ├── test_yap_security.py    # 25 pruebas
│   ├── test_yap_functional.py  # 56 pruebas
│   └── run_tests.py            # Ejecutor con reporte
├── .githooks/post-checkout    # Hook informativo de rama
├── .github/
│   ├── workflows/test.yml      # CI: 81 pruebas + verificación estática
│   └── adev/                   # Configuración A-Dev (ver sección 7)
├── docs/                  # Documentación
└── USAGE.md              # Guía de uso
```

---

## 6. Tests

```bash
pip install pytest
python3 -m pytest tests/ -v          # 81 pruebas (sin LLM/GPU/Internet)
python3 tests/run_tests.py --report  # Reporte TXT
python3 tests/run_tests.py --vm      # Infra (solo en VM)
```

**Cobertura:** 25 seguridad + 56 funcional + 5 infra = 81/81 ✓

---

## 7. Configuración A-Dev (para agentes)

Las políticas, skills, agents y RAG de este proyecto viven en `.github/adev/`:

```
.github/adev/
├── ADEV.md              # Doctrina (espejo de upstream)
├── policies/
│   ├── HD-YAP-SEC-001.json   # Seguridad whitelist (MUST)
│   ├── HD-YAP-TEST-001.json  # Tests CI pasan (MUST)
│   └── HD-YAP-BRANCH-001.json # Disciplina de ramas (SHOULD)
├── skills/
│   └── yap-read-only-inspection/SKILL.md
├── agents/
│   └── yap-reviewer.md   # Agente revisor de PRs
├── rag/
│   ├── architecture.md    # Contexto RAG: arquitectura
│   ├── security.md        # Contexto RAG: seguridad
│   └── config.md         # Contexto RAG: configuración
└── README.md            # Índice de esta carpeta
```

**Rutas canónicas para agentes:**
- Agentes: `.github/adev/agents/`
- RAG: `.github/adev/rag/`
- Políticas: `.github/adev/policies/`
- Skills: `.github/adev/skills/`

Cualquier agente debe leer `.github/adev/README.md` en el primer prompt para ubicar estas rutas.

---

## 8. Flujo de trabajo (A-Dev + Yap)

1. **Leer** `.github/adev/README.md` → localizar agents/RAG/policies.
2. **Inspeccionar** con `yap-read-only-inspection` (sin efectos).
3. **Rama fresca** por cambio: `git checkout -b fix/issue-NNN`.
4. **Commits atómicos** con Conventional Commits.
5. **Tests** locales antes de push: `pytest tests/`.
6. **PR** → workflow de revisión automática evaluá `HD-YAP-TEST-001`.
7. **Auto-merge** si CI pasa; si no, `request-changes`.

---

## 9. Convenciones de código

- Español en strings de usuario; español/inglés en comentarios técnicos.
- `ponytail:` prefijo en comentarios de workarounds (sin dependencias externas).
- Sin Rich/Textual — ANSI directo para TUI.
- `shutil.which()` antes de `subprocess.Popen` para apps.

---

## 10. Referencias

- [A-Dev upstream](https://github.com/scanalesespinoza/adev)
- [Yap issues](https://github.com/ChincoLinux/Yap/issues)
- [llama.cpp](https://github.com/ggerganov/llama.cpp)
