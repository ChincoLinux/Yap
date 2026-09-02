# Cómo conectar Yap (Linux) a Agent Platform

Esto se hace **en Linux** (ChincoLinux, Debian 13, o una VM). El alumno no
toca GCP. Tú clonas el repo, despliegas el agente y dejas el token en el
laboratorio.

Al terminar, `python3 yap.py nube` muestra `Motor: NUBE` y una consulta
sale a **Gemini 3.7 Flash** en Gemini Enterprise Agent Platform.

No uses PowerShell. Todo es `bash`.

---

## 0. Qué vas a montar

```
[PC Linux / ChincoLinux]
   yap.py  --HTTPS Bearer-->  Agent Platform (reasoningEngines:query)
                                   modelo: gemini-3.7-flash
                                   region: southamerica-west1
```

Yap habla solo. **No hace falta** `puerta_local.py` en Linux.

Si Agent Platform no responde, Yap cae al Llama local y escribe
`[WARN] Nube no disponible, usando LLM local.`

---

## 1. Checklist (no sigas si falta uno)

En una terminal Linux:

```bash
python3 --version          # 3.12 o 3.13
gcloud --version           # Google Cloud SDK
pwd                        # debes estar en la carpeta Yap
```

- [ ] Cuenta Google que puede crear proyectos.
- [ ] Facturación vinculada (sin esto Gemini da 403).
- [ ] Estás **dentro** del repo: `.../Yap`.

Si `gcloud` no existe:

```bash
# Debian / ChincoLinux
curl -fsSL https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud --version
```

**Listo cuando:** `python3 --version` y `gcloud --version` imprimen números.

---

## 2. Login y proyecto

```bash
gcloud auth login
gcloud auth application-default login
```

Se abre el navegador (o te da un enlace). Entras. Vuelves.

Crea el proyecto. El ID es tuyo, minúsculas, sin espacios:

```bash
gcloud projects create yap-nube-kirto --name="Yap Nube"
gcloud config set project yap-nube-kirto
gcloud config get-value project
```

El último comando **tiene que** imprimir `yap-nube-kirto`.

Facturación: https://console.cloud.google.com/billing/linkedaccount  
Selecciona el proyecto → vincula la cuenta.

**Listo cuando:** el proyecto aparece con billing linked.

---

## 3. Encender APIs y región

```bash
gcloud config set project yap-nube-kirto
gcloud services enable aiplatform.googleapis.com
gcloud services enable storage.googleapis.com
```

Región del piloto: Santiago.

```bash
export PROJECT_ID=yap-nube-kirto
export LOCATION=southamerica-west1
```

Si más adelante el modelo da 404, cambia a `us-central1` y **repite desde
este export**.

**Listo cuando:** los `gcloud services enable` terminan sin rojo.

---

## 4. Probar Gemini desde Linux (aún sin Yap)

```bash
TOKEN=$(gcloud auth print-access-token)
curl -sS -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  "https://${LOCATION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/publishers/google/models/gemini-3.7-flash:generateContent" \
  -d '{"contents":[{"role":"user","parts":[{"text":"Responde solo: hola desde yap"}]}]}'
```

| Resultado | Qué hacer |
|---|---|
| JSON con `"text": "hola desde yap"` | Sigue |
| 403 / billing | Paso 2, facturación |
| 404 model | `export LOCATION=us-central1` y reintenta este curl |
| 401 | `gcloud auth login` otra vez |

**Listo cuando:** Gemini te dijo hola. Si no, **no despliegues el agente**.

---

## 5. Subir el agente `yap_nube` a Agent Platform

Bucket (el nombre debe ser único en todo Google):

```bash
export STAGING_BUCKET=gs://yap-nube-kirto-staging
gcloud storage buckets create "$STAGING_BUCKET" \
  --project="$PROJECT_ID" --location="$LOCATION"
```

SDK **solo en tu máquina de operador**, no en el alumno:

```bash
python3 -m pip install --upgrade "google-cloud-aiplatform[agent_engines,adk]>=1.112"
```

Despliegue (varios minutos, no lo mates):

```bash
cd /ruta/al/repo/Yap
export PROJECT_ID=yap-nube-kirto
export LOCATION=southamerica-west1
export STAGING_BUCKET=gs://yap-nube-kirto-staging
python3 agent-platform/_deploy.py
```

Al final:

```text
RESOURCE: projects/yap-nube-kirto/locations/southamerica-west1/reasoningEngines/1234567890
```

Copia **solo el número** (`1234567890`). Ese es `ENGINE_ID`.
Guárdalo en un bloc de notas, **nunca** en git.

```bash
export ENGINE_ID=1234567890
```

**Listo cuando:** tienes un `ENGINE_ID` numérico.

---

## 6. Conectar Yap en Linux (el paso que importa)

Siempre en la **misma** terminal, porque los `export` se pierden al cerrarla.

```bash
cd /ruta/al/repo/Yap

export YAP_CLOUD_ENABLED=1
export YAP_CLOUD_BACKEND=agent_platform
export YAP_CLOUD_PROJECT="$PROJECT_ID"
export YAP_CLOUD_LOCATION="$LOCATION"
export YAP_CLOUD_ENGINE_ID="$ENGINE_ID"
export YAP_CLOUD_MODEL=gemini-3.7-flash
export YAP_CLOUD_TOKEN="$(gcloud auth print-access-token)"

python3 yap.py nube
```

Tienes que ver:

- `Motor: NUBE`
- `Backend: agent_platform`
- `Host: southamerica-west1-aiplatform.googleapis.com` (o `us-central1-...`)
- `Host permitido: si`
- `Token de flota: presente`

Consulta de verdad:

```bash
python3 yap.py nube explica la diferencia entre while y for en PSeInt
```

**Listo cuando:** imprime `Consultando agente en la nube (Gemini 3.7 Flash)...`
y **no** imprime `[WARN] Nube no disponible`.

Atajo del repo (hace los export y el status):

```bash
export PROJECT_ID=yap-nube-kirto
export ENGINE_ID=1234567890
chmod +x agent-platform/conectar-linux.sh
./agent-platform/conectar-linux.sh --query "explica while"
```

---

## 7. Dejarlo fijo en el Linux del laboratorio

No uses `gcloud auth login` en el PC del alumno.

1. Crea una **cuenta de servicio** de flota:

```bash
gcloud iam service-accounts create yap-infer \
  --display-name="Yap Agent Platform"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:yap-infer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

2. En **tu** PC de operador, mint un token de corta vida **o** deja un
   access token renovable. Lo simple para el piloto:

```bash
# En el Linux del lab, como root:
sudo mkdir -p /etc/yap
sudo chmod 755 /etc/yap
```

Copia `agent-platform/nube.env.example` a `/etc/yap/nube.env` y rellena
proyecto + ENGINE_ID.

El token **no** va en el example. En el lab:

```bash
# renovar el token (crontab del operador, no del alumno)
gcloud auth print-access-token | sudo tee /etc/yap/cloud-token >/dev/null
sudo chmod 600 /etc/yap/cloud-token
sudo chown root:root /etc/yap/cloud-token
```

3. Yap lee el archivo solo:

```bash
set -a
. /etc/yap/nube.env
set +a
python3 /usr/local/bin/yap nube
```

O, si arrancas Yap a mano en esa máquina:

```bash
export YAP_CLOUD_ENABLED=1
export YAP_CLOUD_BACKEND=agent_platform
export YAP_CLOUD_PROJECT=yap-nube-kirto
export YAP_CLOUD_LOCATION=southamerica-west1
export YAP_CLOUD_ENGINE_ID=1234567890
export YAP_CLOUD_TOKEN_FILE=/etc/yap/cloud-token
python3 yap.py
```

`Motor: NUBE` arriba. `abre firefox` sigue en local. Las consultas
`explica...` se van a Agent Platform.

---

## 8. Si falla

| Qué ves | Causa | Qué hacer |
|---|---|---|
| `Motor: LOCAL` | No exportaste `YAP_CLOUD_ENABLED=1` o cambiaste de terminal | Repite el bloque del paso 6 **entero** |
| `Engine: (falta YAP_CLOUD_ENGINE_ID)` | No pegaste el número del deploy | `export YAP_CLOUD_ENGINE_ID=...` |
| `Token de flota: ausente` | Token vacío o archivo ilegible | `echo $YAP_CLOUD_TOKEN` debe ser un chorro largo |
| `[WARN] Nube no disponible` | 401/403/404 de GCP | curl del paso 4; luego el ENGINE_ID |
| 404 model | Región sin Gemini 3.7 Flash | `export YAP_CLOUD_LOCATION=us-central1` |
| 401 | Token caducó (~1 h) | `export YAP_CLOUD_TOKEN=$(gcloud auth print-access-token)` |
| Responde el Llama 1B | El `[WARN]` está arriba | Lee la primera línea |
| `Host permitido: no` | Backend no es `agent_platform` | `export YAP_CLOUD_BACKEND=agent_platform` |

---

## 9. Qué no hagas

- No subas `/etc/yap/cloud-token` ni `nube.env` a git.
- No le pidas al alumno una cuenta Google Cloud.
- No apuntes Yap a `generativelanguage.googleapis.com` a mano: el backend
  `agent_platform` ya construye la URL de Agent Runtime.
- No uses la puerta `puerta_local.py` en Linux para este camino. Eso era
  un traductor de desarrollo. En Linux Yap habla Agent Platform directo.

---

## 10. Receta para pegar el próximo día (Linux)

```bash
cd /ruta/al/repo/Yap
export PROJECT_ID=yap-nube-kirto
export LOCATION=southamerica-west1
export ENGINE_ID=1234567890

export YAP_CLOUD_ENABLED=1
export YAP_CLOUD_BACKEND=agent_platform
export YAP_CLOUD_PROJECT=$PROJECT_ID
export YAP_CLOUD_LOCATION=$LOCATION
export YAP_CLOUD_ENGINE_ID=$ENGINE_ID
export YAP_CLOUD_TOKEN=$(gcloud auth print-access-token)

python3 yap.py nube explica while
```
