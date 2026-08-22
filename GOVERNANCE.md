# Governanza de la Organización / Organization Governance

Este documento define el modelo de gobernanza de **ChincoLinux**. Toda la operatoria técnica sigue la doctrina **[A-Dev](ADEV.md)**.

> **Overlay local de este repositorio**: Yap declara **trunk-based development** como flujo de trabajo (ver [docs/TRUNK-BASED.md](docs/TRUNK-BASED.md) y [AGENTS.md](AGENTS.md)). **Todo cambio entra a `main` mediante un PR aprobado — sin excepciones.** El bypass de admin está prohibido por doctrina del repositorio, aunque GitHub lo permita técnicamente. El bot `yap-reviewer` publica análisis como comentario; la aprobación es siempre humana (`core-devs`).

## Roles

| Rol | Equipo | Responsabilidades |
|-----|--------|-------------------|
| **Owner** | Admin (org) | Dirección estratégica, billing, políticas de la org, decisiones finales |
| **Mantenedor** | `core-devs` | Revisar y aprobar PRs, definir dirección técnica, enforce del código de conducta, releases |
| **Colaborador** | `contributors` | Contribuciones activas, revisión de issues, apoyo a la comunidad |
| **Comunidad** | Miembros | Issues, PRs, discusión y documentación |

## Flujo de decisiones / Decision flow

1. **Cambios de código**: PR revisado y aprobado por `core-devs` antes de merge. **Todo cambio** —sin importar tamaño— pasa por PR. Sin bypass de admin (ver [AGENTS.md](AGENTS.md)).
2. **Cambios de doctrina/política**: propuesta como issue + PR en el repositorio `.github` de la org; decisión por consenso de `core-devs`.
3. **Decisiones registradas**: las decisiones relevantes se registran en `DECISION-LOG.md` de cada repositorio cuando aplique.

## Cómo convertirse en mantenedor / Becoming a maintainer

Un colaborador puede ser nominado para `core-devs` al cumplir:

1. Contribuciones técnicas consistentes (PRs mergeados de calidad).
2. Participación activa en code review y soporte comunitario.
3. Actividad sostenida en el tiempo y alineación con el [código de conducta](CODE_OF_CONDUCT.md).

La nominación la hace un mantenedor existente y se aprueba por mayoría simple de `core-devs`.

## Releases y versionamiento / Releases

- El versionamiento y tagging ocurren en cadencia manual (ver A-Dev), no en cada PR.
- `main` siempre debe estar verde (CI) y con las validaciones del alcance aplicadas.
- En Yap los releases se cortan desde `main` (trunk-based): ver [docs/TRUNK-BASED.md](docs/TRUNK-BASED.md).

## Políticas de repositorios / Repository policies

- Permiso por defecto para miembros: **lectura**.
- La creación de repositorios está restringida a admins.
- Todo repositorio de la org adopta este modelaje de equipo, plantillas y flujo de PR.
- `main` está cubierto por branch protection que exige **PR + CI verde**. **Sin bypass de admin** (`enforce_admins: true`). **Overlay trunk-based de Yap** ([docs/TRUNK-BASED.md](docs/TRUNK-BASED.md), [AGENTS.md](AGENTS.md)): ramas cortas e integración frecuente; todo cambio entra vía PR aprobado, sin importar el tamaño o el rol del autor.

## Seguridad de la cuenta / Account security

- La **autenticación de dos factores (2FA)** es requisito de membresía: los mantenedores con acceso de escritura y el equipo `core-devs` deben tener 2FA activa en su cuenta de GitHub.
- La verificación de 2FA se realiza al aceptar nuevas membresías e invitaciones.
- Reportes de vulnerabilidades: ver [SECURITY.md](SECURITY.md) — canal único vía GitHub Security Advisories.

## Aprobación y cambios a este documento

Los cambios a este documento se hacen por PR, revisado por `core-devs`.