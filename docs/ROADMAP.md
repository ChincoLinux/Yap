# Yap — Roadmap

**Última actualización:** 2026-10-12

## Visión

Yap es el asistente IA local de ChincoLinux, diseñado para funcionar en hardware educativo
limitado (3-8 GB RAM, CPU-only). El objetivo es convertirlo en un **agente profesor** completo
que guíe al estudiante a través de su aprendizaje, con control de sesiones, evaluaciones
automáticas y empaquetado **multiplataforma**: `.deb`, `.rpm`, Flatpak e instalador de Windows.

## Fases

### Fase 1 — Fundaciones del agente profesor (v1.1)
**Objetivo:** Convertir Yap de un chatbot en un agente educativo con sesiones estructuradas.

| # | Issue | Prioridad | Estado |
|---|-------|-----------|--------|
| 21 | Control de sesiones dentro del agente | P0 | Completado |
| 22 | Explicación automática al abrir Yap (onboarding interactivo) | P0 | Completado |
| 23 | Sistema de evaluación automática con feedback del LLM | P1 | Completado |
| 24 | Perfil de estudiante (nombre, nivel, cursos activos, preferencias) | P1 | Completado |
| 25 | Modo profesor — panel de monitoreo de progreso de estudiantes | P2 | Completado |

### Fase 2 — Roadmap del agente profesor (v1.2)
**Objetivo:** Cumplir el roadmap completo de profesor → estudiante.

| # | Issue | Prioridad | Estado |
|---|-------|-----------|--------|
| 26 | Cursos adicionales — MAT1101, INF1101, TEL1101 | P1 | Completado |
| 27 | Sistema de ejercicios interactivos con validación automática | P1 | Completado (PR #61) |
| 28 | Adaptación de dificultad según progreso del estudiante | P2 | Completado |
| 29 | Feedback pedagógico estructurado (formativo vs sumativo) | P2 | Completado |
| 30 | Exportación de progreso a PDF/CSV para el docente | P2 | CSV disponible · PDF/HTML pendiente |

### Fase 3 — Empaquetado multiplataforma (v1.3)
**Objetivo:** Yap instalable en cualquier SO donde trabaje el aula.

El alcance cambió respecto a la primera versión de este roadmap, que lo limitaba a la ISO
de ChincoLinux. #32 y #34 se cerraron por esa decisión.

| # | Issue | Prioridad | Estado |
|---|-------|-----------|--------|
| 31 | Crear paquete .deb para Yap | P0 | Completado |
| 32 | Integrar Yap en el build de la ISO de ChincoLinux | P0 | Cerrado — fuera de alcance (1) |
| 33 | Configuración post-install automática (systemd, AppArmor, whitelists) | P1 | Completado (2) |
| 34 | Tests de integración en ChincoLinux OS (Live USB / VM) | P1 | Cerrado — fuera de alcance (1) |
| 35 | Documentación de despliegue para administradores escolares | P2 | Completado |
| 202 | La GUI `yap_desktop` no llega a ningún paquete instalado | P0 | Abierto |
| 203 | Binario standalone con PyInstaller (`yap.exe` y binario Linux) | P1 | Abierto |

### Fase 4 — Pulido y estabilidad (v1.4)
**Objetivo:** Software sólido listo para producción en aulas.

| # | Issue | Prioridad | Estado |
|---|-------|-----------|--------|
| 36 | i18n — soporte multi-idioma (español, inglés, mapudungun) | P2 | Completado |
| 37 | Accesibilidad — lector de pantalla, alto contraste, fuentes grandes | P2 | Completado |
| 38 | Telemetría local anónima — métricas de uso para mejorar el agente | P3 | Completado (3) |
| 39 | Modo offline total — sin dependencia de red en ningún flujo | P1 | Suspendido (`cloud-suspended`) |
| 40 | Benchmarks de rendimiento en hardware educativo real | P1 | Cerrado — decisión registrada (4) |
| 204 | Refactor: dividir `yap.py` (más de 8000 líneas) en paquete instalable | P1 | Abierto |

### Fase 5 — YAP DESKTOP AI FOR STUDENT (v1.5)

**Objetivo:** Que el alumno pueda instalar Yap como aplicación de escritorio y usarlo como
CLI, app de escritorio o binario standalone: el mismo producto, tres formas de ejecutarlo.

Epic **#199**. La GUI existe (`yap_desktop/`, más de 1200 líneas, con bandeja, atajo global y
motor en segundo plano) pero **no está empaquetada en ningún objetivo**: ni `.deb`, ni
`.rpm`, ni Flatpak, ni Inno Setup.

| # | Issue | Prioridad | Estado |
|---|-------|-----------|--------|
| 201 | `pyproject.toml` con dependencias y entry points `yap` y `yap-gui` | P0 | Abierto — PR #232 |
| 202 | GUI `yap_desktop` sin empaquetar | P0 | Abierto |
| 204 | Refactor: dividir `yap.py` en paquete instalable | P1 | Abierto |
| 203 | Binario standalone con PyInstaller | P1 | Abierto |
| 205 | Página web de descarga | P2 | Abierto |
| 206 | Optimizar el repo para desarrollo con agentes de IA | P2 | Abierto |

### Fase 6 — YAP WEB (v2)

**Objetivo:** Frontend y backend con la ingeniería de Artemisa: DevSecOps, CI con puertas
de calidad y E2E.

Epic **#208**. La web consumirá artefactos de release vía GitHub API; nunca clona el repo
en tiempo de ejecución. La telemetría es agregada, sin PII.

| # | Issue | Prioridad | Estado |
|---|-------|-----------|--------|
| 209 | Decidir stack y hosting | P0 | Cerrado — decisión registrada |
| 210 | Backend de releases, telemetría de descargas y checks | P1 | Abierto |
| 211 | Endurecimiento DevSecOps y tests E2E | P1 | Abierto |
| 215 | Arquitectura del repo de la web | P1 | Abierto |
| 216 | Animaciones y UI/UX del frontend | P2 | Abierto |
| 233 | Temática y diseño/UI-UX de la app | P2 | Abierto |
| 214 | Medir si el RAG mejora al agente | P2 | Abierto |

## Seguridad

Los issues de seguridad se tratan fuera de las fases porque bloquean cualquier release.

| # | Issue | Prioridad | Estado |
|---|-------|-----------|--------|
| 213 | Clave de invocación de Cloud Run hardcodeada — rotar en GCP | P0 | Abierto — requiere acción del usuario |
| 234 | `cmd_webfetch` descarga sin techo de tamaño | P1 | Abierto — PR #244 |
| 235 | Modelos GGUF sin checksum | P1 | Abierto |
| 236 | Whitelists empujadas por `/tmp` antes de `sudo mv` | P1 | Abierto — PR #246 |
| 238 | JSON de USB sin límite de tamaño | P1 | Abierto — PR #244 |
| 240 | Ninguna action pineada por SHA | P1 | Abierto |
| 241 | Tres tests de seguridad no prueban lo que afirman | P1 | Abierto |

## Bugs detectados pendientes de revisión

Hallazgos surgidos durante la validación de #21 en Debian 13 Trixie. Ninguno
pertenecía al alcance de ese issue y cada uno se resolvió por su cuenta.

| # | Descripción | Ubicación | Prioridad | Estado |
|---|-------------|-----------|-----------|--------|
| B1 | El `sed` que extrae el nombre del modelo desde `yap.py` no elimina el paréntesis de cierre de `os.environ.get(...)`. El nombre resultante queda como `Llama-3.2-1B-Instruct-Q4_K_M.gguf)` y la URL de descarga se construye inválida, por lo que la instalación aborta al descargar el modelo. | `setup.sh` — `extraer_nombre_modelo()` | P0 | Corregido (`grep -oE`, ver comentario `ponytail`) |
| B2 | `cmd_curso()` captura `FileNotFoundError`, `ValueError` y `JSONDecodeError`, pero no `PermissionError`. Un fichero de curso sin permisos de lectura produce una traza completa en pantalla en lugar de un mensaje de error controlado. | `yap.py` — `cmd_curso()` | P2 | Corregido (#170, PR #171) |
| B3 | El menú del modo interactivo numera las entradas como `[1] [2] [3]`, lo que sugiere que son opciones seleccionables. Al escribir un número, el texto se envía al LLM como consulta en lugar de ejecutar la acción correspondiente. | `yap.py` — `display_menu()` | P2 | Resuelto (#59): las rutas de teclado se resuelven en `interpret()` y las opciones que necesitan datos muestran una pista de uso |
### Notas

**(1) #32 y #34 — cerrados por alcance.** Yap es software empaquetado para cualquier SO,
no un componente de la ISO de ChincoLinux. La decisión se registró al cerrar ambos issues.
`docs/PACKAGING.md` y `AGENTS.md` declaran el alcance vigente.

**(2) #33 — completado (vía #129).** Las whitelists escolares (#71) y el paquete
`.deb` (#31) ya están integrados. La post-instalación incorpora una regla
de usuario systemd-tmpfiles para `~/.config/yap/`, validación real del perfil
AppArmor (enforce por defecto), preservación de configuración local y
pruebas de instalación, reinstalación y purga en Debian 12/13.
El Issue #129 completó los criterios pendientes:
- Unidades systemd `yap-daemon.service`, `yap-sync.service` y `yap-sync.timer`.
- Comandos CLI: `yap --postinstall-check`, `yap --daemon`, `yap --daemon-status`, `yap --sync`.
- Siembra con permisos root de `agent/yap.md` y whitelists (`0644`).
- Carga y verificación de AppArmor en modo enforce.
- Integración en `packaging/` (Debian/RPM) y `setup.sh`.

**(3) #38 — entregado, dos métricas pendientes.** Los criterios de aceptación
del issue están cubiertos: `telemetry.json`, comando `telemetria`, exportación
anónima opt-in, garantía de no transmisión y pruebas. El issue está cerrado;
quedan por implementar dos de las métricas descritas en la propuesta. Sus
dependencias (#21 y #23) ya están cerradas, así que están desbloqueadas:

| Métrica pendiente | Depende de | Estado |
|---|---|---|
| Tiempo promedio por sesión | #21 — control de sesiones | desbloqueada (issue cerrado) |
| Actividades con más reprobaciones | #23 — evaluación automática | desbloqueada (issue cerrado) |

**(4) #40 — cerrado.** Los benchmarks se cerraron por falta de hardware real.
Si se retoman, la decisión debe registrarse en el issue.

## Prioridades globales

```
P0 — Crítico, bloquea el siguiente release
P1 — Importante, debe estar en el siguiente release
P2 — Deseable, planear para el release siguiente
P3 — Futuro, no comprometido
```

## Dependencias entre fases

```
Fase 1 (sesiones, onboarding, evaluación)
  ↓
Fase 2 (cursos, ejercicios, adaptación)
  ↓
Fase 3 (empaquetado multiplataforma: .deb, .rpm, Flatpak, Windows)
  ↓
Fase 4 (i18n, accesibilidad, telemetría, estabilidad)
  ↓
Fase 5 (escritorio: GUI empaquetada, CLI y binario standalone)
  ↓
Fase 6 (web: frontend, backend, DevSecOps)
```

## Métricas de éxito

- **Fase 1:** Estudiante puede iniciar sesión, recibir explicación, y completar una EA con evaluación
- **Fase 2:** 3+ cursos disponibles con ejercicios auto-validados
- **Fase 3:** `apt install yap` funciona en Debian/Ubuntu; `.rpm`, Flatpak e instalador de Windows generados por CI
- **Fase 4:** Usable en aula real con 30+ estudiantes simultáneos
- **Fase 5:** `yap-gui` arranca tras instalar el paquete en cualquiera de los 4 formatos
- **Fase 6:** La web publica un release y un alumno descarga el binario sin tocar el repo

## Issues suspendidos

38 issues con la etiqueta `cloud-suspended` permanecen abiertos sin tocarse. Se retomarán
cuando se decida el alcance de la nube.
