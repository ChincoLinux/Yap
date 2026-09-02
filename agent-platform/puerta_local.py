#!/usr/bin/env python3
"""Puerta local Yap <-> GCP.

Yap habla un JSON propio. GCP habla generateContent o Agent Runtime.
Esta puerta traduce. Solo para tu PC de desarrollo, no para el aula.

Uso:
  set PROJECT_ID=tu-proyecto
  set LOCATION=southamerica-west1
  python agent-platform/puerta_local.py
"""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROJECT = os.environ.get("PROJECT_ID", "").strip()
LOCATION = os.environ.get("LOCATION", "southamerica-west1").strip()
ENGINE_ID = os.environ.get("ENGINE_ID", "").strip()
MODE = os.environ.get("YAP_PUERTA_MODE", "generate").strip().lower()  # generate | agent
PORT = int(os.environ.get("YAP_PUERTA_PORT", "8787"))
MODEL = os.environ.get("YAP_CLOUD_MODEL", "gemini-3.7-flash").strip()

SYSTEM = (
    "Eres Yap Nube, tutor educativo de ChincoLinux en espanol. "
    "Responde claro y breve. No pidas datos personales. "
    "No ejecutes comandos ni abras aplicaciones."
)


def _token():
    env = os.environ.get("YAP_CLOUD_TOKEN", "").strip()
    if env:
        return env
    try:
        out = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as err:
        raise RuntimeError("No pude obtener token. Instala gcloud y corre: gcloud auth login") from err
    token = (out.stdout or "").strip()
    if out.returncode != 0 or not token:
        err = (out.stderr or out.stdout or "gcloud auth print-access-token fallo").strip()
        raise RuntimeError(err)
    return token


def _post_gcp(url, payload):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + _token(),
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _texto_de_gemini(data):
    if not isinstance(data, dict):
        return ""
    cands = data.get("candidates") or []
    if cands:
        parts = (((cands[0] or {}).get("content") or {}).get("parts") or [])
        texts = [p.get("text") for p in parts if isinstance(p, dict) and p.get("text")]
        if texts:
            return "\n".join(texts).strip()
    for key in ("texto", "text", "output"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _llamar_generate(prompt):
    if not PROJECT:
        raise RuntimeError("Falta PROJECT_ID. Ejemplo: set PROJECT_ID=mi-proyecto")
    url = (
        f"https://{LOCATION}-aiplatform.googleapis.com/v1/"
        f"projects/{PROJECT}/locations/{LOCATION}/publishers/google/models/{MODEL}:generateContent"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048},
    }
    data = _post_gcp(url, payload)
    texto = _texto_de_gemini(data)
    if not texto:
        raise RuntimeError("Gemini no devolvio texto. Respuesta: " + json.dumps(data)[:500])
    return texto


def _llamar_agente(prompt, user_id="yap-local"):
    if not PROJECT or not ENGINE_ID:
        raise RuntimeError("Faltan PROJECT_ID y ENGINE_ID para el modo agent")
    url = (
        f"https://{LOCATION}-aiplatform.googleapis.com/v1/"
        f"projects/{PROJECT}/locations/{LOCATION}/reasoningEngines/{ENGINE_ID}:query"
    )
    payload = {
        "class_method": "async_stream_query",
        "input": {"user_id": user_id, "message": prompt},
    }
    try:
        data = _post_gcp(url, payload)
    except urllib.error.HTTPError:
        payload["class_method"] = "query"
        payload["input"] = {"input": prompt}
        data = _post_gcp(url, payload)
    texto = _texto_de_gemini(data)
    if not texto and isinstance(data, dict):
        texto = json.dumps(data, ensure_ascii=False)[:2000]
    return texto or "(sin texto del agente)"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[puerta] " + (fmt % args) + "\n")

    def _send(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or "0")
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"texto": "", "error": "JSON invalido"})
            return
        prompt = (body.get("prompt") or body.get("message") or "").strip()
        if not prompt:
            self._send(400, {"texto": "", "error": "Falta prompt"})
            return
        try:
            if MODE == "agent":
                texto = _llamar_agente(prompt)
            else:
                texto = _llamar_generate(prompt)
        except urllib.error.HTTPError as err:
            detalle = err.read().decode("utf-8", errors="replace")[:800]
            self._send(502, {"texto": "", "error": f"GCP HTTP {err.code}: {detalle}"})
            return
        except Exception as err:
            self._send(502, {"texto": "", "error": str(err)})
            return
        self._send(200, {"texto": texto, "modelo": MODEL})

    def do_GET(self):
        self._send(200, {
            "ok": True,
            "mode": MODE,
            "model": MODEL,
            "project": PROJECT or "(falta PROJECT_ID)",
            "location": LOCATION,
        })


def main():
    if MODE not in ("generate", "agent"):
        sys.exit("YAP_PUERTA_MODE debe ser generate o agent")
    print(f"Puerta Yap -> GCP  http://127.0.0.1:{PORT}/v1/query")
    print(f"  modo     = {MODE}")
    print(f"  proyecto = {PROJECT or '(FALTA PROJECT_ID)'}")
    print(f"  region   = {LOCATION}")
    print(f"  modelo   = {MODEL}")
    if MODE == "agent":
        print(f"  engine   = {ENGINE_ID or '(FALTA ENGINE_ID)'}")
    print("Deja esta ventana abierta. En otra, corre Yap.")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
