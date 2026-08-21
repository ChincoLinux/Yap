import sys, os, json, datetime

with open("yap.py", "r") as f:
    content = f.read()

# 1. Insert PROFILE_FILE
profile_def = """PROFILE_FILE = os.path.expanduser("~/.config/yap/profile.json")\n"""
if "PROFILE_FILE =" not in content:
    content = content.replace('PROGRESS_FILE = os.path.expanduser("~/.config/yap/progress.json")', 
                              profile_def + 'PROGRESS_FILE = os.path.expanduser("~/.config/yap/progress.json")')

# 2. Insert profile functions
profile_functions = """
def cargar_perfil():
    path = PROFILE_FILE
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

def guardar_perfil(perfil):
    path = PROFILE_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(perfil, f, indent=2, ensure_ascii=False)

def run_onboarding():
    sys.stdout.write(f"\\n{C['CYAN']}=================================================={C['RESET']}\\n")
    sys.stdout.write(f"{C['GREEN']} ¡Bienvenido a Yap! Tu asistente y tutor personal {C['RESET']}\\n")
    sys.stdout.write(f"{C['CYAN']}=================================================={C['RESET']}\\n\\n")
    
    print(f"{C['YELLOW']}1. ¿Qué es Yap?{C['RESET']}")
    print("Yap es tu entorno de aprendizaje interactivo desde la terminal.")
    print("Puede ayudarte a abrir aplicaciones, buscar en internet o guiarte")
    print("paso a paso en tus cursos de programación y tecnología.\\n")
    input(f"{C['GRAY']}[Presiona Enter para continuar]{C['RESET']}")
    
    print(f"\\n{C['YELLOW']}2. ¿Cómo usarlo?{C['RESET']}")
    print("Solo tienes que escribir lo que necesitas de forma natural. Por ejemplo:")
    print("  > abre firefox")
    print("  > busca historia de linux")
    print("  > ayuda\\n")
    input(f"{C['GRAY']}[Presiona Enter para continuar]{C['RESET']}")
    
    print(f"\\n{C['YELLOW']}3. ¿Qué puedo aprender?{C['RESET']}")
    print("Yap incluye cursos interactivos donde avanzas haciendo actividades.")
    print("Prueba escribir: 'curso' para ver la lista de cursos disponibles.\\n")
    input(f"{C['GRAY']}[Presiona Enter para continuar]{C['RESET']}")
    
    print(f"\\n{C['YELLOW']}4. Para empezar, ¿cuál es tu nombre?{C['RESET']}")
    nombre = input(f"{C['GREEN']}Nombre{C['RESET']} > ").strip()
    if not nombre:
        nombre = "Estudiante"
        
    perfil = {
        "nombre": nombre,
        "onboarding_completed": True,
        "primer_uso": _now_iso()
    }
    guardar_perfil(perfil)
    
    print(f"\\n¡Listo, {nombre}! Ya puedes empezar a explorar.")
    print(f"Si alguna vez quieres volver a ver esto, escribe: {C['CYAN']}yap --tutorial{C['RESET']}\\n")
    return perfil

"""
if "def cargar_perfil():" not in content:
    content = content.replace("def cargar_progreso():", profile_functions + "def cargar_progreso():")

# 3. Add to main()
main_add = """
        perfil = cargar_perfil()
        if not perfil:
            perfil = run_onboarding()
        else:
            nombre = perfil.get('nombre', 'Estudiante')
            
            resumen_progreso = "Sin cursos iniciados."
            progreso = cargar_progreso().get("cursos", {})
            if progreso:
                for curso, eas in progreso.items():
                    for ea_id, data in eas.items():
                        if not data.get("completada", False):
                            act = data.get("actividad_actual", 1)
                            total = data.get("total_actividades", 5) # Default 5
                            resumen_progreso = f"Curso: {curso} ({ea_id}, actividad {act}/{total})"
                            break
                    if resumen_progreso != "Sin cursos iniciados.":
                        break
            
            sesiones = _load_history_sessions()
            if sesiones:
                ultima_ts = sesiones[-1].get("timestamp", "")
                try:
                    import datetime as dt_mod
                    ultima_dt = dt_mod.datetime.fromisoformat(ultima_ts)
                    ahora = dt_mod.datetime.now()
                    dias = (ahora - ultima_dt).days
                    if dias == 0:
                        hace = "hoy"
                    elif dias == 1:
                        hace = "ayer"
                    else:
                        hace = f"hace {dias} días"
                except:
                    hace = "desconocido"
            else:
                hace = "nunca"
                
            sys.stdout.write(f"\\n{C['CYAN']}Bienvenido de vuelta, {nombre}.{C['RESET']}\\n")
            sys.stdout.write(f"{C['GRAY']}Sesión anterior: {hace} | {resumen_progreso}{C['RESET']}\\n")
            sys.stdout.write(f"{C['GRAY']}Escribe 'retomar' para continuar donde quedaste, o 'ayuda' para ver comandos.{C['RESET']}\\n\\n")
"""

if "perfil = cargar_perfil()" not in content:
    content = content.replace("sys.stdout.write(render_art(CHINCO_ART, C['CYAN']) + \"\\n\")", main_add.strip() + "\n        sys.stdout.write(render_art(CHINCO_ART, C['CYAN']) + \"\\n\")")

# 4. Add aliases
if '"retomar"' not in content:
    content = content.replace('if stripped in ("historial --ultimo"):', 'if stripped in ("historial --ultimo", "retomar"):')

if '"--tutorial"' not in content:
    content = content.replace('if stripped in ("guia", "guia rapida", "tutorial", "como usar"):', 'if stripped in ("guia", "guia rapida", "tutorial", "como usar", "--tutorial"):')

with open("yap.py", "w") as f:
    f.write(content)

