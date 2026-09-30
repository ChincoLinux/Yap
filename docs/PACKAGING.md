# Empaquetado .deb de Yap

Guia para construir, instalar y publicar los paquetes Debian de Yap (issues #31 y #33).

## Paquetes

| Paquete | Archivo | Contenido |
|---|---|---|
| `yap` | `yap_<ver>_amd64.deb` | `yap.py`, `llama-cli` estatico, whitelists, cursos, perfil AppArmor |
| `yap-models-1b` | `yap-models-1b_<ver>_all.deb` | Llama 3.2 1B Instruct Q4_K_M (~0.81 GB) |
| `yap-models-3b` | `yap-models-3b_<ver>_all.deb` | Llama 3.2 3B Instruct Q4_K_M (~1.9 GB) |

Los modelos van en paquetes separados: el agente cabe en un `.deb` pequeno y cada aula elige 1B o 3B segun la RAM.

## Instalacion

Tras descargar los `.deb` (release de GitHub o build local):

```bash
sudo apt install ./yap_1.0.0_amd64.deb
sudo apt install ./yap-models-1b_1.0.0_all.deb    # equipos ~2 GB RAM
# o
sudo apt install ./yap-models-3b_1.0.0_all.deb    # equipos ~3.5 GB RAM
```

`apt install ./archivo.deb` resuelve dependencias (`python3`, `libnotify-bin`, `apparmor`). No hace falta `sudo ./setup.sh`.

El `postinst` de `yap`:

1. Copia whitelists, PSeInt y cursos a `/etc/yap/` **solo si no existen** (no pisa cambios del admin).
2. Valida el perfil AppArmor instalado por `dpkg` en `/etc/apparmor.d/usr.local.bin.yap` y lo carga si el kernel permite AppArmor.
3. Crea el symlink `/usr/local/bin/yap` → `/opt/yap/yap.py`.

El paquete instala ademas `/usr/share/user-tmpfiles.d/yap.conf`. Al iniciar
la siguiente sesion de usuario con systemd, `systemd-tmpfiles-setup.service`
crea `~/.config/yap/` con permisos `0700` y propietario del usuario. No se
recorren los directorios personales ni se ejecuta tmpfiles como root en
`postinst`. La regla no elimina datos por antiguedad. `libpam-systemd` se
recomienda para integrar las sesiones de usuario.

En una sesion ya abierta se puede aplicar la regla como el propio usuario:

```bash
systemd-tmpfiles --user --create yap.conf
stat -c '%U %a %n' ~/.config/yap
```

Sin una sesion systemd, la creacion al login no aplica; Yap sigue creando
su directorio al guardar datos. El paquete no instala ni habilita
`yap-daemon.service`: la inferencia persistente, la condicion de RAM y
`yap --daemon-status` siguen pendientes de decision en #33.

### AppArmor y actualizaciones

El perfil se llama **`yap`** y cubre el launcher y el script instalado en
`/opt/yap/yap.py`. No declara modo complain: la instalacion limpia usa
enforce cuando AppArmor esta disponible. Una desactivacion explicita del
administrador en `/etc/apparmor.d/disable/` se respeta.

El perfil es un **conffile de dpkg**: las reinstalaciones conservan las
modificaciones locales, `remove` lo conserva y `purge` lo elimina. En la
primera actualizacion desde paquetes antiguos, que copiaban ese archivo
sin registrarlo como conffile, `dpkg` puede pedir elegir entre el perfil
existente y el nuevo. Revisar las diferencias y adoptar el perfil corregido,
reaplicando las personalizaciones necesarias. No forzar globalmente el
reemplazo de configuraciones locales. Si el perfil conservado contiene
errores de sintaxis, corregirlo y ejecutar `sudo dpkg --configure yap`.

`postinst` compila el perfil incluso sin soporte de kernel. Los errores de
sintaxis o de carga con AppArmor disponible hacen fallar la configuracion
del paquete; no se ocultan. En contenedores o kernels sin AppArmor se emite
un aviso explicito: el perfil esta instalado, **sin confinamiento activo**.
Durante actualizaciones, el nuevo `prerm` ya no descarga el perfil; en
desinstalaciones sigue descargandolo.

Verificacion en una VM Debian con AppArmor activo:

```bash
sudo aa-status
sudo cat /sys/kernel/security/apparmor/profiles | grep '^yap ('
yap --apparmor-status
yap ayuda
```

Comprobar tambien una consulta local y las aplicaciones educativas del
aula; compilar un perfil no demuestra que todos los flujos funcionen bajo
confinamiento. Las pruebas en contenedores no sustituyen esa validacion.

English: the package validates and loads AppArmor when the kernel supports
it, preserves administrator changes through dpkg conffiles, and installs a
user tmpfiles rule for a private Yap directory at session startup. Containers
validate syntax and the package lifecycle, not live kernel confinement. The
persistent inference daemon remains outside this delivery.

El `postinst` de `yap-models-*` descarga el GGUF a `/opt/yap/models/` si el archivo no viene ya embebido en el paquete.

Purge conserva `~/.config/yap/` (progreso e historial del estudiante):

```bash
sudo apt purge yap yap-models-1b yap-models-3b
```

## Layout instalado

```
/opt/yap/yap.py
/opt/yap/models/*.gguf          # paquetes yap-models-*
/usr/local/bin/yap              → /opt/yap/yap.py
/usr/local/bin/llama-cli        # binario estatico
/usr/share/yap/whitelist/       # defaults
/usr/share/yap/pseint/
/usr/share/yap/cursos/
/usr/share/yap/apparmor/
/usr/share/user-tmpfiles.d/yap.conf  # regla de sesion, no limpieza de progreso
/usr/share/doc/yap/
/etc/yap/                       # configs vivas (postinst)
/etc/apparmor.d/usr.local.bin.yap    # conffile gestionado por dpkg
```

## Construir

Requisito: Debian/Ubuntu con `dpkg-deb`. Compilar `llama-cli` pide `git`, `cmake` y `build-essential`.

```bash
chmod +x build-deb.sh

# Paquete real (compila llama.cpp, tag b5097, enlace estatico CPU-only)
./build-deb.sh --outdir dist

# CI / pruebas: llama-cli stub, sin compilar
./build-deb.sh --stub-llama --outdir dist

# Usar un llama-cli ya compilado
./build-deb.sh --llama-cli /usr/local/bin/llama-cli

# ISO offline: embebe el GGUF dentro del .deb (descarga ~0.81 / 1.9 GB)
./build-deb.sh --embed-models 1b
./build-deb.sh --embed-models all
```

Salida en `dist/`:

```
yap_<ver>_amd64.deb
yap-models-1b_<ver>_all.deb
yap-models-3b_<ver>_all.deb
```

Plantillas en `packaging/`:

```
packaging/
├── yap/DEBIAN/{control,conffiles,postinst,prerm,postrm}
├── yap/user-tmpfiles.d/yap.conf
├── yap/copyright
├── yap-models-1b/DEBIAN/{control,postinst,postrm}
└── yap-models-3b/DEBIAN/{control,postinst,postrm}
```

`@VERSION@` se toma de `VERSION`. `@INSTALLED_SIZE@` lo calcula `build-deb.sh`.

## CI

`.github/workflows/build-deb.yml`:

| Evento | Que hace |
|---|---|
| Pull request a `main` | Tests de empaquetado, AppArmor y whitelists + `.deb` stub + instalacion, reinstalacion y purga en contenedores **Debian 12 (bookworm) y 13 (trixie)** |
| GitHub Release publicado | Compila llama.cpp y adjunta los `.deb` al release |
| `workflow_dispatch` | Build real; opcional embeber modelos |

Las pruebas de maintainer scripts ejecutan el shell real sobre rutas
temporales con el parser simulado para errores y disponibilidad del kernel.
Otra prueba compila el perfil con `apparmor_parser` real. La prueba Debian
ejecuta `apt` y `dpkg-reconfigure` en el contenedor, y
`systemd-tmpfiles --user` como un usuario sin privilegios. Comprueba que
reinstalar conserva configuraciones y que
purgar conserva el progreso. Se usa un stub de llama-cli y un GGUF simulado;
no se valida inferencia ni se descargan modelos.

Referencias: [systemd-tmpfiles](https://www.freedesktop.org/software/systemd/man/systemd-tmpfiles.html)
y [configuracion de paquetes Debian](https://www.debian.org/doc/debian-policy/ap-pkg-conffiles.html).

## Repositorio apt (opcional)

Este issue publica artefactos de release, no un repo apt completo. En un servidor interno:

```bash
reprepro includedeb stable dist/yap_*.deb
# o un Packages.gz generado con dpkg-scanpackages
```

En el cliente:

```bash
sudo apt install yap yap-models-1b
```

La integracion en la ISO de ChincoLinux es el issue #32.

## Relacion con setup.sh

`setup.sh` sigue siendo el instalador de **desarrollo** (clona llama.cpp, symlink al repo, git hooks). El `.deb` es el instalador de **produccion** para aulas: binario precompilado, configs en `/etc/yap/`, AppArmor automatico.
