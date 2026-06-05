from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(value: Any, fallback: str = "item") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or fallback


def clamp_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def value_from(values: dict[str, Any], existing: dict[str, Any], key: str, default: Any) -> Any:
    if key in values:
        return values[key]
    return existing.get(key, default)


def project_from(values: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    name_source = values["name"] if "name" in values else existing.get("name", "")
    name = str(name_source or "").strip()
    if not name:
        raise ValueError("name is required")
    project_id = slug(values.get("project_id") or existing.get("project_id") or name, "project")
    created_at = existing.get("created_at") or now_iso()
    return {
        "project_id": project_id,
        "name": name,
        "genre": str(value_from(values, existing, "genre", "悬疑")),
        "platform": str(value_from(values, existing, "platform", "douyin")),
        "premise": str(value_from(values, existing, "premise", "")),
        "default_duration_seconds": clamp_int(
            value_from(values, existing, "default_duration_seconds", 30), 3, 180, 30
        ),
        "default_shot_count": clamp_int(value_from(values, existing, "default_shot_count", 6), 1, 24, 6),
        "default_style_id": slug(value_from(values, existing, "default_style_id", "clean_anime_drama")),
        "status": str(value_from(values, existing, "status", "active")),
        "created_at": created_at,
        "updated_at": now_iso(),
    }


def character_from(project_id: str, values: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    name_source = values["name"] if "name" in values else existing.get("name", "")
    name = str(name_source or "").strip()
    if not name:
        raise ValueError("character name is required")
    character_id = slug(values.get("character_id") or existing.get("character_id") or name, "character")
    return {
        "character_id": character_id,
        "project_id": slug(project_id, "project"),
        "name": name,
        "role": str(value_from(values, existing, "role", "")),
        "appearance": str(value_from(values, existing, "appearance", "")),
        "personality": str(value_from(values, existing, "personality", "")),
        "costume": str(value_from(values, existing, "costume", "")),
        "reference_image": str(value_from(values, existing, "reference_image", "")),
        "prompt_fragment": str(value_from(values, existing, "prompt_fragment", "")),
        "created_at": existing.get("created_at") or now_iso(),
        "updated_at": now_iso(),
    }


def style_from(project_id: str, values: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    name_source = values["name"] if "name" in values else existing.get("name", "")
    name = str(name_source or "").strip()
    if not name:
        raise ValueError("style name is required")
    style_id = slug(values.get("style_id") or existing.get("style_id") or name, "style")
    return {
        "style_id": style_id,
        "project_id": slug(project_id, "project"),
        "name": name,
        "base_prompt": str(value_from(values, existing, "base_prompt", "")),
        "negative_prompt": str(value_from(values, existing, "negative_prompt", "")),
        "aspect_ratio": str(value_from(values, existing, "aspect_ratio", "9:16")),
        "palette": str(value_from(values, existing, "palette", "")),
        "camera_style": str(value_from(values, existing, "camera_style", "")),
        "provider": str(value_from(values, existing, "provider", "openai")),
        "created_at": existing.get("created_at") or now_iso(),
        "updated_at": now_iso(),
    }
