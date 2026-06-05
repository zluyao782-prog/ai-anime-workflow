#!/usr/bin/env bash
set -euo pipefail

echo "== Disk =="
df -h /mnt/c /mnt/d

echo
echo "== ComfyUI D install =="
test -x /mnt/d/Codex/ai-anime-workflow/comfyui-venv/bin/python && echo "ComfyUI venv: OK" || echo "ComfyUI venv: missing"
test -d /mnt/d/Codex/ai-anime-workflow/ComfyUI && echo "ComfyUI source: OK" || echo "ComfyUI source: missing"

echo
echo "== Ollama =="
ollama --version || true
systemctl is-active ollama || true
systemctl show ollama --property=Environment --no-pager || true

echo
echo "== Models =="
ollama list || true

