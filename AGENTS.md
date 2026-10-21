# AI Agents Guide for Yap

This guide helps AI agents (like Claude Code, Devin, Antigravity, etc.) understand how to collaborate effectively on Yap.

> **Fuente de verdad:** `AGENTS.md` es la **guía operativa y contrato de ejecución** para agentes de IA en este repositorio. `CLAUDE.md` actúa como tarjeta de referencia técnica complementaria alineada con este documento.

---

## Project Context

**Yap** is a local AI assistant, CPU-only, for educational environments with limited resources (ChincoLinux / Debian 13).

- **Tech Stack**: Python 3.12 (stdlib-only runtime), llama.cpp (static link, CPU-only), Llama 3.2 Instruct (GGUF Q4_K_M)
- **Language**: Spanish (user-facing), Spanish/English (technical comments)
- **License**: MIT
- **Philosophy**: Educational, privacy-first, offline-capable, stdlib-only (zero pip dependencies for agent execution)

| Atributo | Valor |
|---|---|
| Repositorio | `ChincoLinux/Yap` (organización) |
| Fork de trabajo | `VECTORG99/Yap` |
| Código principal | paquete `yap/` (más de 8000 líneas, stdlib-only); `yap.py` es el shim de entrada; `yap_core.py` el motor asíncrono (#152) |
| Interfaz gráfica | paquete `yap_desktop/` (PyQt6/PySide6, widget flotante, bandeja y hotkey) |
| CI | `.github/workflows/` (12 workflows, `test.yml` da los checks requeridos); `pytest tests/` = más de 1200 tests, sin LLM/GPU/Internet |
| Modelo | Llama 3.2 1B/3B Instruct (Q4_K_M, CPU-only) |

---

## Setup del Entorno de Desarrollo (en < 10 minutos)

> **Criterio clave:** Un agente o desarrollador puede levantar el entorno completo para ejecutar tests y validaciones leyendo únicamente esta sección.

El agente Yap en sí es **100% biblioteca estándar de Python (stdlib-only)** y no requiere ningún paquete externo para ejecutarse. Sin embargo, para desarrollo, ejecución de tests y verificación de calidad se utilizan herramientas estándar de desarrollo.

### 1. Requisitos previos
- Python >= 3.11 (recomendado Python 3.12)
- Git

### 2. Pasos de inicialización paso a paso

```bash
# Paso 1: Clonar el repositorio y entrar en él
git clone https://github.com/ChincoLinux/Yap.git
cd Yap

# Paso 2: Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate       # En Linux/macOS
# .venv\Scripts\Activate.ps1    # En Windows PowerShell

# Paso 3: Instalar herramientas de test y calidad (fijadas a versiones de CI)
pip install pytest==8.3.3 pytest-cov==5.0.0 ruff==0.6.9 pyflakes==3.2.0 pip-audit==2.7.3

# Paso 4: Ejecutar la suite completa de pruebas (100% offline, con mocking total)
python3 -m pytest tests/ -q

# Paso 5: Verificar linters y formateo
ruff format --check *.py yap/ tests/
ruff check *.py yap/ tests/
pyflakes *.py yap/ tests/
```

### 3. One-liner para agentes

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install pytest==8.3.3 pytest-cov==5.0.0 ruff==0.6.9 pyflakes==3.2.0 && pytest tests/ -q
```

---

## Comandos de un Solo Vistazo (Quick Reference Cheat Sheet)

| Tarea | Comando | Propósito |
|---|---|---|
| **Formato** | `ruff format --check *.py yap/ tests/` | Verifica formato PEP8 / Black style sin alterar archivos |
| **Autoformato** | `ruff format *.py yap/ tests/` | Aplica correcciones de formato automáticamente |
| **Linter** | `ruff check *.py yap/ tests/` | Comprueba errores de estilo y buenas prácticas |
| **Auto-fix Linter**| `ruff check --fix *.py yap/ tests/` | Resuelve automáticamente violaciones mecánicas |
| **Análisis estático**| `python3 -m pyflakes *.py yap/ tests/` | Detecta variables sin usar e imports huérfanos |
| **Auditoría dependencias**| `pip-audit --strict` | Audita paquetes instalados contra vulnerabilidades conocidas |
| **Suite completa** | `python3 -m pytest tests/ -v` | Ejecuta las más de 1200 pruebas de la suite |
| **Tests rápidos** | `python3 -m pytest tests/ -q` | Ejecución silenciosa y rápida |
| **Tests seguridad**| `python3 -m pytest tests/test_yap_security.py -v` | Verifica whitelists, inyecciones y límites |
| **Reporte educativo**| `python3 tests/run_tests.py --report` | Genera reporte TXT con mapeo de 26 requisitos pedagógicos |
| **Smoke test CLI** | `python3 -m yap --one-shot "¿Qué es un algoritmo?"` | Consulta directa sin interactividad |
| **Smoke test Desktop** | `python3 -m pytest tests/test_yap_desktop.py -v` | Valida componentes de interfaz gráfica sin DISPLAY |
| **Empaquetado test**| `./build-deb.sh --stub-llama --no-models` | Construye `.deb` localmente sin compilar llama.cpp |

---

## Mapa de Módulos (ficheros con más de 200 líneas)

Para facilitar la navegación inmediata sin necesidad de explorar el árbol ciegamente:

| Fichero / Módulo | Líneas aprox. | Componente | Descripción y Responsabilidad |
|---|---|---|---|
| `yap/__init__.py` | ~7325 | Core / CLI | Implementación principal: CLI interactiva, TUI ANSI, router `interpret()`, clasificador `classify_intent()`, handlers `cmd_*()`, RAG BM25, cursos JSON, PSeInt, perfiles y telemetría |
| `tests/test_yap_evaluacion.py` | ~919 | Tests | Evaluación formativa, rúbricas de progreso y generación de feedback para el estudiante |
| `yap_core.py` | ~894 | Core / Engine | Motor asíncrono desacoplado: streaming de inferencia (`stream_query`), cola de tareas en segundo plano (`TaskQueue`) para GUI y servicios |
| `tests/test_yap_functional.py` | ~698 | Tests | Tests funcionales de comandos CLI, navegación en TUI, lanzamiento de aplicaciones, webfetch y gestión de turnos de diálogo |
| `tests/test_yap_rag.py` | ~632 | Tests | Tests de búsqueda léxica BM25, cobertura de contenido, tokenización y filtrado de relevancia |
| `tests/test_yap_super.py` | ~622 | Tests | Integración y fallback con Super Yap (cliente Gradio alojado en Cloud Run) |
| `tests/test_yap_core.py` | ~559 | Tests | Pruebas de concurrencia, hilos daemon, timeouts y emisión de tokens en `yap_core.py` |
| `setup.sh` | ~546 | Instalación | Script Bash de setup interactivo: compila `llama.cpp` CPU-only estático, descarga modelo GGUF según rama, crea configs en `/etc/yap/` y symlinks |
| `tests/test_yap_accesibilidad.py` | ~541 | Tests | Accesibilidad: alto contraste, detección de Orca, ampliación de fuentes y atajos de teclado |
| `tests/test_yap_deb.py` | ~528 | Tests | Empaquetado Debian: control de permisos, presencia de ficheros en `/opt/yap/`, symlinks y scripts de maintainer |
| `tests/test_yap_adaptive.py` | ~520 | Tests | Lógica de dificultad adaptativa según desempeño histórico del estudiante |
| `tests/test_yap_sessions.py` | ~494 | Tests | Persistencia, archivo y reanudación de sesiones de trabajo del alumno |
| `tests/test_yap_ejercicios.py` | ~476 | Tests | Catálogo de ejercicios PSeInt, pistas graduales y evaluación de sintaxis/algoritmos |
| `tests/run_tests.py` | ~472 | Testing CLI | Runner unificado: ejecuta suite, chequeos de infraestructura, modo `--vm` y mapeo de 26 requisitos |
| `tests/test_yap_profesor.py` | ~462 | Tests | Modo profesor: bloqueo de configuraciones, PIN del docente y auditoría de aula |
| `tests/test_yap_security.py` | ~422 | Tests | Suite de seguridad: validación de apps y dominios en whitelist, inyecciones, timeouts y contención |
| `tests/test_yap_perfil.py` | ~416 | Tests | Gestión de perfil escolar (nombre, nivel, idioma) y progreso almacenado en JSON local |
| `tests/rag_eval.py` | ~352 | Tests / RAG | Evaluación cuantitativa de precisión en recuperación sobre el corpus curricular |
| `build-deb.sh` | ~328 | Packaging | Generador de paquetes Debian (`yap_*.deb`, `yap-models-*.deb`) con staging y cálculo de tamaño instalado |
| `tests/test_checksums_modelos.py` | ~305 | Tests | Validación de integridad criptográfica (SHA-256) de binarios compilados y modelos GGUF |
| `yap_desktop/widget.py` | ~304 | Desktop | Ventana flotante de chat en PyQt6/PySide6, renderizador seguro de Markdown a HTML y widgets de entrada |
| `tests/test_yap_confirmation.py` | ~278 | Tests | Verificación del mecanismo interactivo de confirmación previa para acciones potencialmente críticas |
| `tests/test_yap_apparmor.py` | ~264 | Tests | Conformidad del perfil AppArmor `/etc/apparmor.d/usr.local.bin.yap` y restricciones de kernel |
| `tests/test_yap_feedback.py` | ~262 | Tests | Recolección de feedback anónimo y telemetría educativa |
| `tests/test_yap_i18n.py` | ~261 | Tests | Cobertura idiomática (español, inglés, mapudungun) y paridad de claves en `i18n/*.json` |
| `tests/test_yap_desktop.py` | ~257 | Tests | Tests sin DISPLAY de `yap_desktop`: daemon worker, bandeja, atajos globales y resolución de paquete |
| `tests/test_yap_telemetry.py` | ~254 | Tests | Métricas locales de rendimiento e inferencia offline |
| `deploy-yap.sh` | ~233 | Despliegue | Script de despliegue masivo en redes locales de laboratorios escolares mediante SSH |
| `tests/benchmark.py` | ~216 | Benchmarks | Medición de tiempos de arranque, latencia de inferencia y consumo de memoria RAM |
| `tests/test_yap_security_audit.py` | ~214 | Tests | Auditoría estática automatizada de código para prevenir regresiones de seguridad |

---

## Autonomous AI Agent Contract

### Zonas Seguras vs. Puntos Críticos y Peligrosos

Un agente que opere en este repositorio debe respetar estrictamente estos límites de frontera:

#### ✅ Áreas Seguras (Permitido modificar siguiendo el issue)
- `yap/`: Lógica interna, comandos educativos, RAG, tutorial PSeInt, formato TUI.
- `yap_core.py`: Motor de streaming y cola asíncrona.
- `yap_desktop/`: Interfaz de escritorio, widgets, bandejas y listeners.
- `tests/`: Nuevas pruebas unitarias o de integración que acompañen la funcionalidad.
- `docs/`, `i18n/`, `cursos/`: Documentación, traducciones y cursos en formato JSON.

#### ⚠️ Puntos Críticos / Zonas de Peligro (Requieren especial precaución o confirmación humana)
1. **Whitelists (`whitelist/apps.conf` y `whitelist/web.conf`)**:
   - Gobernadas por la política `HD-YAP-SEC-001` (MUST).
   - **NUNCA** añadir binarios ni dominios arbitrarios sin especificación explícita en el issue y tests de seguridad acompañantes.
2. **AppArmor (`apparmor/usr.local.bin.yap`)**:
   - Confinamiento estricto a nivel de kernel. Cualquier alteración debe mantener compatibilidad con Debian 13 y openSUSE/Fedora.
3. **Modo Profesor y PIN de Seguridad (`tests/test_yap_profesor.py`)**:
   - Protege la integridad del entorno en el aula frente a modificaciones de alumnos. No debe debilitarse ni saltearse bajo ninguna circunstancia.
4. **Políticas A-Dev Hardness (`.github/adev/policies/*.json`)**:
   - Documentos normativos del repositorio. No deben modificarse sin aprobación de los mantenedores de `core-devs`.
5. **Workflows de CI (`.github/workflows/*.yml`)**:
   - Las 12 automatizaciones de GitHub Actions protegen `main`. Cualquier cambio en pipelines requiere revisión detallada y prueba en ramas dedicadas.
6. **Prohibiciones Absolutas de Código** (detectadas en CI por `pr-quality-suite.yml`):
   - ❌ `shell=True`, `eval()`, `os.system()`
   - ❌ `import socket`, `import ctypes`, `import pickle`, `import base64`
   - ❌ `open()` en modo escritura fuera de rutas permitidas
   - ❌ `os.remove`, `shutil.rmtree` en código fuente del agente

---

## Labels Guide for AI Agents

### Issue Labels

**Type Labels:**
- `bug` - Algo no funciona
- `enhancement` / `feature-request` - Nueva funcionalidad o mejora
- `documentation` - Trabajo de documentación
- `question` - Preguntas sobre el proyecto
- `platform-maintenance` - Mantenimiento de infraestructura o CI

**Priority Labels:**
- `priority:P0` - Crítico, requiere atención inmediata
- `priority:P1` - Alta prioridad
- `priority:P2` - Prioridad media
- `priority:P3` - Baja prioridad

**Status Labels:**
- `good first issue` / `buen primer issue` - Adecuado para recién llegados
- `help wanted` / `Se necesita ayuda` - Requiere atención adicional
- `needs-human` - Requiere decisión o intervención humana

**Resolution Labels:**
- `duplicate` - Issue/PR duplicado
- `invalid` / `no valido` - No procede
- `wontfix` / `no solucionar` - No se implementará

### Pull Request Labels

**PR State Labels** (gestionadas por la automatización `pr-state-labeler.yml` — NO aplicar manualmente):
- `pr:draft` - PR en borrador / trabajo en progreso
- `pr:checks-pending` - Checks de CI ejecutándose
- `pr:checks-failed` - Algún check de CI falló
- `pr:needs-review` - CI verde, listo para revisión de maintainers
- `pr:changes-requested` - Maintainer solicitó cambios
- `pr:approved` - Aprobaciones humanas requeridas concedidas
- `pr:merged` - PR fusionada en main
- `pr:blocked` - Bloqueada por conflictos o dependencias

---

## Common Workflows

### Protocolo de Higiene de Ramas (A-Dev Regla 50)
1. **Limpieza de ramas fusionadas**: Eliminar ramas locales y remotas ya integradas.
2. **Sincronizar con `origin/main`**: Asegurarse de que `main` está actualizado (`git checkout main && git pull origin main`).
3. **Rama dedicada por cambio (Reglas 48 y 49)**: Crear SIEMPRE una rama limpia desde el `main` más actual. Nunca reutilizar ramas previas. Nomenclatura obligatoria: `feat/issue-XXX-desc`, `fix/issue-XXX-desc`, `docs/issue-XXX-desc`, `chore/issue-XXX-desc`.

### Issue → PR → Merge Workflow
1. **Issue creado** con etiquetas de tipo y prioridad.
2. **Creación de rama** siguiendo el protocolo de higiene.
3. **Desarrollo y tests locales**: `pytest tests/` + `ruff format --check` + `ruff check`.
4. **PR creada** con `Closes #XXX` en el cuerpo y título bajo Conventional Commits.
5. **CI checks ejecutan automáticamente** (12 workflows coordinados).
6. **Revisión de código**: Revisión humana obligatoria por miembros de `core-devs` (con comentarios consultivos del bot `yap-reviewer`).
7. **Merge**: Auto-merge nativo o fusión manual tras CI verde y aprobación humana.

---

## File Locations

```
Yap/
├── AGENTS.md              # ESTE ARCHIVO — guía y contrato operativo para agentes IA
├── ADEV.md                # Doctrina A-Dev upstream
├── CLAUDE.md              # Resumen arquitectónico técnico
├── CONTRIBUTING.md        # Guía de contribución para la comunidad
├── GOVERNANCE.md          # Gobernanza de la organización ChincoLinux
├── yap.py                 # Shim de entrada: from yap import main (#204)
├── yap/                   # Paquete principal del agente (implementación stdlib-only)
├── yap_core.py            # Motor desacoplado con streaming asíncrono (#152)
├── yap_desktop/           # Aplicación gráfica de escritorio (PyQt6/PySide6)
├── setup.sh               # Instalador interactivo / compilador de llama.cpp
├── build-deb.sh           # Generador de paquetes Debian (.deb)
├── deploy-yap.sh          # Despliegue masivo por SSH para laboratorios
├── i18n/                  # Traducciones JSON (es, en, arn)
├── whitelist/             # Listas blancas de seguridad
│   ├── apps.conf          # Aplicaciones permitidas multi-binario
│   └── web.conf           # Dominios web aprobados
├── cursos/                # Material pedagógico en JSON (FPY1101, etc.)
├── tests/                 # Suite completa (más de 1200 pruebas, 0 dependencias externas)
├── docs/                  # Documentación extendida (ROADMAP, RAG, REVIEW, TRUNK-BASED, etc.)
├── .github/
│   ├── workflows/         # 12 workflows de CI/CD y automatización
│   ├── adev/              # Políticas Hardness y agentes de revisión
│   └── ISSUE_TEMPLATE/    # Plantillas de issues de GitHub
├── .githooks/             # Hook post-checkout (detección de rama y modelo)
└── apparmor/              # Perfil AppArmor de confinamiento en producción
```

---

## Resources

- [A-Dev](https://github.com/scanalesespinoza/adev) — doctrina upstream
- [Trunk-Based Development](https://trunkbaseddevelopment.com/) — referencia externa
- `docs/TRUNK-BASED.md` — overlay local TBD
- `docs/REVIEW.md` — checklist previo a solicitar revisión
- `CLAUDE.md` — tarjeta de arquitectura técnica complementaria
