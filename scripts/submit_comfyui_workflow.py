#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from anime_workflow.services.comfyui_client import ComfyUIClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit a ComfyUI prompt JSON to a local ComfyUI server.")
    parser.add_argument("workflow", type=Path, help="Path to API-format ComfyUI prompt JSON.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8188", help="ComfyUI server URL.")
    args = parser.parse_args()

    prompt = json.loads(args.workflow.read_text(encoding="utf-8"))
    prompt_id = ComfyUIClient(base_url=args.base_url).submit_prompt(prompt)
    print(prompt_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
