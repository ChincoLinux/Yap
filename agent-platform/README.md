# Agent platform — Super Yap (#91)

Super Yap no usa Gemini ni pip ni un Llama 8B local. El PC del alumno
sigue en 1B/3B. Si `llama-cli` tarda 3 minutos, Yap consulta Gradio 5 en
Cloud Run. El protocolo vive en `docs/SUPER-YAP.md`.

| Artefacto | Rol |
|---|---|
| `../yap.py` | Cliente Gradio (`urllib` + cookies, sin `requests`) |
| `super.env.example` | Variables para `/etc/yap/super.env` |

```bash
# en el PC del alumno
set -a; . agent-platform/super.env.example; set +a
python3 yap.py super
# si el local tarda 3 min, o:
python3 yap.py super explica un ciclo para
```
