# Changelog

All notable changes to Yap are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Control de sesiones dentro del agente (#21): crear, pausar, retomar, cerrar y
  listar sesiones, con límite de 3 abiertas, prompt marcado con la sesión activa
  y archivado en el historial al cerrar
- Evaluación automática de actividades de EA con feedback del LLM (#23)
- Tipos `respuesta_libre`, `codigo_pseint`, `opcion_multiple` y `completar` en el JSON del curso
- `progress.json` guarda puntaje, intentos y fecha de aprobación; máximo 3 intentos por actividad
- `yap progreso` muestra % completado, promedio, reprobadas y nota chilena (1.0-7.0)
- CI Quality Suite adaptada de Homedir (os-santiago/homedir): `pr-quality-suite.yml` (ruff style + pyflakes static + pytest coverage + pip-audit deps + arch validation), `pr-traceability-check.yml` (verifica `Closes #N` en cada PR), `pr-state-labeler.yml` (auto-label `pr:needs-review`/`pr:approved`/etc.), `quality-gates.yml` (CodeQL Python + TruffleHog secret scan + dependency review), `pr-validation.yml` (build & verify + smoke test CLI)
- Scripts de CI: `scripts/ci/check_pr_traceability.py`, `scripts/ci/label_pr_state.py`, `scripts/ci/pr_preflight.sh`
- Auto-asignación semanal de issues al equipo
- Protección de rama main (sin push directo, sin bypass de admin)
- A-Dev Hardness framework integration (políticas, skills, agentes, RAG)
- `AGENTS.md`: guía para agentes IA (estilo Homedir) con labels, workflows, convenciones

### Changed
- Post-checkout hook no aborta el checkout de ramas
- README actualizado con URL correcta del repositorio
- `pr-review.yml`: bot `yap-reviewer` ahora solo publica comentarios (advisory), no aprueba ni rechaza
- Auto-merge nativo de GitHub (squash) habilitado desde settings del repo (sin workflow dedicado)
- Docs alineadas con modelo Homedir: todo cambio vía PR, sin push directo, sin bypass de admin

### Removed
- `fallback-merge.yml`: merge sin branch protection (peligroso)
- `auto-merge.yml`: workflow dedicado de auto-merge (reemplazado por auto-merge nativo de GitHub)

### Fixed
- `nota_chilena()` no redondea puntajes en [59.1, 60) a 4.0
- Fallback de evaluación trata "no es correcto" / "no esta correcto" como reprobado
- Parser JSON reconcilia `aprobado` y `puntaje` para que no se apruebe con 2.0 ni se repruebe con nota de aprobación
- setup.sh lee VERSION despues de definir SCRIPT_DIR
- auto-release.yml importa os al actualizar el CHANGELOG
- fallback-merge.yml eliminado: mergeaba PRs no relacionadas y aceptaba aprobaciones obsoletas
- setup.sh no falla cuando yap-agent.md no existe
- Path traversal vulnerability en domain whitelist (#1)
- Conversation history and context management (#2)
- Graceful handling of blocked apps (#3)

## [1.0.0-beta] - 2026-06-17

### Added
- Agente IA local para entornos educativos con recursos limitados
- Basado en Llama 3.2 Instruct, ejecución CPU-only
- Soporte de 3 a 8 GB de RAM media
- TUI con interfaz ANSI
- Sistema de cursos configurable
- Curso FPY1101 — guía de aprendizaje integrada
- Capa de confirmación humana para acciones sensibles (#12)
- Historial persistente entre sesiones (#13)
- Integración con AppArmor (#14)
- Auditoría de seguridad post-talleres formativos (#15)

## [1.0.0-beta] - 2026-08-21

### Added
- A-Dev Hardness framework integration
  - Políticas: HD-YAP-SEC-001 (MUST), HD-YAP-TEST-001 (MUST), HD-YAP-BRANCH-001 (SHOULD)
  - Skill: yap-read-only-inspection (R0)
  - Agente: yap-reviewer (PR review automático)
  - RAG: architecture.md, security.md, config.md
- CLAUDE.md documentación completa del proyecto
- Workflow pr-review.yml para revisión automática A-Dev
- VERSION para versionado semver

### Changed
- Integración completa con doctrina A-Dev upstream

### Fixed
