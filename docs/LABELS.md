# Guía de labels / Label guide

Referencia única de etiquetas de este repositorio (issue y PR). Fuente:
[#75](https://github.com/ChincoLinux/Yap/issues/75). Doctrina asociada:
[ADEV.md](../ADEV.md), [AGENTS.md](../AGENTS.md),
[docs/TRUNK-BASED.md](TRUNK-BASED.md).

## Labels de issue (se aplican manualmente)

### Tipo (exactamente una)

| Label | Uso |
|---|---|
| `bug` | Algo no funciona |
| `enhancement` / `feature-request` | Nueva feature o mejora |
| `documentation` | Trabajo de documentación |
| `question` | Pregunta sobre el proyecto |
| `platform-maintenance` | Infraestructura/plataforma |
| `test` | Trabajo de pruebas |

### Prioridad (exactamente una)

| Label | Uso |
|---|---|
| `priority:P0` | Crítico, atención inmediata |
| `priority:P1` | Alta prioridad |
| `priority:P2` | Prioridad media |
| `priority:P3` | Baja prioridad |

### Estado

| Label | Uso |
|---|---|
| `good first issue` / `buen primer issue` | Apto para newcomers |
| `help wanted` / `Se necesita ayuda` | Requiere atención extra |
| `needs-human` | Requiere decisión humana |
| `cloud-suspended` | Suspendido por decisión económica (nube). **No se trabaja** |

### Resolución

| Label | Uso |
|---|---|
| `duplicate` | Ya existe |
| `invalid` / `no valido` | No procede |
| `wontfix` / `no solucionar` | No se trabajará |

## Labels de PR

### Estado del PR (auto-asignadas por `pr-state-labeler.yml` — NO aplicar a mano)

| Label | Significado |
|---|---|
| `pr:draft` | PR en draft / WIP |
| `pr:checks-pending` | CI corriendo |
| `pr:checks-failed` | CI fallando |
| `pr:needs-review` | CI verde, listo para review |
| `pr:changes-requested` | Mantenedor pidiendo cambios |
| `pr:approved` | Approval humana recibida |
| `pr:merged` | PR mergeado |
| `pr:blocked` | Bloqueado: conflictos, stale, etc. |

### Riesgo del PR (se aplican manualmente, exactamente una)

| Label | Tipo de cambio | Min approvals |
|---|---|---|
| `pr:risk-low` | Docs, typos, config | 1 |
| `pr:risk-medium` | Features, refactors, nuevas deps | 2 (1 code owner) |
| `pr:risk-high` | Seguridad, breaking changes | 2 (code owners + security) |
| `pr:risk-critical` | Auth, encryption, financial | 3 (all + security) |

> **Nota sobre approvals:** la configuración actual del repo
> (`branch protection` + ruleset `main-protection`) exige
> `required_approving_review_count: 0` y **sí** exige
> `required_review_thread_resolution: true`. Las approvals siguen siendo
> esperadas por doctrina (`GOVERNANCE.md`, `docs/TRUNK-BASED.md`): nadie
> aprueba su propio PR y no se usa bypass de admin. Que la protección técnica
> no exija approval es una **brecha conocida**; subirla a 1 es decisión de
> `core-devs`.

### Self-attestation (se aplican manualmente)

| Label | Significado |
|---|---|
| `pr:traceability-ok` | `Closes #N` presente y el issue existe con type + priority |
| `pr:tests-ok` | Tests añadidos/actualizados |
| `pr:i18n-ok` | i18n completo (ES + EN) para cambios visibles al usuario |
| `pr:acceptance-ok` | Criterios de aceptación del issue vinculados cumplidos |

### Labels de sistemas externos (auto-asignadas)

| Label | Sistema |
|---|---|
| `ai-sdlc-assist`, `ai-sdlc-track`, `ready-to-implement` | AI SDLC |
| `wos-review` | WOS delegation hook |
| `scc-*` (`scc-approved`, `scc-failing-checks`, `scc-merged`, `scc-under-review`, `scc-waiting-checks`), `wip-pr` | SCC |

> Si los sistemas externos dejan de usarse, procede eliminar sus labels para
> reducir ruido (issue aparte, decisión de `core-devs`).

## Regla de trazabilidad

Todo issue y toda PR deben estar enlazados entre sí: la PR declara
`Closes #N` y el issue recibe comentario con la PR. El bot `yap-reviewer`
publica análisis de las políticas Hardness (`HD-YAP-*`) como comentario
**advisory**; la aprobación final es siempre humana (`core-devs`).
