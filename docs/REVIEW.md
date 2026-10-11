# Checklist de revisión de PR

- [ ] **Código**: pasa `flake8`/`ruff` (si existiera). No hay dependencias externas.
- [ ] **Tests**: `pytest -q` muestra `976 passed, 3 skipped`.
- [ ] **Documentación**: `README.md` enlaza a `docs/REVIEW.md` y `docs/PACKAGING.md`.
- [ ] **Empaquetado**: `build-deb.sh` genera un `.deb` sin errores.
- [ ] **Seguridad**: revisado por `yap-reviewer` (lista blanca, etc.).
- [ ] **Cambios de configuración**: `whitelist/*` y `cursos/*` permanecen válidos.
- [ ] **Historial**: mensaje de commit sigue convención Conventional Commits.
