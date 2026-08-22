# AGENTS.md — Yap (ChincoLinux)

> **Lectura obligatoria para todo agente IA (Devin, Claude, Copilot, etc.) antes de operar en este repositorio.**
> Este archivo es el punto de entrada canónico del contexto de trabajo. complementa, no reemplaza, `ADEV.md` (doctrina) y `CLAUDE.md` (arquitectura técnica).

---

## 1. Identidad del proyecto

**Yap** es un asistente IA local, CPU-only, para entornos educativos con recursos limitados (ChincoLinux / Debian 13). Ver `CLAUDE.md` para arquitectura detallada.

| Atributo | Valor |
|---|---|
| Repositorio | `ChincoLinux/Yap` (organización) |
| Fork de trabajo | `VECTORG99/Yap` |
| Lenguaje | Python 3.12 |
| Archivo principal | `yap.py` (~1253 líneas) |
| CI | `.github/workflows/test.yml` — 49+ tests, sin LLM/GPU/Internet |
| Licencia | MIT |

---

## 2. Flujo de trabajo: Trunk-Based Development (NO NEGOCIABLE)

Este repositorio opera bajo **Trunk-Based Development (TBD)** como overlay local sobre la doctrina [A-Dev](ADEV.md).

### Regla fundamental

> **Todo cambio entra a `main` mediante un Pull Request aprobado. No existen excepciones.**

- ❌ **Prohibido el push directo a `main`**, `lowmem` o `ultra-lowmem`.
- ❌ **Prohibido el bypass de admin** para saltarse branch protection. Aunque GitHub lo permita técnicamente (`enforce_admins`), la doctrina del repositorio lo prohíbe. Si eres admin y necesitas merge, pide approval a otro miembro de `core-devs`.
- ✅ **Todo cambio** —sin importar tamaño— pasa por: rama fresca → PR → CI verde → approval humana → merge (squash).
- ✅ **Auto-merge nativo** se activa tras approval + CI verde. El bot `yap-reviewer` publica comentarios de análisis pero **no aprueba**; la aprobación es siempre humana.

### Ciclo de vida de un cambio

```
issue → rama fresca (feat/fix/docs/...) → commits atómicos → PR (Closes #N)
  → CI verde (49+ tests) → yap-reviewer comenta → approval humana (core-devs)
  → auto-merge (squash) → branch eliminada → verificar main verde
```

### Ramas

| Rama | Propósito | Protegida |
|---|---|---|
| `main` | Línea de integración única, siempre verde | ✅ |
| `lowmem` | Configuración de memoria reducida (3B Q4_K_M, ctx 2048) | ✅ |
| `ultra-lowmem` | Configuración de memoria mínima (1B Q4_K_M, ctx 2048) | ✅ |

- Las ramas de feature son **cortas** (<48h ideal), una por objetivo, basadas en `main`.
- Commits con **Conventional Commits**: `feat:` `fix:` `docs:` `refactor:` `chore:` `test:` `ci:`.
- Resuelve conflictos con **rebase** sobre `main`. Nunca `force push` a ramas compartidas.
- Tras merge: la rama se elimina automáticamente (`delete_branch_on_merge: true`).

### Naming de ramas

```
feat/<número-issue>-<descripción-corta>    # ej: feat/38-telemetria
fix/<número-issue>-<descripción-corta>     # ej: fix/15-path-traversal
docs/<número-issue>-<descripción-corta>    # ej: docs/35-deploy-admin
```

---

## 3. Limitaciones de A-Dev y del bot reviewer (LEER ANTES DE TOCAR CI)

### `GITHUB_TOKEN` no puede aprobar PRs

GitHub prohíbe que el `GITHUB_TOKEN` de un workflow emita reviews de tipo `APPROVE`. Esto es una **limitación de plataforma**, no un bug.

**Consecuencia:**
- El workflow `pr-review.yml` (bot `yap-reviewer`) **solo publica comentarios** con su análisis. Nunca aprueba.
- La aprobación es **siempre humana** (un miembro de `core-devs` ejecuta `gh pr review <N> --approve`).
- El bot puede emitir `REQUEST_CHANGES` (eso sí está permitido), pero los `CHANGES_REQUESTED` del bot son **advisory** — no bloquean el merge por sí solos. La decisión final es humana.

### Auto-merge nativo

El auto-merge se habilita con `GITHUB_TOKEN` (no requiere PAT ni App dedicada):

1. PR abierto/ready_for_review → `auto-merge.yml` habilita auto-merge (squash) en el PR.
2. CI pasa (49+ tests + branch-check).
3. Humano aprueba (`gh pr review --approve`).
4. GitHub fusiona automáticamente (squash) si todas las condiciones de branch protection se cumplen.
5. La rama se elimina automáticamente.

### Políticas Hardness (`.github/adev/policies/`)

| Política | Nivel | Qué verifica |
|---|---|---|
| `HD-YAP-SEC-001` | MUST | No `shell=True`, `eval()`, `os.system()`, imports prohibidos (`socket`, `ctypes`, `pickle`, `base64`) |
| `HD-YAP-TEST-001` | MUST | CI verde (49+ tests), cero regresiones |
| `HD-YAP-BRANCH-001` | SHOULD | Rama sigue Conventional Commits, PR atómico, no push directo a main |

El bot evalúa estas políticas en cada PR y comenta el resultado. Si una MUST falla, el bot emite `REQUEST_CHANGES` (advisory). La aprobación humana final debe respetar el veredicto del bot.

### Falsos positivos conocidos del bot

El bot busca patrones prohibidos como **substring en el diff completo**. Esto genera falsos positivos cuando:
- El diff menciona `shell=True` en **comentarios o documentación** (ej: README que documenta la verificación estática).
- Tests verifican que `shell=True` **no existe** (el string aparece en el test que lo niega).

Ante un `CHANGES_REQUESTED` del bot, **verificar manualmente** si el patrón está en código ejecutable o en texto/documentación antes de bloquear.

---

## 4. Seguridad (no negociable)

Ver `CLAUDE.md` §3 para detalles completos. Resumen:

- ❌ `shell=True`, `eval()`, `os.system()` — prohibidos en `yap.py`
- ❌ `import socket`, `ctypes`, `pickle`, `base64` — prohibidos
- ❌ `open()` en modo escritura fuera de paths permitidos
- ❌ `os.remove`, `shutil.rmtree` en código fuente
- ✅ Todo `subprocess.run()` / `Popen()` debe tener `timeout=`
- ✅ Contenido webfetch limitado a 3000 chars
- ✅ Whitelists: `whitelist/apps.conf` (binarios) y `whitelist/web.conf` (dominios)

---

## 5. Contexto para agentes IA (Devin, Claude, etc.)

### Antes de empezar a trabajar

1. **Lee este archivo** (`AGENTS.md`) — contexto de trabajo y reglas TBD.
2. **Lee `ADEV.md`** — doctrina operacional (47 reglas + colaboración multi-agente).
3. **Lee `CLAUDE.md`** — arquitectura técnica, funciones clave, constantes críticas.
4. **Lee `.github/adev/policies/*.json`** — políticas Hardness vigentes.
5. **Verifica estado**: `git status`, `git log --oneline -5`, `gh pr list --repo ChincoLinux/Yap`.

### Al hacer cambios

1. **Crea una rama fresca** desde `main`: `git checkout main && git pull && git checkout -b feat/<issue>-<desc>`.
2. **Un issue, un PR** — no mezcles objetivos. Si aparece trabajo adicional, ábrelo como issue nuevo.
3. **Commits atómicos** con Conventional Commits.
4. **Ejecuta tests** antes de push: `python3 -m pytest tests/ -v`.
5. **Abre el PR** con `Closes #N` en la descripción.
6. **No apruebes tu propio PR** — pide review a otro miembro de `core-devs`.
7. **No hagas merge sin approval** — aunque tengas permisos de admin, la doctrina lo prohíbe.
8. **No hagas force push** a ramas compartidas.
9. **Tras merge**: verifica que `main` está verde, la rama se eliminó.

### Multi-agente

Si otro agente está trabajando en el repo:
- `git fetch` antes de empezar.
- No edites archivos que otro agente está modificando sin coordinación explícita.
- Comunica estado en commits, PRs y handoffs.

---

## 6. Comandos útiles

```bash
# Clonar y configurar
git clone https://github.com/ChincoLinux/Yap.git
cd Yap

# Crear rama para un issue
git checkout main && git pull origin main
git checkout -b feat/38-telemetria

# Ejecutar tests
python3 -m pytest tests/ -v

# Abrir PR
gh pr create --repo ChincoLinux/Yap --title "feat: telemetría local anónima" --body "Closes #38"

# Revisar un PR
gh pr view 58 --repo ChincoLinux/Yap
gh pr diff 58 --repo ChincoLinux/Yap

# Aprobar un PR (solo core-devs, no auto-aprobar)
gh pr review 58 --repo ChincoLinux/Yap --approve --body "Code review OK. CI verde, políticas A-Dev cumplidas."

# Request changes
gh pr review 58 --repo ChincoLinux/Yap --request-changes --body "Issues: ..."

# Re-run del bot reviewer
gh workflow run pr-review.yml --repo ChincoLinux/Yap -f pr_number=58
```

---

## 7. Estructura del repositorio

```
Yap/
├── AGENTS.md              # ESTE ARCHIVO — contexto para agentes IA
├── ADEV.md                # Doctrina A-Dev (upstream)
├── CLAUDE.md              # Arquitectura técnica detallada
├── CONTRIBUTING.md        # Guía de contribución
├── GOVERNANCE.md          # Gobernanza de la organización
├── yap.py                 # Agente principal (~1253 líneas)
├── setup.sh               # Instalador
├── whitelist/             # Apps y dominios permitidos
├── cursos/                # JSON de cursos (FPY1101, etc.)
├── tests/                 # Suite de tests (49+)
├── docs/                  # ROADMAP, TRUNK-BASED, SECURITY-AUDIT
├── .github/
│   ├── workflows/         # CI, auto-merge, pr-review, auto-release
│   ├── adev/              # Políticas Hardness + agente reviewer
│   └── ISSUE_TEMPLATE/    # Plantillas de issues
├── .githooks/             # Hook post-checkout (cambio de modelo)
└── apparmor/              # Perfil AppArmor
```

---

## 8. Referencias

- [A-Dev](https://github.com/scanalesespinoza/adev) — doctrina upstream
- [Trunk-Based Development](https://trunkbaseddevelopment.com/) — referencia externa
- `docs/TRUNK-BASED.md` — overlay local TBD
- `CLAUDE.md` — arquitectura técnica
- `.github/adev/agents/yap-reviewer.md` — contrato del bot reviewer
