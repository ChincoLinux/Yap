# Yap — Guia de uso rapido

## Instalacion

```bash
git clone https://github.com/VECTORG99/Yap.git
cd Yap
chmod +x setup.sh
sudo ./setup.sh
```

Ver requisitos detallados en [README.md](README.md#61-requisitos-del-sistema).

## Comandos basicos

| Comando | Descripcion |
|---------|-------------|
| `yap` | Modo interactivo TUI (curses, 0 dependencias). Escribe preguntas o comandos. |
| `yap guia` | Tutorial interactivo de 7 pasos. |
| `yap ayuda` | Lista de comandos disponibles. |
| `yap progreso` | Progreso de cursos. |

| `yap sesion` | Estado de la sesion activa. |
| `yap sesion pausar` | Pausar la sesion y guardar el contexto. |
| `yap sesion retomar 3` | Retomar una sesion pausada. |

| `yap telemetria` | Resumen local de tu uso de Yap. |
| `yap nube` | Estado del agente en la nube (LOCAL / NUBE / DEGRADADO). |
| `yap nube <pregunta>` | Forzar consulta a Gemini 3.7 Flash; si falla, usa el LLM local. |
| `yap curso FPY1101` | Plan de estudio del curso. |
| `yap iniciar EA1` | Comenzar una experiencia de aprendizaje. |
| `yap <pregunta>` | Consulta directa al AI. |
| `yap que es python` | Pregunta sobre programacion. |
| `yap busca <tema>` | Buscar en Wikipedia y resumir con AI. |
| `yap abre firefox` | Abrir aplicacion permitida. |

## Modo interactivo

Ejecuta `yap` sin argumentos para abrir la TUI interactiva (curses, 0 dependencias externas). Pantalla dividida con output arriba e input abajo, prompt "Chinco > ", historial con flechas.

Si la terminal no soporta curses, cae en REPL clasico:

```
Chinco > abre firefox         → Abre Firefox
Chinco > busca variable       → Wikipedia + resumen AI
Chinco > como hago un ciclo   → Tutor PSeInt
Chinco > ayuda                → Lista de comandos
Chinco > salir                → Salir
Chinco > que es un algoritmo  → Consulta directa al AI
Chinco > nube                 → Estado LOCAL / NUBE / DEGRADADO
Chinco > nube explica while   → Gemini 3.7 Flash (si el lab lo habilitó)
```

## Sistema de cursos

### Ver plan de estudio

```bash
yap curso FPY1101
```

Muestra resultados de aprendizaje (RAs), experiencias de aprendizaje (EAs), horas y herramientas del curso.

### Iniciar una experiencia de aprendizaje

```bash
yap iniciar EA1
```

Flujo de la sesion:

1. **Vista general** — descripcion de la EA, actividades listadas (con tipo de evaluacion si aplica).
2. **Por cada actividad** — descripcion, consigna, herramienta sugerida.
   - Si la actividad tiene `tipo` de evaluacion: escribe tu respuesta. El LLM (o comparacion exacta en opcion multiple) devuelve puntaje y feedback.
   - Hasta 3 intentos por actividad (configurable con `YAP_MAX_INTENTOS` o `max_intentos` en el JSON). Si repruebas, puedes `saltar`.
   - `pregunta ...` = consultar al tutor con contexto del curso y de la sesion activa.
   - `abrir pseint` = lanzar herramienta sugerida.
   - `salir` = guardar progreso y salir.
   - Actividades sin `tipo` siguen el flujo anterior: `Enter` = marcar como hecha.
3. **Al completar todas** — promedio 0-100 y nota final en escala chilena (1.0-7.0, 60% = 4.0).

El progreso se guarda automaticamente al completar cada actividad (archivo atomico en `~/.config/yap/progress.json`).

### Retomar una sesion

```bash
yap iniciar EA1
```

Retoma desde la ultima actividad completada. Las actividades ya hechas aparecen con checkmark (✓).

### Agregar un curso nuevo

Crea un archivo JSON en `/etc/yap/cursos/MAT1101.json`:

```json
{
  "codigo": "MAT1101",
  "nombre": "Algebra Superior",
  "horas": 90,
  "semanas": 18,
  "ambiente": "Aula B-12",
  "herramientas": ["Python 3", "SymPy"],
  "ras": [
    {"id": "RA1", "nombre": "Resuelve sistemas de ecuaciones...", "descripcion": "...", "ponderacion": 40}
  ],
  "eas": [
    {
      "id": "EA1",
      "nombre": "Ecuaciones lineales",
      "horas": 30,
      "ponderacion": 30,
      "descripcion": "Resolucion de sistemas...",
      "herramientas": ["Python 3"],
      "actividades": [
        {
          "orden": 1,
          "nombre": "Sistemas 2x2",
          "descripcion": "Resuelve sistemas...",
          "tool_hint": "Python 3",
          "tipo": "respuesta_libre",
          "criterios_evaluacion": ["Plantea el sistema", "Obtiene la solucion correcta"]
        },
        {
          "orden": 2,
          "nombre": "Sistemas 3x3",
          "descripcion": "...",
          "tool_hint": "Python 3",
          "tipo": "opcion_multiple",
          "opciones": ["Una solucion", "Infinitas", "Ninguna"],
          "respuesta_correcta": "Una solucion",
          "criterios_evaluacion": ["Identifica el caso"]
        }
      ],
      "evaluaciones": [
        {"nombre": "Eva Parcial", "descripcion": "Evaluacion parcial...", "tipo": "individual", "ponderacion": 20}
      ],
      "experiencia_formativa_trabajo": "Guia de ejercicios..."
    }
  ]
}
```

No necesitas modificar el codigo — `listar_cursos()` descubre archivos por glob.

## PSeInt

```bash
yap como hago un ciclo mientras   → Tutor PSeInt
yap quiero aprender pseint         → Tutorial interactivo completo
```

El tutor responde con pseudocodigo paso a paso. El tutorial abre PSeInt y guia PDF con ejercicios asistidos por AI.

## Busqueda en Wikipedia

```bash
yap busca que es una variable en programacion
```

Obtiene contenido de Wikipedia, lo resume con el LLM local, y muestra la fuente. Sin conexion a internet requerida (el LLM corre local).

## Aplicaciones permitidas

```bash
yap abre firefox
yap abre thonny
yap abre geogebra
```

Las apps permitidas se configuran en `/etc/yap/whitelist/apps.conf`. Intentar abrir una app no listada muestra la lista de las disponibles.

La whitelist viene preconfigurada para un entorno escolar:

| Area | Aplicaciones |
|------|--------------|
| Ofimatica | LibreOffice, Evince |
| Navegacion | Firefox |
| Programacion | PSeInt, Thonny, Scratch |
| Ciencias y matematicas | Kalzium, Geogebra |
| Arte | Krita |
| Educacion infantil | GCompris |
| Sistema | Micro, Htop |

Una aplicacion solo se abre si ademas esta instalada en el equipo. Las entradas
admiten varios binarios separados por coma, porque el nombre cambia entre
versiones de Debian: `Firefox:firefox-esr,firefox`.

## Progreso

```bash
yap progreso
```

Muestra el avance por curso y EA: porcentaje completado, puntaje promedio, actividades reprobadas o saltadas, y nota (1.0-7.0).

El archivo de progreso esta en `~/.config/yap/progress.json`. Se guarda atomicamente (sin riesgo de corruption por corte de energia). Cada actividad evaluada guarda `puntaje`, `intentos` y `fecha_aprobacion`.

### Tipos de evaluacion en actividades

Cada actividad de una EA puede declarar:

| `tipo` | Como se evalua |
|--------|----------------|
| `respuesta_libre` | El LLM verifica los `criterios_evaluacion` |
| `codigo_pseint` | El LLM valida sintaxis PSeInt y la logica |
| `opcion_multiple` | Comparacion exacta con `respuesta_correcta` (sin LLM) |
| `completar` | El LLM valida si la respuesta completa lo pedido |

Campos: `criterios_evaluacion` (lista), `enunciado` (opcional), `opciones` y `respuesta_correcta` (requeridos en opcion multiple), `max_intentos` (opcional, default 3).

El evaluador responde JSON `{aprobado, puntaje, feedback, criterios_cumplidos, criterios_fallidos, sugerencia}`. Si el LLM devuelve texto plano, Yap lo interpreta igual.

## Sesiones

Una **sesion** agrupa el contexto de trabajo: el curso y la EA en curso, junto con los
turnos de conversacion con el tutor. Puede pausarse y reanudarse posteriormente
conservando dicho contexto.

### Comandos

| Comando | Descripcion |
|---------|-------------|
| `yap sesion` | Estado de la sesion activa y resumen de las pausadas. |
| `yap sesion nueva` | Inicia una sesion limpia (pausa la anterior si la hay). |
| `yap sesion pausar` | Pausa la sesion y guarda el contexto de conversacion. |
| `yap sesion retomar [ID]` | Retoma una sesion pausada. Sin ID, retoma la ultima. |
| `yap sesion cerrar` | Cierra la sesion y la archiva en el historial. |
| `yap sesion listar` | Lista todas las sesiones, incluidas las cerradas. |

El identificador se muestra en el prompt del modo interactivo:

```
Chinco [S1] > que es un ciclo mientras
```

### Flujo tipico

```bash
yap curso FPY1101        # abre una sesion asociada al curso automaticamente
yap iniciar EA1          # asocia la EA a la sesion activa
yap sesion pausar        # interrupcion: guarda el contexto y libera la sesion
yap sesion retomar       # reanudacion: restaura la conversacion previa
yap sesion cerrar        # cierre de la unidad: archiva en el historial
```

Al salir del modo interactivo con una sesion activa, Yap solicita confirmacion para
pausarla o cerrarla (`p/C`, cierra por defecto).

### Limites y almacenamiento

- Maximo **3 sesiones abiertas** simultaneamente (activas o pausadas). Configurable
  mediante la variable de entorno `YAP_MAX_SESSIONS`.
- Solo puede existir **una sesion activa**: abrir o retomar otra pausa la anterior.
- Las sesiones se almacenan en `~/.config/yap/sessions.json`, con escritura atomica.
- Al **cerrar** una sesion, su conversacion se traslada a `~/.config/yap/history.json`
  y queda disponible mediante `yap historial` y `yap historial --ultimo`. Las sesiones
  **pausadas no** se archivan hasta su cierre.

## Telemetria local

Yap lleva un registro de **cuantas veces** se usa cada funcion, para saber que
partes resultan utiles y cuales pasan desapercibidas.

### Que se registra, y que no

| Se registra | No se registra |
|-------------|----------------|
| Contadores por accion (`query: 7`, `curso: 3`) | El texto de tus consultas |
| Fecha del primer y ultimo uso | Los parametros de los comandos |
| Que funciones no has usado nunca | Nombres, rutas o cualquier dato personal |

**Nada se transmite.** El archivo vive en `~/.config/yap/telemetry.json` y no
existe ningun envio automatico. Compartirlo requiere una accion explicita tuya.

### Comandos

| Comando | Descripcion |
|---------|-------------|
| `yap telemetria` | Resumen de uso: mas usadas, nunca usadas y total. |
| `yap telemetria exportar` | Crea una copia anonima que puedes compartir. |
| `yap telemetria desactivar` | Deja de registrar uso. |
| `yap telemetria activar` | Vuelve a registrar. |
| `yap telemetria borrar` | Elimina los datos acumulados. |

### Exportacion

```bash
yap telemetria exportar
```

Genera `~/.config/yap/telemetry-export.json` con unicamente los contadores:

```json
{
  "version": 1,
  "comandos": { "curso": 3, "open_app": 1, "query": 7 },
  "total": 11,
  "sin_usar": ["search", "webfetch", "pseint"]
}
```

Sin fechas, sin rutas y sin identificadores. El archivo queda en tu equipo; si
decides enviarlo a los desarrolladores, lo haces tu manualmente.

### Desactivar la recoleccion

```bash
yap telemetria desactivar
```

Los contadores dejan de incrementarse de inmediato. Los datos previos se
conservan hasta que ejecutes `yap telemetria borrar`.

## Ramas de configuracion

| Rama | RAM | Modelo | Uso |
|------|-----|--------|-----|
| `main` | ~3GB | 3B Q4_K_M | Escritorio moderno |
| `lowmem` | ~1.8GB | 3B Q4_K_M reducido | PCs antiguos |
| `ultra-lowmem` | ~1.3GB | 1B Q4_K_M | Netbooks / Raspberry Pi |

```bash
git checkout lowmem
```

## Seguridad

- Sin `shell=True` en subprocess — imposible inyeccion de comandos.
- Whitelist de aplicaciones y dominios en `/etc/yap/whitelist/`.
- URLs de Wikipedia validadas contra `*.wikipedia.org`.
- Contenido limitado a 3000 caracteres.
- Timeout de 30s en subprocess.

## Solucion de problemas

| Problema | Solucion |
|----------|----------|
| `llama-cli: command not found` | El modelo no esta instalado. Corre `setup.sh` o descarga el GGUF manualmente. |
| Curso no encontrado | Verifica que el JSON este en `/etc/yap/cursos/`. |
| Progreso no se guarda | Verifica permisos de `~/.config/yap/`. |
| `[ERROR] No se pudo` | Verifica `MODEL_PATH` en `yap.py` (linea 30). |
| Clasificador lento | Usa comandos exactos (`curso`, `guia`, `progreso`, `ayuda`) para evitar el LLM. |

## Referencias

- [README completo](README.md)
- [Llama 3.2](https://ai.meta.com/blog/llama-3-2-connect-2024-vision-edge-mobile-devices/)
- [llama.cpp](https://github.com/ggerganov/llama.cpp)
