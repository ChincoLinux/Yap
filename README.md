# Yap: Asistente de IA Local para Entornos Educativos con Recursos Limitados

**Version:** `1.0.1` (ver [`VERSION`](VERSION) · [CHANGELOG.md](CHANGELOG.md)) | [![Yap CI](https://github.com/VECTORG99/Yap/actions/workflows/test.yml/badge.svg)](https://github.com/VECTORG99/Yap/actions/workflows/test.yml)

**Sistema de agente conversacional basado en **Llama 3.2**, ejecucion **CPU-only**, disenado para **Debian 13** con soporte de 3 a 8 GB de RAM mediante ramas de configuracion graduales.**

| | |
|---|---|
| **Modelo** | Llama 3.2 3B / 1B Instruct (GGUF Q4_K_M) |
| **Runtime** | llama.cpp, CPU-only, enlace estatico |
| **Dependencias de Python** | ninguna (solo stdlib) |
| **Dependencias de tests** | `pytest` |
| **Idioma** | Espanol |
| **Licencia** | MIT |

---

## Resumen

**Yap** es un asistente de inteligencia artificial que opera integramente en local
sobre CPU, sin dependencia de conexion a Internet para su funcionamiento base.
Emplea el modelo **Llama 3.2 Instruct** (GGUF Q4_K_M) ejecutado mediante
**llama.cpp** con enlace estatico, e implementa un sistema de seguridad basado
en **listas blancas** (whitelist) de aplicaciones y dominios. El proyecto se
distribuye en **tres ramas** (`main`, `lowmem`, `ultra-lowmem`) que escalan el
consumo de RAM desde ~3.5 GB hasta ~1.8 GB, adaptandose a hardware educativo de
distintas capacidades. La clasificacion de intenciones se realiza mediante el
propio LLM, eliminando la necesidad de patrones rigidos y proporcionando
tolerancia a errores ortograficos y variaciones sintacticas.

No es solo un chat: es un **entorno de practica para el aula**. Sobre el mismo
agente hay un sistema de cursos con RAs y EAs, catalogo de ejercicios PSeInt
evaluados automaticamente, tutor paso a paso, perfil del estudiante, historial
persistente entre sesiones, dificultad adaptativa, RAG local offline, feedback
pedagogico con nota chilena, telemetria anonima en disco y modo accesible para
lector de pantalla. Todas esas capacidades viven en un unico archivo,
[`yap.py`](yap.py), y operan 100% offline.

| Documento | Para que |
|---|---|
| [USAGE.md](USAGE.md) | Referencia rapida de comandos y solucion de problemas |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Despliegue individual y masivo en red escolar |
| [docs/PACKAGING.md](docs/PACKAGING.md) | Empaquetado `.deb` y repositorio apt |
| [docs/SUPER-YAP.md](docs/SUPER-YAP.md) | Cliente Gradio en Cloud Run (opt-in) |
| [docs/RAG.md](docs/RAG.md) | RAG local con BM25, sin dependencias |
| [docs/SECURITY-AUDIT.md](docs/SECURITY-AUDIT.md) | Auditoria de seguridad post-talleres |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Roadmap y prioridades |
| [tests/README.md](tests/README.md) | Suite de pruebas: 21 archivos, 825 tests |
| [AGENTS.md](AGENTS.md) | Guia para agentes IA que colaboran en el repo |
| [CLAUDE.md](CLAUDE.md) | Arquitectura tecnica resumida |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Como contribuir |

---

## Estructura del repositorio

```
Yap/
├── yap.py                 # El agente completo (~6200 lineas, stdlib-only)
├── setup.sh               # Instalador de desarrollo: compila llama.cpp, baja el modelo
├── build-deb.sh           # Genera yap_*.deb y yap-models-*.deb (#31)
├── deploy-yap.sh          # Despliegue masivo por SSH en un lab (#31)
├── VERSION                # Version, leida por setup.sh y auto-release
├── whitelist/
│   ├── apps.conf          # Aplicaciones permitidas (Nombre:bin1,bin2)
│   ├── web.conf           # Dominios permitidos para webfetch
│   └── pseint/
│       ├── ejercicios.conf        # Catalogo v1 y v2
│       └── guia_ejercicios.pdf    # Guia de solucion, la abre el tutorial
├── cursos/                # Cursos en JSON (FPY1101.json)
├── packaging/             # Plantillas DEBIAN: yap, yap-models-1b, yap-models-3b
├── apparmor/              # Perfiles AppArmor del agente (#14)
├── tests/                 # 21 archivos de pruebas, 825 tests + run_tests.py
├── docs/                  # DEPLOY, PACKAGING, RAG, ROADMAP, SECURITY-AUDIT, SUPER-YAP, TRUNK-BASED
├── scripts/ci/            # Utilidades de CI: trazabilidad PR, labels, preflight
├── agent-platform/        # Plantillas de despliegue de Super Yap
├── .githooks/post-checkout# Aviso de cambio de modelo al cambiar de rama
├── .github/
│   ├── workflows/         # 11 workflows (CI, revision A-Dev, releases, quality gates)
│   ├── adev/              # Politicas Hardness, agente reviewer, RAG, skills
│   └── ISSUE_TEMPLATE/
├── AGENTS.md  CLAUDE.md  ADEV.md  GOVERNANCE.md  CONTRIBUTING.md
├── README.md  USAGE.md  CHANGELOG.md  SECURITY.md  SUPPORT.md  CODE_OF_CONDUCT.md
└── LICENSE   MIT
```

---

## Tabla de contenidos

- [1. Objetivos](#1-objetivos)
- [2. Especificaciones tecnicas](#2-especificaciones-tecnicas)
- [3. Arquitectura del sistema](#3-arquitectura-del-sistema)
- [4. Componentes del stack tecnologico](#4-componentes-del-stack-tecnologico)
- [5. Seguridad](#5-seguridad)
- [6. Instalacion](#6-instalacion)
- [7. Ramas de configuracion](#7-ramas-de-configuracion)
- [8. Uso](#8-uso)
- [9. Limitaciones](#9-limitaciones)
- [10. Trabajo futuro](#10-trabajo-futuro)
- [11. Licencia](#11-licencia)
- [12. Pruebas y verificacion](#12-pruebas-y-verificacion)
- [13. Contribuir](#13-contribuir)

---

## 1. Objetivos

Construir un sistema Debian estable ultraligero con un agente IA local (**CPU-only**) capaz de:

- **Responder en espanol** con enfoque educativo.
- **Ejecutar acciones seguras** del sistema mediante tooling controlado por whitelist.
- **Abrir aplicaciones** desde una lista blanca configurable.
- **Recuperar informacion** de sitios web aprobados.
- **Aplicar restricciones** para acciones sensibles.
- **Emitir alertas graficas** mediante `notify-send`.
- **Practicar y evaluar** con un sistema de cursos y ejercicios, sin salir del aula.
- **Functionar sin conexion**: todo el material pedagogico vive en disco y se
  indexa con un RAG local.

---

## 2. Especificaciones tecnicas

| Componente | Detalle |
|---|---|
| **Modelo** | Llama 3.2 3B Instruct (GGUF Q4_K_M) / 1B Instruct |
| **Runtime** | llama.cpp (CPU-only, enlace estatico) |
| **RAM minima** | ~3.5 GB (main), ~3.1 GB (lowmem), ~1.8 GB (ultra-lowmem) |
| **Contexto** | `MAX_CTX = 2048` tokens (constante en `yap.py`; cada rama ajusta su `llama-cli`) |
| **Historial** | `MAX_HISTORY = 6` turnos en memoria; `MAX_HISTORY_SESSIONS = 20` sesiones en disco |
| **Latencia estimada** | 5-10 s primeros tokens en CPU (2 nucleos), ~40 tok/s |
| **Idioma** | Espanol |
| **SO destino** | Debian 13 (64-bit) |
| **Dependencias Python** | ninguna — `yap.py` es stdlib-only por politica del proyecto |

### 2.1 Constantes de configuracion

Todas en el bloque superior de [`yap.py`](yap.py), sobreescribibles por variable
de entorno cuando el caso lo pide:

| Constante | Default | Entorno | Para que |
|---|---|---|---|
| `MODEL_PATH` | `/opt/yap/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf` | `YAP_MODEL_PATH` | Techo 3B: un path con 8B se ignora y cae al 3B |
| `MAX_CTX` | `2048` | — | Tokens de contexto de `llama-cli` |
| `MAX_HISTORY` | `6` | — | Turnos de conversacion en memoria |
| `LLAMA_THREADS` | `2` | `YAP_LLAMA_THREADS` | Hilos de inferencia |
| `LLAMA_TEMP_QUERY` | `0.7` | `YAP_LLAMA_TEMP_QUERY` | Temperatura de respuesta |
| `LLAMA_TEMP_PSEINT` | `0.5` | `YAP_LLAMA_TEMP_PSEINT` | Temperatura del tutor |
| `LLAMA_TEMP_CLASSIFY` | `0.1` | `YAP_LLAMA_TEMP_CLASSIFY` | Baja, para que el clasificador sea estable |
| `LLAMA_TEMP_EVAL` | `0.2` | `YAP_LLAMA_TEMP_EVAL` | Baja, para que el evaluador devuelva JSON |
| `MAX_INTENTOS_EJERCICIO` | `3` | `YAP_MAX_INTENTOS` | Intentos por actividad o ejercicio |
| `PUNTAJE_APROBACION` | `60` | `YAP_PUNTAJE_APROBACION` | Puntaje que se considera aprobado |
| `MAX_OPEN_SESSIONS` | `3` | `YAP_MAX_SESSIONS` | Sesiones abiertas simultaneas |
| RAG | `RAG_ENABLED=1`, `RAG_TOP_K=5`, `RAG_MAX_CONTEXT_TOKENS=512` | `YAP_RAG_ENABLED`, `YAP_RAG_TOP_K`, `YAP_RAG_MAX_TOKENS` | Recuperacion contextual local sobre `cursos/`, `docs/`, `whitelist/`, `USAGE.md` y `AGENTS.md` (#118) |
| Super Yap | opt-in | `YAP_SUPER_ENABLED`, `YAP_SUPER_ENDPOINT`, `YAP_SUPER_TOKEN`, `YAP_SUPER_TOKEN_FILE`, `YAP_SUPER_TIMEOUT`, `YAP_SUPER_HOSTS`, `YAP_SUPER_INTERNET` | Cliente Gradio en Cloud Run (#91) |
| Diagnostico | apagado | `YAP_DEBUG` | Trazas internas |

---

## 3. Arquitectura del sistema

### 3.1 Diagrama de capas

```
+----------+     +---------+     +------------+
| Usuario  | --> | CLI yap | --> | interpret()|
+----------+     +---------+     +------------+
                                        |
              +-------------------------+-------------------------+
              |                         |                         |
              v                         v                         v
     +------------------+     +------------------+     +------------------+
     | Rutas por teclado|     | classify_intent()|     | Menu numerado    |
     | (sin LLM)        |     | (LLM, temp 0.1)  |     | (TUI)            |
     +------------------+     +------------------+     +------------------+
              |                         |                         |
              +-------------------------+-------------------------+
                                        |
                                        v
                              +--------------------+
                              |  handle_action()   |
                              +--------------------+
                                        |
     +-----------+-----------+-----------+-----------+-----------+
     |           |           |           |           |           |
     v           v           v           v           v           v
+----------+ +---------+ +--------+ +---------+ +--------+ +--------+
| Whitelist| | Whitelist| |  LLM   | |  RAG    | |Evaluac.| |Sesiones|
| apps     | | web     | | local  | | BM25    | |LLM     | |perfil  |
+----------+ +---------+ +--------+ +---------+ +--------+ +--------+
     |           |           |           |           |           |
     v           v           v           v           v           v
+----------+ +---------+ +--------+ +---------+ +--------+ +--------+
| Lanzar   | | Webfetch| |Respues-| |Contexto | |Puntaje | |Historial|
| app      | | + 3000  | |ta      | |recuperado| |nota 1-7| | en disco|
| + alerta | | chars   | |        | |         | |        | |
+----------+ +---------+ +--------+ +---------+ +--------+ +--------+
```

### 3.2 Flujo de una consulta

1. El usuario escribe un comando o pregunta en la terminal, o elige una opcion
   del menu numerado.
2. `interpret()` (`yap.py:5825`) decide sin gastar LLM cuando puede: rutas por
   teclado (`abre`, `busca`, `pseint`, `curso`, `sesion`, `telemetria`, `rag`,
   `super`, `perfil`, `menu`...) y opciones del menu por numero. Con el modelo 1B
   el clasificador acierta poco, asi que todo lo que el menu anuncia tiene una
   ruta directa.
3. Si nada coincide, `classify_intent()` (`yap.py:5757`) consulta al LLM con un
   prompt de clasificacion y recibe `ACCION|PARAMETRO`.
4. `handle_action()` (`yap.py:6059`) ejecuta la accion, actualiza el historial y
   los contadores de telemetria.
5. El resultado se muestra en pantalla; si procede, se lanza el RAG y se evaluan
   actividades cuando la sesion esta dentro de un curso.

### 3.3 Componentes del sistema

| Componente | Funcion |
|---|---|
| **TUI** | Interfaz de linea de comandos: curses nativo, ANSI directo, 0 dependencias |
| **Menu numerado** | 15 opciones que cubren lo mas usado sin memorizar comandos |
| **Router `interpret()`** | Resuelve ordenes conocidas sin pasar por el LLM |
| **Clasificador** | `classify_intent()` decide la intencion con el propio LLM |
| **Whitelist de apps** | Lista de aplicaciones permitidas con soporte multi-binario |
| **Whitelist de dominios** | Lista de dominios permitidos para webfetch |
| **LLM local** | Llama 3.2 via `llama-cli`, CPU-only, con historial |
| **Super Yap** | Cliente Gradio en Cloud Run, opt-in, con reenvio de `HISTORY` |
| **RAG local** | Recuperacion contextual con Okapi BM25, 100% stdlib ([docs/RAG.md](docs/RAG.md)) |
| **Cursos** | JSON en `cursos/`, con RAs, EAs, actividades y evaluaciones tipadas |
| **Ejercicios PSeInt** | Catalogo v1/v2 con 4 tipos de evaluacion y pistas progresivas |
| **Evaluador** | Puntaje + feedback por LLM, con fallback textual sin LLM |
| **Perfil** | Nombre, nivel e idioma, inyectados al system prompt (#24) |
| **Sesiones** | Pausa, retoma, archiva; el contexto sobrevive al cierre (#21) |
| **Historial** | Ultimas 20 sesiones en disco, reanudables (#13) |
| **Dificultad adaptativa** | Sube o baja el nivel segun el rendimiento (#30) |
| **Accesibilidad** | Alto contraste, fuentes 2x, deteccion de Orca, teclado (#37) |
| **Telemetria** | Contadores locales anonimos, exportables y desactivables (#38) |
| **Notificador** | Alertas graficas mediante `notify-send` |

---

## 4. Componentes del stack tecnologico

### 4.1 Bash — Script de instalacion (`setup.sh`)

El instalador automatiza la configuracion del entorno. Conceptos clave:

| Concepto | Explicacion |
|---|---|
| **`set -euo pipefail`** | Modo estricto: `-e` aborta en error; `-u` variables no definidas como error; `-o pipefail` propaga errores en tuberias |
| **`SCRIPT_DIR`** | Obtiene la ruta absoluta del directorio del script mediante `${BASH_SOURCE[0]}` antes de leer `VERSION` |
| **`git clone --depth 1`** | Clonado superficial (un solo commit) para minimizar ancho de banda |
| **`cmake` + `cmake --build`** | Configuracion y compilacion con `-DBUILD_SHARED_LIBS=OFF` para enlace estatico |
| **Descarga del modelo** | Lee `MODEL_PATH` de `yap.py` y descarga el `.gguf` correspondiente (3B o 1B) |
| **`ln -sf`** | Enlace simbolico a `yap.py` en el repositorio; `git pull` actualiza sin reinstalar |
| **`core.hooksPath`** | Instala `.githooks/post-checkout`, que informa del cambio de modelo al cambiar de rama |

### 4.2 Python — Agente principal (`yap.py`)

Un solo archivo, ~6200 lineas, **stdlib-only**. Los imports son a proposito
pocos: `subprocess`, `sys`, `os`, `time`, `shutil`, `textwrap`, `json`, `glob`,
`urllib.*`, `http.cookiejar`, `re`, `atexit`, `unicodedata`, `math`, `hashlib`.
Prohibidos por politica: `socket`, `ctypes`, `pickle`, `base64`, `requests`.

Mapa por bloques (los numeros de linea son de la version en `main`):

| Lineas | Bloque | Que hace |
|---|---|---|
| 1–29 | Constantes de rutas | `/etc/yap/{whitelist,pseint,cursos}` |
| 31–127 | TUI ChincoLinux | ASCII art, cajas, menu numerado, paleta ANSI |
| 130–158 | Modelo y constantes | `MODEL_PATH`, `MAX_CTX`, temperaturas, tipos de ejercicio |
| 160–217 | Super Yap (#91) | Ajustes de cliente Gradio, whitelist de hosts |
| 218–308 | Confirmacion humana (#12) | Acciones sensibles, niveles de confianza, persistencia |
| 309–332 | Whitelists | `load_whitelist()`, `load_domain_whitelist()` |
| 333–588 | Ejercicios y cursos | Parser v1/v2, catalogo, carga y validacion de cursos |
| 590–687 | Validacion de cursos | Esquema de JSON, actividades evaluables, listado |
| 688–932 | Perfil (#24) | Config, normalizacion, escritura atomica, system prompt |
| 933–1324 | Accesibilidad (#37) | Opciones, sanitizado ANSI, deteccion de Orca, alto contraste, fuentes grandes |
| 1325–1457 | Teclado (#37) | Lectura de teclas, menu interactivo navegable |
| 1458–1577 | Progreso e historial (#13) | `progress.json`, ultimas 20 sesiones, `cmd_historial()` |
| 1578–1961 | Sesiones (#21) | CRUD, pausa, retoma, archivo, prompt con contexto |
| 1962–2187 | Telemetria (#38) | Contadores, acciones sin usar, exportacion, borrado |
| 2188–2245 | Onboarding y progreso | Tutorial de bienvenida, carga/guardado |
| 2246–2661 | RAG local (#118) | Tokenizador, chunking, `RagBM25Index`, persistencia, `cmd_rag()` |
| 2662–3270 | Evaluacion (#23) | Schema, parser de JSON del LLM, fallback, nota chilena |
| 3271–3984 | Ejercicios (#27) | Evaluacion por tipo, pistas, intentos, `cmd_ejercicios()` |
| 3985–4165 | Adaptativo (#30) | `AdaptiveEngine`: reglas de subida, bajada y mantenimiento |
| 4166–4673 | Cursos | `cmd_curso()`, `iniciar_ea()`, `cmd_mostrar_progreso()` |
| 4674–4780 | Notificacion y AppArmor (#14) | `notify()`, `apparmor_status()`, `cmd_apparmor_status()` |
| 4781–4858 | Acciones base | `cmd_open_app()` con `shutil.which()`, `cmd_webfetch()` con 3000 chars |
| 4859–5481 | Super Yap cliente | Delegacion, hosts permitidos, SSE, `cmd_query_super()` |
| 5482–5756 | Consultas y PSeInt | `cmd_query()`, `cmd_pseint()`, `cmd_intro_pseint()` |
| 5757–5824 | `classify_intent()` | Clasificacion con LLM, temp 0.1, fallback a `query` |
| 5825–5953 | `interpret()` | Rutas por teclado, menu por numero, delegacion al clasificador |
| 5954–6221 | `main()` y `handle_action()` | Arranque, TUI curses, REPL de reserva, despacho de acciones |

### 4.3 llama.cpp y GGUF

| Componente | Rol |
|---|---|
| **llama.cpp** | Runtime de inferencia en C/C++ para modelos Llama en CPU. Compilado desde fuente con enlace estatico (`-DBUILD_SHARED_LIBS=OFF`) |
| **GGUF** | Formato de archivo para modelos cuantizados. **Q4_K_M**: cuantizacion de 4 bits con mezcla K-quant, balance calidad-rendimiento |
| **llama-cli** | Parametros: `-m` (modelo), `-p` (prompt), `-n 384` (tokens), `--temp` (por tipo de consulta), `--ctx-size 2048`, `--cache-type-k/v q8_0` (KV cache cuantizada), `--threads 2`, `-no-cnv`, `--no-display-prompt` |

Las nueve llamadas a `subprocess` pasan `stdin=subprocess.DEVNULL` y todas
llevan `timeout=`. Sin eso, `llama-cli` heredaba la terminal, apagaba el eco con
`tcsetattr` y las consultas del estudiante se volvian invisibles a partir de la
segunda pregunta (#99).

### 4.4 CMake — Sistema de compilacion

| Parametro | Explicacion |
|---|---|
| **`-DCMAKE_BUILD_TYPE=Release`** | Optimiza el binario para velocidad |
| **`-DBUILD_SHARED_LIBS=OFF`** | Enlaza todo estaticamente; sin dependencia de `libllama.so` |
| **`-DLLAMA_CURL=OFF`** | Deshabilita soporte CURL (se usa `wget` para descargas) |
| **`-DLLAMA_CUDA=OFF`** | Deshabilita soporte GPU NVIDIA |
| **`-DLLAMA_METAL=OFF`** | Deshabilita soporte GPU Apple |

### 4.5 VirtualBox — Entorno de desarrollo

| Comando | Funcion |
|---|---|
| **`VBoxManage createvm`** | Crea y registra una maquina virtual |
| **`VBoxManage modifyvm`** | Configura RAM, CPU, VRAM y red NAT |
| **`VBoxManage createmedium disk`** | Crea disco virtual de 50 GB dinamico |
| **`VBoxManage storagectl`** | Agrega controlador SATA |
| **`VBoxManage storageattach`** | Monta ISO de instalacion |
| **`VBoxManage startvm`** | Inicia la maquina virtual |

### 4.6 Debian Linux — Paquetes del sistema base

| Paquete | Proposito |
|---|---|
| **build-essential** | Compilador `gcc` y herramientas base para llama.cpp |
| **cmake** | Generador de archivos de compilacion |
| **libcurl4-openssl-dev** | Headers de libcurl (requerido por llama.cpp) |
| **python3-pip** | Instalador de paquetes Python |
| **libnotify-bin** | Cliente `notify-send` para alertas graficas |
| **libreoffice, evince, firefox-esr, micro, htop** | Aplicaciones incluidas en la whitelist |

---

## 5. Seguridad

La seguridad de Yap no depende de un solo mecanismo: son capas
independientes, y todas estan cubiertas por pruebas.

### 5.1 Capas de defensa

| Capa | Que impide |
|---|---|
| **Whitelist de binarios** | Ejecutar cualquier comando del sistema |
| **Whitelist de dominios** | Salir a la red hacia donde no sea |
| **Validacion estricta de dominio** | Que `notwikipedia.org` pase por `wikipedia.org` |
| **`shell=False` siempre** | Inyeccion de comandos via metacaracteres |
| **`timeout=` en toda llamada** | Que el agente se cuelgue esperando un subproceso |
| **`stdin=DEVNULL`** | Que un hijo robe la terminal y apague el eco (#99) |
| **Limite de 3000 chars** | Que una pagina entera se coma el contexto |
| **Confirmacion humana (#12)** | Acciones sensibles sin una segunda confirmacion |
| **AppArmor (#14)** | Que el proceso se escape de su perfil declarado |
| **Sin escritura fuera de rutas** | Que el agente modifique archivos del sistema |
| **Sin imports peligrosos** | `socket`, `ctypes`, `pickle`, `base64` estan prohibidos |

### 5.2 Whitelist de aplicaciones (`/etc/yap/whitelist/apps.conf`)

- Mapea **nombres visibles** a comandos del sistema: `Nombre:bin1,bin2`.
- Soporta **multiples binarios alternativos** separados por coma (ej. `firefox-esr,firefox`).
- El agente prueba cada binario en orden hasta encontrar uno disponible mediante
  `shutil.which()`, y valida con `shutil.which()` **antes** de cualquier
  `Popen`.
- Si la app no esta en la lista, el bloqueo es **graceful**: muestra `[ERROR]` y
  la lista de apps permitidas, sin ejecutarla.

### 5.3 Whitelist de dominios (`/etc/yap/whitelist/web.conf`)

- Lista de dominios permitidos para **webfetch**.
- Validacion estricta: coincidencia exacta o subdominio directo
  (`domain == d or domain.endswith("." + d)`).
- Contenido limitado a **3000 caracteres** (`text[:3000]` en `cmd_webfetch()`).
- Se rechazan esquemas no HTTP y destinos locales: `file:///etc/passwd`,
  `127.0.0.1`, `[::1]`, `javascript:`.

> **Correccion de seguridad** (commit `348e9b0`): la implementacion original
> usaba `domain.endswith(d)`, lo que permitia que `notwikipedia.org` coincidiera
> con `wikipedia.org`. El test `test_notwikipedia_no_coincide` fija el
> comportamiento.

### 5.4 Confirmacion humana para acciones sensibles (#12)

`confirm_action()` pide una segunda confirmacion antes de ejecutar acciones
marcadas como sensibles. Las respuestas quedan registradas y una accion
confirmada se marca como confiable para no volver a preguntar
(`_record_confirmation`, `_is_trusted`). La persistencia sobrevive entre
ejecuciones.

### 5.5 AppArmor (#14)

`apparmor_status()` informa si el perfil del agente esta cargado y en modo
`enforce` o `complain`. Los perfiles viven en [`apparmor/`](apparmor/) y se
instalan con el paquete `.deb`. Comandos: `yap --apparmor-status`.

### 5.6 Datos que el agente puede tocar

Lectura (configuracion del sistema, nunca se escribe):

| Ruta | Proposito |
|---|---|
| `/etc/yap/whitelist/` | Whitelists de apps y dominios |
| `/etc/yap/cursos/` | Cursos JSON |
| `/etc/yap/pseint/` | Catalogo de ejercicios y guia en PDF |
| `cursos/*.json`, `docs/*.md`, `whitelist/*.conf`, `USAGE.md`, `AGENTS.md` | Corpus del RAG local |

Escritura (solo bajo `~/.config/yap/`, que respeta `$XDG_CONFIG_HOME`):

| Ruta | Proposito |
|---|---|
| `~/.config/yap/profile.json` | Perfil: nombre, nivel, idioma, accesibilidad, estadisticas |
| `~/.config/yap/progress.json` | Progreso del estudiante en cursos y ejercicios |
| `~/.config/yap/history.json` | Ultimas 20 sesiones, reanudables |
| `~/.config/yap/sessions.json` | Sesiones abiertas, pausadas y archivadas |
| `~/.config/yap/telemetry.json` | Contadores locales anonimos de uso |
| `~/.config/yap/index/bm25_index.json` | Indice RAG, reconstruido cuando cambia el hash del corpus |

`os.remove` y `shutil.rmtree` no aparecen en el codigo fuente. Las escrituras
son atomicas (`os.replace` sobre un `.tmp`), asi que un corte de energia no
deja un JSON truncado. La telemetria es anonima, local y desactivable:
`telemetria off` y `telemetria borrar`.

### 5.7 Acciones bloqueadas por diseno

- Ejecucion de comandos arbitrarios del sistema.
- Operaciones de red fuera de la whitelist.
- Instalacion o eliminacion de software.
- Modificacion de archivos del sistema.
- Lectura arbitraria del disco.

### 5.8 Auditoria

Los hallazgos de la revision de seguridad estan en
[docs/SECURITY-AUDIT.md](docs/SECURITY-AUDIT.md), y el fuzzing de entrada
(path traversal, esquemas, unicode, JSON corrupto, inputs grandes) vive en
`tests/test_yap_security_audit.py` (27 pruebas).

## 6. Instalacion

### 6.1 Requisitos del sistema

- **SO:** Debian 13 (o derivada) 64-bit.
- **RAM:** 8 GB (main), 6 GB (`lowmem`), 3-4 GB (`ultra-lowmem`).
- **Disco:** 5 GB libres, de los cuales el modelo ocupa 0.81 GB (1B) o 2.0 GB (3B).
- **Red:** solo durante la instalacion, para clonar y descargar el modelo.
  Despues, Yap funciona 100% offline.
- **Para compilar:** `build-essential` y `cmake` (no hacen falta si instalas el
  `.deb`, que trae `llama-cli` precompilado).

### 6.2 Paquete .deb (recomendado en aulas)

```bash
sudo apt install ./yap_1.0.1_amd64.deb
sudo apt install ./yap-models-1b_1.0.1_all.deb    # ~2 GB RAM
# sudo apt install ./yap-models-3b_1.0.1_all.deb  # ~3.5 GB RAM
```

Los tres paquetes:

| Paquete | Contenido |
|---|---|
| `yap` | El agente, `llama-cli` precompilado, whitelists, AppArmor, symlink |
| `yap-models-1b` | Llama 3.2 1B Q4_K_M (0.81 GB) — para equipos de 3-4 GB |
| `yap-models-3b` | Llama 3.2 3B Q4_K_M (2.0 GB) — para equipos de 8 GB |

No requiere `setup.sh` ni `build-essential`. Como construir los paquetes, montar
un repositorio apt o generar una ISO offline: [docs/PACKAGING.md](docs/PACKAGING.md).

### 6.3 Procedimiento de desarrollo (`setup.sh`)

```bash
git clone https://github.com/ChincoLinux/Yap.git
cd Yap
# Opcional: seleccionar rama antes de instalar
# git checkout lowmem         # 6 GB RAM
# git checkout ultra-lowmem   # 3-4 GB RAM
bash setup.sh
```

> **Nota sobre ramas:** Al clonar, git descarga todas las ramas remotas pero
> solo hace checkout de `main`. Para cambiar a `lowmem` o `ultra-lowmem`,
> simplemente `git checkout lowmem` — git creará la rama local automáticamente.
> Si usaste `git clone --depth 1` (clon superficial), primero ejecuta
> `git fetch --all` para descargar las demás ramas antes de hacer checkout.

El instalador realiza automaticamente:

1. Instalacion de dependencias del sistema (`build-essential`, `cmake`, `python3`, `libnotify`, `libcurl`).
2. Compilacion de **llama.cpp** desde fuente con enlace estatico.
3. **Descarga del modelo** — Lee `MODEL_PATH` de `yap.py` y descarga el `.gguf` correspondiente (3B o 1B).
4. Instalacion del agente Yap y whitelists en `/etc/yap/`.
5. Instalacion de la configuracion de PSeInt y de los cursos en `/etc/yap/`.
6. Instalacion de aplicaciones sugeridas (LibreOffice, Firefox, Evince, Micro, Htop).
7. Enlace simbolico `/usr/local/bin/yap` y activacion de `.githooks/post-checkout`.
8. Verificacion de componentes.

### 6.4 Despliegue en un laboratorio

```bash
./deploy-yap.sh --user alumno --parallel 4          # por SSH a varios equipos
./deploy-yap.sh --user alumno --dry-run              # ver que haria, sin ejecutar
./deploy-yap.sh --mirror /srv/mirror/Yap --branch main   # desde un mirror NFS/HTTP
```

Opciones: `--mirror`, `--branch`, `--whitelist`, `--user`, `--dry-run`,
`--parallel`. Guia completa, incluidos los permisos sudoers del administrador y
el checklist de despliegue: [docs/DEPLOY.md](docs/DEPLOY.md).

### 6.5 Actualizacion

```bash
cd ~/Yap
git pull
# El enlace simbolico en /usr/local/bin/yap apunta al repositorio;
# no es necesario reinstalar.
```

Cambiar de modelo (por ejemplo, de `ultra-lowmem` a `main`) si requiere
descargar el `.gguf` que falta. La tabla de cuando hace falta re-ejecutar
`setup.sh` esta en la seccion 7.3.

---

## 7. Ramas de configuracion

El proyecto mantiene **tres ramas** con distintos perfiles de consumo de RAM y calidad de respuesta:

| Rama | Modelo | Contexto | KV Cache | RAM total | Ideal para |
|---|---|---|---|---|---|
| **main** | 3B Q4_K_M (2.0 GB) | 4096 | FP16 | ~3.5 GB | 8 GB+ RAM |
| **lowmem** | 3B Q4_K_M (2.0 GB) | 2048 | Q8_0 | ~3.1 GB | 6 GB RAM |
| **ultra-lowmem** | 1B Q4_K_M (0.81 GB) | 2048 | Q8_0 | ~1.8 GB | 3-4 GB RAM |

> La tabla describe el perfil objetivo de cada rama. El valor efectivo es el
> `MAX_CTX` del `yap.py` que tienes en el disco, y el CI lo verifica con
> `branch-check`. En `main` en este momento `MAX_CTX = 2048`.

**Techo del modelo: 3B.** `_modelo_local_path()` descarta cualquier
`YAP_MODEL_PATH` que apunte a un 8B y cae al 3B; el 1B sigue permitido para
`ultra-lowmem`.

**Super Yap** (opt-in, issue #91) consulta Gradio `/chat` en Cloud Run si el Yap local (1B/3B) **tarda 3 minutos** o se pasa de tokens, **sin perder el historial**. No hay modelo 8B local. `super on` / `super off` cambian el motor. Ver [docs/SUPER-YAP.md](docs/SUPER-YAP.md).

### 7.1 Cambio entre ramas

```bash
cd ~/Yap
git checkout main        # maxima calidad
git checkout lowmem        # balanceado
git checkout ultra-lowmem  # minima RAM
```

El enlace simbolico en `/usr/local/bin/yap` apunta al repositorio: el cambio es inmediato.

### 7.2 Hook post-checkout — informacion automatica al cambiar de rama

Al hacer `git checkout <rama>`, un **hook de git** (`.githooks/post-checkout`) se ejecuta automaticamente y muestra:

- **Rama anterior** y modelo que usaba.
- **Rama actual** y modelo que usara.
- **Estado del modelo**: si ya existe en disco o si falta descargar.
- **Modelos inactivos**: se listan pero **no se eliminan** — disponibles para cuando vuelvas a esa rama.
- **Siguiente paso**: si ejecutar `setup.sh` o si ya esta listo para usar.

El hook se activa al instalar con `setup.sh` (configura `git config core.hooksPath .githooks`).

### 7.3 Gestion de modelos

`setup.sh` se ejecuta **una sola vez** al instalar. Detecta automaticamente la rama actual y descarga el modelo que corresponda:

| Cambio | Requiere re-ejecutar `setup.sh` | Accion |
|---|---|---|
| **main** ↔ **lowmem** | **No** | Solo `git checkout` (mismo modelo 3B) |
| **ultra-lowmem** → **main/lowmem** | Solo para descargar modelo 3B | `git checkout` + `sudo wget <URL del 3B>` o re-ejecutar `setup.sh` |
| **main/lowmem** → **ultra-lowmem** | Solo para descargar modelo 1B | `git checkout` + `sudo wget <URL del 1B>` o re-ejecutar `setup.sh` |

Re-ejecutar `setup.sh` despues de cambiar de rama es **seguro**: detecta lo que ya existe y solo descarga lo faltante.

### 7.4 Optimizaciones aplicadas por rama

| Optimizacion | main | lowmem | ultra-lowmem |
|---|---|---|---|
| Contexto (`--ctx-size`) | 4096 | 2048 | 2048 |
| KV cache (`--cache-type-k/v`) | FP16 | Q8_0 | Q8_0 |
| Flash Attention (`--flash-attn`) | No | Si | Si |
| Hilos (`--threads`) | 4 | 2 | 2 |
| Ahorro RAM | — | ~400 MB | ~1.7 GB |

---

Para una referencia rapida de todos los comandos, ejemplos y solucion de problemas, ver [USAGE.md](USAGE.md).

## 8. Uso

### 8.1 Modo interactivo (TUI)

```bash
yap
```

Abre la TUI interactiva nativa (curses, 0 dependencias externas): pantalla dividida con
salida arriba, entrada abajo, prompt **Chinco >** , historial con flechas,
scroll con RePág/AvPág y Tab para completar comandos.

Si la terminal no soporta curses, cae en el REPL clasico de texto.

```text
Chinco > Abre LibreOffice
Chinco > busca variable en programacion
Chinco > salir
```

La primera vez tras instalar se muestra el **onboarding**: que es Yap, como
pedir una app, como llegar a los cursos, y se pide el nombre del estudiante.
Se repite con `yap --tutorial`. En cualquier momento, escribir un numero (1-15)
muestra el **menu de opciones**.

### 8.2 Modo comando directo

```bash
yap Abre LibreOffice
yap Busca https://es.wikipedia.org/wiki/Linux
yap Busca que es una particion de disco
yap Que es Debian?
```

### 8.3 Acciones soportadas

| Accion | Ejemplo | Descripcion |
|---|---|---|
| **Abrir aplicacion** | `yap Abre LibreOffice` | Abre la app si esta en whitelist (soporta multi-binario) |
| **Webfetch + resumen** | `yap Busca https://es.wikipedia.org/wiki/Linux` | Obtiene contenido del sitio, lo limpia de HTML y lo envia al LLM para resumir |
| **Busqueda Wikipedia** | `yap Busca que es Linux` | Consulta la API REST de Wikipedia, extrae contenido y resume con el LLM; muestra la fuente |
| **Consulta LLM** | `yap Que es Debian?` | Responde con el modelo local. Mas rapido pero sin fuente verificable |
| **Menu** | `yap menu` | Vuelve a mostrar las 15 opciones numeradas |
| **Ayuda** | `yap ayuda` | Lista de comandos con descripcion |
| **Guia rapida** | `yap guia` | Tutorial interactivo de 7 pasos por todas las funciones |
| **Tutor PSeInt** | `yap pseint como hago un ciclo mientras` | Guias paso a paso, sin historial, contexto reducido para ahorrar RAM |
| **Tutorial PSeInt** | `yap aprender pseint` | Tutorial interactivo: abre el PDF, lanza PSeInt, guia paso a paso |
| **Ejercicios** | `yap ejercicios` / `yap ejercicios lista` | Practica evaluada: 4 tipos, pistas progresivas, validacion exacta o LLM |
| **Ver curso** | `yap curso FPY1101` | Plan completo: RAs, EAs, horas, ponderaciones |
| **Iniciar EA** | `yap iniciar EA1` | Sesion guiada por una experiencia de aprendizaje |
| **Progreso** | `yap progreso` / `yap mi progreso` | Avance, promedio, reprobadas y nota final |
| **Perfil** | `yap perfil` | Nombre, nivel e idioma. `perfil nivel avanzado`, `perfil nombre Ana` |
| **Accesibilidad** | `yap accesibilidad` | Estado. `accesibilidad alto_contraste on`, `accesibilidad fuentes on`, `accesibilidad lector on`, `accesibilidad teclado on` |
| **Sesion** | `yap sesion` | Estado. `sesion nueva`, `sesion pausar`, `sesion retomar 3`, `sesion cerrar`, `sesion listar` |
| **Historial** | `yap historial` | Sesiones anteriores. `historial --ultimo` (o `retomar`) reanuda la ultima |
| **Telemetria** | `yap telemetria` | Resumen local de uso. `telemetria exportar`, `telemetria off`, `telemetria borrar` |
| **RAG** | `yap rag` | Estado del indice. `rag rebuild`, `rag buscar particiones` |
| **Super Yap** | `yap super` | Estado de la nube. `super on`, `super off`, `super <pregunta>` |
| **AppArmor** | `yap --apparmor-status` | Si el perfil esta cargado y en `enforce` o `complain` |

Lista de contactos rapidos y ejemplos: [USAGE.md](USAGE.md).

### 8.4 Ordenes que no pasan por el LLM

`interpret()` resuelve por teclado todo lo que el menu anuncia, sin consultar al
clasificador. Con el modelo 1B el clasificador acierta poco, y estas son
justamente las ordenes que el estudiante mas usa:

| Escribe | Resuelve |
|---|---|
| `abre firefox` / `abrir firefox` | Abre una app de la whitelist |
| `busca que es un algoritmo` / `buscar ...` | Wikipedia + resumen |
| `pseint como hago un ciclo` / `tutor pseint ...` | Tutor paso a paso |
| `aprender pseint` | Tutorial interactivo |
| `curso FPY1101` | Plan de estudio |
| `iniciar EA1` | Sesion de la EA |
| `ejercicios [lista \| <id>]` | Catalogo de ejercicios |
| `1` … `15` | Opcion del menu; si necesita datos, muestra un ejemplo de uso |
| `guia`, `ayuda`, `menu`, `salir` | Navegacion |

El texto posterior a la orden se respeta tal cual, con sus mayusculas:
`busca Linus Torvalds` busca exactamente eso. Si escribes solo `abre` sin nada
mas, Yap se lo pasa al modelo para que interprete la intencion.

### 8.5 Clasificacion de intenciones

Cuando ninguna ruta directa aplica, `classify_intent()` consulta al LLM con
temperatura 0.1 y recibe `ACCION|PARAMETRO`. Eso aporta:

- **Tolerancia a errores ortograficos**: "Abre", "abre" y "abrir" se clasifican
  como `open_app`.
- **Flexibilidad sintactica**: "busca sobre Linux" y "que es Linux" se distinguen.
- **Modo tutor PSeInt**: preguntas de programacion responden con guias paso a
  paso, sin historial de conversacion.
- **Historial de conversacion**: hasta 6 turnos (`MAX_HISTORY`) en modo interactivo.
- **Fallback**: si el LLM no responde o expira, la consulta se degrada a
  `query` en vez de fallar.

Las acciones del clasificador son `open_app`, `search`, `webfetch`, `query` y
`pseint`.

### 8.6 Flujo del tutorial PSeInt

Al ejecutar `yap quiero aprender pseint` o seleccionar "Introduccion PSeInt" desde el menu de ayuda, el sistema ejecuta el siguiente flujo:

1. **Carga de ejercicios**: `cargar_ejercicios()` lee `/etc/yap/pseint/ejercicios.conf` (bloques v2 `[id]` y lineas v1 `Titulo:Descripcion|GuiaSolucion`).
2. **Apertura del PDF**: El sistema abre el archivo `guia_ejercicios.pdf` (pre-generado, instalado por `setup.sh` en `/etc/yap/pseint/`) que contiene los ejercicios y sus guias de resolucion paso a paso con formato profesional.
3. **Apertura de PSeInt**: `cmd_open_app("pseint")` lanza el entorno PSeInt desde la whitelist.
4. **Presentacion paso a paso**: El tutorial muestra cada paso de la guia uno por uno. El estudiante presiona Enter para avanzar.
5. **Bucle de asistencia**: En cualquier momento, el estudiante puede escribir una pregunta. `cmd_pseint()` recibe el contexto completo: titulo del ejercicio, descripcion, guia de resolucion completa (todos los pasos) y el paso actual. Asi la IA responde con precision sobre exactamente donde esta atascado el estudiante.
6. **Comandos**: `ayuda` (pista), `siguiente` (siguiente ejercicio), `salir` (terminar).

### 8.6.1 Practica evaluada (`yap ejercicios`)

Modo distinto al tutorial: el estudiante **escribe** la respuesta y Yap la evalua. La solucion permanece oculta.

```bash
yap ejercicios lista          # catalogo con estado
yap ejercicios                # pendientes, con validacion
yap ejercicios hola_mundo     # un ejercicio
Chinco > ejercicios
```

Cada ejercicio v2 en `/etc/yap/pseint/ejercicios.conf` declara:

| Campo | Uso |
|---|---|
| `tipo` | `codigo_pseint`, `respuesta_libre` (alias `respuesta_texto`), `opcion_multiple`, `completar` |
| `enunciado` | Consigna visible |
| `pista1` `pista2` `pista3` | Conceptual, parcial, casi solucion |
| `solucion` / `criterio` | Referencia oculta y criterios |
| `validacion` | `exacta` (sin LLM) o `llm` |

- `opcion_multiple` y `completar` (con `solucion`) se comparan de forma exacta, sin LLM.
- `codigo_pseint` y `respuesta_libre` usan el evaluador LLM (`evaluar_actividad` / `evaluar_ejercicio`).
- Si la respuesta es incorrecta se ofrece `pista` (3 niveles). Hasta 3 intentos (`YAP_MAX_INTENTOS`).
- El progreso se guarda en `progress.json` bajo `ejercicios.{id}`.
- Una actividad de EA puede apuntar al catalogo con `"ejercicio_id": "hola_mundo"`.

Las lineas v1 `Titulo:Descripcion|GuiaSolucion` siguen cargando para el tutorial; no son evaluables en `yap ejercicios`.

### 8.7 Sistema de Cursos

Yap incluye un sistema de cursos configurable. El primer curso implementado es **FPY1101 Fundamentos de Programacion** (126 horas, 18 semanas), basado en el PIA y PDA institucional.

#### 8.7.1 Iniciar un curso

```bash
yap curso FPY1101        # Plan completo con RAs, EAs y evaluaciones
Chinco > curso FPY1101   # Desde el modo interactivo
```

Aparece una pantalla con:
- Datos del curso: horas, semanas, herramientas
- **4 Resultados de Aprendizaje (RAs)**: RA1 (algoritmos), RA2 (programacion Python), RA3 (estructuras de datos), RA4 (funciones)
- **3 Experiencias de Aprendizaje (EAs)**: EA1 (algoritmos con PSeInt, 35h, 35%), EA2 (Python, 49h, 60%), EA3 (colecciones y funciones, 35h, 25%)
- **Evaluacion Final Transversal (EFT)**: 7 horas, 40% de la nota final

#### 8.7.2 Iniciar una Experiencia de Aprendizaje

```bash
yap iniciar EA1           # Sesion guiada de Fundamentos de Algoritmos
yap iniciar EA2           # Sesion guiada de Programacion con Python
yap iniciar EA3           # Sesion guiada de Colecciones y Funciones
```

Cada EA muestra:
- **Actividades numeradas** con descripcion detallada (12 en total, del PDA oficial)
- **Estado de progreso**: ✓ completado, · pendiente
- **Herramientas sugeridas** para cada actividad
- **Evaluaciones formativas y parciales** con sus ponderaciones

#### 8.7.3 Flujo de una sesion EA

1. Inicias con `yap iniciar EA1`
2. El sistema muestra la actividad actual con consignas, criterios y (si aplica) opciones
3. Si la actividad tiene `tipo` de evaluacion, escribes tu respuesta. Yap la evalua:
   - `respuesta_libre` / `completar` / `codigo_pseint` → el LLM local devuelve JSON con puntaje y feedback
   - `opcion_multiple` → comparacion exacta, sin LLM
4. Hasta **3 intentos** por actividad. Si repruebas puedes `saltar`. `pregunta ...` consulta al tutor sin gastar intento
5. **abrir [app]** → lanzar herramienta (PSeInt, VS Code, Terminal, Navegador)
6. **salir** → guardar progreso y salir
7. Al completar la EA se calcula promedio 0-100 y **nota final 1.0-7.0** (escala chilena, 60% = 4.0)
8. Actividades sin `tipo` conservan el flujo anterior: **Enter** marca como hecha

La evaluacion ocurre dentro de la sesion activa: el contexto del curso, la EA y la conversacion reciente se envian al LLM para un feedback mas contextual.

#### 8.7.4 Progreso y persistencia

El progreso se guarda automaticamente en `~/.config/yap/progress.json`. Cada intento guarda `puntaje`, `intentos` y `fecha_aprobacion`. Si el sistema se apaga, al volver retomas donde quedaste.

```bash
yap mi progreso           # % completado, promedio, reprobadas y nota
```

#### 8.7.5 Agregar mas cursos

Los cursos se definen en archivos JSON en `cursos/`. Para agregar uno nuevo:

1. Crea `cursos/MAT1101.json` con la estructura de PIA/PDA
2. `setup.sh` lo instala automaticamente en `/etc/yap/cursos/`
3. `yap curso MAT1101` ya funciona sin modificar codigo

Estructura minima del JSON:
```json
{
  "codigo": "MAT1101",
  "nombre": "Matematicas",
  "horas": 90,
  "semanas": 18,
  "ras": [{"id": "RA1", "descripcion": "...", "indicadores": ["IL1.1"]}],
  "eas": [{"id": "EA1", "nombre": "...", "descripcion": "...", "horas": 30,
           "actividades": [{"orden": 1, "nombre": "Act1", "descripcion": "...",
             "tipo": "respuesta_libre", "criterios_evaluacion": ["..."]}],
           "evaluaciones": []}],
  "evaluaciones": []
}
```

### 8.8 Guia rapida integrada

Escribe `yap guia` para un tutorial interactivo de 7 pasos que recorre todas
las funciones. `yap --tutorial` repite el onboarding de bienvenida.

```
Chinco > guia

  ┌─ PASO 1: Bienvenida a ChincoLinux ─────────────────────┐
  │ Escribe 'yap' para entrar al modo interactivo.          │
  │ El prompt 'Chinco > ' con colores te indica que estas   │
  │ dentro. Todos los comandos funcionan igual aqui.         │
  └─────────────────────────────────────────────────────────┘

  ┌─ PASO 2: Abrir herramientas ───────────────────────────┐
  │ 'Abre Firefox' — lanza apps de la whitelist.            │
  │ 'abrir pseint' — desde una sesion EA abre herramientas  │
  └─────────────────────────────────────────────────────────┘

  ... (Enter para continuar, Ctrl+C o 'salir' para terminar)
```

### 8.9 Perfil del estudiante (#24)

```bash
yap perfil                            # ver
yap perfil nombre Ana                 # cambia el nombre
yap perfil nivel avanzado             # basico | intermedio | avanzado
yap perfil idioma es                  # es | en
```

El perfil vive en `~/.config/yap/profile.json` y se inyecta al system prompt, de
modo que el agente conoce el nombre y el nivel del estudiante. Tambien guarda
preferencias (idioma, tema, feedback detallado, notificaciones, opciones de
accesibilidad), el flag de onboarding completado y estadisticas de uso. Las
escrituras son atomicas.

El nivel inicial de la dificultad adaptativa se deriva del perfil.

### 8.10 Accesibilidad (#37)

```bash
yap accesibilidad                          # estado de las cuatro opciones
yap accesibilidad alto_contraste on        # paleta de alto contraste
yap accesibilidad fuentes on               # escala de texto 2x
yap accesibilidad lector on                 # sanitiza ANSI para lector de pantalla
yap accesibilidad teclado on               # navegacion completa por teclado
```

- **Alto contraste**: replaces la paleta ANSI por una version legible.
- **Fuentes grandes**: duplica el ancho de celda al dibujar cajas y menus.
- **Lector de pantalla**: detecta **Orca** por variables de entorno y filtra las
  secuencias ANSI con un `_FiltroSalida` sobre `stdout`, para que el estudiante
  oiga texto limpio en vez de secuencias de escape.
- **Teclado**: `menu_interactivo()` permite recorrer opciones con flechas,
  `Home`/`End` y `Enter`, sin raton.

### 8.11 Sesiones e historial (#21, #13)

```bash
yap sesion                    # estado de la sesion activa
yap sesion nueva              # abrir una sesion nueva
yap sesion listar             # sesiones abiertas y pausadas
yap sesion pausar             # guardar el contexto y seguir despues
yap sesion retomar 3          # retomar la sesion 3
yap sesion cerrar             # archivar y limpiar
yap sesion asociar FPY1101 EA1  # asociar a un curso y una EA

yap historial                 # ultimas 20 sesiones
yap historial --ultimo        # (o `retomar`) reanuda la ultima
```

Cada sesion guarda contexto, curso, EA, historial de turnos y timestamps. Al
cerrar se archiva en `history.json`, y al salir de la TUI la sesion abierta se
pausa sola. Se pueden tener `YAP_MAX_SESSIONS` (3 por defecto) sesiones abiertas
a la vez.

### 8.12 Telemetria local (#38)

```bash
yap telemetria            # resumen: que usas y que no
yap telemetria exportar   # vuelca el JSON a la terminal
yap telemetria off        # deja de recolectar
yap telemetria on
yap telemetria borrar     # elimina el archivo local
```

Contadores anonimos de uso en `~/.config/yap/telemetry.json`: cuantas veces se
llamo a cada accion, y cuales comandos **nunca** se han usado. Sin identificador
de usuario, sin red, sin reloj de pared: el archivo se puede leer y borrar por
el estudiante en cualquier momento.

### 8.13 RAG local (#118)

Recuperacion augmentada offline con Okapi BM25, 100% stdlib. Antes de responder,
Yap recupera los fragmentos mas relevantes del corpus y los injecta como
contexto.

```bash
yap rag                    # activo, ruta del indice, nº de fragmentos y archivos
yap rag rebuild            # reconstruir el indice y medir la latencia
yap rag buscar particiones # busqueda directa, muestra los puntajes BM25
```

| | |
|---|---|
| **Corpus** | `cursos/*.json`, `docs/*.md`, `whitelist/*.conf`, `USAGE.md`, `AGENTS.md` |
| **Chunking** | por encabezado markdown o doble salto de linea, 300 palabras por fragmento |
| **Indice** | `~/.config/yap/index/bm25_index.json`, revalidado por hash del corpus |
| **`RAG_TOP_K`** | 5 fragmentos recuperados (default) |
| **`RAG_MAX_CONTEXT_TOKENS`** | 512 tokens de contexto inyectado (default) |
| **Degradacion** | si el indice falla, Yap responde igual sin contexto RAG |

Detalle de diseno y tuneles: [docs/RAG.md](docs/RAG.md).

### 8.14 Super Yap — Gradio en Cloud Run (#91)

Cliente Gradio 5 en Cloud Run escrito con `urllib` y `http.cookiejar` (sin
`requests`, sin `socket`). Opt-in: el estudiante sigue trabajando con el modelo
local de 1B/3B, y la nube entra solo cuando el local no da la talla.

```bash
yap super            # estado: motor actual, endpoint, si responde
yap super on         # forzar la nube en todas las consultas
yap super off        # volver al local
yap super <pregunta> # forzar una consulta puntual
```

- **Delegacion automatica**: si `llama-cli` tarda 3 minutos o el prompt excede
  los tokens del contexto local, Yap consulta Gradio **reenviando el historial
  vivo** (`HISTORY`), asi que no se pierde el hilo.
- **Fallback**: si la nube no responde, se vuelve al LLM local.
- **Whitelist de hosts**: solo loopback, LAN privada o el host pin de Cloud Run.
  Se rechaza cualquier otro destino.
- Plantillas de despliegue en [`agent-platform/`](agent-platform/).

Ver [docs/SUPER-YAP.md](docs/SUPER-YAP.md).

### 8.15 Dificultad adaptativa (#30)

`AdaptiveEngine` observa el rendimiento (puntajes, intentos, pistas usadas) y
propone subir o bajar el nivel del estudiante. Las reglas de subida exigen
varias respuestas correctas consecutivas; las de bajada, varios fallos; entre
ambas hay mantenimiento, para que el nivel no oscile. El mapeo entre nivel del
perfil y nivel de dificultad, y las variantes por tipo de actividad, se fijan
en `tests/test_yap_adaptive.py` (45 pruebas).

---

## 9. Limitaciones

- **Contexto limitado**: `MAX_CTX = 2048` tokens (~1500 palabras). El RAG
  recupera hasta 512 tokens extra, pero el modelo no razona sobre mas.
- **Persistencia por usuario, no por equipo**: el progreso, el perfil, las
  sesiones y la telemetria viven en `~/.config/yap/` del usuario actual. No hay
  sincronizacion entre maquinas.
- **Latencia**: en CPU con 2 nucleos la primera respuesta puede tardar hasta
  60 s. El LLM local es el cuello de botella de todo lo que pasa por el.
- **Alucinaciones**: Llama 3.2 3B puede generar informacion incorrecta. Para
  datos factuales conviene `webfetch` o `busca` (Wikipedia), que muestran fuente.
- **El evaluador tambien alucina**: la nota de `respuesta_libre` y
  `codigo_pseint` la pone el LLM. Por eso `opcion_multiple` y `completar` se
  comparan de forma exacta, sin LLM, y por eso existe la nota seca cuando el
  LLM no responde.
- **Clasificador debil en 1B**: con el modelo de `ultra-lowmem` el clasificador de
  intenciones acierta poco. De ahi las rutas por teclado de la seccion 8.4.
- **Idioma**: optimizado para espanol; el perfil admite `en` pero el resultado
  es inconsistente.
- **Sin GPU ni aceleracion hardware**: CPU-only por diseno, para que quepa en
  el hardware del aula.
- **Super Yap es una excepcion de red**: aunque es opt-in, si se activa sale a
  Internet. El resto de Yap es 100% offline.

---

## 10. Trabajo futuro

### Fase 1 — MVP (completada)

- [x] LLM local (Llama 3.2 Instruct).
- [x] CLI interactiva (TUI curses) y por comando directo.
- [x] Tooling de sistema con whitelist.
- [x] Alertas graficas (`notify-send`).
- [x] Whitelist configurable de apps y dominios.
- [x] Busqueda en Wikipedia y webfetch con limite de 3000 chars.
- [x] Onboarding de bienvenida.

### Fase 2 — Optimizacion y seguridad (completada)

- [x] Compilacion estatica de llama.cpp (sin dependencia de `libllama.so`).
- [x] Correccion de seguridad en whitelist de dominios (`notwikipedia.org`).
- [x] Soporte multi-binario en whitelist de apps (fallback `firefox-esr` → `firefox`).
- [x] Desactivacion de modo conversacion en llama-cli (`-no-cnv`, `--no-display-prompt`).
- [x] Aislamiento de la terminal: `stdin=DEVNULL` en toda llamada a `subprocess` (#99).
- [x] Confirmacion humana para acciones sensibles (#12).
- [x] Integracion con **AppArmor** (#14).
- [x] Fuzzing de entrada: traversal, esquemas, unicode, JSON corrupto, inputs grandes.
- [x] Instalador `.deb` con repositorio apt opcional (#31).
- [x] Despliegue masivo en red escolar por SSH.

### Fase 3 — Entorno pedagogico (completada)

- [x] Sistema de cursos con RAs, EAs y actividades tipadas (`cursos/*.json`).
- [x] Evaluacion automatica de actividades con feedback del LLM (#23).
- [x] Catalogo de ejercicios PSeInt con 4 tipos y pistas progresivas (#27).
- [x] Tutor y tutorial interactivo de PSeInt.
- [x] Feedback pedagogico con nota chilena 1.0-7.0 (#29).
- [x] Perfil del estudiante inyectado al system prompt (#24).
- [x] Historial persistente entre sesiones (#13).
- [x] Sesiones pausables, retomables y archivables (#21).
- [x] Dificultad adaptativa segun rendimiento (#30).
- [x] Accesibilidad: alto contraste, fuentes grandes, lector de pantalla, teclado (#37).
- [x] Telemetria local anonima, exportable y desactivable (#38).
- [x] RAG local con BM25, sin dependencias (#118).
- [x] Rutas por teclado para las ordenes del menu (#59).
- [x] Super Yap en Cloud Run con reenvio de historial (#91).

### Fase 4 — En desarrollo

- [ ] Mas fuentes en la whitelist educativa.
- [ ] Interfaz de configuracion grafica.
- [ ] Exportar el progreso del estudiante para el docente.
- [ ] Catalogo de ejercicios mas amplio, authored por el curso.

### Vision a largo plazo

- [ ] Plugins de tooling extensibles.
- [ ] Integracion con gestores de coursework externos.
- [ ] Cuantizacion mas agresiva para equipos de 2 GB.
- [ ] Evaluacion entre pares: que un estudiante evalue la respuesta de otro.

El detalle de fases, dependencias y metricas esta en
[docs/ROADMAP.md](docs/ROADMAP.md).

---

## 11. Licencia

Este proyecto se distribuye bajo **licencia MIT** (ver [LICENSE](LICENSE)). El modelo **Llama 3.2** esta sujeto a los terminos de la **Licencia Llama 3.2 de Meta**.

---

## 12. Pruebas y verificacion

La suite tiene **21 archivos y 825 pruebas**. La unica dependencia externa es
`pytest`: ni el modelo, ni la GPU, ni Internet. Detalle por archivo y por
requisito en [tests/README.md](tests/README.md).

### 12.1 Como ejecutar

```bash
python3 -m pip install pytest          # unica dependencia

python3 -m pytest tests/ -v            # 825 pruebas (desarrollo y CI)
python3 -m pytest tests/test_yap_rag.py -v   # un area
python3 -m pytest tests/ -v -k whitelist    # por palabra clave

python3 tests/run_tests.py             # runner: etapas + chequeos + requisitos
python3 tests/run_tests.py --report    # runner + tests/report/report_<fecha>.txt
```

### 12.2 Los dos ejecutores, y cuando usar cada uno

| | `pytest tests/` | `python3 tests/run_tests.py` |
|---|---|---|
| Archivos | los 21 | los 5 de `ARCHIVOS_PYTEST` |
| Pruebas | 825 | 237 |
| Chequeos de infraestructura | no | si (5) |
| Chequeo estatico de `yap.py` | no | si (5) |
| Mapeo de 26 requisitos | no | si |
| Reporte TXT | no | con `--report` |
| Para que | desarrollo, CI | auditoria de entrega |

Los numeros no cuadran al decimal porque el parser del runner cuenta lineas con
`PASSED` y `FAILED`: un test `SKIPPED` no suma. Hay 2 skips en los cinco
archivos del runner (237 contados, 239 recogidos) y 2 en la suite completa.

`run_tests.py` ejecuta 5 etapas en orden: pytest sobre los archivos de
`ARCHIVOS_PYTEST`, verificaciones de infraestructura, verificacion estatica del
codigo fuente, mapeo de requisitos y resumen.

#### Requisitos de `run_tests.py`

- **Python 3.12+**, stdlib-only. La unica dependencia externa es `pytest`.
- **No** necesita el modelo GGUF, `llama-cli`, GPU ni Internet: la suite mockea
  `subprocess`, `urllib.request` y `shutil.which`.
- **No** necesita haber instalado Yap. Las 5 verificaciones de
  infraestructura —symlink `/usr/local/bin/yap`, `llama-cli` en el PATH, el
  modelo en `MODEL_PATH`, `/etc/yap/whitelist/apps.conf` y `web.conf`— miden la
  instalacion, no el codigo, asi que **fallan por diseño** en CI o en un portatil
  donde no se instalo nada.
- **Timeout de 120 s por archivo** de pytest: el techo de la primera etapa son
  10 minutos. El resto es instantaneo.
- **`--vm` es cosmetico**: cambia la etiqueta del encabezado a "VM (con LLM)".
  Las verificaciones de infraestructura se ejecutan **siempre**, con o sin la
  opcion; `--vm` no las filtra.
- **Codigo de salida**: `0` si no falla ninguna prueba ni chequeo estatico, `1`
  si falla alguna. El mapeo de requisitos **no** altera el codigo de salida: en
  un host sin Yap instalado `CFG-01..03` quedan en rojo sin que eso invalide un
  PR de codigo.
- **Aislamiento de la nube**: `tests/conftest.py` fija `YAP_SUPER_ENABLED=0` y
  `YAP_SUPER_INTERNET=0` en una fixture `autouse`, salvo que la variable ya este
  definida en el entorno. Ningun test habla con Cloud Run.

#### Los 26 requisitos catalogados

`REQUISITOS` en `tests/run_tests.py` es la fuente unica de verdad: ahi esta la
descripcion de cada ID, y `main()` solo aporta el estado. Si un ID queda en un
lado y no en el otro, el runner lo avisa.

| Familia | IDs | Significado |
|---|---|---|
| **SEG** | 01-08 | Whitelist, anti-inyeccion, limites de recursos |
| **FUN** | 01-12 | Capacidades del agente |
| **SEC** | 01 | Catalogo de ejercicios PSeInt |
| **CFG** | 01-03 | Instalacion en el sistema |
| **PKG** | 01-02 | Empaquetado `.deb` (#31) |

La tabla completa ID ↔ archivo ↔ clase de prueba esta en
[tests/README.md](tests/README.md).

### 12.3 Integracion continua (GitHub Actions)

Once workflows en `.github/workflows/`. El principal, `test.yml`, corre en cada
`push` y `pull request` a `main`, `lowmem` o `ultra-lowmem`:

| Job | Que hace |
|---|---|
| **unit-tests** | Python 3.12: seguridad, funcional, evaluacion y Super Yap, mas verificacion estatica (`shell=True`, `eval()`, `os.system()`) y validacion de las whitelists del repo |
| **branch-check** | Verifica que `MODEL_PATH` en cada rama apunte al modelo correcto |
| **results** | Resumen del pipeline |

Los demas workflows cubren el ciclo de vida del PR y del repo:

| Workflow | Que hace |
|---|---|
| `pr-review.yml` | Agente `yap-reviewer` (A-Dev) evalua las politicas Hardness y deja un comentario asesor. Nunca aprueba ni rechaza |
| `pr-validation.yml` | Validacion de la estructura del PR |
| `pr-state-labeler.yml` | Etiqueta el estado del PR (`pr:needs-review`, `pr:changes-requested`, ...) |
| `pr-traceability-check.yml` | Exige que el PR referencie un issue; si no, comenta y etiqueta `needs-human` |
| `pr-quality-suite.yml` | Suite de calidad extendida |
| `quality-gates.yml` | Puertas de calidad antes del merge |
| `build-deb.yml` | Construye los paquetes `.deb` |
| `auto-release.yml` | Version bump y CHANGELOG desde un PR a `main`, nunca push directo |
| `weekly-sprint-assignment.yml` | Asignacion semanal de issues |
| `auto-add-to-project.yml` | Anade issues al project del roadmap |

Reglas de rama que el CI y la doctrina A-Dev hacen cumplir:

- `main` esta protegida: `enforce_admins: true`, sin push directo, sin force push.
- Cada cambio va en una rama fresca con nombre convencional
  (`feat/issue-NNN-...`, `fix/issue-NNN-...`).
- Commits con [Conventional Commits](https://www.conventionalcommits.org/).
- Todo PR referencia su issue con `Closes #NNN` (una linea por issue).
- La suite debe estar verde antes de pedir revision.

[![Yap CI](https://github.com/VECTORG99/Yap/actions/workflows/test.yml/badge.svg)](https://github.com/VECTORG99/Yap/actions/workflows/test.yml)

### 12.4 Pruebas de seguridad (`test_yap_security.py`, 25)

| Clase | Prueba | Verifica |
|---|---|---|
| **TestAppWhitelist** | `test_app_permitida_devuelve_ok` | App en whitelist se carga correctamente |
| | `test_app_bloqueada_muestra_alternativas` | App bloqueada → `[ERROR]` + lista de apps permitidas |
| | `test_app_bloqueada_no_ejecuta_comando` | App bloqueada → `subprocess.Popen` NO se llama |
| | `test_multiples_binarios_fallback` | `firefox-esr,firefox` → lista de 2 binarios |
| **TestDomainWhitelist** | `test_dominio_permitido_exacto` | `wikipedia.org` en whitelist → pasa |
| | `test_subdominio_permitido` | `es.wikipedia.org` → pasa (subdominio directo) |
| | `test_dominio_bloqueado_muestra_alternativas` | `malware.com` → `[ERROR]` + dominios permitidos |
| | `test_notwikipedia_no_coincide` | `notwikipedia.org` no hace match con `wikipedia.org` |
| **TestCommandSecurity** | `test_no_shell_true_en_subprocess` | Escanea codigo: `shell=True` NO aparece |
| | `test_no_eval` | Escanea codigo: `eval()` NO aparece |
| | `test_no_os_system` | Escanea codigo: `os.system()` NO aparece |
| | `test_command_injection_app_name` | `"; rm -rf /"`, `$(whoami)`, `` `id` ``, `&& shutdown` → bloqueados |
| | `test_url_injection` | `file:///etc/passwd`, `127.0.0.1`, `[::1]`, `javascript:` → bloqueados |
| **TestConfigLoading** | `test_whitelist_ignora_comentarios` | Lineas con `#` se ignoran |
| | `test_whitelist_ignora_lineas_vacias` | Lineas vacias se ignoran |
| | `test_formato_invalido_ignorado` | Lineas sin `:` se ignoran |
| **TestSecurityLimits** | `test_contenido_limitado_3000_chars` | `text[:3000]` existe en `cmd_webfetch` |
| | `test_timeout_en_subprocess` | Toda llamada a `subprocess.run()` tiene `timeout=` |
| **TestFileSystemSecurity** | `test_no_escritura_fuera_de_whitelist` | Sin `open(w)`, `os.remove`, `shutil.rmtree` en codigo |
| **TestRealConfig** | `test_apps_conf_existe` | `whitelist/apps.conf` existe en el repo |
| | `test_web_conf_existe` | `whitelist/web.conf` existe en el repo |
| | `test_apps_conf_tiene_contenido` | apps.conf tiene entradas validas |
| | `test_web_conf_tiene_contenido` | web.conf tiene dominios validos |
| **TestCodeQuality** | `test_no_shebang_incorrecto` | `#!/usr/bin/env python3` correcto |
| | `test_imports_minimos` | Sin imports peligrosos (`socket`, `ctypes`, `pickle`, `base64`) |

El resto de areas con su archivo y sus clases:

| Archivo | Pruebas | Clases principales |
|---|---|---|
| `test_yap_security_audit.py` | 27 | `TestPathTraversal`, `TestSchemeValidation`, `TestAppInjectionFuzz`, `TestLargeInputFuzz`, `TestUnicodeFuzz`, `TestCorruptJsonFuzz` |
| `test_yap_functional.py` | 59 | `TestOpenApp`, `TestWebfetch`, `TestIntentClassification`, `TestQuery`, `TestHistory`, `TestNotifications`, `TestPSeIntConfig`, `TestIntroduccionPSeInt`, `TestPSeIntTutor`, `TestArchitecture`, `TestChincoTUI`, `TestCourseSystem`, `TestProgreso`, `TestCursoCommand` |
| `test_yap_evaluacion.py` | 63 | `TestSchemaEvaluacion`, `TestParserEvaluacion`, `TestEvaluarActividad`, `TestProgresoEvaluacion`, `TestNotaChilena`, `TestFlujoEvaluacion`, `TestCmdProgresoNotas`, `TestIntegracionFPY1101`, `TestComandosActividad` |
| `test_yap_super.py` | 58 | `TestConsultaParaSuper`, `TestHostSuperPermitido`, `TestDelegacion`, `TestCmdQuerySuper`, `TestInterpretSuper`, `TestGradioNube`, `TestFallbackLocalASuper` |
| `test_yap_deb.py` | 34 | `TestYapDebianTemplates`, `TestModelPackages`, `TestBuildDebScript`, `TestBuildDebSmoke`, `TestPostinstCopySemantics` |
| `test_yap_ejercicios.py` | 35 | `TestParserEjercicios`, `TestEvaluarEjercicio`, `TestPistas`, `TestFlujoEjercicio`, `TestCliEjercicios`, `TestHookEA` |
| `test_yap_accesibilidad.py` | 90 | `TestSanitizarSalida`, `TestDetectarOrca`, `TestAltoContraste`, `TestFuentesGrandes`, `TestNavegacionTeclado` |
| `test_yap_sessions.py` | 75 | `TestSessionStore`, `TestSessionCRUD`, `TestSessionLimit`, `TestCmdSesion`, `TestSessionExit` |
| `test_yap_rag.py` | 61 | `TestRagBM25Index`, `TestRagPersistence`, `TestRagRetrieve`, `TestRagPathTraversal`, `TestRagGoldenSet` |
| `test_yap_perfil.py` | 61 | `TestNormalizacion`, `TestEscrituraAtomica`, `TestCmdPerfil`, `TestSystemPromptInjection` |
| `test_yap_adaptive.py` | 45 | `TestReglaSubida`, `TestReglaBajada`, `TestMantenimiento`, `TestMapeoPerfil` |
| `test_yap_telemetry.py` | 41 | `TestTelemetryStore`, `TestRegistrarUso`, `TestAccionesSinUsar`, `TestPrivacidad` |
| `test_yap_feedback.py` | 32 | `TestTipoFeedback`, `TestPautasDelPrompt`, `TestFeedbackSumativo` |
| `test_yap_rutas_teclado.py` | 32 | `TestRutasDeTeclado`, `TestPistas`, `TestMenu` |
| `test_yap_config_escolar.py` | 21 | `TestAppsEducativas`, `TestDominiosEducativos`, `TestAppArmorEnforce` |
| `test_yap_confirmation.py` | 20 | `TestSensitiveActions`, `TestConfirmAction`, `TestTrustedLevel` |
| `test_yap_history.py` | 17 | `TestHistorySave`, `TestHistoryLoad`, `TestMaxSessions`, `TestCmdHistorial` |
| `test_yap_apparmor.py` | 17 | `TestAppArmorStatus`, `TestProfileExists`, `TestSetupShIntegration` |
| `test_yap_terminal.py` | 9 | `TestNingunProcesoHeredaLaTerminal`, `TestRutasDeLlamaCli` |
| `test_yap_onboarding.py` | 3 | Onboarding de bienvenida |

### 12.5 Mecanismo de pruebas

Todas las pruebas se ejecutan **sin el modelo LLM** y **sin red**, mediante
mocking:

```
subprocess.run      → mock (devuelve stdout/stderr predefinidos)
urllib.request      → mock (devuelve HTML de prueba)
shutil.which        → mock (devuelve rutas falsas)
```

Hay ademas pruebas que escanean el **codigo fuente** de `yap.py` en busca de
patrones prohibidos. Ojo con los falsos positivos: si un comentario o una
cadena de texto contiene `shell=True`, el patron aparece igual. El bot
`yap-reviewer` busca sobre el diff completo y por eso marca things que en
realidad son texto; verifica siempre que el match este en codigo ejecutable.

Los **agregados del runner**: en un host donde Yap esta instalado, las 5
verificaciones de infraestructura y los 5 chequeos estaticos de codigo pasan
todos, y el mapeo queda en 26/26. En CI, donde no hay nada instalado, las 5 de
infraestructura caen y el mapeo queda en 23/26 con `CFG-01..03` en rojo: eso
esperado, y el codigo de salida sigue siendo el de las pruebas.

| Clase | Prueba | Verifica |
|---|---|---|
| **TestAppWhitelist** | `test_app_permitida_devuelve_ok` | App en whitelist se carga correctamente |
| | `test_app_bloqueada_muestra_alternativas` | App bloqueada → `[ERROR]` + lista de apps permitidas |
| | `test_app_bloqueada_no_ejecuta_comando` | App bloqueada → `subprocess.Popen` NO se llama |
| | `test_multiples_binarios_fallback` | `firefox-esr,firefox` → lista de 2 binarios |
| **TestDomainWhitelist** | `test_dominio_permitido_exacto` | `wikipedia.org` en whitelist → pasa |
| | `test_subdominio_permitido` | `es.wikipedia.org` → pasa (subdominio directo) |
| | `test_dominio_bloqueado_muestra_alternativas` | `malware.com` → `[ERROR]` + dominios permitidos |
| | `test_notwikipedia_no_coincide` | `notwikipedia.org` no hace match con `wikipedia.org` |
| **TestCommandSecurity** | `test_no_shell_true_en_subprocess` | Escanea codigo: `shell=True` NO aparece |
| | `test_no_eval` | Escanea codigo: `eval()` NO aparece |
| | `test_no_os_system` | Escanea codigo: `os.system()` NO aparece |
| | `test_command_injection_app_name` | `"; rm -rf /"`, `$(whoami)`, `` `id` ``, `&& shutdown` → bloqueados |
| | `test_url_injection` | `file:///etc/passwd`, `127.0.0.1`, `[::1]`, `javascript:` → bloqueados |
| **TestConfigLoading** | `test_whitelist_ignora_comentarios` | Lineas con `#` se ignoran |
| | `test_whitelist_ignora_lineas_vacias` | Lineas vacias se ignoran |
| | `test_formato_invalido_ignorado` | Lineas sin `:` se ignoran |
| **TestSecurityLimits** | `test_contenido_limitado_3000_chars` | `text[:3000]` existe en `cmd_webfetch` |
| | `test_timeout_en_subprocess` | Toda llamada a `subprocess.run()` tiene `timeout=` |
| **TestFileSystemSecurity** | `test_no_escritura_fuera_de_whitelist` | Sin `open(w)`, `os.remove`, `shutil.rmtree` en codigo |
| **TestRealConfig** | `test_apps_conf_existe` | `whitelist/apps.conf` existe en el repo |
| | `test_web_conf_existe` | `whitelist/web.conf` existe en el repo |
| | `test_apps_conf_tiene_contenido` | apps.conf tiene entradas validas |
| | `test_web_conf_tiene_contenido` | web.conf tiene dominios validos |
| **TestCodeQuality** | `test_no_shebang_incorrecto` | `#!/usr/bin/env python3` correcto |
| | `test_imports_minimos` | Sin imports peligrosos (`socket`, `ctypes`, `pickle`, `base64`) |

---

## 13. Contribuir

Lee [CONTRIBUTING.md](CONTRIBUTING.md) y, antes de tocar nada,
[AGENTS.md](AGENTS.md). El flujo es trunk-based:

1. **Rama fresca desde `main`**: `git checkout -b feat/issue-NNN-descripcion`.
   Nunca reutilices una rama ya commiteada ni mergeada.
2. **Commits atomicos** con [Conventional Commits](https://www.conventionalcommits.org/):
   `feat:`, `fix:`, `docs:`, `test:`, `chore:`.
3. **Pruebas locales verdes** antes de pedir revision:
   `python3 -m pytest tests/ -v`.
4. **PR** que referencia su issue (`Closes #NNN`, una linea por issue) y
   completa el checklist de [PULL_REQUEST_TEMPLATE.md](PULL_REQUEST_TEMPLATE.md).
5. **Revision**: el bot `yap-reviewer` evalua las politicas A-Dev y deja un comentario
   asesor; la decision siempre es de una persona. Ningun agente se aprueba a si
   mismo.
6. **Merge** por squash con auto-merge, y borrado de la rama.

Invariantes que el CI y la doctrina A-Dev hacen cumplir:

| Regla | Como se comprueba |
|---|---|
| Sin push directo a `main` | Branch protection con `enforce_admins: true` |
| Sin force push | `allow_force_pushes: false` |
| Cada cambio en su rama | `pr-validation.yml` + revision A-Dev |
| PR ligado a un issue | `pr-traceability-check.yml` |
| Suite verde | `test.yml` |
| Sin patrones peligrosos | `test_yap_security.py` + paso estatico del CI |
| Politicas de seguridad | `.github/adev/policies/HD-YAP-*.json` |

Convenciones de codigo: espanol en los strings de usuario, espanol o ingles en
los comentarios tecnicos, prefijo `ponytail:` en workarounds sin dependencias
externas, ANSI directo para la TUI (sin Rich ni Textual),
`shutil.which()` antes de todo `Popen`, y `timeout=` en toda llamada a
`subprocess`.

---

> **Referencias**: [llama.cpp](https://github.com/ggerganov/llama.cpp) | [Llama 3.2](https://ai.meta.com/blog/llama-3-2-connect-2024-vision-edge-mobile-devices/) | [GGUF format](https://github.com/ggerganov/ggml/blob/main/docs/gguf.md) | [Debian](https://www.debian.org/) | [VirtualBox](https://www.virtualbox.org/) | [A-Dev](https://github.com/scanalesespinoza/adev) | [Trunk-Based Development](https://trunkbaseddevelopment.com/) | [Conventional Commits](https://www.conventionalcommits.org/)
