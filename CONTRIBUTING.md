# Contributing / Contribuir

Gracias por querer contribuir a **Yap**. Este documento aplica a este repositorio y a sus copias en la organización ChincoLinux.

Gracias por contribuir / Thank you for contributing.

## Primeros pasos / Getting started

1. Lee el `README.md` y `USAGE.md` del repositorio.
2. Revisa los issues abiertos (busca etiquetas `good first issue` / `help wanted`).
3. Comunica tu intención: abre un issue o comenta en uno existente antes de trabajar.

## Flujo de trabajo / Workflow

Este repositorio trabaja bajo **trunk-based development**: ver **[docs/TRUNK-BASED.md](docs/TRUNK-BASED.md)** y **[AGENTS.md](AGENTS.md)** (contexto para agentes IA).

- La línea de integración única es `main`; siempre en verde (CI: `.github/workflows/test.yml`).
- **Ramas cortas** (idealmente <48h), una por objetivo, basadas en un issue (`Closes #N`).
- **Commits atómicos** con **Conventional Commits** (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`, `ci:`).
- **Todo cambio entra vía PR aprobado** — sin excepciones. No se permite push directo a `main`, `lowmem` o `ultra-lowmem`, ni siquiera a admins (ver `AGENTS.md` §2). El bypass de admin está prohibido por doctrina del repositorio.
- **Auto-merge nativo**: tras CI verde + approval humana, GitHub fusiona automáticamente (squash). El bot `yap-reviewer` publica análisis como comentario; la aprobación es siempre humana (`core-devs`).
- Doctrina general de la organización: **[A-Dev](ADEV.md)**.

## Reglas de calidad / Quality rules

- `main` siempre debe estar verde.
- Nada de secretos, credenciales ni datos personales en código o docs.
- Contenido comunitario bilingüe: **es** primario, **en** mirror cuando aplique.
- Resuelve conflictos con rebase sobre `main`; nunca `force push` en ramas compartidas.

## Estructura de equipos / Teams

- **`core-devs`**: mantenedores con permiso de revisión/merge.
- **`contributors`**: colaboradores activos con acceso de escritura.

## ¿Dudas? / Questions

Abre un issue en este repositorio o contacta al equipo de `core-devs`.