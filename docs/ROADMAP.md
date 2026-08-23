# Yap — Roadmap

**Última actualización:** 2026-08-22

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
| 21 | Control de sesiones dentro del agente | P0 | En revisión |
| 22 | Explicación automática al abrir Yap (onboarding interactivo) | P0 | Planeado |
| 23 | Sistema de evaluación automática con feedback del LLM | P1 | Completado |
| 24 | Perfil de estudiante (nombre, nivel, cursos activos, preferencias) | P1 | Planeado |
| 25 | Modo profesor — panel de monitoreo de progreso de estudiantes | P2 | Planeado |

### Fase 2 — Roadmap del agente profesor (v1.2)
**Objetivo:** Cumplir el roadmap completo de profesor → estudiante.

| # | Issue | Prioridad | Estado |
|---|-------|-----------|--------|
| 26 | Cursos adicionales — MAT1101, INF1101, TEL1101 | P1 | Planeado |
| 27 | Sistema de ejercicios interactivos con validación automática | P1 | Planeado |
| 28 | Adaptación de dificultad según progreso del estudiante | P2 | Planeado |
| 29 | Feedback pedagógico estructurado (formativo vs sumativo) | P2 | Planeado |
| 30 | Exportación de progreso a PDF/CSV para el docente | P2 | Planeado |

### Fase 3 — Empaquetado para ChincoLinux OS (v1.3)
**Objetivo:** Dejar Yap listo para integrarse en la ISO de ChincoLinux.

| # | Issue | Prioridad | Estado |
|---|-------|-----------|--------|
| 31 | Crear paquete .deb para Yap | P0 | Completado |
| 32 | Integrar Yap en el build de la ISO de ChincoLinux | P0 | Planeado |
| 33 | Configuración post-install automática (systemd, AppArmor, whitelists) | P1 | Parcial (1) |
| 34 | Tests de integración en ChincoLinux OS (Live USB / VM) | P1 | Planeado |
| 35 | Documentación de despliegue para administradores escolares | P2 | Planeado |

### Fase 4 — Pulido y estabilidad (v1.4)
**Objetivo:** Software sólido listo para producción en aulas.

| # | Issue | Prioridad | Estado |
|---|-------|-----------|--------|
| 36 | i18n — soporte multi-idioma (español, inglés, mapudungun) | P2 | Planeado |
| 37 | Accesibilidad — lector de pantalla, alto contraste, fuentes grandes | P2 | Planeado |
| 38 | Telemetría local anónima — métricas de uso para mejorar el agente | P3 | Planeado |
| 39 | Modo offline total — sin dependencia de red en ningún flujo | P1 | Planeado |
| 40 | Benchmarks de rendimiento en hardware educativo real | P1 | Planeado |

## Bugs detectados pendientes de revisión

Hallazgos surgidos durante la validación de #21 en Debian 13 Trixie. Ninguno
pertenece al alcance de ese issue y todos requieren un issue propio.

| # | Descripción | Ubicación | Prioridad | Estado |
|---|-------------|-----------|-----------|--------|
| B1 | El `sed` que extrae el nombre del modelo desde `yap.py` no elimina el paréntesis de cierre de `os.environ.get(...)`. El nombre resultante queda como `Llama-3.2-1B-Instruct-Q4_K_M.gguf)` y la URL de descarga se construye inválida, por lo que la instalación aborta al descargar el modelo. | `setup.sh:142` | P0 | Por revisar |
| B2 | `cmd_curso()` captura `FileNotFoundError`, `ValueError` y `JSONDecodeError`, pero no `PermissionError`. Un fichero de curso sin permisos de lectura produce una traza completa en pantalla en lugar de un mensaje de error controlado. | `yap.py:804` | P2 | Por revisar |
| B3 | El menú del modo interactivo numera las entradas como `[1] [2] [3]`, lo que sugiere que son opciones seleccionables. Al escribir un número, el texto se envía al LLM como consulta en lugar de ejecutar la acción correspondiente. | `yap.py` — `display_menu()` | P2 | Por revisar |
### Notas

**(1) #33 — entrega parcial.** Se cubren las whitelists escolares, el perfil
AppArmor en modo enforce (#14) y el `postinst` del paquete `.deb` (#31).
Queda pendiente el daemon systemd:

| Criterio pendiente | Motivo |
|---|---|
| Servicio systemd `yap-daemon` | Yap invoca `llama-cli` de nuevo en cada consulta, sin proceso persistente. Precargar el modelo exige migrar a `llama-server`, lo que excede una tarea de configuración post-install y merece issue propio |

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
