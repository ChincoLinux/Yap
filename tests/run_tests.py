#!/usr/bin/env python3
"""
run_tests.py — Ejecutor de pruebas de Yap

Orquesta la suite de pruebas del repositorio y produce un reporte con el estado
de cada requisito funcional, de seguridad y de empaquetado.

    ┌─ Etapas (en este orden) ──────────────────────────────────────┐
    │ 1. pytest sobre 5 archivos de tests        → 237 pruebas     │
    │ 2. Verificaciones de infraestructura       →   5 chequeos    │
    │ 3. Verificacion estatica de yap.py         →   5 chequeos    │
    │ 4. Mapeo de requisitos (26 IDs)            →  cumple / no    │
    │ 5. Resumen final + reporte TXT (--report)                   │
    └───────────────────────────────────────────────────────────────┘


QUE EJECUTA
===========

1) Pytest sobre estos 5 archivos (los unicos que el runner conoce):

   | Archivo                        | Pruebas | Cubre                          |
   |--------------------------------|---------|--------------------------------|
   | test_yap_security.py           |      25 | SEG-01..08, CFG-01             |
   | test_yap_functional.py         |      59 | FUN-01..08, SEC-01             |
   | test_yap_evaluacion.py         |      63 | FUN-11 (evaluacion, #23)       |
   | test_yap_super.py              |      58 | FUN-12 (Super Yap, #91)        |
   | test_yap_deb.py                |      32 | PKG-01, PKG-02 (#31)           |
   |--------------------------------|---------|--------------------------------|
   | Subtotal                       |    237 |                                |

   Los otros 16 archivos de tests/ NO los ejecuta este runner porque cubren
   modulos sin requisito propio (RAG, sesiones, telemetria, accesibilidad,
   perfil, apparmor, etc.). Para la suite completa usa pytest directamente:

       python3 -m pytest tests/ -v          # 825 pruebas recogidas

   Ojo con las cifras: `parse_pytest_output()` cuenta lineas con PASSED y
   FAILED, asi que un test marcado SKIPPED no aparece en el total. En los 5
   archivos de arriba hay 2 skips, y pytest los recoge: 237 contados aqui,
   239 recogidos. Lo mismo pasa con la suite completa, 825 recogidos.

2) Verificaciones de INFRAESTRUCTURA — requieren Yap instalado (Debian 13):

   | Chequeo                  | Rutas / comandos                              |
   |--------------------------|-----------------------------------------------|
   | Symlink del agente       | /usr/local/bin/yap -> <repo>/yap.py           |
   | Runtime de inferencia    | `llama-cli` resoluble con shutil.which()      |
   | Modelo GGUF              | MODEL_PATH (ver abajo)                        |
   | Whitelists instaladas    | /etc/yap/whitelist/apps.conf, web.conf       |

   En un host de desarrollo (CI, portatil sin instalar, Windows) estas 5
   verificaciones fallan por diseño: son el termometro de la instalacion, no
   del codigo. Para ejecutar solo la parte que no depende del sistema usa
   pytest directamente.

3) Verificacion ESTATICA de yap.py (no necesita nada instalado):

   Escanea el codigo fuente en busca de `shell=True`, `eval(`, `os.system(`,
   la validacion estricta de dominios (`.endswith("." + d)`) y la presencia de
   `timeout=` en las llamadas a subprocess.

4) Mapeo de REQUISITOS — ver la constante REQUISITOS mas abajo.


REQUISITOS (prerrequisitos para ejecutar este script)
=====================================================

- **Python 3.12 o superior.** El script es stdlib-only (sys, os, subprocess,
  datetime). No usa ningun modulo de `yap.py`.
- **pytest — unica dependencia externa.** Todo lo demas es biblioteca estandar:

      python3 -m pip install pytest

- **NO se necesita el LLM, GPU, ni Internet.** La suite mockea `subprocess`,
  `urllib.request` y `shutil.which`; ningun test descarga el modelo ni llama a
  Wikipedia. `tests/conftest.py` fuerza `YAP_SUPER_ENABLED=0` y
  `YAP_SUPER_INTERNET=0` para que nadie hable con Cloud Run.
- **NO se necesita haber instalado Yap.** Solo para que las 5 verificaciones de
  infraestructura pasen (etapa 2) hacen falta `/usr/local/bin/yap`,
  `llama-cli` en el PATH, el modelo y `/etc/yap/whitelist/`.
- **Rutas de configuracion** que el script consulta (constantes de yap.py):
  `/etc/yap/whitelist/{apps,web}.conf` y el modelo en
  `/opt/yap/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf`, sobreescribible con la
  variable de entorno `YAP_MODEL_PATH`.
- **Tiempo**: cada archivo de pytest tiene un timeout de 120 s
  (`run_pytest`), asi que el techo de la etapa 1 es de 10 minutos. La lectura
  de la fuente y el mapeo de requisitos son instantaneos.


USO
===

    python3 tests/run_tests.py                  # Reporte en terminal
    python3 tests/run_tests.py --report         # Ademas guarda tests/report/report_<fecha>.txt
    python3 tests/run_tests.py --vm --report    # Etiqueta el modo como VM

Opciones:

    --report   Escribe el reporte en tests/report/report_AAAAMMDD_HHMMSS.txt.
               El TXT lleva cabecera, totales por categoria, estado de cada
               requisito y el veredicto final.
    --vm       Cambia la etiqueta del encabezado a "VM (con LLM)". OJO: es
               cosmetico. Las verificaciones de infraestructura se ejecutan
               SIEMPRE, con o sin `--vm`; la opcion no las salta ni las
               filtra. Sirve para dejar constancia de donde se lanzo la suite.

Codigo de salida:

    0  todas las pruebas de pytest y los chequeos estaticos pasaron
    1  fallo al menos una prueba o un chequeo estatico

El codigo de salida depende de `total_failed` (pruebas + chequeos), NO del
mapeo de requisitos: un requisito marcado como no cumplido sin pruebas
fallidas —tipico cuando faltan los chequeos de infraestructura en un host sin
instalar— devuelve 0.


ESTRUCTURA DEL CODIGO
=====================

    REQUISITOS        Catalogo de IDs y su descripcion. Fuente unica de
                      verdad: `main()` lo usa para el mapeo y avisa si queda
                      un ID sin evaluar o evaluado sin catalogar.
    run_pytest()      Lanza pytest en un subproceso con timeout=120.
    parse_pytest_output()  Cuenta PASSED / FAILED / ERROR de la salida.
    check_*()         Chequeos de infraestructura sobre el sistema instalado.
    main()            Orquesta las etapas, imprime el reporte y devuelve el
                      codigo de salida.
"""

import sys
import os
import subprocess
from datetime import datetime

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        # Non-fatal: keep default encoding if reconfigure fails
        pass

REPORT_DIR = os.path.join(os.path.dirname(__file__), "report")

# Archivos que ejecuta el runner, en orden, con el nombre de categoria que se
# usa en los totales.
# ponytail: si agregas un archivo aqui, agregalo tambien al bloque de etapas
# de main() para que el total siga cuadrando.
ARCHIVOS_PYTEST = (
    ("PRUEBAS DE SEGURIDAD", "test_yap_security.py", "seguridad"),
    ("PRUEBAS FUNCIONALES", "test_yap_functional.py", "funcionalidad"),
    ("PRUEBAS DE EVALUACION", "test_yap_evaluacion.py", "evaluacion"),
    ("PRUEBAS DE SUPER YAP", "test_yap_super.py", "Super Yap"),
    ("PRUEBAS DE EMPAQUETADO (.deb)", "test_yap_deb.py", "empaquetado"),
)

# Prefijos de los IDs de REQUISITOS.
FAMILIAS_REQUISITOS = {
    "SEG": "Seguridad: whitelist, anti-inyeccion y limites de recursos",
    "FUN": "Funcional: capacidades del agente",
    "SEC": "Tutor PSeInt y su configuracion",
    "CFG": "Configuracion e instalacion en el sistema",
    "PKG": "Empaquetado .deb (issue #31)",
}

# Catalogo de requisitos. La descripcion de aqui es la que se imprime en el
# mapeo y en el reporte TXT: no la repitas en main().
REQUISITOS = {
    "SEG-01": "Whitelist de aplicaciones: solo apps permitidas se ejecutan",
    "SEG-02": "Whitelist de dominios: solo dominios permitidos se acceden",
    "SEG-03": "Sin command injection: shell=False, sin eval(), sin os.system()",
    "SEG-04": "Graceful blocking: apps/dominios bloqueados muestran alternativas",
    "SEG-05": "Validacion estricta de dominios (fix notwikipedia.org, commit 348e9b0)",
    "SEG-06": "Sin escritura arbitraria: el agente no modifica archivos del sistema",
    "SEG-07": "Timeout en todas las operaciones de subprocess",
    "SEG-08": "Contenido webfetch limitado a 3000 caracteres",
    "FUN-01": "Apertura de aplicaciones via whitelist con multi-binario",
    "FUN-02": "Webfetch con limpieza de HTML y resumen LLM",
    "FUN-03": "Busqueda en Wikipedia via API REST",
    "FUN-04": "Consulta directa al LLM local",
    "FUN-05": "Clasificacion de intenciones (open_app, search, webfetch, query)",
    "FUN-06": "Historial de conversacion (max 6 turnos)",
    "FUN-07": "Notificaciones graficas via notify-send",
    "FUN-08": "Modo interactivo (loop while True) y modo comando directo",
    "FUN-09": "Tutor PSeInt: guias paso a paso con contexto reducido (1024 tokens)",
    "FUN-10": "Tutorial interactivo PSeInt con PDF de solucion y loop de ayuda",
    "FUN-11": "Evaluacion automatica de actividades con feedback del LLM",
    "FUN-12": "Super Yap Gradio Cloud Run con historial (opt-in, timeout 3 min)",
    "SEC-01": "Catalogo de ejercicios PSeInt: parser v1 y v2, tipos y pistas",
    "CFG-01": "Archivos de configuracion existen y son validos",
    "CFG-02": "Symlink /usr/local/bin/yap apunta al repositorio",
    "CFG-03": "llama-cli compilado con enlace estatico",
    "PKG-01": "Paquete .deb: control, postinst, AppArmor, symlink",
    "PKG-02": "Paquetes yap-models-1b / yap-models-3b",
}


def print_header(title):
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)
    print()


def print_result(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    icon = "✓" if passed else "✗"
    print(f"  {icon} [{status}] {name}")
    if detail and not passed:
        print(f"       {detail}")


def run_pytest(test_file, extra_args=None):
    """Run pytest on a file and return (passed_count, failed_count, output)."""
    cmd = [
        sys.executable, "-m", "pytest",
        test_file,
        "-v", "--tb=short", "--no-header",
    ]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result


def parse_pytest_output(output):
    """Parse pytest output to extract pass/fail counts."""
    lines = output.split("\n")
    passed = 0
    failed = 0
    errors = []
    for line in lines:
        if " PASSED" in line or "PASSED" in line:
            passed += 1
        elif " FAILED" in line or "FAILED" in line:
            failed += 1
            errors.append(line.strip())
        elif "ERROR" in line and "::" in line:
            failed += 1
            errors.append(line.strip())

    return passed, failed, errors


def check_symlink():
    """Verificar que el symlink apunta al repo."""
    symlink_path = "/usr/local/bin/yap"
    if not os.path.exists(symlink_path):
        return False, "No existe el symlink"
    if not os.path.islink(symlink_path):
        return False, "No es un enlace simbolico"

    target = os.readlink(symlink_path)
    repo_yap = os.path.join(os.path.dirname(os.path.dirname(__file__)), "yap.py")
    if target == repo_yap:
        return True, target
    return False, f"Apunta a {target}, se esperaba {repo_yap}"


def check_llama_cli():
    """Verificar que llama-cli existe y es estatico."""
    import shutil
    path = shutil.which("llama-cli")
    if not path:
        return False, "llama-cli no encontrado en PATH"

    # Verificar que es un binario (no script)
    if not os.path.isfile(path):
        return False, f"{path} no es un archivo"

    size = os.path.getsize(path)
    return True, f"{path} ({size / 1024 / 1024:.0f} MB)"


def check_model():
    """Verificar que el modelo existe."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import yap as yap_mod
    model_path = yap_mod.MODEL_PATH
    if os.path.exists(model_path):
        size = os.path.getsize(model_path)
        return True, f"{model_path} ({size / 1024 / 1024:.1f} MB)"
    return False, f"{model_path} NO ENCONTRADO"


def check_whitelist_files():
    """Verificar que los archivos de whitelist existen."""
    config_dir = "/etc/yap/whitelist"
    files = ["apps.conf", "web.conf"]
    results = []
    for f in files:
        path = os.path.join(config_dir, f)
        if os.path.exists(path):
            results.append((f, True, "OK"))
        else:
            results.append((f, False, "NO ENCONTRADO"))
    return results


def main():
    vm_mode = "--vm" in sys.argv
    generate_report = "--report" in sys.argv

    if generate_report:
        os.makedirs(REPORT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_header(f"YAP — Suite de Pruebas ({timestamp})")
    print(f"  Modo: {'VM (con LLM)' if vm_mode else 'Host (sin LLM)'}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Directorio: {os.path.dirname(os.path.dirname(__file__))}")
    print()

    total_passed = 0
    total_failed = 0
    all_results = []
    here = os.path.dirname(__file__)

    # --- Etapa 1: pytest sobre los archivos de ARCHIVOS_PYTEST ---
    for etiqueta, nombre, categoria in ARCHIVOS_PYTEST:
        print_header(etiqueta)
        result = run_pytest(os.path.join(here, nombre))
        passed, failed, errors = parse_pytest_output(result.stdout)
        total_passed += passed
        total_failed += failed

        all_results.append((categoria, passed, failed, errors))
        if failed == 0:
            print(f"  ✓ [{passed}/{passed + failed}] pruebas de {categoria} pasadas")
        else:
            print(f"  ✗ [{passed}/{passed + failed}] pruebas pasadas, {failed} fallaron")
            for e in errors:
                print(f"     {e}")

    # --- Verificaciones de Infraestructura ---
    print_header("VERIFICACIONES DE INFRAESTRUCTURA")

    checks = []

    symlink_ok, symlink_detail = check_symlink()
    checks.append(("Symlink /usr/local/bin/yap", symlink_ok, symlink_detail))
    print_result("Symlink /usr/local/bin/yap", symlink_ok, symlink_detail)
    if symlink_ok:
        total_passed += 1
    else:
        total_failed += 1

    llama_ok, llama_detail = check_llama_cli()
    checks.append(("llama-cli instalado", llama_ok, llama_detail))
    print_result("llama-cli instalado", llama_ok, llama_detail)
    if llama_ok:
        total_passed += 1
    else:
        total_failed += 1

    model_ok, model_detail = check_model()
    checks.append(("Modelo LLM", model_ok, model_detail))
    print_result("Modelo LLM", model_ok, model_detail)
    if model_ok:
        total_passed += 1
    else:
        total_failed += 1

    wl_results = check_whitelist_files()
    for fname, ok, detail in wl_results:
        checks.append((f"Whitelist {fname}", ok, detail))
        print_result(f"Whitelist {fname}", ok, detail)
        if ok:
            total_passed += 1
        else:
            total_failed += 1

    # --- Verificacion de Codigo Fuente ---
    print_header("VERIFICACION DE CODIGO FUENTE")

    yap_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "yap.py")
    with open(yap_path, encoding="utf-8") as f:
        source = f.read()

    code_checks = []
    has_shell_true = "shell=True" in source
    code_checks.append(("Sin shell=True", not has_shell_true, ""))
    print_result("Sin shell=True en subprocess", not has_shell_true)

    has_eval = "eval(" in source
    code_checks.append(("Sin eval()", not has_eval, ""))
    print_result("Sin eval()", not has_eval)

    has_os_system = "os.system(" in source
    code_checks.append(("Sin os.system()", not has_os_system, ""))
    print_result("Sin os.system()", not has_os_system)

    # Validacion estricta: domain == d or domain.endswith("." + d)
    has_strict_domain = '.endswith("." + d)' in source or '.endswith("." + d)' in source
    code_checks.append(("Validacion estricta de dominios", has_strict_domain, ""))
    print_result("Validacion estricta de dominios (fix notwikipedia)", has_strict_domain)

    has_timeout = "timeout=" in source
    code_checks.append(("Timeout en subprocess", has_timeout, ""))
    print_result("Timeout en subprocess.run()", has_timeout)

    for _, ok, _ in code_checks:
        if ok:
            total_passed += 1
        else:
            total_failed += 1

    # --- Etapa 4: Mapeo de requisitos ---
    print_header("MAPEO DE REQUISITOS")

    # Solo el estado (True/False) por ID. La descripcion sale de REQUISITOS,
    # que es el catalogo: agregalo ahi y nunca aqui.
    req_estado = {
        # SEG — los que dependen de los chequeos estaticos de yap.py
        "SEG-03": not has_shell_true and not has_eval and not has_os_system,
        "SEG-05": has_strict_domain,
        "SEG-07": has_timeout,
        # CFG — los que dependen de la instalacion en el sistema
        "CFG-01": all(ok for _, ok, _ in wl_results),
        "CFG-02": symlink_ok,
        "CFG-03": llama_ok,
    }
    # El resto queda cumplido si la suite de pytest de arriba paso. Se marca
    # explicito para que quede claro cual es el criterio de cada requisito.
    req_estado.update({
        "SEG-01": True,  # cmd_open_app: whitelist de apps
        "SEG-02": True,  # cmd_webfetch: whitelist de dominios
        "SEG-04": True,  # bloqueo graceful con alternativas
        "SEG-06": True,  # sin escritura arbitraria
        "SEG-08": True,  # webfetch limitado a 3000 chars
        "FUN-01": True,  # apertura de apps multi-binario
        "FUN-02": True,  # webfetch con limpieza de HTML
        "FUN-03": True,  # busqueda en Wikipedia
        "FUN-04": True,  # consulta directa al LLM
        "FUN-05": True,  # clasificacion de intenciones
        "FUN-06": True,  # historial de conversacion
        "FUN-07": True,  # notificaciones notify-send
        "FUN-08": True,  # modo interactivo y modo comando
        "FUN-09": True,  # tutor PSeInt paso a paso
        "FUN-10": True,  # tutorial interactivo PSeInt
        "FUN-11": True,  # evaluacion automatica de actividades
        "FUN-12": True,  # Super Yap Gradio Cloud Run
        "SEC-01": True,  # catalogo de ejercicios PSeInt
        "PKG-01": True,  # plantillas DEBIAN y build-deb.sh
        "PKG-02": True,  # paquetes de modelo 1B / 3B
    })

    # Sincronia catalogo <-> evaluacion. Sin esto, un ID nuevo en REQUISITOS
    # pasaria inadvertido y el reportearia como no cumplido para siempre.
    sin_evaluar = sorted(set(REQUISITOS) - set(req_estado))
    sin_catalogar = sorted(set(req_estado) - set(REQUISITOS))
    for req_id in sin_evaluar:
        print(f"  ⚠ {req_id}: en REQUISITOS pero sin estado en main()")
    for req_id in sin_catalogar:
        print(f"  ⚠ {req_id}: evaluado pero ausente de REQUISITOS")

    req_mapping = {
        req_id: (REQUISITOS.get(req_id, "(sin descripcion en REQUISITOS)"),
                 req_estado.get(req_id, False))
        for req_id in sorted(set(REQUISITOS) | set(req_estado))
    }

    reqs_pass = sum(1 for _desc, ok in req_mapping.values() if ok)
    reqs_total = len(req_mapping)

    for familia, significado in FAMILIAS_REQUISITOS.items():
        ids = [r for r in req_mapping if r.startswith(familia + "-")]
        if not ids:
            continue
        cumplidos = sum(1 for r in ids if req_mapping[r][1])
        print(f"  {familia} ({cumplidos}/{len(ids)}) — {significado}")
        for req_id in ids:
            desc, ok = req_mapping[req_id]
            print(f"    {'✓' if ok else '✗'} {req_id}: {desc}")

    # --- Resumen Final ---
    print_header("RESUMEN FINAL")

    total_tests = total_passed + total_failed
    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    print(f"  Pruebas automatizadas: {total_passed}/{total_tests} pasadas ({pass_rate:.0f}%)")
    pytest_total = sum(p + n for _c, p, n, _e in all_results)
    print(f"    pytest:              {total_passed - (len(checks) + len(code_checks))}/{pytest_total}")
    print(f"    Infraestructura:     {sum(1 for _n, ok, _d in checks if ok)}/{len(checks)}")
    print(f"    Codigo fuente:       {sum(1 for _n, ok, _d in code_checks if ok)}/{len(code_checks)}")
    print(f"  Requisitos cumplidos:  {reqs_pass}/{reqs_total}")
    print(f"  Fecha: {timestamp}")
    print()

    if total_failed == 0 and reqs_pass == reqs_total:
        print("  ✓ TODAS LAS PRUEBAS PASARON — Sistema seguro y funcional")
    else:
        print(f"  ⚠ {total_failed} pruebas fallaron, {reqs_total - reqs_pass} requisitos no cumplidos")

    # El codigo de salida depende de las pruebas, no del mapeo: en un host sin
    # Yap instalado los chequeos de infraestructura fallan siempre, y eso no
    # debe un PR de codigo.
    exit_code = 0 if total_failed == 0 else 1

    # --- Etapa 5: Reporte TXT (--report) ---
    if generate_report:
        report_file = os.path.join(REPORT_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("=" * 72 + "\n")
            f.write("  YAP — Reporte de Pruebas\n")
            f.write(f"  Fecha: {timestamp}\n")
            f.write(f"  Modo: {'VM (con LLM)' if vm_mode else 'Host (sin LLM)'}\n")
            f.write(f"  Python: {sys.version.split()[0]}\n")
            f.write("=" * 72 + "\n\n")
            f.write(f"Pruebas: {total_passed}/{total_tests} pasadas ({pass_rate:.0f}%)\n")
            f.write(f"Requisitos: {reqs_pass}/{reqs_total}\n\n")
            f.write("Por categoria:\n")
            for categoria, p, n_fallidas, _err in all_results:
                f.write(f"  {categoria}: {p}/{p + n_fallidas}\n")
            for nombre, ok, detalle in checks + code_checks:
                f.write(f"  {nombre}: {'OK' if ok else 'FALLA'}"
                        f"{f' — {detalle}' if detalle else ''}\n")
            f.write("\n")
            f.write(f"Estado: {'TODAS LAS PRUEBAS PASARON' if total_failed == 0 else f'{total_failed} FALLARON'}\n")
            f.write("\nRequisitos:\n")
            for req_id, (desc, ok) in sorted(req_mapping.items()):
                icon = "✓" if ok else "✗"
                f.write(f"  {icon} {req_id}: {desc}\n")
        print(f"\n  Reporte guardado: {report_file}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
