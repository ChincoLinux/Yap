# Yap — Guía de despliegue para administradores escolares

> Documento orientado al administrador de una escuela que necesita desplegar Yap
> en varios computadores (laboratorio, sala de clases). Para uso individual del
> estudiante, ver [USAGE.md](../USAGE.md).

Esta guía cubre cuatro escenarios:

1. [Instalación individual](#1-instalación-individual) — un solo equipo.
2. [Instalación masiva en red escolar](#2-instalación-masiva-en-red-escolar) — varios equipos vía SSH.
3. [Configuración post-instalación](#3-configuración-post-instalación) — whitelists, AppArmor, modelo.
4. [Mantenimiento](#4-mantenimiento) — actualizaciones, respaldos, monitoreo.

Más una sección de [administración](#5-administración) para personalizar Yap por colegio.

---

## Requisitos previos

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| CPU | x86_64, 2 núcleos | 4 núcleos |
| RAM | 2 GB (rama `ultra-lowmem`) | 4 GB (rama `main`) |
| Disco | 3 GB libres | 5 GB libres |
| SO | Debian 12+ / Ubuntu 22.04+ (basado en apt) | Debian 12 |
| Red | No requerida tras la instalación | Solo para descarga inicial |
| Permisos | `sudo` en cada equipo | — |

Yap funciona **100% offline** una vez instalado. La red solo se necesita durante
la instalación para descargar `llama.cpp` (compilación) y el modelo GGUF.

> **Nota sobre paquete .deb:** el empaquetado APT (`apt install yap`) es trabajo
> del issue #31 y aún no está disponible. Mientras tanto, el despliegue se realiza
> desde el repositorio git con `setup.sh`, que es el flujo soportado y probado.

---

## 1. Instalación individual

Para un solo computador (por ejemplo, el equipo del docente o un estudiante aislado).

```bash
# 1. Clonar el repositorio
sudo git clone https://github.com/ChincoLinux/Yap.git /opt/Yap

# 2. Entrar al directorio y ejecutar el instalador
cd /opt/Yap
sudo ./setup.sh
```

`setup.sh` realiza automáticamente:

1. Instala dependencias del sistema (`build-essential`, `cmake`, `python3`, etc.).
2. Compila `llama.cpp` y coloca `llama-cli` en `/usr/local/bin/`.
3. Descarga el modelo GGUF correspondiente a la rama activa (ver [ramas de modelo](#ramas-de-modelo-según-ram)).
4. Copia whitelists, cursos y el agente a `/etc/yap/`.
5. Crea el symlink `/usr/local/bin/yap → /opt/Yap/yap.py`.
6. Instala aplicaciones sugeridas (LibreOffice, Firefox ESR, PSeInt, etc.).
7. Carga el perfil AppArmor de Yap (si AppArmor está presente).

Al terminar, verifica con:

```bash
yap --apparmor-status
yap ayuda
```

### Ramas de modelo según RAM

El modelo se elige cambiando de rama **antes** de ejecutar `setup.sh`. Cada rama
descarga un modelo distinto optimizado para la RAM disponible:

| Rama | RAM estimada | Modelo | Hardware objetivo |
|------|--------------|--------|-------------------|
| `main` | ~3.5 GB | Llama-3.2-3B Q4_K_M | Escritorio moderno (≥4 GB) |
| `lowmem` | ~3.1 GB | Llama-3.2-3B Q4_K_M, ctx reducido | PCs antiguos (≥3 GB) |
| `ultra-lowmem` | ~1.8 GB | Llama-3.2-1B Q4_K_M | Netbooks / Raspberry Pi (≥2 GB) |

```bash
cd /opt/Yap
sudo git checkout ultra-lowmem   # elegir según hardware
sudo ./setup.sh
```

> Cambiar entre `main` y `lowmem` **no** requiere re-ejecutar `setup.sh` (mismo
> modelo 3B). Cambiar a `ultra-lowmem` sí requiere re-ejecutarlo para descargar
> el modelo 1B. El symlink `/usr/local/bin/yap` se actualiza al instante con el
> `git checkout`.

---

## 2. Instalación masiva en red escolar

Para desplegar Yap en 10–40 computadores de un laboratorio desde un equipo
administrador (con acceso SSH a todos los equipos).

### 2.1 Preparar el mirror local (recomendado)

Compilar `llama.cpp` en cada equipo es lento y descarga lo mismo N veces. Para
evitarlo, prepara un mirror en el equipo administrador:

```bash
# En el equipo administrador (con internet)
sudo git clone https://github.com/ChincoLinux/Yap.git /srv/mirror/Yap
sudo git -C /srv/mirror/Yap checkout ultra-lowmem   # rama según hardware del lab

# Descargar el modelo una sola vez (lo hará setup.sh en el mirror)
cd /srv/mirror/Yap && sudo ./setup.sh

# Compartir el mirror por NFS o HTTP local
sudo apt install -y nfs-kernel-server
echo "/srv/mirror/Yap  *(ro,sync,no_subtree_check)" | sudo tee -a /etc/exports
sudo exportfs -ra
```

Los equipos del laboratorio montarán `/srv/mirror/Yap` en lugar de clonar desde
GitHub, reutilizando el modelo ya descargado.

### 2.2 Lista de hosts

Crea un archivo de texto con un host por línea (IP o nombre DNS):

```bash
# /etc/yap/lab1.txt
10.0.0.11
10.0.0.12
10.0.0.13
10.0.0.14
10.0.0.15
```

### 2.3 Despliegue con `deploy-yap.sh`

El repositorio incluye `deploy-yap.sh` para orquestar la instalación por SSH:

```bash
# Sintaxis
sudo ./deploy-yap.sh --hosts /etc/yap/lab1.txt [opciones]

# Opciones:
#   --mirror /srv/mirror/Yap   Usar mirror local (NFS/HTTP) en lugar de clonar de GitHub
#   --branch ultra-lowmem      Rama/modelo a desplegar (default: ultra-lowmem)
#   --whitelist /etc/yap/whitelist  Empujar whitelists centralizadas tras instalar
#   --user alumno              Usuario SSH remoto (default: alumno)
#   --dry-run                  Solo mostrar qué se haría, sin ejecutar
#   --parallel 4               Equipos simultáneos (default: 4)
```

Ejemplo completo para un laboratorio de 15 netbooks:

```bash
sudo ./deploy-yap.sh \
  --hosts /etc/yap/lab1.txt \
  --mirror /srv/mirror/Yap \
  --branch ultra-lowmem \
  --whitelist /etc/yap/whitelist \
  --user alumno \
  --parallel 4
```

El script:

1. Verifica conectividad SSH a cada host (`--dry-run` para validar antes).
2. Copia el repositorio desde el mirror (o clona de GitHub si no hay mirror).
3. Ejecuta `setup.sh` en cada equipo de forma paralela y controlada.
4. Opcionalmente empuja whitelists centralizadas.
5. Genera un reporte final con el estado de cada host.

> **Requisitos SSH:** el usuario remoto (`alumno`) debe tener `sudo` sin contraseña
> en cada equipo, o configurar `NOPASSWD` en `/etc/sudoers.d/yap-deploy` para los
> comandos de instalación. Ver [ejemplo de sudoers](#apéndice-a-sudoers-para-despliegue).

### 2.4 Whitelists centralizadas vía NFS

Para que todos los equipos usen las mismas whitelists sin editar cada uno:

```bash
# En el administrador: exportar las whitelists por NFS
echo "/etc/yap/whitelist  *(ro,sync,no_subtree_check)" | sudo tee -a /etc/exports
sudo exportfs -ra

# En cada equipo (o integrado en deploy-yap.sh):
# Montar sobre /etc/yap/whitelist para que todos lean la misma config
sudo mount -t nfs administrador:/etc/yap/whitelist /etc/yap/whitelist
```

Añadir al `/etc/fstab` de cada equipo para persistencia:

```
administrador:/etc/yap/whitelist  /etc/yap/whitelist  nfs  ro,defaults  0  0
```

---

## 3. Configuración post-instalación

### 3.1 Personalizar whitelists por colegio

Las whitelists viven en `/etc/yap/whitelist/`:

| Archivo | Controla | Formato |
|---------|----------|---------|
| `apps.conf` | Aplicaciones que `yap abre <X>` puede lanzar | `Nombre:comando1,comando2` |
| `web.conf` | Dominios permitidos para `webfetch` y `busca` | un dominio por línea |

Ejemplo: permitir solo LibreOffice y Firefox, bloquear todo web:

```bash
# /etc/yap/whitelist/apps.conf
LibreOffice:libreoffice
Firefox:firefox-esr,firefox

# /etc/yap/whitelist/web.conf  (vacío = sin webfetch)
# wikipedia.org
```

> Yap recarga las whitelists en cada invocación, no requiere reiniciar nada.

### 3.2 Activar AppArmor (recomendado)

`setup.sh` carga el perfil AppArmor automáticamente si AppArmor está presente.
Para verificar o activar manualmente:

```bash
yap --apparmor-status

# Si no está cargado:
sudo cp /opt/Yap/apparmor/usr.local.bin.yap /etc/apparmor.d/
sudo apparmor_parser -r /etc/apparmor.d/usr.local.bin.yap
```

El perfil restringe qué archivos y redes puede tocar Yap. Recomendado mantenerlo
en modo `enforce` en equipos de estudiantes.

### 3.3 Elegir modelo según RAM del equipo

Si el laboratorio tiene hardware heterogéneo, despliega la rama según cada equipo:

```bash
# En un equipo con ≥4 GB RAM
sudo git -C /opt/Yap checkout main && sudo /opt/Yap/setup.sh

# En una netbook con 2 GB RAM
sudo git -C /opt/Yap checkout ultra-lowmem && sudo /opt/Yap/setup.sh
```

`deploy-yap.sh --branch` permite especificar la rama para todo el lote. Para
hardware mixto, ejecuta el script dos veces con `--hosts` y `--branch` distintos.

---

## 4. Mantenimiento

### 4.1 Actualizar Yap

Como `/usr/local/bin/yap` es un symlink al repositorio, actualizar es solo
`git pull`:

```bash
sudo git -C /opt/Yap pull
# El agente se actualiza al instante. No requiere re-ejecutar setup.sh
# salvo que el cambio incluya nuevas dependencias o un nuevo modelo.
```

Para validar que la actualización no rompió nada:

```bash
yap ayuda
yap --apparmor-status
```

### 4.2 Respaldar progreso de estudiantes

El progreso de cada estudiante vive en `~/.config/yap/`:

| Archivo | Contenido |
|---------|-----------|
| `progress.json` | Avance por curso y EA |
| `history.json` | Historial de conversaciones (últimas 20 sesiones) |
| `confirmations.json` | Acciones confirmadas (confianza progresiva) |

Respaldo centralizado desde el administrador:

```bash
# Respaldar /home de todos los equipos del lab
for host in $(cat /etc/yap/lab1.txt); do
  rsync -a "alumno@${host}:/home/*/.config/yap/" \
    "/srv/backups/yap/${host}/"
done
```

Restaurar a un equipo:

```bash
sudo rsync -a /srv/backups/yap/10.0.0.11/ \
  "alumno@10.0.0.11:/home/alumno/.config/yap/"
```

### 4.3 Monitoreo

```bash
# Estado de AppArmor en un equipo remoto
ssh alumno@10.0.0.11 'yap --apparmor-status'

# Verificar que el agente responde
ssh alumno@10.0.0.11 'yap ayuda'

# Espacio en disco (el modelo pesa ~0.8–1.9 GB)
ssh alumno@10.0.0.11 'df -h /opt/yap'
```

---

## 5. Administración

### 5.1 Añadir un curso personalizado

Crea un JSON en `/etc/yap/cursos/` siguiendo el schema de `FPY1101.json`:

```bash
sudo cp mi-curso.json /etc/yap/cursos/MAT1101.json
```

Yap lo descubre automáticamente por glob (`listar_cursos()`); no requiere
modificar código. Ver [USAGE.md § Agregar un curso nuevo](../USAGE.md#agregar-un-curso-nuevo)
para el formato completo del JSON y las claves requeridas (`codigo`, `nombre`,
`horas`, `semanas`, `ras`, `eas`, `evaluaciones`).

### 5.2 Modificar whitelists

Editar directamente `/etc/yap/whitelist/apps.conf` y `web.conf`. Si usas
whitelists centralizadas por NFS (§2.4), editar en el servidor NFS afecta a
todos los equipos al instante.

### 5.3 Cambiar el modelo (3B vs 1B)

```bash
sudo git -C /opt/Yap checkout main          # 3B, mejor calidad, ~3.5 GB RAM
sudo git -C /opt/Yap checkout ultra-lowmem  # 1B, más rápido, ~1.8 GB RAM
sudo /opt/Yap/setup.sh                      # solo si cambió el modelo
```

### 5.4 Deshabilitar características para exámenes

Durante una evaluación, puedes bloquear acceso a apps y web sin desinstalar Yap:

```bash
# Respaldar whitelists originales
sudo cp /etc/yap/whitelist/apps.conf /etc/yap/whitelist/apps.conf.bak
sudo cp /etc/yap/whitelist/web.conf  /etc/yap/whitelist/web.conf.bak

# Vaciar whitelists (solo consultas al LLM local, sin apps ni web)
echo "# Whitelist vacía durante examen" | sudo tee /etc/yap/whitelist/apps.conf
echo "# Whitelist vacía durante examen" | sudo tee /etc/yap/whitelist/web.conf

# Tras el examen, restaurar
sudo mv /etc/yap/whitelist/apps.conf.bak /etc/yap/whitelist/apps.conf
sudo mv /etc/yap/whitelist/web.conf.bak  /etc/yap/whitelist/web.conf
```

> El LLM local (`llama-cli`) sigue funcionando: el estudiante puede preguntar al
> tutor, pero no puede abrir aplicaciones ni hacer `webfetch`. Esto cubre el caso
> de exámenes donde se permite razonamiento asistido pero no navegación.

---

## Apéndice A: sudoers para despliegue

Para que `deploy-yap.sh` funcione sin pedir contraseña en cada equipo, crea
`/etc/sudoers.d/yap-deploy` en cada host:

```
alumno ALL=(root) NOPASSWD: /opt/Yap/setup.sh, /usr/bin/git, /bin/cp, /bin/mount
```

Validar sintaxis antes de guardar:

```bash
sudo visudo -c -f /etc/sudoers.d/yap-deploy
```

## Apéndice B: Checklist de despliegue

- [ ] Verificar RAM de cada equipo y elegir rama (`main` / `lowmem` / `ultra-lowmem`).
- [ ] Preparar mirror local con el modelo ya descargado (§2.1).
- [ ] Crear archivo de hosts (`/etc/yap/lab1.txt`).
- [ ] Configurar sudoers en cada equipo (Apéndice A).
- [ ] Ejecutar `deploy-yap.sh --dry-run` para validar conectividad.
- [ ] Ejecutar `deploy-yap.sh` con `--mirror` y `--branch`.
- [ ] Verificar `yap --apparmor-status` en al menos un equipo.
- [ ] Configurar whitelists por colegio (§3.1) o centralizadas por NFS (§2.4).
- [ ] Programar respaldos de `~/.config/yap/` (§4.2).

---

## Referencias

- [USAGE.md](../USAGE.md) — Guía de uso para el estudiante.
- [README.md](../README.md) — Visión general y requisitos del sistema.
- [docs/ROADMAP.md](ROADMAP.md) — Hoja de ruta del proyecto.
- [ADEV.md](../ADEV.md) — Doctrina operativa de la organización.
