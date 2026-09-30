# Super Yap — Gradio en Cloud Run (#91)

El alumno sigue usando **Yap local** (Llama 3.2 1B/3B, CPU). Super Yap **no
corre un Llama 8B local** ni hiperparámetros de `llama.cpp` en el PC del
aula. El modelo grande vive en **Google Cloud Run** (Gradio 5 `/chat`).

Si hay **internet** (el host Gradio pin responde), Yap consulta esa nube
y reenvía el historial. Sin red, usa el Llama local (techo 3B). También
va a la nube si `llama-cli` tarda 3 minutos, se pasa de tokens o el
usuario escribe `super` / `nube`. Abrir apps, Wikipedia y webfetch nunca
salen del kernel local.

## Por qué no hay 8B local

Llama 3.2 Instruct en texto solo existe en **1B y 3B**. Un 8B Q4_K_M pedía
~7 GB libres y un segundo proceso (`super_yap.py`). Eso se retiró: el PC
del alumno no carga hiperparámetros de Super Yap (`YAP_SUPER_CTX`,
`YAP_SUPER_THREADS`, GGUF 8B, umbral de 7 GB).

| Perfil | Modelo | Dónde |
|---|---|---|
| Yap local (`ultra-lowmem`) | Llama 3.2 1B | PC del alumno |
| Yap local (`main`) | Llama 3.2 3B | PC del alumno |
| **Super Yap** | Gradio Cloud Run | Google Cloud (`southamerica-west1`) |

## Contrato local → Gradio (sin perder contexto)

`yap.py` clasifica la intención **en local**. En modo `auto`, si hay
internet usa Gradio; si no, el 1B/3B. Si `llama-cli` supera **180 s**,
también hace el protocolo Gradio 5 y **append** del turno a `HISTORY`.

`super on` manda todas las consultas a la nube. `super <pregunta>` fuerza
una. Si Gradio falla, se usa el LLM local y se muestra
`[WARN] Super Yap no disponible, usando LLM local.`

## Arranque

En el PC del alumno no hace falta un servidor 8B:

```bash
python3 yap.py super                 # estado (Gradio Cloud Run)
python3 yap.py super on              # todas las consultas a Super Yap
python3 yap.py super off             # vuelve al local (auto: 3 min / tokens)
python3 yap.py super explica la diferencia entre while y for
```

Endpoint por defecto: hostname pin Gradio en `yap.py`.
`YAP_SUPER_ENABLED=0` fuerza el Yap local. `YAP_SUPER_ENABLED=1` activa
aunque el endpoint no sea el pin Gradio (sigue exigiendo host permitido).

## Variables

| Variable | Default | Rol |
|---|---|---|
| `YAP_SUPER_ENABLED` | auto | `1` fuerza on; `0` fuerza local. Vacío: on si el host es Gradio Cloud Run |
| `YAP_SUPER_ENDPOINT` | Gradio Cloud Run | Loopback, LAN, IP `137.184.146.113` o hostname Gradio pin |
| `YAP_SUPER_HOSTS` | (vacío) | Hostnames extra del aula (coincidencia exacta, sin DNS) |
| `YAP_SUPER_TOKEN` | (clave Gradio) | `?key=` en Gradio; Bearer en `/v1/query`. Obligatorio si el endpoint no es loopback/pin |
| `YAP_SUPER_TOKEN_FILE` | `/etc/yap/super-token` | Alternativa al env |
| `YAP_SUPER_TIMEOUT` | `90` | Segundos del POST JSON; SSE Gradio usa ≥180 s |
| `YAP_LLAMA_TIMEOUT` | `180` | Timeout del llama-cli local. A los 3 min se consulta Gradio |
| `YAP_SUPER_INTERNET` | auto | `1` asume red; `0` fuerza local. Vacío: GET corto al host Gradio |

El token no va en el repo ni en `~/.config/yap/` del estudiante.

## Comandos

```
yap super                 # estado LOCAL / SUPER / DEGRADADO (sin secretos)
yap super on              # menú: todas las consultas a Super Yap
yap super off             # menú: volver al Yap local (auto)
yap super <pregunta>      # forzar Super Yap; fallback local si cae
yap nube                  # alias de super
```

## Protocolo Gradio (Cloud Run)

`GET /` no es JSON: la web del agente devuelve HTML de Gradio 5
(`window.gradio_config` / `window.gradio_api_info`). El chat público es
`/chat`.

1. `GET /?key=…` — lee `root`, `api_prefix` y el `fn_index` de `"api_name": "chat"`.
2. `POST {api_prefix}/queue/join` con
   `data: [{text, files: []}, historial]` y `session_hash`.
3. `GET {api_prefix}/queue/data?session_hash=…` (SSE `process_completed`).

Cliente en `yap.py` con `urllib` + `http.cookiejar` (stdlib, cookies de
sesión como `requests.Session`). No hay `requests`. Timeouts: HTML/join
30 s, SSE 180 s. El contrato JSON `/v1/query` se usa si el endpoint no es
el hostname Gradio.

## Seguridad

- `yap.py` no importa `socket`. El cliente usa `urllib.request` como webfetch.
- Hosts públicos (`8.8.8.8`, `googleapis.com`) están bloqueados.
  Excepciones pin: hostname Gradio Cloud Run y `137.184.146.113`.
  No se permite `*.run.app` genérico.
- Super Yap **sugiere**; no abre apps ni ejecuta comandos.
- Rutas `/home/...` y correos se sustituyen antes de salir del PC del alumno.
