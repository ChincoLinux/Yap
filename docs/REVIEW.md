# Checklist de revisión de PR

Ejecutar antes de pedir review. Es la lista mínima que el autor declara y que el
revisor verifica; la misma lista vive en la sección "Checklist previo" de
[PULL_REQUEST_TEMPLATE.md](../PULL_REQUEST_TEMPLATE.md).

## Local (obligatorio)

- [ ] **Formato:** `ruff format --check *.py yap/ tests/` → *already formatted*.
- [ ] **Lint:** `ruff check *.py yap/ tests/` → sin errores.
- [ ] **Análisis estático:** `python3 -m pyflakes *.py yap/ tests/` → sin salida.
- [ ] **Tests:** `python3 -m pytest tests/ -q` → 0 failed (los skips son pruebas que necesitan un sistema instalado).
- [ ] **Workflows:** `actionlint .github/workflows/*.yml` → sin errores de sintaxis
      (sólo si la PR toca `.github/workflows/`).
- [ ] **Scripts de shell:** `python3 -m pytest tests/test_packaging_scripts.py -q`
      → valida `sh -n`/`bash -n` con el intérprete del shebang de cada script
      (obligatorio si tocas `*.sh`, `setup.sh` o `build-deb.sh`).
- [ ] **Empaquetado:** `./build-deb.sh` genera el `.deb` sin errores
      (obligatorio si cambia `packaging/`, `setup.sh`, `yap.py`, `yap/` o `yap_core.py`).
      En un sistema real, añadir `sh packaging/test-integration-os.sh`
      (ver [docs/INTEGRATION.md](INTEGRATION.md)).

## Criterios del repositorio

- [ ] **Sin dependencias nuevas:** el código del agente (`yap.py`, el paquete `yap/`,
      `yap_core.py`) sigue siendo stdlib-only.
- [ ] **Prohibido en el código del agente** (`*.py` de la raíz y `yap/`): `shell=True`, `eval()`, `os.system()`,
      `import socket/ctypes/pickle/base64`, `open()` en modo escritura fuera de las
      rutas permitidas, `os.remove` / `shutil.rmtree`.
- [ ] **Requisito:** todo `subprocess.run()` / `Popen()` lleva `timeout=` y
      `stdin=subprocess.DEVNULL`; `shutil.which()` antes de lanzar binarios.
- [ ] **Tests:** si el cambio toca comportamiento visible, tiene test en la misma PR.
- [ ] **i18n:** texto visible al usuario → clave en `i18n/es.json` **e**
      `i18n/en.json` (`arn` cae a `es` por fallback).
- [ ] **Seguridad:** revisado por `yap-reviewer` (advisory). Si marca
      `HD-YAP-SEC-001`, verificar a mano: es frecuente el falso positivo cuando el
      patrón aparece en documentación o en tests que lo verifican ausente.
- [ ] **Whitelists:** `whitelist/*` y `cursos/*` siguen válidos.

## Trazabilidad y estilo

- [ ] **Conventional Commits** en el título: `feat:` `fix:` `docs:` `refactor:`
      `chore:` `test:` `ci:`.
- [ ] **`Closes #N`** en el cuerpo, con el issue existente y etiquetado
      (type + priority). Ver [docs/LABELS.md](LABELS.md).
- [ ] **Un solo objetivo** por PR (atomicidad A-Dev); si mezcla docs + feature, dividir.
- [ ] **Rama corta** desde `main`, sin `force push` en ramas compartidas.
- [ ] **CI verde** y ningún hilo de review sin resolver
      (`required_review_thread_resolution` está activo en `main`).
- [ ] **Aprobación humana** de `core-devs` distinta del autor; sin bypass de admin
      ([GOVERNANCE.md](../GOVERNANCE.md), [docs/TRUNK-BASED.md](TRUNK-BASED.md)).

## Después del merge

- [ ] Verificar `main` verde (`gh run list --branch main`).
- [ ] Cerrar el issue si el squash no lo cerró solo.
- [ ] Borrar la rama local y remota ya mergeada (A-Dev reglas 32/33).
