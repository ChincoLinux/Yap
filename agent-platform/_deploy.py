#!/usr/bin/env python3
"""Sube yap_nube a Gemini Enterprise Agent Platform.

Requiere:
  set PROJECT_ID=tu-proyecto
  set LOCATION=southamerica-west1
  set STAGING_BUCKET=gs://tu-bucket
  pip install "google-cloud-aiplatform[agent_engines,adk]>=1.112"
  gcloud auth application-default login
"""

import os
import sys

PROJECT = os.environ.get("PROJECT_ID", "").strip()
LOCATION = os.environ.get("LOCATION", "southamerica-west1").strip()
BUCKET = os.environ.get("STAGING_BUCKET", "").strip()

if not PROJECT or not BUCKET:
    sys.exit("Faltan PROJECT_ID y/o STAGING_BUCKET")
if not BUCKET.startswith("gs://"):
    sys.exit("STAGING_BUCKET debe empezar con gs://")

try:
    from google.adk.agents import Agent
    import vertexai
    from vertexai.agent_engines import AdkApp
except ImportError:
    sys.exit(
        'Instala el SDK:\n'
        '  python -m pip install --upgrade "google-cloud-aiplatform[agent_engines,adk]>=1.112"'
    )

client = vertexai.Client(project=PROJECT, location=LOCATION)

agent = Agent(
    model="gemini-3.7-flash",
    name="yap_nube",
    instruction=(
        "Eres Yap Nube, tutor educativo de ChincoLinux en espanol. "
        "Responde claro y breve. No pidas datos personales. "
        "No ejecutes comandos ni abras aplicaciones. "
        "La nube sugiere; el kernel local decide."
    ),
)
app = AdkApp(agent=agent)

print("Desplegando yap_nube en", PROJECT, LOCATION, "...")
remote = client.agent_engines.create(
    agent=app,
    config={
        "display_name": "yap-nube",
        "requirements": ["google-cloud-aiplatform[agent_engines,adk]"],
        "staging_bucket": BUCKET,
    },
)
name = getattr(getattr(remote, "api_resource", None), "name", None) or str(remote)
print()
print("RESOURCE:", name)
print()
print("Copia el ultimo numero (ENGINE_ID) y usalo asi:")
print("  set ENGINE_ID=ESE_NUMERO")
print("  set YAP_PUERTA_MODE=agent")
