# Yap — Delegación a Gemini 3.7 Flash (Agent Platform)

**¿Quieres conectarlo desde Linux a Agent Platform?** sigue
[CONECTAR-GCP.md](CONECTAR-GCP.md) (bash, paso a paso).

El resto de este archivo es el contrato técnico.

El aula no depende de la nube. El LLM local (Llama 3.2 + llama.cpp) es el
camino por defecto. Gemini 3.7 Flash en Gemini Enterprise Agent Platform
es un acelerador opt-in que despliegan quienes clonan este repositorio.

El alumno no necesita cuenta de Google Cloud.

## Contrato local → nube

`yap.py` clasifica la intención **en local**. Solo las consultas complejas
(`cloud_query`) se reenvían, si el despliegue lo habilitó.

POST JSON (HTTPS, sin timeout) al endpoint privado del laboratorio:

```json
{
  "intent": "query",
  "model": "gemini-3.7-flash",
  "prompt": "explica la diferencia entre while y for",
  "message": "explica la diferencia entre while y for",
  "curso": "FPY1101",
  "ea": "EA1",
  "historial": [{"rol": "user", "texto": "..."}],
  "request_id": "yap-1710000000000"
}
```

Respuesta esperada:

```json
{"texto": "...", "modelo": "gemini-3.7-flash", "uso": {"prompt": 10, "respuesta": 20, "total": 30}}
```

También se aceptan formas de Agent Platform / Gemini (`content.parts`,
`candidates`). Si el POST falla o el host no es privado, Yap usa el LLM
local y muestra `[WARN] Nube no disponible, usando LLM local.`

## Variables de entorno (imagen del laboratorio)

| Variable | Default | Rol |
|---|---|---|
| `YAP_CLOUD_ENABLED` | off | `1` / `true` / `si` para activar |
| `YAP_CLOUD_BACKEND` | `contract` | `agent_platform` (Linux → Agent Runtime), `generate` (Gemini directo), `contract` (PSC `10.40.0.10`) |
| `YAP_CLOUD_PROJECT` | (vacío) | Proyecto GCP |
| `YAP_CLOUD_LOCATION` | `southamerica-west1` | Región |
| `YAP_CLOUD_ENGINE_ID` | (vacío) | ID del reasoningEngine (Fase B) |
| `YAP_CLOUD_ENDPOINT` | (auto) | Si se omite, `agent_platform` arma la URL de `*:query` |
| `YAP_CLOUD_MODEL` | `gemini-3.7-flash` | Modelo invocado |
| `YAP_CLOUD_TOKEN` | (vacío) | Bearer (`gcloud auth print-access-token`) |
| `YAP_CLOUD_TOKEN_FILE` | `/etc/yap/cloud-token` | Alternativa a la env |
| `YAP_CLOUD_CIDR` | `10.40.0.0/16` | Red privada permitida (modo `contract`) |
| `YAP_CLOUD_HOSTS` | (vacío) | Extra. Con `agent_platform` se permite `*-aiplatform.googleapis.com` |
| `YAP_CLOUD_TLS_INSECURE` | off | Solo laboratorio con cert interno |

Sin `YAP_CLOUD_ENABLED=1` el comportamiento es 100 % local.

El token lo inyecta el despliegue (root-only). No va en el repo ni en
`~/.config/yap/` del estudiante.

## Comandos

```
yap nube                 # estado LOCAL / NUBE / DEGRADADO (sin secretos)
yap nube <pregunta>      # forzar Gemini 3.7 Flash; fallback local si cae
```

Las consultas largas o de razonamiento (`explica`, `genera`, `rúbrica`…)
se delegan solas cuando la nube está configurada.

## Agent Platform

El agente ADK vive en `agent-platform/yap_nube/`:

- Modelo: `gemini-3.7-flash`
- Runtime: Gemini Enterprise Agent Platform (evolución de Vertex AI)
- Región recomendada: `southamerica-west1`

Quienes clonan el repo despliegan ese agente detrás de Private Service
Connect (`10.40.0.10`) y Cloud VPN. Ver el informe de arquitectura GCP
del piloto. El PC ChincoLinux solo enruta `10.40.0.0/16` por el gateway
del aula; fuera del campus no hay túnel y Yap sigue en LOCAL.
