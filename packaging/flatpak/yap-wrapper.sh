#!/bin/bash
# yap-wrapper.sh — Flatpak wrapper for yap.py
# Sets up paths relative to Flatpak sandbox before launching the agent.
exec python3 /app/lib/yap/yap.py \
    --llama-cli /app/bin/llama-cli \
    "$@"
