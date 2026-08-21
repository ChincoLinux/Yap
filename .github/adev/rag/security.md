# RAG: Seguridad de Yap (ChincoLinux)

> Contexto recuperable para agentes. Fuente de verdad: `yap.py`, `whitelist/`, `tests/test_yap_security.py`.

---

## Modelo de seguridad: Listas Blancas (Whitelists)

Yap opera bajo **zero-trust a nivel de acciones del sistema**. Solo lo explícitamente permitido se ejecuta.

### Whitelist de aplicaciones (`whitelist/apps.conf`)

```
# Formato: Nombre visible:binario1,binario2
LibreOffice:libreoffice
Firefox:firefox-esr,firefox
PSeInt:pseint
```

**Carga** (`load_whitelist()`):
```python
apps = {}
for line in f:
    line = line.strip()
    if line and not line.startswith("#"):
        parts = line.split(":", 1)
        if len(parts) == 2:
            apps[parts[0].lower()] = [c.strip() for c in parts[1].split(",")]
```

**Validación** (`cmd_open_app()`):
- `shutil.which(binario)` por cada binario en orden
- Si ninguno disponible → `[ERROR]` + lista de apps permitidas
- Si encontrado → `subprocess.Popen([binario, ...])` (sin shell=True)

### Whitelist de dominios (`whitelist/web.conf`)

```
wikipedia.org
debian.org
```

**Carga** (`load_domain_whitelist()`):
```python
domains = []
for line in f:
    line = line.strip()
    if line and not line.startswith("#"):
        domains.append(line.lower())
```

**Validación** (`cmd_webfetch()`):
```python
# Coincidencia exacta o subdominio directo
def validar_dominio(dominio, dominios_permitidos):
    dominio = dominio.lower()
    return any(dominio == d or dominio.endswith("." + d) for d in dominios_permitidos)
```

⚠️ **Corrección de seguridad** (commit `348e9b0`): la implementación original usaba `domain.endswith(d)` que permitía que `notwikipedia.org` coincidiera con `wikipedia.org`. Ahora usa `domain == d or domain.endswith("." + d)`.

---

## Reglas de código (verificadas en CI)

| Regla | Verificación | Política |
|---|---|---|
| ❌ `shell=True` | `grep -rn "shell=True" yap.py` | HD-YAP-SEC-001 |
| ❌ `eval()` | `grep -rn "eval(" yap.py` | HD-YAP-SEC-001 |
| ❌ `os.system()` | `grep -rn "os.system(" yap.py` | HD-YAP-SEC-001 |
| ❌ `open()` escritura fuera whitelist | Análisis estático | HD-YAP-SEC-001 |
| ❌ `os.remove`, `shutil.rmtree` | Análisis estático | HD-YAP-SEC-001 |
| ✅ `timeout=` en todo `subprocess.run()` | Test `test_timeout_en_subprocess` | HD-YAP-SEC-001 |
| ✅ Límite 3000 chars webfetch | `text[:3000]` | HD-YAP-SEC-001 |
| ✅ Sin imports peligrosos | `socket`, `ctypes`, `pickle`, `base64` prohibidos | HD-YAP-SEC-001 |

---

## Tests de seguridad (25 pruebas)

### TestAppWhitelist (4)
- `test_app_permitida_devuelve_ok` — app en whitelist carga OK
- `test_app_bloqueada_muestra_alternativas` — bloqueada → `[ERROR]` + lista
- `test_app_bloqueada_no_ejecuta_comando` — `subprocess.Popen` NO se llama
- `test_multiples_binarios_fallback` — `firefox-esr,firefox` → 2 binarios

### TestDomainWhitelist (4)
- `test_dominio_permitido_exacto` — `wikipedia.org` pasa
- `test_subdominio_permitido` — `es.wikipedia.org` pasa
- `test_dominio_bloqueado_muestra_alternativas` — `malware.com` → `[ERROR]`
- `test_notwikipedia_no_coincide` — `notwikipedia.org` NO hace match

### TestCommandSecurity (7)
- `test_no_shell_true_en_subprocess` — scan: sin `shell=True`
- `test_no_eval` — scan: sin `eval()`
- `test_no_os_system` — scan: sin `os.system()`
- `test_command_injection_app_name` — `"; rm -rf /"`, `$(whoami)`, `` `id` ``, `&& shutdown` → bloqueados
- `test_url_injection` — `file:///etc/passwd`, `127.0.0.1`, `[::1]`, `javascript:` → bloqueados

### TestConfigLoading (4)
- `test_whitelist_ignora_comentarios` — líneas `#` ignoradas
- `test_whitelist_ignora_lineas_vacias` — líneas vacías ignoradas
- `test_formato_invalido_ignorado` — líneas sin `:` ignoradas

### TestSecurityLimits (2)
- `test_contenido_limitado_3000_chars` — `text[:3000]` en `cmd_webfetch`
- `test_timeout_en_subprocess` — todo `subprocess.run()` tiene `timeout=`

### TestFileSystemSecurity (1)
- `test_no_escritura_fuera_de_whitelist` — sin `open(w)`, `os.remove`, `shutil.rmtree`

### TestRealConfig (4)
- `test_apps_conf_existe` — `whitelist/apps.conf` existe
- `test_web_conf_existe` — `whitelist/web.conf` existe
- `test_apps_conf_tiene_contenido` — entradas válidas
- `test_web_conf_tiene_contenido` — dominios válidos

### TestCodeQuality (2)
- `test_no_shebang_incorrecto` — `#!/usr/bin/env python3`
- `test_imports_minimos` — sin imports peligrosos

---

## Acciones bloqueadas por diseño

| Acción | Por qué |
|---|---|
| Comandos arbitrarios del sistema | Bypass whitelist apps; RCE potencial |
| Red fuera de whitelist | Exfiltración, fetch de contenido malicioso |
| Instalar/eliminar software | Persistencia, modificación de entorno |
| Modificar archivos del sistema | Integridad de `/etc/yap/`, seguridad educativa |

---

## Inyección de comandos (mitigada)

```python
# App name con meta-caracteres
"; rm -rf /"     → rechazado (no en whitelist, char inválido)
$(whoami)        → rechazado
`id`             → rechazado
&& shutdown      → rechazado

# URL con esquemas no permitidos
file:///etc/passwd  → rechazado (no es http/https válido)
javascript:         → rechazado
[::1]               → rechazado (no es dominio whitelist)
```

**Mecanismo**: validación en dos capas:
1. Whitelist membership (app name / domain exacto)
2. `shutil.which()` confirma binario real antes de `Popen([binario])` — no se interpola string a shell

---

## Notificaciones (`notify-send`)

```python
notify(title, message, urgency="normal"):
    # urgency ∈ {low, normal, critical}
    subprocess.run(["notify-send", "-u", urgency, title, message], timeout=10)
```

Sin `shell=True`, con `timeout=10`.

---

## Precedencia de seguridad (Hardness)

1. **Safety/Law/Privacy** (máxima) — protección de estudiantes, datos
2. **User aims/bounds** — intención del usuario dentro de whitelist
3. **Repo/Org doctrine** — `HD-YAP-SEC-001`, `CLAUDE.md`
4. **Local overlays** — rama específica (lowmem ≠ master)
5. **Skill contract** — `yap-read-only-inspection` (R0)
6. **General defaults** — Python stdlib segura

**Conflicto**: una política de nivel superior (MUST) nunca se rompe silenciosamente por una inferior.

---

## Referencias de código

- `yap.py:29-43` — `load_whitelist`
- `yap.py:45-53` — `load_domain_whitelist`
- `yap.py:56-64` — `notify`
- `yap.py:67-101` — `cmd_open_app`
- `yap.py:104-133` — `cmd_webfetch`
- `tests/test_yap_security.py` — suite completa (25 pruebas)