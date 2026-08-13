# Trunk-Based Development / Desarrollo basado en trunk

Este repositorio trabaja bajo **trunk-based development** como *local overlay* documentado sobre la doctrina organizacional **[A-Dev](https://github.com/ChincoLinux/.github/blob/main/ADEV.md)**.

## Principios / Principles

1. `main` es la **única línea de integración**: siempre debe estar verde (CI: `.github/workflows/test.yml`) y en estado desplegable.
2. **Ramas de corta vida** (típicamente <48 horas), una por objetivo, creadas desde `main` y ligadas a un issue (`Closes #N`).
3. **Integración frecuente**: nunca mantengas ramas divergentes durante días; resuelve conflictos con **rebase** sobre `main`.
4. **Commits atómicos** con **Conventional Commits**: `feat:` `fix:` `docs:` `refactor:` `chore:` `test:` `ci:`.
5. **Push directo a `main`**: permitido —en la copia personal `VECTORG99/Yap`— para cambios **pequeños y verificados** (documentación, fixes triviales, chores, formateo). Condición: ejecuta la validación más acotada que pruebe el cambio antes de empujar (en Yap: `python3 -m pytest tests/`). En la copia de la organización (`ChincoLinux/Yap`) `main` exige cambios vía PR; el push directo queda limitado al bypass de admins.
6. **PR con revisión obligatoria** para cambios con impacto: funcionalidad, API, seguridad, infraestructura, y cualquier cambio a plantillas o archivos de comunidad.
7. **Nunca `force push`** a `main` ni a ramas compartidas.
8. Tras el merge: **borra la rama** y verifica el estado de `main`.
9. **Releases**: versionado y tagging manual desde `main` (ver [GOVERNANCE.md](GOVERNANCE.md)).

## Referencias / References

- Doctrina organizacional: [A-Dev (canónico)](https://github.com/ChincoLinux/.github/blob/main/ADEV.md)
- Guía de contribución: [CONTRIBUTING.md](CONTRIBUTING.md)
- Plantilla de PR: [PULL_REQUEST_TEMPLATE.md](PULL_REQUEST_TEMPLATE.md)