# Yap — Auditoría de seguridad

**Fecha:** 2026-10-13 · **Base:** `main` @ `1082e80` · **Reemplaza a:** la auditoría de 2026-08-14

## Resumen

**Sin hallazgos críticos en código de producción.** Las cuatro prohibiciones centrales de `HD-YAP-SEC-001` tienen **cero** ocurrencias en todo el repo. El riesgo que queda está en CI/CD y en la configuración del repositorio, no en el agente.

---

## Alcance

La auditoría anterior cubría `yap.py`, `setup.sh`, `apparmor/` y `tests/`. Esta cubre las siete superficies que ejecutan o distribuyen código:

| Superficie | Líneas / cantidad | Cubierta antes |
|---|---|---|
| `yap.py` | 8220 | sí |
| `yap_desktop/` | 1251 | **no** |
| `setup.sh` | 594 | sí |
| `deploy-yap.sh` | 265 | **no** |
| `build-deb.sh` | 371 | **no** |
| `packaging/` (RPM, Flatpak, Inno Setup) | — | **no** |
| `.github/workflows/` | 12 workflows | **no** |
| `apparmor/usr.local.bin.yap` | 84 | sí |

La auditoría anterior declaraba `yap.py (932 líneas)`; el fichero tiene **8220**. Ver #239.

---

## Métodos

Recorrido **AST** de los 52 ficheros Python, no `grep`. La distinción importa — ver "Falsos positivos" abajo, donde un `grep` habría dado cuatro falsos positivos de los que dos llevan a conclusiones incorrectas.

Comprobado contra los criterios de `docs/REVIEW.md` (`HD-YAP-SEC-001`), y verificado el estado de cada recomendación de la auditoría anterior.

---

## Verificación de prohibiciones

| Requisito | Ocurrencias |
|---|---|
| `shell=True` | **0** |
| `eval()` / `exec()` builtin | **0** |
| `os.system()` / `os.popen()` | **0** |
| `import socket / ctypes / pickle / base64 / shelve / marshal` | **0** |
| `subprocess.run` sin `timeout=` | **0** |
| Imports no-stdlib | **0** |
| `curl -k` / `wget --no-check-certificate` / `curl \| sh` | **0** |
| `chmod 777` | **0** |

### Los cuatro `Popen` sin `timeout=`

Todos justificados, verificados uno a uno:

| Ubicación | Por qué es correcto |
|---|---|
| `yap.py:3745` | `proc.communicate(timeout=120)` a continuación |
| `yap.py:6413` | App de GUI desprendida, `start_new_session=True` |
| `yap.py:7444` | `xdg-open`, proceso desprendido |
| `yap_desktop/daemon.py:177` | `communicate(timeout=self._timeout)` |

En el PR #253 los tres de `yap.py` llevan un comentario `yap-sin-timeout` declarando la excepción en el propio código, y hay un test que falla si se quita el marcador.

---

## AppArmor

El perfil **no fija rutas de código**, sólo ejecutables permitidos: `llama-cli`, `xdg-open`, `notify-send`, `firefox*`, `libreoffice*`, `pseint`, `evince`, `okular`, `gedit`, `code`, `python3`. Referencia `/opt/yap/`, que cubre el paquete `yap/` introducido en #254.

**Sin impacto tras el cambio de estructura.** Deniega por defecto.

---

## CI/CD

| Workflow | Permisos | Evaluación |
|---|---|---|
| `pr-quality-suite` | `contents: read` | correcto |
| `pr-validation` | `contents: read` | correcto |
| `quality-gates` | `contents: read` | correcto |
| `pr-review` | `contents:read, pull-requests:write` | correcto |
| `pr-state-labeler`, `pr-traceability-check` | `pull-requests:write, issues:write` | correcto |
| `auto-release`, `build-deb`, `build-packages` | `contents: write` | correcto, actions pineadas |
| `test.yml` | `contents: read` | correcto (#255) |
| `auto-add-to-project` | `{}` + PAT de org justificado | correcto (#255) |

Las **59** referencias a actions están pineadas por SHA desde #249. Sin `pull_request_target` en ningún workflow.

---

## Hallazgos

### H-1 — `PROJECT_PAT` sin justificar en el fichero — **baja** (corregido en #255)

`auto-add-to-project.yml` y `weekly-sprint-assignment.yml` usan `${{ secrets.PROJECT_PAT }}`.

*Corrección:* la primera versión de esta auditoría afirmaba que el secreto no existía, porque `GET /repos/.../actions/secrets` devuelve `total_count: 0`. Es un secreto **de organización**: `GET /repos/.../actions/organization-secrets` lo lista, y los dos workflows corren en verde. El error fue consultar sólo el endpoint de repositorio.

El PAT es necesario: el `GITHUB_TOKEN` no puede escribir en un Project v2 de la organización ni asignar issues en otros repos. Lo que faltaba era hacerlo explícito, porque **un PAT no lo limita el bloque `permissions:`**. Ahora cada uso lleva un comentario con el motivo, y `tests/test_workflows_permisos.py` lo exige.

### H-2 — Dos workflows sin `permissions:` explícito — **baja** (corregido en #255)

`test.yml` y `auto-add-to-project.yml` heredaban el default de Settings, que no aparece en ningún diff. Ahora `test.yml` declara `contents: read` y `auto-add-to-project.yml` declara `permissions: {}`, porque no usa el `GITHUB_TOKEN`. El test exige `permissions:` a nivel raíz en todos los workflows.

### H-3 — `sha_pinning_required` desactivado — **media**

El pineado lo sostienen los 7 tests de `test_actions_pineadas.py`, pero GitHub no lo exige. El `PATCH` devuelve `404` desde el PAT actual (sin permiso de administración). Hay que activarlo a mano en **Settings → Actions → General**.

### H-4 — Rate limiting del LLM sin implementar — **media**

La recomendación P1 de la auditoría anterior. Verificado: **0** ocurrencias. Sigue pendiente un año después.

El coste es local —el modelo corre en el equipo del alumno—, pero sin límite una consulta en bucle agota CPU y batería en un Celeron sin que el alumno entienda por qué la máquina va lenta.

### H-5 — `docs/REVIEW.md` desactualizado tras #204 — **baja**

La checklist dice *"Prohibido en `yap.py`"* y manda ejecutar `ruff format --check yap.py tests/`. Con #254, `yap.py` es un shim de 43 líneas y la implementación vive en `yap/__init__.py`. La checklist deja de apuntar al código que hay que revisar.

---

## Falsos positivos descartados

La auditoría anterior advertía: *"es frecuente el falso positivo cuando el patrón aparece en documentación o en tests que lo verifican ausente."* Se confirmó:

- **`yap_desktop/app.py:177` — `exec()`**. Es `app.exec()`, el event loop de Qt. Un `grep` por `exec(` lo marca; el AST distingue builtin de atributo. Marcarlo como crítico habría sido incorrecto.
- **37 `shutil.rmtree` y 2 `os.remove`**. Todos en `tests/`, limpiando directorios temporales.
- **16 `subprocess.run` sin `stdin=DEVNULL`**, casi todos en tests que lanzan `bash -n` o `pytest`, sin entrada interactiva.

---

## Estado de la auditoría anterior (2026-08-14)

Sus tres hallazgos siguen **mitigados y verificados en esta revisión**:

| Hallazgo | Estado |
|---|---|
| H-01 Path traversal en `cargar_curso()` | mitigado — `basename()` + `realpath` confinado |
| H-02 Scheme no validado en `cmd_webfetch()` | mitigado — sólo `http`/`https` |
| H-03 Confirmaciones sin validar | aceptado — fichero de usuario, escritura atómica, AppArmor confina `~/.config/yap/` |

Y sus recomendaciones:

| Recomendación | Estado hoy |
|---|---|
| P0 — AppArmor enforce | **hecho**, enforce por defecto en la post-instalación |
| P1 — rate limiting en `cmd_query` | **sin implementar** (H-4) |
| P2 — cifrar `history.json` | sin hacer. El contenido es texto de chat del alumno |
| P3 — sandboxing con bubblewrap | sin hacer |

---

## Hallazgos posteriores a esa auditoría, ya corregidos

La auditoría anterior no pudo verlos porque no existían. Todos cerrados en esta rama de trabajo:

| Issue | Qué era | Cerrado por |
|---|---|---|
| #213 (parte de código) | Clave de Cloud Run hardcodeada | #251 |
| #234 | `cmd_webfetch` descarga sin techo | #244 |
| #235 | Modelos GGUF sin checksum | #252 |
| #236 | Whitelists empujadas por `/tmp` | #246 |
| #237 | Informe de despliegue borrado por su propio `trap` | #246 |
| #238 | JSON de USB sin límite de tamaño | #244 |
| #240 | Ninguna action pineada por SHA | #249 |
| #241 | Tres tests de seguridad que no prueban lo que afirman | #248 |
| #242 | Instalador de Windows cinco releases desfasado | #245 |

---

## Conclusión

El código de ejecución de Yap está en buen estado para su contexto: un agente local en el aula, sin superficie de red propia y confinado por AppArmor.

El riesgo residual está en tres sitios, ninguno explotable desde el aula:

1. **Configuración de GitHub** — H-1, H-2, H-3. Ninguno es una vulnerabilidad; los tres son ajustes.
2. **Un P1 sin implementar** — H-4, el rate limiting. Es el único que afecta al alumno, y afecta a su experiencia, no a su seguridad.
3. **Una credencial viva en el historial de git** — #213. Está fuera del código desde #251, pero sigue en el historial desde `51202e7` y en cada clone. **Hay que revocarla en GCP.** Es lo único de esta lista que una revisión de código no puede resolver.
