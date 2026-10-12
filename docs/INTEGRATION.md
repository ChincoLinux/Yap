# Integración en ChincoLinux OS / Integration tests (#34)

Cómo verificar que Yap funciona **en un sistema real** (Live USB, VM o laptop
educativa), no sólo en el contenedor de CI.

## 1. Verificación automatizada

Con Yap ya instalado (`.deb` o ISO):

```bash
sh packaging/test-integration-os.sh          # todas las comprobaciones
sh packaging/test-integration-os.sh --help   # qué comprueba
```

Comprueba los 8 puntos del issue:

| # | Comprobación | Qué espera |
|---|---|---|
| 1 | `yap` en el PATH | binario resoluble |
| 2 | `yap --apparmor-status` | modo **enforce** |
| 3 | `yap ayuda` | imprime comandos |
| 4 | `yap curso FPY1101` | muestra el curso |
| 5 | `/etc/yap/whitelist/` | `apps.conf` y `web.conf` |
| 6 | `/opt/yap/models/` | al menos un `.gguf` |
| 7 | `aa-exec … cat /etc/shadow` | **denegado** por el perfil |
| 8 | `yap --daemon-status` | responde |

Sale con `0` si todo pasa y `1` si algo falla (`SKIP` no cuenta como fallo).
La sintaxis de todos los scripts de empaquetado se verifica en CI con
`tests/test_packaging_scripts.py` (`sh -n`).

## 2. Checklist manual en hardware real

Para el laptop educativo (Celeron N4000 / 4 GB, ver también [PERFORMANCE.md](PERFORMANCE.md)):

- [ ] Arranque desde Live USB
- [ ] `yap` responde en < 10 s con el modelo 1B
- [ ] AppArmor en enforce (`yap --apparmor-status`)
- [ ] Whitelists activas: `yap abre firefox` pasa, `yap abre calc` se bloquea
- [ ] No supera 2 GB de RAM durante una consulta (`ps` / `htop`)
- [ ] `sh packaging/test-integration-os.sh` → 0 fallas

## 3. CI con VM (QEMU) — pendiente

El issue propone correr esta verificación en GitHub Actions con QEMU/VirtualBox
contra la ISO de ChincoLinux OS. **No está implementado** y queda fuera de este
repositorio mientras no haya:

1. Una imagen de ChincoLinux OS publicada y descargable en CI (hoy el build de la
   ISO vive fuera de este repo, ver issue #32).
2. Un runner con suficiente RAM para la VM (2 GB mínimos).

Cuando existan ambos, el paso será: descargar ISO → `qemu-system-x86_64 …` →
ssh/serial → `sh packaging/test-integration-os.sh` → publicar el resumen.
Mientras tanto, la verificación se hace con el checklist manual de arriba.

## Referencias

- Empaquetado: [PACKAGING.md](PACKAGING.md)
- Rendimiento: [PERFORMANCE.md](PERFORMANCE.md)
- Post-install: `yap --postinstall-check` (issue #129)
- Instalación en contenedor (CI): `packaging/test-install-debian.sh`
