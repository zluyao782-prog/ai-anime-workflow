#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFYUI_DIR="${COMFYUI_DIR:-$ROOT/tools/ComfyUI}"
COMFYUI_VENV="${COMFYUI_VENV:-$ROOT/tools/comfyui-venv}"

if [[ ! -d "$COMFYUI_DIR" ]]; then
  echo "ComfyUI checkout not found: $COMFYUI_DIR" >&2
  exit 1
fi

if [[ ! -x "$COMFYUI_VENV/bin/python" ]]; then
  echo "ComfyUI virtualenv not found: $COMFYUI_VENV" >&2
  echo "Create it and install ComfyUI requirements before starting the server." >&2
  exit 1
fi

cd "$COMFYUI_DIR"
"$COMFYUI_VENV/bin/python" main.py --cpu --listen 127.0.0.1 --port 8188

