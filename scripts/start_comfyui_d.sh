#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFYUI_DIR="/mnt/d/Codex/ai-anime-workflow/ComfyUI"
COMFYUI_VENV="/mnt/d/Codex/ai-anime-workflow/comfyui-venv"

COMFYUI_DIR="$COMFYUI_DIR" COMFYUI_VENV="$COMFYUI_VENV" "$ROOT/scripts/start_comfyui_cpu.sh"

