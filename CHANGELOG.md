# Changelog

All notable changes to Yap are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Sistema de ejercicios interactivos con validación automática (#27): formato v2 de `ejercicios.conf`, 4 tipos, pistas de 3 niveles, `yap ejercicios`, progreso en `progress.json` e integración con EAs vía `ejercicio_id`
- Auto-asignación semanal de issues al equipo
- Workflow de auto-merge cuando PR es aprobada y CI pasa
- Protección de rama main (sin push directo, requiere approval)
- A-Dev Hardness framework integration (políticas, skills, agentes, RAG)

### Changed
- Post-checkout hook no aborta el checkout de ramas
- README actualizado con URL correcta del repositorio

### Fixed
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
