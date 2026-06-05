#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFYUI_DIR="${COMFYUI_DIR:-$ROOT/tools/ComfyUI}"
NODE_SRC="$ROOT/comfyui_custom_nodes/external_anime_api_bridge"
NODE_DST="$COMFYUI_DIR/custom_nodes/external_anime_api_bridge"

if [[ ! -d "$COMFYUI_DIR" ]]; then
  echo "ComfyUI checkout not found: $COMFYUI_DIR" >&2
  exit 1
fi

mkdir -p "$COMFYUI_DIR/custom_nodes"
rm -rf "$NODE_DST"
cp -R "$NODE_SRC" "$NODE_DST"
echo "Installed External Anime API Bridge node to $NODE_DST"

