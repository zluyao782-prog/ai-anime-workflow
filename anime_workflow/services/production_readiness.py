from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from anime_workflow.launcher.config import effective_comfyui_base_url
from anime_workflow.launcher.services import check_http_json
from anime_workflow.services.workflow_templates import list_workflow_templates


def configured_output_dir(config: dict[str, Any], project_root: Path) -> Path:
    path = Path(str(config.get("output_dir") or "data/exports"))
    if path.is_absolute():
        return path
    return Path(project_root) / path


def production_readiness(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    base_url = effective_comfyui_base_url(config)
    comfyui = check_http_json(f"{base_url.rstrip('/')}/system_stats")
    ffmpeg_path = shutil.which("ffmpeg") or ""
    output_dir = configured_output_dir(config, Path(project_root))
    templates = list_workflow_templates()

    checks = {
        "openai": _openai_check(config),
        "comfyui": {"ok": bool(comfyui["ok"]), "base_url": base_url, "detail": comfyui["detail"]},
        "ffmpeg": {"ok": bool(ffmpeg_path), "path": ffmpeg_path},
        "output_dir": {"ok": True, "path": str(output_dir)},
        "workflow_templates": {"ok": bool(templates), "count": len(templates), "templates": templates},
    }
    return {
        "ok": all(check["ok"] for check in checks.values()),
        "checks": checks,
        "project_root": str(Path(project_root)),
    }


def _openai_check(config: dict[str, Any]) -> dict[str, Any]:
    model = str(config.get("openai_image_model") or "gpt-image-2")
    base_url = str(config.get("openai_base_url") or "")
    if not config.get("openai_api_key"):
        return {
            "ok": False,
            "model": model,
            "base_url": base_url,
            "detail": "OpenAI API Key is not configured",
        }
    return {"ok": True, "model": model, "base_url": base_url, "detail": "configured"}
