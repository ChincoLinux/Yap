# Yap: Asistente de IA Local para Entornos Educativos con Recursos Limitados

**Version:** `1.0.0-beta` | [![Yap CI](https://github.com/VECTORG99/Yap/actions/workflows/test.yml/badge.svg)](https://github.com/VECTORG99/Yap/actions/workflows/test.yml)

**Sistema de agente conversacional basado en **Llama 3.2**, ejecucion **CPU-only**, disenado para **Debian 13** con soporte de 3 a 8 GB de RAM mediante ramas de configuracion graduales.**

---

## Resumen

**Yap** es un asistente de inteligencia artificial que opera integramente en local sobre CPU, sin dependencia de conexion a Internet para su funcionamiento base. Emplea el modelo **Llama 3.2 Instruct** (GGUF Q4_K_M) ejecutado mediante **llama.cpp** con enlace estatico, e implementa un sistema de seguridad basado en **listas blancas** (whitelist) de aplicaciones y dominios. El proyecto se distribuye en **tres ramas** (`master`, `lowmem`, `ultra-lowmem`) que escalan el consumo de RAM desde ~3.5 GB hasta ~1.8 GB, adaptandose a hardware educativo de distintas capacidades. La clasificacion de intenciones se realiza mediante el propio LLM, eliminando la necesidad de patrones rigidos y proporcionando tolerancia a errores ortograficos y variaciones sintacticas.

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

---

## 1. Objetivos

Construir un sistema Debian estable ultraligero con un agente IA local (**CPU-only**) capaz de:

- **Responder en espanol** con enfoque educativo.
- **Ejecutar acciones seguras** del sistema mediante tooling controlado por whitelist.
- **Abrir aplicaciones** desde una lista blanca configurable.
- **Recuperar informacion** de sitios web aprobados.
- **Aplicar restricciones** para acciones sensibles.
- **Emitir alertas graficas** mediante `notify-send`.

---

## 2. Especificaciones tecnicas

| Componente | Detalle |
|---|---|
| **Modelo** | Llama 3.2 3B Instruct (GGUF Q4_K_M) / 1B Instruct |
| **Runtime** | llama.cpp (CPU-only, enlace estatico) |
| **RAM minima** | ~3.5 GB (master), ~3.1 GB (lowmem), ~1.8 GB (ultra-lowmem) |
| **Contexto** | 4096 tokens (master) / 2048 tokens (lowmem, ultra-lowmem) |
| **Latencia estimada** | 5-10 s primeras tokens en CPU (2 nucleos), ~40 tok/s |
| **Idioma** | Espanol |
| **SO destino** | Debian 13 (64-bit) |

---

## 3. Arquitectura del sistema

### 3.1 Diagrama de capas

```
+----------+     +---------+     +------------+
| Usuario  | --> | CLI yap | --> | Interprete |
+----------+     +---------+     +------------+
                                       |
                     +-----------------+------------------+
                     |                 |                  |
                     v                 v                  v
             +------------+    +-----------+     +------------+
             | Whitelist  |    | Whitelist |     | LLM local  |
             | apps       |    | web       |     | llama.cpp  |
             +------------+    +-----------+     +------------+
                     |                 |                  |
                     v                 v                  v
             +------------+    +-----------+     +------------+
             | Lanzar app |    | Webfetch  |     | Respuesta  |
             | + alerta   |    | + limite  |     | educativa  |
             +------------+    | 2000 chars|     +------------+
                               +-----------+
```

### 3.2 Flujo de una consulta

1. El usuario escribe un comando en la terminal.
2. `classify_intent()` envia el texto al LLM con un **prompt de clasificacion**.
3. El LLM responde con `ACCION|PARAMETRO`: `open_app`, `search` (Wikipedia), `webfetch` (URL directa), o `query` (consulta general).
4. `handle_action()` ejecuta la accion contra la whitelist o el LLM segun corresponda.
5. El resultado se muestra en pantalla.

### 3.3 Componentes del sistema

| Componente | Funcion |
|---|---|
| **CLI** | Interfaz de linea de comandos (modo interactivo y comando directo) |
| **Interprete** | Clasifica la intencion del usuario mediante el LLM |
| **Whitelist de apps** | Lista de aplicaciones permitidas con soporte multi-binario |
| **Whitelist de dominios** | Lista de dominios permitidos para webfetch |
| **LLM local** | Modelo Llama 3.2 ejecutado con llama.cpp |
| **Notificador** | Alertas graficas mediante `notify-send` |

---

## 4. Componentes del stack tecnologico

### 4.1 Bash — Script de instalacion (`setup.sh`)

El instalador automatiza la configuracion del entorno. Conceptos clave:

| Linea(s) | Concepto | Explicacion |
|---|---|---|
| 2 | **`set -euo pipefail`** | Modo estricto: `-e` aborta en error; `-u` variables no definidas como error; `-o pipefail` propaga errores en tuberias |
| 14 | **`SCRIPT_DIR`** | Obtiene la ruta absoluta del directorio del script mediante `${BASH_SOURCE[0]}` |
| 38 | **`git clone --depth 1`** | Clonado superficial (un solo commit) para minimizar ancho de banda |
| 41-42 | **`cmake` + `cmake --build`** | Configuracion y compilacion con `-DBUILD_SHARED_LIBS=OFF` para enlace estatico |
| 47-52 | **Descarga del modelo** | Lee `MODEL_PATH` de `yap.py` y descarga el `.gguf` correspondiente (3B o 1B) |
| 63 | **`ln -sf`** | Enlace simbolico a `yap.py` en el repositorio; `git pull` actualiza sin reinstalar |

### 4.2 Python — Agente principal (`yap.py`)

| Linea(s) | Funcion | Proposito |
|---|---|---|
| 29-43 | **`load_whitelist()`** | Carga `apps.conf` (clave:binarios) con list comprehension y `strip()` |
| 45-53 | **`load_domain_whitelist()`** | Carga dominios permitidos con validacion exacta o subdominio |
| 56-64 | **`notify()`** | Notificacion grafica via `notify-send` con 3 niveles de urgencia |
| 67-101 | **`cmd_open_app()`** | Busca binario con `shutil.which()`, ejecuta y captura version; graceful blocking si no esta en whitelist |
| 104-133 | **`cmd_webfetch()`** | Valida dominio, descarga contenido, elimina HTML via regex, limita a 3000 caracteres |
| 136-178 | **`cmd_query()`** | Construye prompt con tokens Llama 3.2 Instruct e historial de conversacion |
| 178-216 | **`classify_intent()`** | Clasificacion de intencion mediante el LLM: `open_app`, `search`, `webfetch`, `query` |
| 222-236 | **`main()`** | Modo comando directo o interactivo con loop `while True` |
| 240-270 | **`handle_action()`** | Centraliza la logica de todas las acciones y gestiona el historial |

### 4.3 llama.cpp y GGUF

| Componente | Rol |
|---|---|
| **llama.cpp** | Runtime de inferencia en C/C++ para modelos Llama en CPU. Compilado desde fuente con enlace estatico (`-DBUILD_SHARED_LIBS=OFF`) |
| **GGUF** | Formato de archivo para modelos cuantizados. **Q4_K_M**: cuantizacion de 4 bits con mezcla K-quant, balance calidad-rendimiento |
| **llama-cli** | Parametros: `-m` (modelo), `-p` (prompt), `-n 384` (tokens), `--temp 0.7`, `--ctx-size` (2048/4096), `--cache-type-k/q q8_0` (KV cache cuantizada), `--threads 2`, `-no-cnv`, `--no-display-prompt` |

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

### 5.1 Whitelist de aplicaciones (`/etc/yap/whitelist/apps.conf`)

- Mapea **nombres visibles** a comandos del sistema.
- Soporta **multiples binarios alternativos** separados por coma (ej. `firefox-esr,firefox`).
- El agente prueba cada binario en orden hasta encontrar uno disponible mediante `shutil.which()`.

### 5.2 Whitelist de dominios (`/etc/yap/whitelist/web.conf`)

- Lista de dominios permitidos para **webfetch**.
- Validacion estricta: coincidencia exacta o sufijo de subdominio (`domain == d or domain.endswith("." + d)`).
- Contenido limitado a **2000 caracteres**.
- **Correccion de seguridad** (commit `348e9b0`): la implementacion original usaba `domain.endswith(d)` lo que permitia que `notwikipedia.org` coincidiera con `wikipedia.org`.

### 5.3 Acciones bloqueadas por diseno

- Ejecucion de comandos arbitrarios del sistema.
- Operaciones de red fuera de la whitelist.
- Instalacion o eliminacion de software.
- Modificacion de archivos del sistema.

---

## 6. Instalacion

### 6.1 Requisitos del sistema

- **SO:** Debian 13 (o derivada) 64-bit.
- **RAM:** 8 GB (3 GB si se usa la rama `ultra-lowmem`).
- **Disco:** 5 GB de espacio libre.
- **Red:** Conexion a Internet (solo durante la instalacion).

### 6.2 Procedimiento

```bash
git clone https://github.com/VECTORG99/Yap.git
cd Yap
# Opcional: seleccionar rama antes de instalar
# git checkout lowmem         # 6 GB RAM
# git checkout ultra-lowmem   # 3-4 GB RAM
bash setup.sh
```

El instalador realiza automaticamente:

1. Instalacion de dependencias del sistema (`build-essential`, `cmake`, `python3`, `libnotify`, `libcurl`).
2. Compilacion de **llama.cpp** desde fuente con enlace estatico.
3. **Descarga del modelo** — Lee `MODEL_PATH` de `yap.py` y descarga el `.gguf` correspondiente (3B o 1B).
4. Instalacion del agente Yap y whitelists en `/etc/yap/`.
5. Instalacion de aplicaciones sugeridas (LibreOffice, Firefox, Evince, Micro, Htop).
6. Verificacion de componentes.

### 6.3 Actualizacion

```bash
cd ~/Yap
git pull
# El enlace simbolico en /usr/local/bin/yap apunta al repositorio;
# no es necesario reinstalar.
```

---

## 7. Ramas de configuracion

El proyecto mantiene **tres ramas** con distintos perfiles de consumo de RAM y calidad de respuesta:

| Rama | Modelo | Contexto | KV Cache | RAM total | Ideal para |
|---|---|---|---|---|---|
| **master** | 3B Q4_K_M (2.0 GB) | 4096 | FP16 | ~3.5 GB | 8 GB+ RAM |
| **lowmem** | 3B Q4_K_M (2.0 GB) | 2048 | Q8_0 | ~3.1 GB | 6 GB RAM |
| **ultra-lowmem** | 1B Q4_K_M (0.81 GB) | 2048 | Q8_0 | ~1.8 GB | 3-4 GB RAM |

### 7.1 Cambio entre ramas

```bash
cd ~/Yap
git checkout master        # maxima calidad
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
| **master** ↔ **lowmem** | **No** | Solo `git checkout` (mismo modelo 3B) |
| **ultra-lowmem** → **master/lowmem** | Solo para descargar modelo 3B | `git checkout` + `sudo wget <URL del 3B>` o re-ejecutar `setup.sh` |
| **master/lowmem** → **ultra-lowmem** | Solo para descargar modelo 1B | `git checkout` + `sudo wget <URL del 1B>` o re-ejecutar `setup.sh` |

Re-ejecutar `setup.sh` despues de cambiar de rama es **seguro**: detecta lo que ya existe y solo descarga lo faltante.

### 7.4 Optimizaciones aplicadas por rama

| Optimizacion | master | lowmem | ultra-lowmem |
|---|---|---|---|
| Contexto (`--ctx-size`) | 4096 | 2048 | 2048 |
| KV cache (`--cache-type-k/v`) | FP16 | Q8_0 | Q8_0 |
| Flash Attention (`--flash-attn`) | No | Si | Si |
| Hilos (`--threads`) | 4 | 2 | 2 |
| Ahorro RAM | — | ~400 MB | ~1.7 GB |

---

## 8. Uso

### 8.1 Modo interactivo

```bash
yap
Yap > Abre LibreOffice
```

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
| **Consulta LLM** | `yap Que es Debian?` | Responde directamente con el modelo LLM local. Mas rapido pero sin fuente verificable. Soporta historial en modo interactivo |
| **Ayuda** | `yap ayuda` / `yap como usar yap` | Muestra lista de comandos disponibles con descripciones |
| **Tutor PSeInt** | `yap como hago un ciclo mientras` | Consulta al tutor de programacion PSeInt. Responde paso a paso sin historial de conversacion. Contexto reducido (1024 tokens) para minimizar RAM |
| **Tutorial PSeInt** | `yap quiero aprender pseint` | Inicia tutorial interactivo: abre el PDF estatico con la guia de ejercicios, lanza PSeInt, y presenta cada paso de la guia en la terminal. El estudiante puede preguntar dudas; la IA recibe el contexto completo de la guia para responder con precision. |

### 8.4 Clasificacion de intenciones

La funcion **`classify_intent()`** utiliza el propio LLM para determinar la accion a ejecutar, lo que proporciona:

- **Tolerancia a errores ortograficos**: "Abre" y "abre" y "abrir" se clasifican como `open_app`.
- **Flexibilidad sintactica**: "busca sobre Linux" y "que es Linux" se distinguen correctamente.
- **Modo tutor PSeInt**: preguntas sobre programacion/PSeInt se clasifican como `pseint` y responden con guias paso a paso sin historial de conversacion.
- **Tutorial PSeInt**: 'Quiero aprender PSeInt' inicia el tutorial interactivo. Abre un PDF estatico con la guia de resolucion detallada (cada click, cada linea de codigo). La IA presenta los pasos uno a uno y, si el estudiante pregunta, recibe el contexto completo de la solucion para responder con precision sobre el paso exacto donde esta atascado.
- **Historial de conversacion**: hasta 6 turnos almacenados en modo interactivo.

### 8.5 Flujo del tutorial PSeInt

Al ejecutar `yap quiero aprender pseint` o seleccionar "Introduccion PSeInt" desde el menu de ayuda, el sistema ejecuta el siguiente flujo:

1. **Carga de ejercicios**: `cargar_ejercicios()` lee `/etc/yap/pseint/ejercicios.conf` (formato `Titulo:Descripcion|GuiaSolucion`).
2. **Apertura del PDF**: El sistema abre el archivo `guia_ejercicios.pdf` (pre-generado, instalado por `setup.sh` en `/etc/yap/pseint/`) que contiene los ejercicios y sus guias de resolucion paso a paso con formato profesional.
3. **Apertura de PSeInt**: `cmd_open_app("pseint")` lanza el entorno PSeInt desde la whitelist.
4. **Presentacion paso a paso**: El tutorial muestra cada paso de la guia uno por uno. El estudiante presiona Enter para avanzar.
5. **Bucle de asistencia**: En cualquier momento, el estudiante puede escribir una pregunta. `cmd_pseint()` recibe el contexto completo: titulo del ejercicio, descripcion, guia de resolucion completa (todos los pasos) y el paso actual. Asi la IA responde con precision sobre exactamente donde esta atascado el estudiante.
6. **Comandos**: `ayuda` (pista), `siguiente` (siguiente ejercicio), `salir` (terminar).

### Rama lowmem

Para sistemas con solo 6GB RAM, existe la rama `lowmem` con ajustes que liberan ~400MB:

| Rama | Contexto | KV Cache | Flash Attn | RAM total estimada |
|---|---|---|---|---|
| **master** (esta) | 4096 tokens | FP16 | No | ~3.5GB |
| **lowmem** | 2048 tokens | Q8_0 | Si | ~3.1GB |

```bash
git checkout lowmem
```

---

## 9. Limitaciones

- **Contexto limitado**: 2048 tokens (~1500 palabras) en ramas lowmem y ultra-lowmem con KV cache cuantizada Q8_0 para minimizar RAM.
- **Sin persistencia**: cada sesion interactiva es independiente; no hay memoria entre ejecuciones.
- **Latencia**: timeout de 120 s por consulta. En CPU con 2 nucleos, la primera respuesta puede tardar hasta 60 s.
- **Alucinaciones**: el modelo Llama 3.2 3B puede generar informacion incorrecta. Se prefiere `webfetch` para datos factuales.
- **Idioma**: optimizado para espanol; otros idiomas pueden dar resultados inconsistentes.
- **Hardware**: sin soporte GPU ni aceleracion hardware.

---

## 10. Trabajo futuro

### Fase 1 — MVP (completada)

- [x] LLM local (Llama 3.2 Instruct).
- [x] CLI interactiva y por comando directo.
- [x] Tooling de sistema con whitelist.
- [x] Alertas graficas (`notify-send`).
- [x] Whitelist configurable de apps y dominios.
- [x] Demo funcional (abrir app + informacion).

### Fase 2 — Optimizacion y seguridad (completada)

- [x] Compilacion estatica de llama.cpp (sin dependencia de `libllama.so`).
- [x] Correccion de seguridad en whitelist de dominios.
- [x] Soporte multi-binario en whitelist de apps (fallback `firefox-esr` → `firefox`).
- [x] Desactivacion de modo conversacion en llama-cli (`-no-cnv`, `--no-display-prompt`).

### Fase 2 — En desarrollo

- [ ] Capa de confirmacion humana para acciones sensibles.
- [ ] Historial de contexto persistente entre sesiones.
- [ ] Sugerencias de apps alternativas al bloquear.
- [ ] Integracion con **AppArmor**.
- [ ] Instalador `.deb`.
- [ ] Mas fuentes en whitelist educativa.
- [ ] Interfaz de configuracion grafica.

### Fase 3 — Vision a largo plazo

- [ ] Soporte multisesion.
- [ ] Plugins de tooling extensibles.
- [ ] Integracion con gestores de cursos.

---

## 11. Licencia

Este proyecto se distribuye bajo **licencia MIT**. El modelo **Llama 3.2** esta sujeto a los terminos de la **Licencia Llama 3.2 de Meta**.

---

## 12. Pruebas y verificacion

### 12.1 Estructura de la suite

```
tests/
├── test_yap_security.py     # 25 pruebas — seguridad y configuracion
├── test_yap_functional.py   # 56 pruebas — funcionalidad + TUI + cursos
├── run_tests.py             # Ejecutor integrado con reporte
├── report/                  # Reportes generados con --report
└── README.md                # Documentacion de las pruebas
```

Las pruebas usan **`pytest`** con mocking de `subprocess`, `urllib` y `shutil` para evitar dependencia del LLM real. Se ejecutan sin modelo, sin GPU, sin Internet.

```bash
pip install pytest             # Solo requiere pytest
python3 -m pytest tests/ -v    # 81 pruebas
python3 tests/run_tests.py --report   # Reporte TXT con mapeo de requisitos
```

### 12.2 Integracion continua (GitHub Actions)

Cada `push` y `pull request` a `master`, `lowmem` o `ultra-lowmem` ejecuta automaticamente:

| Job | Que hace |
|---|---|
| **unit-tests** | 81 pruebas en Python 3.12 + verificacion estatica (`shell=True`, `eval()`, `os.system()`) + validacion de whitelist |
| **branch-check** | Verifica que `MODEL_PATH` en cada rama apunte al modelo correcto |
| **results** | Resumen del pipeline |

Pipeline definido en `.github/workflows/test.yml`.

[![Yap CI](https://github.com/VECTORG99/Yap/actions/workflows/test.yml/badge.svg)](https://github.com/VECTORG99/Yap/actions/workflows/test.yml)

### 12.3 Pruebas de seguridad (`test_yap_security.py`)

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

### 12.4 Pruebas funcionales (`test_yap_functional.py`)

| Clase | Prueba | Verifica |
|---|---|---|
| **TestOpenApp** | `test_abrir_app_exitosa` | App permitida → `[OK]` + nombre |
| | `test_abrir_app_con_binario_alternativo` | `firefox-esr` no existe → usa `firefox` |
| | `test_app_no_encontrada_mensaje_graceful` | App desconocida → error + alternativas |
| **TestWebfetch** | `test_dominio_bloqueado_mensaje_graceful` | Dominio bloqueado → error + permitidos |
| | `test_subdominio_permitido` | `es.wikipedia.org` → pasa el filtro |
| | `test_fetch_contenido_se_limpia` | Tags HTML eliminados del contenido |
| **TestIntentClassification** | `test_classify_open_app` | `"Abre Firefox"` → `open_app\|firefox` |
| | `test_classify_search` | `"busca que es linux"` → `search\|...` |
| | `test_classify_webfetch` | URL completa → `webfetch\|...` |
| | `test_classify_query` | Pregunta general → `query\|...` |
| | `test_classify_pseint` | `"como hago un ciclo mientras"` → `pseint\|...` |
| | `test_fallback_a_query` | LLM timeout → fallback a `query` |
| **TestQuery** | `test_cmd_query_respuesta_exitosa` | Respuesta del LLM se devuelve correctamente |
| | `test_cmd_query_timeout` | Timeout → `[WARN]` |
| | `test_cmd_query_sin_respuesta` | stdout vacio → muestra stderr |
| **TestHistory** | `test_historial_se_almacena` | Consulta con `store_history=True` → se guarda |
| | `test_historial_no_almacena_si_false` | `store_history=False` → no se guarda |
| | `test_historial_limitado` | Maximo `MAX_HISTORY` entradas (6) |
| **TestNotifications** | `test_notify_enviado` | `notify()` llama a `notify-send` con titulo y mensaje |
| | `test_notify_urgency_levels` | Soporta `-u critical`, `-u normal` |
| **TestPSeIntTutor** | `test_cmd_pseint_respuesta_exitosa` | Tutor PSeInt devuelve guia paso a paso |
| **TestArchitecture** | `test_*_existe` | Verifica que `main()`, `handle_action()`, `interpret()`, `load_whitelist()`, `load_domain_whitelist()`, `cmd_pseint()`, `cmd_intro_pseint()`, `cargar_ejercicios()`, `cargar_ejercicios()` existen y son callables |
| **TestPSeIntConfig** | `test_cargar_ejercicios_*` | Carga de ejercicios desde archivo de configuracion PSeInt |
| **TestIntroduccionPSeInt** | `test_tutorial_*` | Tutorial interactivo: navegacion, ayuda, preguntas al tutor, finalizacion |

### 12.5 Mecanismo de pruebas

Todas las pruebas se ejecutan **sin el modelo LLM** mediante mocking:

```
subprocess.run      → mock (devuelve stdout/stderr predefinidos)
urllib.request      → mock (devuelve HTML de prueba)
shutil.which        → mock (devuelve rutas falsas)
```

Las pruebas de **infraestructura** (symlink, llama-cli, modelo) se ejecutan unicamente en la VM donde Yap esta instalado, mediante:

```bash
python3 tests/run_tests.py --vm --report
```

### 12.6 Resultados

| Categoria | Pruebas | Resultado |
|---|---|---|
| Seguridad (whitelist, injection, dominios) | 25/25 | ✓ 100% |
| Funcional (apps, webfetch, LLM, historial, PSeInt, tutorial, TUI, cursos, progreso) | 56/56 | ✓ 100% |
| Infraestructura (symlink, binarios, whitelist en disco) | 5/5 | ✓ 100% (en VM) |
| **Total** | **81/81** | **✓ 100%** |

---

> **Referencias**: [llama.cpp](https://github.com/ggerganov/llama.cpp) | [Llama 3.2](https://ai.meta.com/blog/llama-3-2-connect-2024-vision-edge-mobile-devices/) | [GGUF format](https://github.com/ggerganov/ggml/blob/master/docs/gguf.md) | [Debian](https://www.debian.org/) | [VirtualBox](https://www.virtualbox.org/)
