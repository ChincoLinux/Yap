# CLAUDE.md — Yap (ChincoLinux)

> **Marco A-Dev y Fuente de Verdad:** Este proyecto opera bajo la doctrina de [A-Dev](https://github.com/scanalesespinoza/adev). La **guía operativa y contrato de ejecución para agentes** está en [AGENTS.md](AGENTS.md). Este archivo es un resumen técnico de arquitectura y ejecución complementario.

---

## 1. Identidad del proyecto

**Yap** es un asistente IA local, CPU-only, para entornos educativos con recursos limitados (ChincoLinux / Debian 13).

| Atributo | Valor |
|---|---|
| Versión | `1.0.1` (fuente: `VERSION`) |
| Modelo | Llama 3.2 Instruct (GGUF Q4_K_M / 1B) |
| Runtime | llama.cpp (enlace estático, CPU-only) |
| Idioma | Español |
| RAM | 1.8 GB – 3.5 GB (según rama) |
| SO | Debian 13 (64-bit) |
| Licencia | MIT |

---

## 2. Arquitectura (paquete `yap/` y `yap_core.py`)

Desde #204 la implementación vive en el paquete `yap/__init__.py`; `yap.py` es un shim
(`from yap import main`) y `python3 -m yap` entra por `yap/__main__.py`.
`yap_core.py` (#152) es el motor desacoplado con streaming que usa la GUI (`yap_desktop/`). Los datos
(`i18n/`, `whitelist/`, `cursos/`) se buscan en `RAIZ_INSTALACION`, el
directorio padre del paquete, nunca con `dirname(__file__)`.

Flujo principal: `entrada → classify_intent() → handle_action() → cmd_*()`.

### Funciones clave

| Función | Módulo | Rol |
|---|---|---|
| `load_whitelist()` | `yap/__init__.py` | Carga `apps.conf` → `{nombre: [binarios]}` |
| `load_domain_whitelist()` | `yap/__init__.py` | Carga `web.conf` → `[dominios]` |
| `cargar_ejercicios()` | `yap/__init__.py` | Lee `ejercicios.conf` PSeInt |
| `cargar_curso()` / `listar_cursos()` | `yap/__init__.py` | Descubre cursos JSON en `CURSOS_DIR` |
| `cmd_open_app()` | `yap/__init__.py` | Lanza app de whitelist con `shutil.which()` |
| `cmd_webfetch()` | `yap/__init__.py` | Valida dominio, limpia HTML, limita 3000 chars |
| `cmd_query()` | `yap/__init__.py` | Prompt Llama 3.2 + historial |
| `classify_intent()` | `yap/__init__.py` | Clasifica: `open_app`\|`search`\|`webfetch`\|`query`\|`pseint` |
| `handle_action()` | `yap/__init__.py` | Centraliza acciones + historial |
| `stream_query()` | `yap_core.py` | Generación y streaming asíncrono para interfaces gráficas |
| `main()` | `yap/__init__.py` | Loop interactivo `while True` en terminal |

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

`open_app` (abrir app whitelist) · `search` (Wikipedia API) · `webfetch` (URL directa) · `query` (LLM directo) · `pseint` (tutor PSeInt) · `super` / `super_query` (Super Yap Gradio Cloud Run, opt-in, #91).

---

## 3. Seguridad (no negociable)

### Whitelists
- **`whitelist/apps.conf`** — `Nombre:bin1,bin2` (multi-binario con fallback)
- **`whitelist/web.conf`** — dominios exactos o subdominio directo (`d == domain or domain.endswith("."+d)`)

### Reglas de código (CI verifica estrictamente)
- ❌ `shell=True`, `eval()`, `os.system()` — prohibidos
- ❌ `open()` en modo escritura fuera de paths permitidos
- ❌ `os.remove`, `shutil.rmtree` en código fuente
- ✅ Todo `subprocess.run()` debe tener `timeout=`
- ✅ Contenido webfetch limitado a 3000 chars
- ✅ Sin imports peligrosos: `socket`, `ctypes`, `pickle`, `base64`

### Acciones bloqueadas por diseño
Comandos arbitrarios · red fuera de whitelist · instalar/eliminar software · modificar archivos del sistema.

---

## 4. Ramas de configuración

| Rama | Modelo | Ctx | KV Cache | RAM | Threads |
|---|---|---|---|---|---|
| `main` | 3B Q4_K_M | 2048 (`MAX_CTX`) | FP16 | ~3.5GB | 4 |
| `lowmem` | 3B Q4_K_M | 2048 | Q8_0 | ~3.1GB | 2 |
| `ultra-lowmem` | 1B Q4_K_M | 2048 | Q8_0 | ~1.8GB | 2 |
| Super Yap (Gradio Cloud Run) | Nube (no hay 8B local) | — | — | 0 GB extra en el PC | — |

Super Yap es opt-in (`YAP_SUPER_ENABLED=1` o auto en Gradio Cloud Run): el alumno sigue en 1B/3B. Si `llama-cli` tarda 3 minutos, se pasa de tokens o hay `super on`, Yap consulta Gradio y reenvía `HISTORY`. Ver `docs/SUPER-YAP.md`.

El hook `.githooks/post-checkout` informa del cambio de modelo al hacer `git checkout`.

---

## 5. Estructura del repo

```
Yap/
├── yap.py                 # Shim de entrada (#204)
├── yap/                   # Paquete del agente (implementación en __init__.py)
├── yap_core.py            # Motor con streaming (#152)
├── yap_desktop/           # Aplicación gráfica de escritorio (PyQt6/PySide6)
├── setup.sh               # Instalador de desarrollo (compila llama.cpp)
├── build-deb.sh           # Genera yap_*.deb y yap-models-*.deb (#31)
├── packaging/             # Plantillas DEBIAN (control, postinst, prerm, postrm)
├── whitelist/
│   ├── apps.conf          # Apps permitidas
│   └── web.conf           # Dominios permitidos
├── cursos/                # JSON de cursos (FPY1101, etc.)
├── tests/                 # Suite de tests (más de 1200 pruebas)
│   ├── test_yap_security.py    # 25 pruebas dedicadas
│   ├── test_yap_functional.py  # 59 pruebas
│   ├── conftest.py             # Aísla Super Yap (YAP_SUPER_*=0)
│   └── run_tests.py            # Ejecutor: 5 archivos, chequeos, 26 requisitos
├── .githooks/post-checkout    # Hook informativo de rama
├── .github/
│   ├── workflows/              # 12 workflows (CI, A-Dev, releases, quality gates)
│   └── adev/                   # Configuración A-Dev (ver sección 7)
├── docs/                  # ROADMAP, PACKAGING, TRUNK-BASED, SECURITY-AUDIT, SUPER-YAP
└── USAGE.md              # Guía de uso
```

---

## 6. Tests

```bash
pip install pytest pytest-cov ruff==0.6.9 pyflakes==3.2.0
python3 -m pytest tests/ -v          # suite completa (sin LLM/GPU/Internet)
python3 tests/run_tests.py --report  # Reporte TXT
python3 tests/run_tests.py --vm      # Infra (solo en VM)
```

**Cobertura:** más de 1200 pruebas. `run_tests.py` ejecuta 5 archivos
(237 pruebas) + 5 chequeos de infraestructura + 5 estáticos + mapeo de 26
requisitos. Detalle en [tests/README.md](tests/README.md).

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

Cualquier agente debe leer `.github/adev/README.md` y [AGENTS.md](AGENTS.md) para ubicar contratos y mapa de módulos.

---

## 8. Flujo de trabajo (A-Dev + Yap)

1. **Leer** [AGENTS.md](AGENTS.md) y `.github/adev/README.md`.
2. **Inspeccionar** con `yap-read-only-inspection` (sin efectos).
3. **Rama fresca** por cambio: `git checkout -b fix/issue-NNN`.
4. **Commits atómicos** con Conventional Commits.
5. **Tests** locales antes de push: `pytest tests/` + `ruff format --check` + `ruff check`.
6. **PR** → workflow de revisión automática evalúa políticas Hardness.
7. **Revisión humana** por `core-devs` y merge nativo.

---

## 9. Convenciones de código

- Español en strings de usuario; español/inglés en comentarios técnicos.
- `ponytail:` prefijo en comentarios de workarounds (sin dependencias externas).
- Sin Rich/Textual — ANSI directo para TUI.
- `shutil.which()` antes de `subprocess.Popen` para apps.

---

## 10. Referencias

- [AGENTS.md](AGENTS.md) — Guía y contrato operativo principal para agentes de IA
- [A-Dev upstream](https://github.com/scanalesespinoza/adev)
- [Yap issues](https://github.com/ChincoLinux/Yap/issues)
- [llama.cpp](https://github.com/ggerganov/llama.cpp)
