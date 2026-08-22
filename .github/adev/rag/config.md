# RAG: Configuración de Yap (ChincoLinux)

> Contexto recuperable para agentes. Fuente de verdad: `yap.py`, `setup.sh`, `whitelist/`, `cursos/`, `.github/workflows/`.

---

## Variables de entorno y constantes

```python
# yap.py — constantes principales
CONFIG_DIR = "/etc/yap"
WHITELIST_APPS = f"{CONFIG_DIR}/whitelist/apps.conf"
WHITELIST_WEB = f"{CONFIG_DIR}/whitelist/web.conf"
PSEINT_DIR = f"{CONFIG_DIR}/pseint"
PSEINT_EXERCISES = f"{PSEINT_DIR}/ejercicios.conf"
PSEINT_GUIA_PDF = f"{PSEINT_DIR}/guia_ejercicios.pdf"
CURSOS_DIR = f"{CONFIG_DIR}/cursos"
PROGRESS_FILE = os.path.expanduser("~/.config/yap/progress.json")

MODEL_PATH = "/opt/yap/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf"  # CAMBIA POR RAMA
MAX_CTX = 2048          # master=4096, lowmem/ultra=2048
MAX_HISTORY = 6
```

---

## Archivos de configuración (instalados por `setup.sh`)

| Archivo | Ubicación | Formato | Propósito |
|---|---|---|---|
| `apps.conf` | `/etc/yap/whitelist/apps.conf` | `Nombre:bin1,bin2` | Apps permitidas multi-binario |
| `web.conf` | `/etc/yap/whitelist/web.conf` | `dominio` (línea) | Dominios webfetch permitidos |
| `ejercicios.conf` | `/etc/yap/pseint/ejercicios.conf` | `Titulo:Desc|Solucion` | Ejercicios PSeInt |
| `guia_ejercicios.pdf` | `/etc/yap/pseint/guia_ejercicios.pdf` | PDF | Guía visual tutorial |
| `FPY1101.json` | `/etc/yap/cursos/FPY1101.json` | JSON (ver schema) | Curso Fundamentos Programación |
| `progress.json` | `~/.config/yap/progress.json` | JSON | Progreso estudiante persistente |

---

## Esquema de curso (JSON)

```json
{
  "codigo": "FPY1101",
  "nombre": "Fundamentos de Programación",
  "horas": 126,
  "semanas": 18,
  "ras": [
    {"id": "RA1", "descripcion": "Diseña algoritmos...", "indicadores": ["IL1.1"]}
  ],
  "eas": [
    {
      "id": "EA1",
      "nombre": "Fundamentos de Algoritmos",
      "descripcion": "...",
      "horas": 35,
      "actividades": [{"orden": 1, "nombre": "Act1", "descripcion": "..."}],
      "evaluaciones": []
    }
  ],
  "evaluaciones": []
}
```

**Validación** (`_validar_curso()`): claves obligatorias en `REQUIRED_CURSO_KEYS`, `REQUIRED_RA_KEYS`, `REQUIRED_EA_KEYS`.

---

## Ramas de configuración (Git)

| Rama | MODEL_PATH | MAX_CTX | KV Cache | Flash Attn | Threads | RAM |
|---|---|---|---|---|---|---|
| `master` | 3B Q4_K_M | 4096 | FP16 | No | 4 | ~3.5GB |
| `lowmem` | 3B Q4_K_M | 2048 | Q8_0 | Sí | 2 | ~3.1GB |
| `ultra-lowmem` | 1B Q4_K_M | 2048 | Q8_0 | Sí | 2 | ~1.8GB |

**Cambio de rama:**
```bash
git checkout master        # máxima calidad
git checkout lowmem        # balanceado
git checkout ultra-lowmem  # mínima RAM
```

**Hook post-checkout** (`.githooks/post-checkout`): se ejecuta auto al `git checkout`, muestra:
- Rama anterior + modelo
- Rama actual + modelo
- Estado descarga (existe/falta)
- Modelos inactivos (no se borran)
- Próximo paso: `setup.sh` o listo

---

## Instalación (`setup.sh`)

### Fases
1. **Deps sistema**: `apt install build-essential cmake libcurl4-openssl-dev python3-pip libnotify-bin`
2. **Compila llama.cpp**: `cmake -DBUILD_SHARED_LIBS=OFF -DLLAMA_CURL=OFF -DLLAMA_CUDA=OFF -DLLAMA_METAL=OFF`
3. **Descarga modelo**: lee `MODEL_PATH` de `yap.py`, `wget` a `/opt/yap/models/`
4. **Instala configs**: copia `whitelist/`, `pseint/`, `cursos/` a `/etc/yap/`
5. **Apps sugeridas**: `libreoffice evince firefox-esr micro htop`
6. **Symlink**: `ln -sf ~/Yap/yap.py /usr/local/bin/yap`
7. **Git hooks**: `git config core.hooksPath .githooks`

### Actualización
```bash
cd ~/Yap
git pull  # symlink apunta al repo, no requiere reinstalar
```

---

## Whitelist apps.conf (formato)

```
# Comentario
NombreVisible:binario1,binario2,binario3
```

- Clave: nombre visible (minúsculas para lookup)
- Valor: lista de binarios separados por coma, orden = prioridad fallback
- `shutil.which()` prueba en orden hasta encontrar uno

**Ejemplo actual:**
```
LibreOffice:libreoffice
Evince:evince
Firefox:firefox-esr,firefox
Micro:micro
Htop:htop
PSeInt:pseint
```

---

## Whitelist web.conf (formato)

```
# Comentario
dominio.com
otro.dominio.org
```

- Un dominio por línea
- Comentarios con `#` ignorados
- Validación: `dominio == permitido OR dominio.endswith("." + permitido)`

**Ejemplo actual:**
```
wikipedia.org
debian.org
```

---

## CI/CD (`.github/workflows/test.yml`)

### Jobs

| Job | Qué hace | Rama |
|---|---|---|
| `unit-tests` | 81 tests pytest + verif. estática (`grep shell=True/eval/os.system`) + validación whitelists | main, lowmem, ultra-lowmem |
| `branch-check` | Verifica `MODEL_PATH` en cada rama apunta al modelo correcto | main, lowmem, ultra-lowmem |
| `results` | Resumen pipeline (siempre corre) | main, lowmem, ultra-lowmem |

### Triggers
- `push` a `main`, `lowmem`, `ultra-lowmem`
- `pull_request` a `main`, `lowmem`, `ultra-lowmem`

### Matriz
- Python 3.12
- Ubuntu latest

---

## Auto-merge (`.github/workflows/auto-merge.yml`)

```yaml
on:
  pull_request_review:
    types: [submitted]
  check_suite:
    types: [completed]

jobs:
  auto-merge:
    if: github.event.review.state == 'approved' && github.event.check_suite.conclusion == 'success'
    steps:
      - gh pr merge --auto --squash
```

**Condiciones:**
- Review = `APPROVED` (de `yap-reviewer` o humano)
- CI = `success`
- No draft, no WIP

---

## Fallback merge (`.github/workflows/fallback-merge.yml`)

Si auto-merge falla (conflictos, etc.), intenta merge manual con rebase.

---

## Auto-release (`.github/workflows/auto-release.yml`)

En merge a `main`:
- Bump version (semver patch)
- Genera changelog
- Crea release GitHub

---

## Project board automation (`.github/workflows/auto-add-to-project.yml`)

Añade PRs/Issues automáticamente al project board de ChincoLinux.

---

## Weekly sprint assignment (`.github/workflows/weekly-sprint-assignment.yml`)

Asigna issues a sprint semanal basado en labels/milestones.

---

## Referencias de código

- `setup.sh` — instalador completo (lee `MODEL_PATH` de `yap.py`)
- `yap.py:16-23` — constantes de paths
- `yap.py:79-81` — `MODEL_PATH`, `MAX_CTX`, `MAX_HISTORY`
- `.github/workflows/*.yml` — pipelines completos