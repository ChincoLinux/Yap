# Yap

Asistente de inteligencia artificial local para ChincoLinux. Disenado para entornos educativos con recursos limitados, corre integramente en CPU sin necesidad de conexion a Internet para su funcionamiento base.

---

## Objetivo del proyecto

Construir un sistema Debian estable ultraligero con un agente IA local (CPU-only) capaz de:

- Responder en espanol con enfoque educativo.
- Ejecutar acciones seguras del sistema mediante tooling controlado por whitelist.
- Abrir aplicaciones desde una lista blanca configurable.
- Recuperar informacion de sitios web aprobados.
- Aplicar restricciones para acciones sensibles.
- Emitir alertas graficas mediante notify-send.

---

## Especificaciones tecnicas

| Componente | Detalle |
|---|---|
| Modelo | Llama 3.2 3B Instruct (GGUF Q4_K_M) |
| Runtime | llama.cpp (CPU-only, sin GPU) |
| RAM minima | 8 GB (5-6 GB utiles para LLM + cache) |
| Contexto | 4096 tokens por defecto |
| Latencia estimada | 2-3 s primeras tokens en CPU |
| Idioma | Espanol |
| SO destino | Debian 13 (64-bit) |

---

## Arquitectura

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

### Flujo de una consulta

1. El usuario escribe un comando en la terminal.
2. El interprete analiza el texto y decide el tipo de accion:
   - Si comienza con "abre", "abrir", "open", "lanzar" o "iniciar": accion de apertura de app.
   - Si comienza con "busca", "buscar", "fetch" o "webfetch" seguido de URL: accion de webfetch.
   - Cualquier otro texto: consulta al LLM.
3. La accion se ejecuta contra la whitelist correspondiente.
4. El resultado se muestra en pantalla y se emite una alerta grafica.

---

## Tecnologias utilizadas

### Bash (setup.sh)

El instalador es un script Bash que automatiza la configuracion del entorno. Conceptos clave:

| Linea(s) | Concepto | Explicacion |
|---|---|---|
| 2 | `set -euo pipefail` | `-e` detiene el script si un comando falla; `-u` trata variables no definidas como error; `-o pipefail` propaga errores en tuberias. |
| 14 | `SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)` | Obtiene la ruta absoluta del directorio donde se encuentra el script, permitiendo ejecutarlo desde cualquier ubicacion. |
| 26-32 | `sudo apt-get install -y -qq` | Instala paquetes sin confirmacion (-y) y con salida silenciosa (-qq). |
| 36 | `mktemp -d` | Crea un directorio temporal unico y seguro para compilar sin dejar residuos. |
| 37 | `cd "$LLAMA_BUILD"` | Cambia al directorio temporal creado. |
| 38 | `git clone --depth 1 --branch "$LLAMACPP_BRANCH"` | Clonado superficial (solo el ultimo commit) para ahorrar ancho de banda y disco. |
| 41 | `cmake .. -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF` | Configura el proyecto CMake en modo Release y deshabilita funcionalidades no necesarias (CURL, CUDA, BLAS, Metal). |
| 42 | `cmake --build . --config Release -j"$(nproc)"` | Compila usando todos los nucleos disponibles. |
| 50 | `if [ ! -f "$MODEL_FILE" ]` | Verifica si el modelo ya existe antes de descargar (reanudacion de instalacion). |
| 62-63 | `sudo ln -sf ...` | Crea un enlace simbolico en /usr/local/bin para que el comando `yap` este disponible globalmente. |

### Python (yap.py)

El agente principal esta escrito en Python 3. Conceptos clave:

| Linea(s) | Concepto | Explicacion |
|---|---|---|
| 4 | `import subprocess` | Permite ejecutar comandos del sistema (llamar a notify-send, abrir apps, ejecutar llama-cli). |
| 8-9 | `import urllib.request, urllib.parse` | Para realizar peticiones HTTP (webfetch) y analizar URLs de forma segura. |
| 13-16 | Constantes de configuracion | Rutas a archivos de whitelist y modelo, inmutables durante la ejecucion. |
| 21-31 | `load_whitelist()` | Lee archivos de configuracion clave:valor, ignora comentarios y lineas vacias. |
| 34-42 | `load_domain_whitelist()` | Carga la lista de dominios permitidos. |
| 45-53 | `notify()` | Envia notificaciones graficas al escritorio mediante notify-send. |
| 56-76 | `cmd_open_app()` | Verifica whitelist, busca el binario en PATH, lo ejecuta y obtiene su version. |
| 79-93 | `cmd_webfetch()` | Valida el dominio contra la whitelist y descarga contenido textual limitado a 2000 caracteres. |
| 96-113 | `cmd_query()` | Envia el prompt al modelo LLM local a traves de llama-cli. |
| 116-127 | `interpret()` | Analiza el texto del usuario para determinar la intencion (abrir app, buscar web, o consultar LLM). |
| 130-154 | `main()` | Punto de entrada: modo comando directo (argv) o modo interactivo (input loop). |

Funcion de dominio (seguridad):
- La validacion en `cmd_webfetch` usa coincidencia exacta o sufijo de subdominio: `domain == d or domain.endswith("." + d)`. Esto evita que `notwikipedia.org` coincida con `wikipedia.org` (bug corregido en commit 348e9b0).

### llama.cpp y GGUF

| Componente | Rol |
|---|---|
| llama.cpp | Runtime de inferencia para modelos Llama en CPU. Compilado desde fuente con optimizaciones nativas. |
| GGUF | Formato de archivo para modelos cuantizados. Q4_K_M significa cuantizacion de 4 bits con mezcla de precisiones para balancear calidad y rendimiento. |
| llama-cli | Herramienta de linea de comandos que carga el modelo GGUF y genera texto. Parametros usados: -m (modelo), -p (prompt), -n (tokens a generar), --temp (temperatura/creatividad), --ctx-size (tamanio del contexto). |

### CMake

| Parametro | Explicacion |
|---|---|
| `-DCMAKE_BUILD_TYPE=Release` | Optimiza el binario para velocidad (sin debug symbols). |
| `-DLLAMA_CURL=OFF` | Deshabilita soporte para descarga de modelos via CURL (no necesario, descargamos con wget). |
| `-DLLAMA_CUDA=OFF` | Deshabilita soporte GPU NVIDIA (CPU-only). |
| `-DLLAMA_BLAS=OFF` | Deshabilita aceleracion BLAS (no disponible en hardware basico). |
| `-DLLAMA_METAL=OFF` | Deshabilita soporte para GPU Apple (no relevante). |

### VirtualBox y VBoxManage

| Comando | Funcion |
|---|---|
| `VBoxManage createvm --name "X" --ostype "Debian_64" --register` | Crea y registra una maquina virtual. |
| `VBoxManage modifyvm --memory 8192 --cpus 2 --vram 100 --nic1 nat` | Configura RAM, CPU, VRAM y red NAT. |
| `VBoxManage createmedium disk --filename X.vdi --size 51200` | Crea disco virtual de 50 GB dinamico. |
| `VBoxManage storagectl --name "SATA Controller" --add sata` | Anade controlador SATA. |
| `VBoxManage storageattach ... --type dvddrive --medium X.iso` | Monta ISO de instalacion. |
| `VBoxManage startvm "X"` | Inicia la maquina virtual. |

### Debian Linux (SO base)

| Paquete | Proposito |
|---|---|
| build-essential | Compilador gcc y herramientas base para compilar llama.cpp. |
| cmake | Generador de archivos de compilacion. |
| libcurl4-openssl-dev | Headers de CURL (requerido por llama.cpp). |
| python3-pip | Instalador de paquetes Python. |
| libnotify-bin | Cliente notify-send para alertas graficas. |
| libreoffice, evince, firefox-esr, micro, htop | Aplicaciones permitidas en whitelist. |

### Seguridad del sistema de whitelist

El agente implementa dos capas de restriccion:

1. **Whitelist de aplicaciones** (`/etc/yap/whitelist/apps.conf`):
   - Mapea nombres visibles a comandos del sistema.
   - El agente solo puede ejecutar binarios listados aqui.
   - La busqueda del binario usa `shutil.which()`, que respeta el PATH del sistema.

2. **Whitelist de dominios** (`/etc/yap/whitelist/web.conf`):
   - Lista de dominios permitidos para webfetch.
   - La validacion es estricta: coincidencia exacta o subdominio directo.
   - El contenido descargado se limita a 2000 caracteres.
   - Se usa un User-Agent personalizado para identificacion.

3. **Acciones bloqueadas por diseno**:
   - Ejecucion de comandos arbitrarios del sistema.
   - Operaciones de red fuera de la whitelist.
   - Instalacion o eliminacion de software.
   - Modificacion de archivos del sistema.

---

## Instalacion

### Requisitos

- Debian 13 (o derivada) 64-bit.
- 8 GB RAM.
- 5 GB de espacio libre en disco.
- Conexion a Internet (solo durante la instalacion).

### Pasos

```bash
git clone https://github.com/VECTORG99/Yap.git
cd Yap
bash setup.sh
```

El instalador realiza automaticamente:

1. Instalacion de dependencias del sistema (build-essential, cmake, python3, libnotify, libcurl).
2. Compilacion de llama.cpp desde fuente.
3. Descarga del modelo Llama 3.2 3B Instruct (GGUF Q4_K_M, ~2 GB).
4. Instalacion del agente Yap y sus listas blancas.
5. Instalacion de aplicaciones sugeridas (LibreOffice, Firefox, Evince, Micro, Htop).
6. Verificacion de componentes.

---

## Uso

### Modo interactivo

```bash
yap
Yap > Abre LibreOffice
```

### Modo comando directo

```bash
yap Abre LibreOffice
yap Busca https://es.wikipedia.org/wiki/Linux
yap Que es una particion de disco?
```

### Acciones soportadas

| Accion | Ejemplo | Descripcion |
|---|---|---|
| Abrir app | `yap Abre LibreOffice` | Abre la app si esta en whitelist. |
| Webfetch | `yap Busca https://es.wikipedia.org/wiki/Linux` | Obtiene contenido del sitio si el dominio esta en whitelist. |
| Consulta LLM | `yap Que es Debian?` | Responde con el modelo LLM local. |

---

## Limitaciones conocidas

- Contexto limitado a 4096 tokens (~3000 palabras). Consultas largas pueden requerir resumen previo.
- Sin conversacion persistente (cada consulta es independiente). Ver issue #2.
- El modelo Llama 3.2 3B puede alucinar informacion. Se prefiere webfetch para datos factuales.
- Solo optimizado para espanol. Otros idiomas pueden dar resultados inconsistentes.
- Sin soporte GPU ni aceleracion hardware.

---

## Roadmap

### Fase 1 — MVP (completada)
- [x] LLM local (Llama 3.2 3B Instruct).
- [x] CLI interactiva y por comando directo.
- [x] Tooling de sistema con whitelist.
- [x] Alertas graficas (notify-send).
- [x] Whitelist configurable de apps y dominios.
- [x] Demo funcional (abrir app + informacion).

### Fase 2 — Proximos sprints
- [ ] Capa de confirmacion humana para acciones sensibles.
- [ ] Historial de contexto persistente (issue #2).
- [ ] Sugerencias de apps alternativas al bloquear (issue #3).
- [ ] Integracion con AppArmor.
- [ ] Instalador .deb.
- [ ] Mas fuentes en whitelist educativa.
- [ ] Interfaz de configuracion grafica.

### Fase 3 — Futuro
- [ ] Soporte multisesion.
- [ ] Plugins de tooling extensibles.
- [ ] Integracion con gestores de cursos.

---

## Licencia

Este proyecto se distribuye bajo licencia MIT. El modelo Llama 3.2 esta sujeto a los terminos de la Licencia Llama 3.2 de Meta.
