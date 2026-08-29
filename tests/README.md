# Yap — Suite de Pruebas

## Estructura

```
tests/
├── test_yap_security.py     # 25 pruebas de seguridad y configuracion
├── test_yap_functional.py   # 32 pruebas funcionales
├── test_yap_evaluacion.py   # Evaluacion automatica de actividades (#23)
├── test_yap_ejercicios.py   # ejercicios interactivos (#27)
├── run_tests.py             # Ejecutor con reporte integrado
├── report/                  # Reportes generados (--report)
└── README.md                # Este archivo
```

## Ejecucion

```bash
# Todas las pruebas (modo host, sin LLM)
python3 -m pytest tests/ -v

# Solo seguridad
python3 -m pytest tests/test_yap_security.py -v

# Solo funcionales
python3 -m pytest tests/test_yap_functional.py -v

# Suite completa con reporte
python3 tests/run_tests.py --report

# Modo VM (incluye verificaciones de infraestructura)
python3 tests/run_tests.py --vm --report
```

## Cobertura de requisitos

| ID | Requisito | Pruebas |
|---|---|---|
| SEG-01 | Whitelist de aplicaciones | `TestAppWhitelist` |
| SEG-02 | Whitelist de dominios | `TestDomainWhitelist` |
| SEG-03 | Sin shell=True, eval(), os.system() | `TestCommandSecurity`, `TestCodeQuality` |
| SEG-04 | Graceful blocking con alternativas | `test_app_bloqueada_muestra_alternativas`, `test_dominio_bloqueado_mensaje_graceful` |
| SEG-05 | Validacion estricta de dominios | `test_notwikipedia_no_coincide` |
| SEG-06 | Sin escritura arbitraria | `TestFileSystemSecurity` |
| SEG-07 | Timeout en subprocess | `test_timeout_en_subprocess` |
| SEG-08 | Limite de chars en webfetch | `test_contenido_limitado_3000_chars` |
| FUN-01 | Apertura de apps multi-binario | `TestOpenApp` |
| FUN-02 | Webfetch con limpieza HTML | `TestWebfetch` |
| FUN-03 | Busqueda Wikipedia API REST | `test_classify_search` |
| FUN-04 | Consulta directa LLM | `TestQuery` |
| FUN-05 | Clasificacion de intenciones | `TestIntentClassification` |
| FUN-06 | Historial de conversacion | `TestHistory` |
| FUN-07 | Notificaciones notify-send | `TestNotifications` |
| FUN-08 | Modo interactivo y comando | `TestArchitecture` |
| FUN-09 | Tutor PSeInt paso a paso | `TestPSeIntTutor` |
| FUN-10 | Tutorial interactivo PSeInt | `TestIntroduccionPSeInt` |
| FUN-11 | Evaluacion automatica de actividades (#23) | `test_yap_evaluacion.py` |
| SEC-01 | Carga de ejercicios PSeInt | `TestPSeIntConfig` |
| FUN-11 | Ejercicios interactivos con validacion (#27) | `test_yap_ejercicios.py` |
| CFG-01 | Archivos de configuracion validos | `TestRealConfig` |
| CFG-02 | Symlink al repositorio | `run_tests.py` (infraestructura) |
| CFG-03 | llama-cli instalado | `run_tests.py` (infraestructura) |
