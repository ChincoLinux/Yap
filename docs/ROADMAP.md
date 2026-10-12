# Yap — Roadmap

**Última actualización:** 2026-10-11

## Visión

Yap es el asistente IA local de ChincoLinux, diseñado para funcionar en hardware educativo
limitado (3-8 GB RAM, CPU-only). El objetivo es convertirlo en un **agente profesor** completo
que guíe al estudiante através de su aprendizaje, con control de sesiones, evaluaciones
automáticas, y empaquetado nativo para la distribución ChincoLinux.

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
| 27 | Sistema de ejercicios interactivos con validación automática | P1 | En revisión (PR #61) |
| 28 | Adaptación de dificultad según progreso del estudiante | P2 | Completado |
| 29 | Feedback pedagógico estructurado (formativo vs sumativo) | P2 | Completado |
| 30 | Exportación de progreso a PDF/CSV para el docente | P2 | CSV disponible · PDF/HTML pendiente |

### Fase 3 — Empaquetado para ChincoLinux OS (v1.3)
**Objetivo:** Dejar Yap listo para integrarse en la ISO de ChincoLinux.

| # | Issue | Prioridad | Estado |
|---|-------|-----------|--------|
| 31 | Crear paquete .deb para Yap | P0 | Completado |
| 32 | Integrar Yap en el build de la ISO de ChincoLinux | P0 | Pendiente — `needs-human` (depende del repo de la ISO) |
| 33 | Configuración post-install automática (systemd, AppArmor, whitelists) | P1 | Completado (1) |
| 34 | Tests de integración en ChincoLinux OS (Live USB / VM) | P1 | Pendiente — requiere ISO/VM |
| 35 | Documentación de despliegue para administradores escolares | P2 | Completado |

### Fase 4 — Pulido y estabilidad (v1.4)
**Objetivo:** Software sólido listo para producción en aulas.

| # | Issue | Prioridad | Estado |
|---|-------|-----------|--------|
| 36 | i18n — soporte multi-idioma (español, inglés, mapudungun) | P2 | Completado |
| 37 | Accesibilidad — lector de pantalla, alto contraste, fuentes grandes | P2 | Completado |
| 38 | Telemetría local anónima — métricas de uso para mejorar el agente | P3 | Completado (2) |
| 39 | Modo offline total — sin dependencia de red en ningún flujo | P1 | Suspendido (`cloud-suspended`) |
| 40 | Benchmarks de rendimiento en hardware educativo real | P1 | Pendiente — requiere hardware real |

## Bugs detectados pendientes de revisión

Hallazgos surgidos durante la validación de #21 en Debian 13 Trixie. Ninguno
pertenecía al alcance de ese issue y cada uno se resolvió por su cuenta.

| # | Descripción | Ubicación | Prioridad | Estado |
|---|-------------|-----------|-----------|--------|
| B1 | El `sed` que extrae el nombre del modelo desde `yap.py` no elimina el paréntesis de cierre de `os.environ.get(...)`. El nombre resultante queda como `Llama-3.2-1B-Instruct-Q4_K_M.gguf)` y la URL de descarga se construye inválida, por lo que la instalación aborta al descargar el modelo. | `setup.sh` — `extraer_nombre_modelo()` | P0 | Corregido (`grep -oE`, ver comentario `ponytail`) |
| B2 | `cmd_curso()` captura `FileNotFoundError`, `ValueError` y `JSONDecodeError`, pero no `PermissionError`. Un fichero de curso sin permisos de lectura produce una traza completa en pantalla en lugar de un mensaje de error controlado. | `yap.py` — `cmd_curso()` | P2 | Corregido (#170, PR #171) |
| B3 | El menú del modo interactivo numera las entradas como `[1] [2] [3]`, lo que sugiere que son opciones seleccionables. Al escribir un número, el texto se envía al LLM como consulta en lugar de ejecutar la acción correspondiente. | `yap.py` — `display_menu()` | P2 | Resuelto (#59): las rutas de teclado se resuelven en `interpret()` y las opciones que necesitan datos muestran una pista de uso |
### Notas

**(1) #33 — completado (vía #129).** Las whitelists escolares (#71) y el paquete
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

**(2) #38 — entregado, dos métricas pendientes.** Los criterios de aceptación
del issue están cubiertos: `telemetry.json`, comando `telemetria`, exportación
anónima opt-in, garantía de no transmisión y pruebas. El issue está cerrado;
quedan por implementar dos de las métricas descritas en la propuesta. Sus
dependencias (#21 y #23) ya están cerradas, así que están desbloqueadas:

| Métrica pendiente | Depende de | Estado |
|---|---|---|
| Tiempo promedio por sesión | #21 — control de sesiones | desbloqueada (issue cerrado) |
| Actividades con más reprobaciones | #23 — evaluación automática | desbloqueada (issue cerrado) |

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
Fase 3 (empaquetado .deb, ISO, integración)
  ↓
Fase 4 (i18n, accesibilidad, telemetría, estabilidad)
```

## Métricas de éxito

- **Fase 1:** Estudiante puede iniciar sesión, recibir explicación, y completar una EA con evaluación
- **Fase 2:** 3+ cursos disponibles con ejercicios auto-validados
- **Fase 3:** `apt install yap` funciona en ChincoLinux OS
- **Fase 4:** Usable en aula real con 30+ estudiantes simultáneos
