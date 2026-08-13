# Pull Request / Solicitación de cambios

> Trabajamos bajo **trunk-based development** ([docs/TRUNK-BASED.md](docs/TRUNK-BASED.md)), con la doctrina organizacional **[A-Dev](https://github.com/ChincoLinux/.github/blob/main/ADEV.md)**: ramas cortas, integración frecuente a `main`, PRs atómicas, commits convencionales y evidencia obligatoria.

## Checklist previo (obligatorio) / Prior checklist (required)

- [ ] La PR resuelve **un solo objetivo** (atomicidad adev). Si mezcla refactor/feature/docs, dividir.
- [ ] Rama corta basada en `main` (trunk-based, idealmente <48h), sin `force push` en la rama.
- [ ] El título usa **Conventional Commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`, `ci:`.
- [ ] Referencia el issue que resuelve: `Closes #N`.
- [ ] Validación ejecutada y evidenciada (check mínima que pruebe el cambio; en Yap: `python3 -m pytest tests/`).
- [ ] Sin secretos, credenciales ni datos personales en el diff.
- [ ] Contenido comunitario bilingüe cuando aplica (es primario / en mirror).

## Descripción

### Objetivo / Objective
<!-- Qué resuelve esta PR -->

### Cambios / Changes
<!-- Lista breve y puntual -->

### Validación realizada / Validation
<!-- Qué se ejecutó y su resultado -->

## Revisión esperada / Review expectations

Un mantenedor de `core-devs` debe aprobar antes del merge. Si la PR es grande, propón dividirla. Los cambios pequeños y verificados pueden integrarse directo a `main` (ver [docs/TRUNK-BASED.md](docs/TRUNK-BASED.md)).