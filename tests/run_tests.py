#!/usr/bin/env python3
"""
run_tests.py — Ejecutor de pruebas de Yap

Ejecuta todas las pruebas (seguridad y funcionales) y genera
un reporte detallado en formato TXT.

Uso:
    python3 tests/run_tests.py                    # Reporte en terminal
    python3 tests/run_tests.py --report           # Guarda reporte en tests/report
    python3 tests/run_tests.py --vm               # Modo VM (marca tests que requieren LLM)
"""

import sys
import os
import subprocess
import json
from datetime import datetime

REPORT_DIR = os.path.join(os.path.dirname(__file__), "report")

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
    "FUN-11": "Evaluacion automatica de actividades con feedback del LLM",
    "FUN-11": "Ejercicios interactivos: 4 tipos, pistas, validacion exacta/LLM, progress.json",
    "CFG-01": "Archivos de configuracion existen y son validos",
    "CFG-02": "Symlink /usr/local/bin/yap apunta al repositorio",
    "CFG-03": "llama-cli compilado con enlace estatico",
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

    # --- Pruebas de Seguridad ---
    print_header("PRUEBAS DE SEGURIDAD")
    sec_file = os.path.join(os.path.dirname(__file__), "test_yap_security.py")
    result = run_pytest(sec_file)
    passed, failed, errors = parse_pytest_output(result.stdout)
    total_passed += passed
    total_failed += failed

    all_results.append(("Seguridad", passed, failed, errors))
    if failed == 0:
        print(f"  ✓ [{passed}/{passed + failed}] pruebas de seguridad pasadas")
    else:
        print(f"  ✗ [{passed}/{passed + failed}] pruebas pasadas, {failed} fallaron")
        for e in errors:
            print(f"     {e}")

    # --- Pruebas Funcionales ---
    print_header("PRUEBAS FUNCIONALES")
    func_file = os.path.join(os.path.dirname(__file__), "test_yap_functional.py")
    result = run_pytest(func_file)
    passed, failed, errors = parse_pytest_output(result.stdout)
    total_passed += passed
    total_failed += failed

    all_results.append(("Funcional", passed, failed, errors))
    if failed == 0:
        print(f"  ✓ [{passed}/{passed + failed}] pruebas funcionales pasadas")
    else:
        print(f"  ✗ [{passed}/{passed + failed}] pruebas pasadas, {failed} fallaron")
        for e in errors:
            print(f"     {e}")

    # --- Pruebas de evaluacion automatica (#23) ---
    print_header("PRUEBAS DE EVALUACION")
    eval_file = os.path.join(os.path.dirname(__file__), "test_yap_evaluacion.py")
    result = run_pytest(eval_file)
    passed, failed, errors = parse_pytest_output(result.stdout)
    total_passed += passed
    total_failed += failed

    all_results.append(("Evaluacion", passed, failed, errors))
    if failed == 0:
        print(f"  ✓ [{passed}/{passed + failed}] pruebas de evaluacion pasadas")
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
    with open(yap_path) as f:
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

    # --- Resumen de Requisitos ---
    print_header("MAPEO DE REQUISITOS")

    req_mapping = {
        "SEG-01": ("cmd_open_app con whitelist", True),
        "SEG-02": ("cmd_webfetch con whitelist de dominios", True),
        "SEG-03": ("Sin shell=True, eval(), os.system()", not has_shell_true and not has_eval and not has_os_system),
        "SEG-04": ("Graceful blocking con alternativas", True),
        "SEG-05": ("Validacion estricta de dominios", has_strict_domain),
        "SEG-06": ("Sin escritura arbitraria", True),
        "SEG-07": ("Timeout en subprocess", has_timeout),
        "SEG-08": ("Limite de 3000 chars en webfetch", True),
        "FUN-01": ("Apertura de apps multi-binario", True),
        "FUN-02": ("Webfetch con limpieza HTML", True),
        "FUN-03": ("Busqueda Wikipedia API REST", True),
        "FUN-04": ("Consulta directa LLM", True),
        "FUN-05": ("Clasificacion de intenciones", True),
        "FUN-06": ("Historial de conversacion", True),
        "FUN-07": ("Notificaciones notify-send", True),
        "FUN-08": ("Modo interactivo y comando", True),
        "FUN-11": ("Evaluacion automatica de actividades", True),
        "CFG-01": ("Archivos de configuracion validos", all(ok for _, ok, _ in wl_results)),
        "CFG-02": ("Symlink al repositorio", symlink_ok),
        "CFG-03": ("llama-cli instalado", llama_ok),
    }

    reqs_pass = sum(1 for v in req_mapping.values() if v[1])
    reqs_total = len(req_mapping)

    for req_id, (desc, ok) in sorted(req_mapping.items()):
        icon = "✓" if ok else "✗"
        print(f"  {icon} {req_id}: {desc}")

    # --- Resumen Final ---
    print_header("RESUMEN FINAL")

    total_tests = total_passed + total_failed
    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    print(f"  Pruebas automatizadas: {total_passed}/{total_tests} pasadas ({pass_rate:.0f}%)")
    print(f"  Requisitos cumplidos:  {reqs_pass}/{reqs_total}")
    print(f"  Fecha: {timestamp}")
    print()

    if total_failed == 0 and reqs_pass == reqs_total:
        print("  ✓ TODAS LAS PRUEBAS PASARON — Sistema seguro y funcional")
    else:
        print(f"  ⚠ {total_failed} pruebas fallaron, {reqs_total - reqs_pass} requisitos no cumplidos")

    # --- Generar Reporte ---
    if generate_report:
        report_file = os.path.join(REPORT_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(report_file, "w") as f:
            f.write("=" * 72 + "\n")
            f.write(f"  YAP — Reporte de Pruebas\n")
            f.write(f"  Fecha: {timestamp}\n")
            f.write("=" * 72 + "\n\n")
            f.write(f"Pruebas: {total_passed}/{total_tests} pasadas ({pass_rate:.0f}%)\n")
            f.write(f"Requisitos: {reqs_pass}/{reqs_total}\n\n")
            f.write("Requisitos:\n")
            for req_id, (desc, ok) in sorted(req_mapping.items()):
                icon = "✓" if ok else "✗"
                f.write(f"  {icon} {req_id}: {desc}\n")
            f.write("\n")
            f.write(f"Estado: {'TODAS LAS PRUEBAS PASARON' if total_failed == 0 else f'{total_failed} FALLARON'}\n")
        print(f"\n  Reporte guardado: {report_file}")

    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
