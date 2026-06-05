#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFYUI_DIR="${COMFYUI_DIR:-$ROOT/tools/ComfyUI}"
COMFYUI_VENV="${COMFYUI_VENV:-$ROOT/tools/comfyui-venv}"

if [[ ! -d "$COMFYUI_DIR" ]]; then
  echo "ComfyUI checkout not found: $COMFYUI_DIR" >&2
  exit 1
fi

python3 -m venv "$COMFYUI_VENV"
"$COMFYUI_VENV/bin/python" -m pip install --upgrade pip
"$COMFYUI_VENV/bin/python" -m pip install -r "$COMFYUI_DIR/requirements.txt"
"$ROOT/scripts/install_comfyui_custom_node.sh"
echo "ComfyUI CPU dependencies installed in $COMFYUI_VENV"

