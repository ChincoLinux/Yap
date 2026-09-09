# Super Yap — modelo grande en el aula (#91)

El alumno sigue usando **Yap local** (Llama 3.2 1B/3B, CPU, sin Internet).
Super Yap es un segundo proceso, en un PC o servidor del laboratorio con
**8 GB de RAM**, que responde las consultas largas sin borrar el historial
del Yap local.

## Por qué Llama 3.1 8B (y no Llama 3.2 8B)

Llama 3.2 Instruct en texto solo existe en **1B y 3B**. El siguiente tamaño
de la misma familia (misma plantilla `<|begin_of_text|>` /
`<|start_header_id|>`) es **Llama 3.1 8B Instruct**.

| Perfil | Modelo | Pesos Q4_K_M | Contexto | RAM total est. |
|---|---|---|---|---|
| Yap local (`ultra-lowmem`) | Llama 3.2 1B | ~0.8 GB | 2048 | ~1.8 GB |
| Yap local (`main`) | Llama 3.2 3B | ~1.9 GB | 4096 | ~3.5 GB |
| **Super Yap** | **Llama 3.1 8B Instruct Q4_K_M** | ~4.9 GB | 4096, KV Q8_0 | **~6.5–7.5 GB** |

Cabe en un host de 8 GB dejando margen para el sistema. Si el GGUF 8B no
está, Super Yap cae al Llama 3.2 3B ya instalado.

## Umbral de RAM (7 GB libres)

Super Yap **no se usa** si el host del 8B tiene menos de **7000 MB libres**:

- `python3 super_yap.py --serve` / REPL / una pregunta: miden `MemAvailable`
  (Linux) o la RAM física libre (Windows). Por debajo de 7 GB, no cargan el
  8B y salen con error.
- `yap.py` en **loopback** (este PC es el host Super Yap): si hay menos de
  7 GB libres, no delega y sigue con el LLM local 1B/3B, con un `[WARN]`.
- Si Super Yap está en **otro PC del aula** (10.x / 192.168.x), el alumno
  no necesita 7 GB: el umbral se aplica en el servidor.

`yap super` muestra la RAM libre y si se llega al umbral. Forzar (laboratorio):
`YAP_SUPER_FORCE=1`. Tests/CI: `YAP_SUPER_RAM_MB=8192`.

## Contrato local → Super Yap (sin perder contexto)

`yap.py` clasifica la intención **en local**. Solo `query` complejas (o
`super <pregunta>`) se reenvían. Cada POST lleva el historial vivo:

```json
{
  "intent": "query",
  "prompt": "ahora dame un ejemplo en PSeInt",
  "historial": [
    {"rol": "user", "texto": "que es un ciclo mientras"},
    {"rol": "assistant", "texto": "Un mientras repite mientras la condicion sea verdadera."}
  ],
  "session_id": "S3",
  "request_id": "yap-20260908T120000"
}
```

Respuesta:

```json
{"texto": "Algoritmo Ejemplo...", "modelo": "Llama-3.1-8B-Instruct-Q4_K_M", "session_id": "S3"}
```

Después del POST, Yap local **append** del turno a `HISTORY`. La siguiente
pregunta local o a Super Yap sigue el mismo hilo. Super Yap, además, guarda
hasta 12 turnos por `session_id` (el local solo retiene 6): si el payload
es un sufijo de la sesión del servidor, se conserva el prefijo antiguo.

Si el POST falla o el host no es privado, Yap usa el LLM local y muestra
`[WARN] Super Yap no disponible, usando LLM local.`

## Arranque

En el PC de 8 GB (laboratorio):

```bash
# Modelo 8B (una vez). Espejo Hugging Face / hf-mirror, mismo patrón que setup.sh.
sudo mkdir -p /opt/yap/models
curl -fL "https://huggingface.co/bartowski/Llama-3.1-8B-Instruct-GGUF/resolve/main/Llama-3.1-8B-Instruct-Q4_K_M.gguf?download=true" \
  -o /opt/yap/models/Llama-3.1-8B-Instruct-Q4_K_M.gguf

python3 super_yap.py --info
python3 super_yap.py --serve
```

En el PC del alumno Super Yap se **activa solo** si hay **≥7 GB libres** y el
destino es el host nube `137.184.146.113` (puerto HTTP **8742**):

```bash
python3 yap.py super
python3 yap.py super explica la diferencia entre while y for
```

Endpoint por defecto: `http://137.184.146.113:8742/v1/query`.
`YAP_SUPER_ENABLED=0` fuerza el Yap local. `YAP_SUPER_ENABLED=1` activa
aunque el PC del alumno no tenga 7 GB (el 8B vive en ese host).

Opcional: dejar `llama-server` con el 8B cargado y apuntar Super Yap a él
para no recargar el GGUF en cada consulta:

```bash
llama-server -m /opt/yap/models/Llama-3.1-8B-Instruct-Q4_K_M.gguf \
  --host 127.0.0.1 --port 8743 --ctx-size 4096 \
  --cache-type-k q8_0 --cache-type-v q8_0 --threads 4
export YAP_SUPER_LLAMA_SERVER=http://127.0.0.1:8743/completion
python3 super_yap.py --serve
```

## Variables

| Variable | Default | Rol |
|---|---|---|
| `YAP_SUPER_ENABLED` | auto | `1` fuerza on; `0` fuerza local. Vacío: on si ≥7 GB libres **y** host `137.184.146.113` |
| `YAP_SUPER_ENDPOINT` | `http://137.184.146.113:8742/v1/query` | Loopback, LAN privada o el host nube pin |
| `YAP_SUPER_HOSTS` | (vacío) | Hostnames extra del aula (coincidencia exacta, sin DNS) |
| `YAP_SUPER_TOKEN` | (vacío) | Bearer. Obligatorio si el endpoint no es loopback |
| `YAP_SUPER_TOKEN_FILE` | `/etc/yap/super-token` | Alternativa al env |
| `YAP_SUPER_TIMEOUT` | `90` | Segundos del POST |
| `YAP_SUPER_MODEL_PATH` | (auto) | GGUF 8B, o 3B si el 8B no está |
| `YAP_SUPER_BIND` | `127.0.0.1` | Loopback, LAN o `137.184.146.113`. Nunca `0.0.0.0` |
| `YAP_SUPER_PORT` | `8742` | Puerto del contrato Yap |
| `YAP_SUPER_CTX` | `4096` | Contexto del 8B |
| `YAP_SUPER_THREADS` | `4` | Hilos CPU |
| `YAP_SUPER_LLAMA_SERVER` | (vacío) | URL `/completion` si el modelo ya está en RAM |
| `YAP_SUPER_RAM_MB` | (auto) | Override de MB libres (tests). Si se omite, se mide el sistema |
| `YAP_SUPER_FORCE` | off | `1` omite el umbral de 7 GB libres |

El token no va en el repo ni en `~/.config/yap/` del estudiante.

## Comandos

```
yap super                 # estado LOCAL / SUPER / DEGRADADO (sin secretos)
yap super <pregunta>      # forzar Super Yap; fallback local si cae
yap nube                  # alias de super
```

Las consultas largas o de razonamiento (`explica`, `diferencia`, `rúbrica`…)
se delegan solas cuando Super Yap está configurado. Abrir apps, Wikipedia y
webfetch **nunca** salen del kernel local.

## Seguridad

- `yap.py` no importa `socket`. El cliente usa `urllib.request` como webfetch.
- Hosts públicos (`8.8.8.8`, `googleapis.com`) están bloqueados.
  Única excepción pin: `137.184.146.113` (Super Yap en la nube).
- Super Yap solo escucha en `127.0.0.1` o una IP RFC1918.
- Super Yap **sugiere**; no abre apps ni ejecuta comandos.
- Rutas `/home/...` y correos se sustituyen antes de salir del PC del alumno.
