# Rendimiento de Yap / Performance

**Estado:** metodología y harness listos; **faltan las mediciones en hardware
real** (issue #40). Ejecutar `tests/benchmark.py` en cada perfil y pegar los
números en la tabla de abajo.

## Cómo medir

```bash
# 1. Instalación real (el .deb o setup.sh), con modelo 1B o 3B en /opt/yap/models
# 2. Desde la máquina del perfil que corresponde:
python3 tests/benchmark.py --quick            # primera pasada (~1 min)
python3 tests/benchmark.py                    # 5 repeticiones por escenario
python3 tests/benchmark.py --json res.json    # resultado para adjuntar

# Sin llama-cli o sin modelo el script sale con código 2 y no inventa datos.
```

Qué mide:

| Métrica | Qué es |
|---|---|
| **Frío** | Primera inferencia con proceso nuevo (sin caché) |
| **Caliente** | Mediana de N corridas de una consulta de chat (`-n 64`) |
| **Comando corto** | Latencia del clasificador (`-n 15`), que corre en cada tecla |
| **tok/s** | Tokens generados por segundo (mediana) |
| **RSS** | Memoria pico del hijo, vía `resource`/`/proc` |

## Perfiles de hardware objetivo

| Perfil | CPU | RAM | Modelo | Resultados |
|---|---|---|---|---|
| Bajo (aula) | Celeron N4000 | 4 GB | Llama 3.2 1B Q4_K_M | ⏳ pendiente |
| Medio | i3-8130U | 8 GB | Llama 3.2 3B Q4_K_M | ⏳ pendiente |
| Alto | i5-10210U | 16 GB | Llama 3.2 3B Q4_K_M | ⏳ pendiente |

Rellenar cada fila con el resumen que imprime `tests/benchmark.py` (frío,
mediana caliente, tok/s) y adjuntar el JSON. Si una máquina no está disponible,
dejar `⏳` — no se inventan números.

## Recomendaciones de modelo (a completar con las mediciones)

- **4 GB RAM / Celeron:** modelo 1B, `--ctx-size` bajo, ramas `lowmem`/`ultra-lowmem`.
- **8 GB RAM:** 3B con contexto moderado.
- **16 GB RAM:** 3B con contexto amplio.

Estas recomendaciones son las reglas actuales del proyecto (`README.md`,
sección *Rama lowmem*); se contrastan con las mediciones de la tabla.

## Criterios de aceptación de #40

- [x] Script `tests/benchmark.py` (stdlib, sin dependencias, sale con código 2
      si no hay modelo o `llama-cli`).
- [ ] Resultados en los 3 perfiles de hardware.
- [x] Esta tabla y metodología en `docs/PERFORMANCE.md`.
- [x] Recomendaciones de modelo según hardware.
