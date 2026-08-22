# Trunk-Based Development / Desarrollo basado en trunk

Este repositorio trabaja bajo **trunk-based development** como *local overlay* documentado sobre la doctrina organizacional **[A-Dev](../ADEV.md)**. Para el contexto completo de trabajo (incluyendo agentes IA), ver **[AGENTS.md](../AGENTS.md)**.

## Principios / Principles

1. `main` es la **única línea de integración**: siempre debe estar verde (CI: `.github/workflows/test.yml`) y en estado desplegable.
2. **Ramas de corta vida** (típicamente <48 horas), una por objetivo, creadas desde `main` y ligadas a un issue (`Closes #N`).
3. **Integración frecuente**: nunca mantengas ramas divergentes durante días; resuelve conflictos con **rebase** sobre `main`.
4. **Commits atómicos** con **Conventional Commits**: `feat:` `fix:` `docs:` `refactor:` `chore:` `test:` `ci:`.
5. **Todo cambio entra a `main` mediante un PR aprobado** — sin excepciones. No se permite push directo a `main`, `lowmem` o `ultra-lowmem`, ni siquiera a administradores. El bypass de admin está prohibido por doctrina del repositorio (ver [AGENTS.md](../AGENTS.md)).
6. **PR con revisión obligatoria** para todo cambio: funcionalidad, API, seguridad, infraestructura, documentación, chores. Un miembro de `core-devs` debe aprobar antes del merge.
7. **Nunca `force push`** a `main` ni a ramas compartidas.
8. Tras el merge: la rama se elimina automáticamente (`delete_branch_on_merge: true`) y se verifica el estado de `main`.
9. **Releases**: versionado y tagging manual desde `main` (ver [GOVERNANCE.md](../GOVERNANCE.md)).

## Auto-merge

El auto-merge nativo de GitHub está habilitado en el repositorio:

1. Al abrir un PR (o marcarlo ready_for_review), el auto-merge (squash) se habilita desde los settings del repo.
2. CI pasa (49+ tests + branch-check).
3. Un humano (`core-devs`) aprueba con `gh pr review <N> --approve`.
4. GitHub fusiona automáticamente (squash) si todas las condiciones de branch protection se cumplen.
5. La rama se elimina automáticamente.

El bot `yap-reviewer` (`pr-review.yml`) publica un comentario con su análisis de políticas Hardness, pero **no aprueba ni rechaza** — la decisión es siempre humana. Ver [AGENTS.md](../AGENTS.md).

## Referencias / References

- Contexto para agentes IA: [AGENTS.md](../AGENTS.md)
- Doctrina organizacional: [ADEV.md](../ADEV.md)
- Guía de contribución: [CONTRIBUTING.md](../CONTRIBUTING.md)
- Plantilla de PR: [PULL_REQUEST_TEMPLATE.md](../PULL_REQUEST_TEMPLATE.md)
- Gobernanza: [GOVERNANCE.md](../GOVERNANCE.md)
