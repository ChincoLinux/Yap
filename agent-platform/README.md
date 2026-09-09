# Agent platform — Super Yap (#91)

Super Yap no usa Gemini ni pip. Es un proceso `llama.cpp` con Llama 3.1 8B
Instruct Q4_K_M en un host de 8 GB. El contrato JSON vive en `docs/SUPER-YAP.md`.

| Artefacto | Rol |
|---|---|
| `../super_yap.py` | Servidor HTTP `127.0.0.1:8742` + REPL |
| `super.env.example` | Variables para `/etc/yap/super.env` |

```bash
python3 super_yap.py --serve
# en otra terminal
set -a; . agent-platform/super.env.example; set +a
python3 yap.py super explica un ciclo para
```
