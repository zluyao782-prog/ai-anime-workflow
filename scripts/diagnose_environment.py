#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from anime_workflow.services.exporter import VideoExporter


def check_command(name: str) -> dict[str, str]:
    path = shutil.which(name)
    return {"name": name, "status": "available" if path else "missing", "path": path or ""}


def check_comfyui(base_url: str = "http://127.0.0.1:8188") -> dict[str, str]:
    try:
        with urlopen(f"{base_url}/system_stats", timeout=2) as response:
            return {"name": "comfyui", "status": "running", "base_url": base_url, "detail": response.read(120).decode("utf-8", errors="replace")}
    except URLError as exc:
        return {"name": "comfyui", "status": "not_running", "base_url": base_url, "detail": str(exc)}


def main() -> int:
    checks = {
        "python": {"name": "python", "status": "available", "version": sys.version.split()[0]},
        "ffmpeg": check_command("ffmpeg"),
        "ollama": check_command("ollama"),
        "comfyui": check_comfyui(),
        "exporter": {"name": "VideoExporter", "status": VideoExporter().diagnose()},
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
