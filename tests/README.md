# Yap — Suite de Pruebas

Suite completa: **21 archivos, 825 pruebas**, sin LLM, sin GPU y sin Internet.
La unica dependencia externa es `pytest`.

```bash
python3 -m pip install pytest    # unica dependencia
python3 -m pytest tests/ -v      # 825 pruebas
```

---

## Estructura

```
tests/
├── conftest.py                 # Fixture que aisla Super Yap (fuerza YAP_SUPER_*=0)
├── run_tests.py                 # Ejecutor con etapas + reporte TXT
├── report/                      # Reportes generados con --report
├── test_yap_security.py        #  25  Whitelist, inyeccion, limites
├── test_yap_security_audit.py  #  27  Fuzzing: traversal, esquemas, unicode, JSON
├── test_yap_functional.py      #  59  Apps, webfetch, intents, PSeInt, TUI, cursos
├── test_yap_evaluacion.py      #  63  Evaluacion automatica de actividades (#23)
├── test_yap_super.py           #  58  Super Yap Gradio Cloud Run (#91)
├── test_yap_deb.py             #  34  Empaquetado .deb (#31)
├── test_yap_ejercicios.py      #  35  Catalogo de ejercicios PSeInt (#27)
├── test_yap_accesibilidad.py   #  90  Alto contraste, Orca, teclado (#37)
├── test_yap_sessions.py        #  75  Sesiones pausables y CRUD (#21)
├── test_yap_rag.py             #  61  RAG local BM25 offline (#118)
├── test_yap_perfil.py          #  61  Perfil del estudiante (#24)
├── test_yap_adaptive.py        #  45  Dificultad adaptativa (#30)
├── test_yap_telemetry.py       #  41  Telemetria local anonima (#38)
├── test_yap_feedback.py        #  32  Feedback pedagogico (#29)
├── test_yap_rutas_teclado.py   #  32  Rutas rapidas sin pasar por el LLM
├── test_yap_config_escolar.py  #  21  WhitelistsApps.conf / web.conf de aula
├── test_yap_confirmation.py    #  20  Confirmacion humana (#12)
├── test_yap_history.py         #  17  Historial persistente entre sesiones (#13)
├── test_yap_apparmor.py        #  17  Perfil AppArmor (#14)
├── test_yap_terminal.py        #   9  Ningun proceso hereda la terminal
├── test_yap_onboarding.py      #   3  Tutorial de bienvenida
└── README.md                   # Este archivo
```

Agrupadas por area, las 825 pruebas quedan asi: seguridad e inyeccion 52 ·
funcional, PSeInt y evaluacion 157 · empaquetado, aula y AppArmor 75 ·
perfil, RAG, sesiones y Super Yap 255 · accesibilidad, adaptacion y telemetria
176 · interaccion, feedback e historial 110.

---

## Ejecutores

Hay dos caminos y no son equivalentes:

| | `pytest tests/` | `python3 tests/run_tests.py` |
|---|---|---|
| Archivos | los 21 | los 5 de `ARCHIVOS_PYTEST` |
| Pruebas | 825 | 237 |
| Chequeos de infraestructura | no | si (5) |
| Chequeo estatico de `yap.py` | no | si (5) |
| Mapeo de 26 requisitos | no | si |
| Reporte TXT | no | con `--report` |
| Sirve para | desarrollo y CI | auditoria de entrega |

`run_tests.py` solo conoce los 5 archivos que estan en la constante
`ARCHIVOS_PYTEST` (los que cubren requisitos con ID propio). Los otros 16
cubren modulos sin requisito catalogado, asi que se ejecutan solo con pytest.

Las cifras no coinciden exactamente: `parse_pytest_output()` cuenta lineas con
`PASSED` y `FAILED`, asi que un test `SKIPPED` no suma. En los 5 archivos del
runner hay 2 skips (237 contados, 239 recogidos) y en la suite completa hay 2
tambien (825 recogidos).

---

## Ejecucion

```bash
# Suite completa, en terminal
python3 -m pytest tests/ -v

# Solo una area
python3 -m pytest tests/test_yap_security.py -v
python3 -m pytest tests/test_yap_rag.py -v

# Solo las pruebas que no dependen del sistema
python3 -m pytest tests/ -v --ignore=tests/test_yap_deb.py

# Un unico test
python3 -m pytest tests/test_yap_functional.py::TestOpenApp -v

# Runner: reporte en terminal
python3 tests/run_tests.py

# Runner: ademas guarda tests/report/report_<AAAAMMDD_HHMMSS>.txt
python3 tests/run_tests.py --report

# Runner: etiqueta el encabezado como "VM (con LLM)"
python3 tests/run_tests.py --vm --report
```

### Requisitos del runner

- **Python 3.12+**, stdlib-only. La unica dependencia externa es `pytest`.
- **No** necesita el modelo GGUF, ni `llama-cli`, ni GPU, ni Internet: la suite
  mockea `subprocess`, `urllib.request` y `shutil.which`.
- **No** necesita haber instalado Yap. Las 5 verificaciones de
  infraestructura (`/usr/local/bin/yap`, `llama-cli` en el PATH, el modelo en
  `MODEL_PATH`, `/etc/yap/whitelist/{apps,web}.conf`) son el termometro de la
  instalacion, y fallan por diseño en un host de desarrollo o en CI.
- **Timeout de 120 s por archivo** de pytest: el techo de la etapa 1 son
  10 minutos. Lo demas es instantaneo.
- `--vm` es cosmetico: cambia la etiqueta del encabezado. Las verificaciones de
  infraestructura se ejecutan siempre, con o sin la opcion.
- Codigo de salida `0` si no falla ninguna prueba ni chequeo estatico, `1` si
  falla alguna. El mapeo de requisitos **no** altera el codigo de salida: en un
  host sin Yap instalado `CFG-01..03` quedan en rojo sin que eso invalide un
  PR de codigo.

### Aislamiento de la nube

`conftest.py` define una fixture `autouse` que fija `YAP_SUPER_ENABLED=0` y
`YAP_SUPER_INTERNET=0` mientras la variable no este ya definida en el entorno.
Por eso ningun test habla con Cloud Run, aunque el repositorio este clones en
una maquina con la variable exportada.

---

## Cobertura de requisitos

Catalogo canonico: la constante `REQUISITOS` de `tests/run_tests.py`. El runner
imprime esas 26 entradas y avisa si algun ID queda sin evaluar.

| Familia | IDs | Significado |
|---|---|---|
| **SEG** | SEG-01 .. SEG-08 | Seguridad: whitelist, anti-inyeccion, limites |
| **FUN** | FUN-01 .. FUN-12 | Funcional: capacidades del agente |
| **SEC** | SEC-01 | Catalogo de ejercicios PSeInt |
| **CFG** | CFG-01 .. CFG-03 | Instalacion en el sistema |
| **PKG** | PKG-01, PKG-02 | Empaquetado .deb (#31) |

| ID | Requisito | Donde se cubre |
|---|---|---|
| SEG-01 | Whitelist de aplicaciones | `TestAppWhitelist` |
| SEG-02 | Whitelist de dominios | `TestDomainWhitelist` |
| SEG-03 | Sin `shell=True`, `eval()`, `os.system()` | `TestCommandSecurity`, `TestCodeQuality` |
| SEG-04 | Bloqueo graceful con alternativas | `test_app_bloqueada_muestra_alternativas`, `test_dominio_bloqueado_mensaje_graceful` |
| SEG-05 | Validacion estricta de dominios | `test_notwikipedia_no_coincide` |
| SEG-06 | Sin escritura arbitraria | `TestFileSystemSecurity` |
| SEG-07 | Timeout en subprocess | `test_timeout_en_subprocess` |
| SEG-08 | webfetch limitado a 3000 chars | `test_contenido_limitado_3000_chars` |
| FUN-01 | Apertura de apps multi-binario | `TestOpenApp` |
| FUN-02 | Webfetch con limpieza de HTML | `TestWebfetch` |
| FUN-03 | Busqueda en Wikipedia (API REST) | `test_classify_search` |
| FUN-04 | Consulta directa al LLM | `TestQuery` |
| FUN-05 | Clasificacion de intenciones | `TestIntentClassification` |
| FUN-06 | Historial de conversacion (6 turnos) | `TestHistory` |
| FUN-07 | Notificaciones `notify-send` | `TestNotifications` |
| FUN-08 | Modo interactivo y modo comando | `TestArchitecture` |
| FUN-09 | Tutor PSeInt paso a paso | `TestPSeIntTutor` |
| FUN-10 | Tutorial interactivo PSeInt | `TestIntroduccionPSeInt` |
| FUN-11 | Evaluacion automatica (#23) | `test_yap_evaluacion.py` (63) |
| FUN-12 | Super Yap Gradio Cloud Run (#91) | `test_yap_super.py` (58) |
| SEC-01 | Parser de ejercicios v1/v2, tipos, pistas | `test_yap_ejercicios.py` (35) |
| CFG-01 | Archivos de configuracion validos | `TestRealConfig` + `check_whitelist_files()` |
| CFG-02 | Symlink al repositorio | `check_symlink()` |
| CFG-03 | `llama-cli` instalado | `check_llama_cli()` |
| PKG-01 | Plantillas DEBIAN y `build-deb.sh` | `TestYapDebianTemplates`, `TestBuildDebScript` |
| PKG-02 | Paquetes de modelo 1B / 3B | `TestModelPackages` |

### Requisitos sin ID propio

Estos modulos se prueban, pero no estan en el catalogo porque no son
requisitos de entrega. Si anades uno, agregalo a `REQUISITOS` **y** al mapa de
`main()`; el runner avisa si se queda solo de un lado.

| Modulo | ID sugerido | Archivo |
|---|---|---|
| RAG local BM25 (#118) | RAG-01 | `test_yap_rag.py` |
| Sesiones (#21) | FUN-13 | `test_yap_sessions.py` |
| Perfil del estudiante (#24) | FUN-14 | `test_yap_perfil.py` |
| Accesibilidad (#37) | FUN-15 | `test_yap_accesibilidad.py` |
| Dificultad adaptativa (#30) | FUN-16 | `test_yap_adaptive.py` |
| Telemetria local (#38) | FUN-17 | `test_yap_telemetry.py` |
| Feedback pedagogico (#29) | FUN-18 | `test_yap_feedback.py` |
| Historial entre sesiones (#13) | FUN-19 | `test_yap_history.py` |
| Confirmacion humana (#12) | SEG-09 | `test_yap_confirmation.py` |
| AppArmor (#14) | PKG-03 | `test_yap_apparmor.py` |
| Fuzzing de entrada | SEG-10 | `test_yap_security_audit.py` |
| Aislamiento de terminal | SEG-11 | `test_yap_terminal.py` |

---

## Mecanismo de pruebas

Ninguna prueba habla con el sistema real:

```
subprocess.run      → mock (stdout/stderr predefinidos)
urllib.request      → mock (HTML de prueba)
shutil.which        → mock (rutas falsas)
```

Ademas hay pruebas que escanean el **codigo fuente** de `yap.py` en busca de
patrones prohibidos (`shell=True`, `eval(`, `os.system(`, `os.remove`,
`shutil.rmtree`, imports de `socket`/`ctypes`/`pickle`/`base64`). Un comentario
o una cadena de texto que contenga el patron puede disparar un falso positivo:
verifica siempre que el match este en codigo ejecutable y no en texto.
