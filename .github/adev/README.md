# .github/adev/ — Configuración A-Dev para Yap

> **Punto de entrada para agentes:** Cualquier agente que trabaje en este repositorio debe leer este archivo **en el primer prompt** para localizar todas las configuraciones, agentes, RAG y políticas.

---

## Rutas canónicas (siempre relativas a la raíz del repo)

| Tipo | Ruta | Descripción |
|---|---|---|
| **Agentes** | `.github/adev/agents/` | Definiciones de agentes (ej. `yap-reviewer.md`) |
| **RAG** | `.github/adev/rag/` | Contexto recuperable: `architecture.md`, `security.md`, `config.md` |
| **Políticas** | `.github/adev/policies/` | JSON schemas `policy-schema.json` (Hardness) |
| **Skills** | `.github/adev/skills/` | Skills A-Dev (ej. `yap-read-only-inspection/`) |

---

## Inicio rápido para agente

```bash
# 1. Leer doctrina y políticas locales
cat .github/adev/ADEV.md              # Doctrina (espejo upstream)
cat .github/adev/policies/*.json      # Políticas Hardness

# 2. Localizar skill de inspección (R0)
cat .github/adev/skills/yap-read-only-inspection/SKILL.md

# 3. Leer contexto RAG necesario
cat .github/adev/rag/architecture.md
cat .github/adev/rag/security.md
cat .github/adev/rag/config.md

# 4. Entender agente revisor de PRs
cat .github/adev/agents/yap-reviewer.md
```

---

## Políticas vigentes (Hardness)

| ID | Nivel | Descripción |
|---|---|---|
| `HD-YAP-SEC-001` | MUST | Whitelists obligatorias — apps y dominios validados antes de ejecutar |
| `HD-YAP-TEST-001` | MUST | 81 tests CI deben pasar (25 seg + 56 func) |
| `HD-YAP-BRANCH-001` | SHOULD | Rama fresca por cambio, commits Conventional, PR atómico |

Ver `.github/adev/policies/*.json` para estructura completa.

---

## Skills disponibles

| Skill | Trigger | Efecto |
|---|---|---|
| `yap-read-only-inspection` | `inspeccionar`, `auditar`, `resumir`, `comparar`, `localizar` | R0 — solo lectura, evidencia explícita |

---

## Agente revisor de PRs

`yap-reviewer.md` implementa revisión automática con:
- Verificación de políticas Hardness
- Evaluación de tests (HD-YAP-TEST-001)
- Comprobación de seguridad (HD-YAP-SEC-001)
- Decisión: **Approve** si todo pasa, **Request Changes** si falla algo

---

## Espejo upstream

La doctrina completa está en `ADEV.md` (raíz del repo) y en el upstream:
- https://github.com/scanalesespinoza/adev
- `framework/hardness/` — modelo de políticas, precedencia, skills

---

## Actualización

Si añades políticas/skills/RAG/agentes:
1. Actualiza este `README.md` (índice)
2. Actualiza `CLAUDE.md` (sección 7)
3. Sigue flujo A-Dev: rama → PR → tests → auto-merge
