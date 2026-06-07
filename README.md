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
| Latencia estimada | 15-30 s primeras tokens en CPU (2 nucleos), ~20 tok/s |
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
2. `classify_intent()` envia el texto al LLM con un prompt de clasificacion.
3. El LLM responde con `ACCION|PARAMETRO`: open_app, search (Wikipedia), webfetch (URL directa), o query (consulta general).
4. `handle_action()` ejecuta la accion contra la whitelist o el LLM segun corresponda.
5. El resultado se muestra en pantalla.

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
| 41 | `cmake .. -DCMAKE_BUILD_TYPE=Release -DLLAMA_CUDA=OFF -DLLAMA_BLAS=OFF -DLLAMA_METAL=OFF -DLLAMA_CURL=OFF -DLLAMA_STATIC=ON` | Configura el proyecto CMake en modo Release, deshabilita funcionalidades no necesarias y activa enlace estatico para evitar dependencia de libllama.so. |
| 42 | `cmake --build . --config Release -j"$(nproc)"` | Compila usando todos los nucleos disponibles. |
| 43 | `sudo cp bin/llama-cli /usr/local/bin/llama-cli` | Copia el binario compilado estaticamente al PATH global. |
| 50 | `if [ ! -f "$MODEL_FILE" ]` | Verifica si el modelo ya existe antes de descargar (reanudacion de instalacion). |
| 63 | `sudo ln -sf "$SCRIPT_DIR/yap.py" "$BIN_DIR/yap"` | Crea un enlace simbolico al archivo del repositorio. Al hacer `git pull`, el symlink apunta automaticamente a la version actualizada sin necesidad de copiar. |

### Python (yap.py)

El agente principal esta escrito en Python 3. Conceptos clave:

| Linea(s) | Concepto | Explicacion |
|---|---|---|
| 4-10 | `import subprocess`, `urllib`, `re`, `shutil` | Ejecucion de comandos, peticiones HTTP, regex HTML, busqueda de binarios. |
| 12-17 | Constantes de configuracion | Rutas a whitelist (`/etc/yap/`), modelo (`/opt/yap/models/`), tokens BOS/HEADER/FOOTER/EOT. |
| 29-43 | `load_whitelist()` | Lee apps.conf (clave:binarios). Usa list comprehension con strip() para eliminar espacios en blancos. |
| 45-53 | `load_domain_whitelist()` | Carga lista de dominios permitidos. Validacion estricta: coincidencia exacta o subdominio directo. |
| 56-64 | `notify()` | Notificacion grafica via notify-send con 3 niveles de urgencia. |
| 67-101 | `cmd_open_app()` | Busca el primer binario usando `shutil.which()`, lo ejecuta y captura version. Si la app no esta en whitelist, lista las apps disponibles (graceful blocking). |
| 104-133 | `cmd_webfetch()` | Valida dominio, descarga contenido, elimina HTML via regex y limita a 3000 chars. Si el dominio esta bloqueado, lista los permitidos. |
| 136-178 | `cmd_query()` | Construye prompt con tokens Llama 3.2 Instruct e historial de conversacion. store_history=False evita duplicar prompts de resumen en historial. |
| 178-216 | `classify_intent()` | Envia el texto al LLM con prompt de clasificacion. LLM responde ACCION|PARAM (open_app, search, webfetch, query). Tolerante a errores ortograficos y sintaxis variada. |
| 218-219 | `interpret()` | Wrapper que llama a `classify_intent()`. |
| 222-236 | `main()` | Modo comando directo o interactivo con loop `while True`. |
| 240-270 | `handle_action()` | Centraliza logica: open_app, search (Wikipedia+LLM+fuente), webfetch (URL+resumen), query (consulta directa al LLM). Gestiona historial. |

Funcion de dominio (seguridad):
- La validacion en `cmd_webfetch` (linea 112) usa coincidencia exacta o sufijo de subdominio: `domain == d or domain.endswith("." + d)`. Esto evita que `notwikipedia.org` coincida con `wikipedia.org` (bug corregido en commit 348e9b0).

### llama.cpp y GGUF

| Componente | Rol |
|---|---|
| llama.cpp | Runtime de inferencia para modelos Llama en CPU. Compilado desde fuente con optimizaciones nativas y enlace estatico (-DLLAMA_STATIC=ON). |
| GGUF | Formato de archivo para modelos cuantizados. Q4_K_M significa cuantizacion de 4 bits con mezcla de precisiones para balancear calidad y rendimiento. |
| llama-cli | Parametros usados: -m (modelo), -p (prompt con tokens especiales Llama 3.2 Instruct), -n (384 tokens), --temp (0.7), --ctx-size (4096), -no-cnv (desactiva modo conversacion automatico), --no-display-prompt (suprime eco del prompt en salida). |

### CMake

| Parametro | Explicacion |
|---|---|---|
| `-DCMAKE_BUILD_TYPE=Release` | Optimiza el binario para velocidad (sin debug symbols). |
| `-DLLAMA_CURL=OFF` | Deshabilita soporte para descarga de modelos via CURL (no necesario, descargamos con wget). |
| `-DLLAMA_CUDA=OFF` | Deshabilita soporte GPU NVIDIA (CPU-only). |
| `-DLLAMA_BLAS=OFF` | Deshabilita aceleracion BLAS (no disponible en hardware basico). |
| `-DLLAMA_METAL=OFF` | Deshabilita soporte para GPU Apple (no relevante). |
| `-DLLAMA_STATIC=ON` | Compilacion estatica para evitar dependencia de libllama.so en tiempo de ejecucion. |

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
   - Soporta multiples binarios alternativos separados por coma (ej. `firefox-esr,firefox`).
   - El agente prueba cada binario en orden hasta encontrar uno disponible.
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
2. Compilacion de llama.cpp desde fuente con enlace estatico.
3. Descarga del modelo Llama 3.2 3B Instruct (GGUF Q4_K_M, ~2 GB).
4. Instalacion del agente Yap y sus listas blancas. El script se copia a `/opt/yap/yap.py` y se crea un enlace simbolico en `/usr/local/bin/yap`.
5. Instalacion de aplicaciones sugeridas (LibreOffice, Firefox, Evince, Micro, Htop).
6. Verificacion de componentes.

### Actualizacion

```bash
cd ~/Yap
git pull
# El enlace simbolico en /usr/local/bin/yap apunta al repo,
# no es necesario copiar.
```

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
yap Busca que es una particion de disco
yap Que es Debian?
```

### Acciones soportadas

| Accion | Ejemplo | Descripcion |
|---|---|---|
| Abrir app | `yap Abre LibreOffice` | Abre la app si esta en whitelist (soporta multiples binarios alternativos). |
| Webfetch + resumen | `yap Busca https://es.wikipedia.org/wiki/Linux` | Obtiene contenido del sitio, lo limpia de HTML y lo envia al LLM para resumir. |
| Busqueda Wikipedia | `yap Busca que es Linux` | Busca en Wikipedia via API REST, extrae el contenido y lo resume con el LLM. Muestra la fuente. Recomendado para informacion factual. |
| Consulta LLM | `yap Que es Debian?` | Responde directamente con el modelo LLM local. Mas rapido pero sin fuente verificable. Soporta historial en modo interactivo. |

---

## Limitaciones conocidas

- Contexto limitado a 4096 tokens (~3000 palabras). Consultas largas pueden requerir resumen previo.
- Sin conversacion persistente (cada consulta es independiente). Ver issue #2.
- Timeout de 120s por consulta. En CPU con 2 nucleos, la primera respuesta puede tardar hasta 60s.
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

### Fase 2 — En progreso
- [x] Compilacion estatica de llama.cpp (sin dependencia de libllama.so).
- [x] Correccion de seguridad en whitelist de dominios (commit 348e9b0).
- [x] Soporte multi-binario en whitelist de apps (fallback firefox-esr -> firefox).
- [x] Desactivacion de modo conversacion en llama-cli (-no-cnv, --no-display-prompt).
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
