# AI Agents Guide for Yap

This guide helps AI agents (like Claude Code, Devin, etc.) understand how to collaborate effectively on Yap.

## Project Context

**Yap** is a local AI assistant, CPU-only, for educational environments with limited resources (ChincoLinux / Debian 13).

- **Tech Stack**: Python 3.12, llama.cpp (static link, CPU-only), Llama 3.2 Instruct (GGUF Q4_K_M)
- **Language**: Spanish (user-facing), Spanish/English (technical comments)
- **License**: MIT
- **Philosophy**: Educational, privacy-first, offline-capable, stdlib-only (no pip dependencies)

| Atributo | Valor |
|---|---|
| Repositorio | `ChincoLinux/Yap` (organización) |
| Fork de trabajo | `VECTORG99/Yap` |
| Archivo principal | `yap.py` (~1253 líneas) |
| CI | `.github/workflows/test.yml` — 49+ tests, sin LLM/GPU/Internet |
| Modelo | Llama 3.2 1B/3B Instruct (Q4_K_M, CPU-only) |

## Labels Guide for AI Agents

### Issue Labels

**Type Labels:**
- `bug` - Something isn't working
- `enhancement` / `feature-request` - New feature or enhancement requests
- `documentation` - Documentation work
- `question` - Questions about the project
- `platform-maintenance` - Infrastructure/platform work

**Priority Labels:**
- `priority:P0` - Critical, immediate attention required
- `priority:P1` - High priority
- `priority:P2` - Medium priority
- `priority:P3` - Low priority

**Status Labels:**
- `good first issue` / `buen primer issue` - Good for newcomers
- `help wanted` / `Se necesita ayuda` - Extra attention needed
- `needs-human` - Requires human decision or intervention

**Resolution Labels:**
- `duplicate` - Issue/PR already exists
- `invalid` / `no valido` - Doesn't seem right
- `wontfix` / `no solucionar` - Won't be worked on

### Pull Request Labels

**PR State Labels** (managed by `pr-state-labeler.yml` automation — do NOT apply manually):

These labels track the PR lifecycle state. They are mutually exclusive and auto-assigned based on CI checks + human review status:

- `pr:draft` - PR is draft / work in progress
- `pr:checks-pending` - CI checks are running
- `pr:checks-failed` - CI checks are failing
- `pr:needs-review` - CI green, ready for maintainer review
- `pr:changes-requested` - Maintainer requested changes
- `pr:approved` - Required human approvals met
- `pr:merged` - PR has been merged
- `pr:blocked` - Blocked: merge conflicts, stale, or other blocker

## Autonomous AI Agent Contract

### When creating issues:
1. Add appropriate **type label** (`bug`, `enhancement`, `documentation`, etc.)
2. Add **priority label** if urgent (`priority:P0`, `priority:P1`)
3. Add `needs-human` if a human decision is required

### When creating PRs:
1. **Always** reference the issue: `Closes #XXX` or `Fixes #XXX`
   - **IMPORTANT**: When closing multiple issues, repeat the keyword per issue:
     `Closes #10` on one line, `Closes #11` on the next. Do NOT use `Closes #10, #11`
     — GitHub only auto-closes the first issue in a comma-separated list without
     repeated keywords.
2. **MUST** use [conventional commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, etc.
3. **MUST** use branch naming: `feat/issue-XXX-description`, `fix/issue-XXX-description`, `docs/issue-XXX-description`.
4. **MUST** write PR title and body — body must include the checklist from `PULL_REQUEST_TEMPLATE.md`.
5. **MUST** run `python3 -m pytest tests/ -v` before pushing. CI must be green.
6. **Do NOT** approve your own PR — ask another member of `core-devs` to review.

### When receiving review feedback:
1. Address ALL requested changes
2. Push changes (don't force push unless necessary)
3. Comment when changes are complete
4. Request re-review if needed

## Common Workflows

### Issue → PR → Merge Workflow

1. **Issue created** with type and priority labels
2. **Developer claims** (comment on issue or open draft PR)
3. **PR created** with `Closes #XXX`, conventional commit title
4. **CI checks run** automatically (49+ tests + branch-check + A-Dev Hardness review)
5. **Code review** by maintainers or AI (advisory comments from `yap-reviewer` bot)
6. **Changes addressed** if requested
7. **Merge** when approved and checks pass (auto-merge native, squash)
8. **Branch deleted** automatically after merge

### Branch Protection

- `main` is protected with `enforce_admins: true` — no admin bypass
- `required_reviews: 0` — no mandatory approval count (human review still expected per A-Dev doctrine)
- `allow_force_pushes: false`
- Auto-merge (squash) enabled via GitHub native settings

### Bot Reviewer (`yap-reviewer`)

The `pr-review.yml` workflow runs the `yap-reviewer` bot on every PR. The bot:
- Evaluates A-Dev Hardness policies (`HD-YAP-SEC-001`, `HD-YAP-TEST-001`, `HD-YAP-BRANCH-001`)
- Posts an **advisory comment** with its analysis
- **Does NOT approve or reject** — the decision is always human

**Known false positives:** The bot searches for forbidden patterns (`shell=True`, `eval()`, etc.) as substrings in the full diff. This can trigger false positives when:
- The diff mentions `shell=True` in **comments or documentation**
- Tests verify that `shell=True` **does not exist** (the string appears in the test that denies it)

Always verify manually if a flagged pattern is in executable code or in text/documentation before blocking.

## Code Conventions

### Commit Messages

- Use **Conventional Commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`, `ci:`
- Reference the issue: `feat: add telemetry (#38)`
- Spanish in user-facing strings; Spanish/English in technical comments
- `ponytail:` prefix in comments for workarounds (no external dependencies)

### Code Style

- Python 3.12, stdlib-only (no pip dependencies in `yap.py`)
- `shutil.which()` before `subprocess.Popen` for app launching
- All `subprocess.run()` / `Popen()` must have `timeout=`
- No `shell=True`, `eval()`, `os.system()` — prohibited
- No `import socket`, `ctypes`, `pickle`, `base64` — prohibited
- ANSI direct for TUI (no Rich/Textual)
- Whitelists: `whitelist/apps.conf` (binaries) and `whitelist/web.conf` (domains)

## File Locations

```
Yap/
├── AGENTS.md              # ESTE ARCHIVO — guía para agentes IA
├── ADEV.md                # Doctrina A-Dev (upstream)
├── CLAUDE.md              # Arquitectura técnica detallada
├── CONTRIBUTING.md        # Guía de contribución
├── GOVERNANCE.md          # Gobernanza de la organización
├── yap.py                 # Agente principal (~1253 líneas)
├── setup.sh               # Instalador (compila llama.cpp, descarga modelo)
├── deploy-yap.sh          # Despliegue masivo por SSH
├── i18n/                  # Traducciones JSON (es, en, arn)
├── whitelist/             # Apps y dominios permitidos
│   ├── apps.conf
│   └── web.conf
├── cursos/                # JSON de cursos (FPY1101, etc.)
├── tests/                 # Suite de tests (49+)
├── docs/                  # ROADMAP, TRUNK-BASED, DEPLOY, SECURITY-AUDIT
├── .github/
│   ├── workflows/         # CI, pr-review, test, auto-release
│   ├── adev/              # Políticas Hardness + agente reviewer
│   └── ISSUE_TEMPLATE/    # Plantillas de issues
├── .githooks/             # Hook post-checkout (cambio de modelo)
└── apparmor/              # Perfil AppArmor
```

### A-Dev Configuration (`.github/adev/`)

- **Policies**: `.github/adev/policies/HD-YAP-*.json`
- **Agent contract**: `.github/adev/agents/yap-reviewer.md`
- **RAG context**: `.github/adev/rag/` (architecture, security, config)
- **Skills**: `.github/adev/skills/`

## Testing

```bash
# Run all tests (49+, no LLM/GPU/Internet needed)
python3 -m pytest tests/ -v

# Run with coverage
python3 -m pytest tests/ -v --cov=yap --cov-report=term-missing

# Run specific test file
python3 -m pytest tests/test_yap_security.py -v

# Run with report
python3 tests/run_tests.py --report
```

**Coverage:** 25 security + 56 functional + 5 infra = 49+ tests ✓

## Security Considerations

### Whitelists (no negociable)

- **`whitelist/apps.conf`** — `Nombre:bin1,bin2` (multi-binario con fallback)
- **`whitelist/web.conf`** — dominios exactos o subdominio directo (`d == domain or domain.endswith("."+d)`)

### Prohibited in `yap.py`

- `shell=True`, `eval()`, `os.system()`
- `import socket`, `ctypes`, `pickle`, `base64`
- `open()` en modo escritura fuera de paths permitidos
- `os.remove`, `shutil.rmtree` en código fuente

### Required

- All `subprocess.run()` / `Popen()` must have `timeout=`
- Webfetch content limited to 3000 chars
- `shutil.which()` validation before launching apps

### Blocked by design

Arbitrary commands · network outside whitelist · install/remove software · modify system files.

## Resources

- [A-Dev](https://github.com/scanalesespinoza/adev) — doctrina upstream
- [Trunk-Based Development](https://trunkbaseddevelopment.com/) — referencia externa
- `docs/TRUNK-BASED.md` — overlay local TBD
- `CLAUDE.md` — arquitectura técnica
- `.github/adev/agents/yap-reviewer.md` — contrato del bot reviewer

## Questions?

- Open an issue with the `question` label
- Contact `core-devs` via GitHub
