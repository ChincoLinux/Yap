# Empaquetado .deb de Yap

Guia para construir, instalar y publicar los paquetes Debian de Yap (issue #31).

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
2. Instala el perfil AppArmor en `/etc/apparmor.d/usr.local.bin.yap` y lo carga con `apparmor_parser`.
3. Crea el symlink `/usr/local/bin/yap` → `/opt/yap/yap.py`.

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
/usr/share/doc/yap/
/etc/yap/                       # configs vivas (postinst)
/etc/apparmor.d/usr.local.bin.yap
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
├── yap/DEBIAN/{control,postinst,prerm,postrm}
├── yap/copyright
├── yap-models-1b/DEBIAN/{control,postinst,postrm}
└── yap-models-3b/DEBIAN/{control,postinst,postrm}
```

`@VERSION@` se toma de `VERSION`. `@INSTALLED_SIZE@` lo calcula `build-deb.sh`.

## CI

`.github/workflows/build-deb.yml`:

| Evento | Que hace |
|---|---|
| Pull request a `main` | Tests `test_yap_deb.py` + `.deb` stub + instalacion en contenedor **Debian 12 (bookworm)** |
| GitHub Release publicado | Compila llama.cpp y adjunta los `.deb` al release |
| `workflow_dispatch` | Build real; opcional embeber modelos |

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
