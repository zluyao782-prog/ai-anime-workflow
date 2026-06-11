from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from anime_workflow.projects.models import slug


VALID_PROVIDERS = {"mock", "openai", "comfyui"}
VALID_STATUSES = {"queued", "running", "completed", "failed", "cancelled"}
VALID_STEPS = {"storyboard", "images", "video"}
VALID_ITEM_STATUSES = {"pending", "running", "completed", "failed", "cancelled", "skipped"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"job_{stamp}_{secrets.token_hex(3)}"


def normalize_steps(values: Any) -> list[str]:
    raw = values if isinstance(values, list) else []
    if not raw:
        raise ValueError("steps is required")
    steps = [str(item).strip() for item in raw]
    if "full" in steps:
        if len(steps) != 1:
            raise ValueError("full must be the only step when used")
        return ["storyboard", "images", "video"]
    invalid = [item for item in steps if item not in VALID_STEPS]
    if invalid:
        raise ValueError(f"invalid step: {invalid[0]}")
    return steps


def normalize_episode_ids(values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ValueError("episode_ids is required")
    episode_ids: list[str] = []
    for value in values:
        episode_id = str(value or "").strip()
        if not episode_id:
            raise ValueError("episode_ids is required")
        normalized = slug(episode_id, "")
        if episode_id != normalized:
            raise ValueError("episode_id is invalid")
        episode_ids.append(normalized)
    return episode_ids


def step_sequence_from(step: str) -> list[str]:
    if step == "storyboard":
        return ["storyboard", "images", "video"]
    if step == "images":
        return ["images", "video"]
    if step == "video":
        return ["video"]
    raise ValueError(f"invalid step: {step}")


def default_job_items(episode_ids: list[str], steps: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "episode_id": episode_id,
            "step": step,
            "status": "pending",
            "error": "",
            "output_path": "",
            "started_at": "",
            "finished_at": "",
        }
        for episode_id in episode_ids
        for step in steps
    ]


def normalize_items(values: Any, episode_ids: list[str], steps: list[str]) -> list[dict[str, Any]]:
    defaults = {(item["episode_id"], item["step"]): item for item in default_job_items(episode_ids, steps)}
    raw_items = values if isinstance(values, list) else []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        episode_id = str(raw.get("episode_id") or "").strip()
        step = str(raw.get("step") or "").strip()
        key = (episode_id, step)
        if key not in defaults:
            continue
        status = str(raw.get("status") or "pending").strip()
        if status not in VALID_ITEM_STATUSES:
            status = "pending"
        defaults[key] = {
            "episode_id": episode_id,
            "step": step,
            "status": status,
            "error": str(raw.get("error") or ""),
            "output_path": str(raw.get("output_path") or ""),
            "started_at": str(raw.get("started_at") or ""),
            "finished_at": str(raw.get("finished_at") or ""),
        }
    return [defaults[(episode_id, step)] for episode_id in episode_ids for step in steps]


def job_from(values: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    project_id = str(values.get("project_id") or existing.get("project_id") or "").strip()
    if not project_id:
        raise ValueError("project_id is required")
    project_id = slug(project_id, "")
    if not project_id:
        raise ValueError("project_id is required")

    provider = str(values.get("provider") or existing.get("provider") or "mock").strip().lower()
    if provider not in VALID_PROVIDERS:
        raise ValueError("provider must be mock, openai, or comfyui")

    steps = normalize_steps(values.get("steps", existing.get("steps")))
    episode_ids = normalize_episode_ids(values.get("episode_ids", existing.get("episode_ids")))
    status = str(values.get("status") or existing.get("status") or "queued")
    if status not in VALID_STATUSES:
        raise ValueError("status is invalid")

    created_at = str(existing.get("created_at") or values.get("created_at") or now_iso())
    completed_steps = int(values.get("completed_steps", existing.get("completed_steps", 0)) or 0)
    total_steps = len(steps) * len(episode_ids)
    progress = int(values.get("progress", existing.get("progress", 0)) or 0)
    if total_steps:
        progress = max(0, min(100, progress))

    return {
        "job_id": str(existing.get("job_id") or values.get("job_id") or job_id()),
        "project_id": project_id,
        "episode_ids": episode_ids,
        "steps": steps,
        "provider": provider,
        "status": status,
        "progress": progress,
        "completed_steps": max(0, min(completed_steps, total_steps)),
        "total_steps": total_steps,
        "current_episode_id": str(values.get("current_episode_id", existing.get("current_episode_id", "")) or ""),
        "current_step": str(values.get("current_step", existing.get("current_step", "")) or ""),
        "error": str(values.get("error", existing.get("error", "")) or ""),
        "cancel_requested": bool(values.get("cancel_requested", existing.get("cancel_requested", False))),
        "created_at": created_at,
        "updated_at": now_iso(),
        "started_at": str(values.get("started_at", existing.get("started_at", "")) or ""),
        "finished_at": str(values.get("finished_at", existing.get("finished_at", "")) or ""),
        "items": normalize_items(values.get("items", existing.get("items")), episode_ids, steps),
    }
