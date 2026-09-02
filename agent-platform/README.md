# Agent Platform — Yap Nube (Gemini 3.7 Flash)

Agente ADK que corre en Gemini Enterprise Agent Platform. No se instala
en el PC del alumno.

```
from agent-platform/yap_nube/agent.py
MODEL = "gemini-3.7-flash"
name  = "yap_nube"
```

Despliegue (operadores que clonan el repo):

1. Crear el agente en Agent Platform con este paquete.
2. Publicarlo por Private Service Connect en `10.40.0.10`.
3. Inyectar el token de flota en la imagen ChincoLinux
   (`/etc/yap/cloud-token` o `YAP_CLOUD_TOKEN`).
4. En el laboratorio: `YAP_CLOUD_ENABLED=1`.

Contrato HTTP y variables: [docs/CLOUD.md](../docs/CLOUD.md).
