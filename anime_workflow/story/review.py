from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


STORYBOARD_REQUIRED = {
    "project_id",
    "episode_id",
    "title",
    "genre",
    "premise",
    "protagonist",
    "style_preset",
    "platform",
    "duration_seconds",
    "shot_count",
    "shots",
}

SHOT_REQUIRED = {
    "shot_id",
    "duration",
    "scene",
    "dialogue",
    "image_prompt",
    "camera",
    "emotion",
    "source_image",
    "anime_image",
}

REVIEW_STATUSES = {"pending", "approved", "rejected", "revise"}

SHOT_EDITABLE = {
    "duration",
    "scene",
    "dialogue",
    "image_prompt",
    "camera",
    "emotion",
    "reference_bindings",
    "workflow_template",
    "review_status",
    "review_note",
}


def validate_storyboard_for_review(storyboard: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(storyboard, dict) or any(key not in storyboard for key in STORYBOARD_REQUIRED):
        raise ValueError("storyboard API returned invalid storyboard")
    if not isinstance(storyboard.get("shots"), list) or not storyboard["shots"]:
        raise ValueError("storyboard API returned invalid storyboard")
    for shot in storyboard["shots"]:
        if not isinstance(shot, dict) or any(key not in shot for key in SHOT_REQUIRED):
            raise ValueError("storyboard API returned invalid storyboard")
    return storyboard


def update_storyboard_shot(storyboard: dict[str, Any], shot_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    next_storyboard = copy_storyboard(validate_storyboard_for_review(storyboard))
    matched = False
    for shot in next_storyboard["shots"]:
        if shot["shot_id"] != shot_id:
            continue
        for key, value in updates.items():
            if key in SHOT_EDITABLE:
                if key == "duration":
                    shot[key] = int(value)
                elif key == "reference_bindings":
                    shot[key] = normalize_reference_bindings(value)
                elif key == "review_status":
                    shot[key] = normalize_review_status(value)
                    shot["reviewed_at"] = now_iso()
                else:
                    shot[key] = str(value)
        matched = True
        break
    if not matched:
        raise FileNotFoundError("shot not found")
    return next_storyboard


def rewrite_storyboard_shot_local(storyboard: dict[str, Any], shot_id: str, instruction: str) -> dict[str, Any]:
    instruction = str(instruction or "增强戏剧张力").strip()
    next_storyboard = copy_storyboard(validate_storyboard_for_review(storyboard))
    for shot in next_storyboard["shots"]:
        if shot["shot_id"] != shot_id:
            continue
        shot["scene"] = f"{shot['scene']} 改写要求：{instruction}。"
        shot["dialogue"] = f"{shot['dialogue']}（{instruction}）"
        shot["image_prompt"] = f"{shot['image_prompt']}, rewrite note: {instruction}, stronger cinematic tension"
        return next_storyboard
    raise FileNotFoundError("shot not found")


def copy_storyboard(storyboard: dict[str, Any]) -> dict[str, Any]:
    copied = dict(storyboard)
    copied["shots"] = [copy.deepcopy(shot) for shot in storyboard["shots"]]
    return copied


def snapshot_storyboard_review(storyboard: dict[str, Any], note: str = "") -> dict[str, Any]:
    next_storyboard = copy_storyboard(validate_storyboard_for_review(storyboard))
    versions = next_storyboard.get("review_versions") if isinstance(next_storyboard.get("review_versions"), list) else []
    snapshot = {
        "version_id": f"review_{len(versions) + 1:03d}",
        "created_at": now_iso(),
        "note": str(note or "").strip(),
        "summary": review_summary(next_storyboard),
        "shots": [
            {
                "shot_id": shot.get("shot_id", ""),
                "scene": shot.get("scene", ""),
                "dialogue": shot.get("dialogue", ""),
                "image_prompt": shot.get("image_prompt", ""),
                "review_status": normalize_review_status(shot.get("review_status", "pending")),
                "review_note": str(shot.get("review_note", "")),
                "anime_image": shot.get("anime_image", ""),
            }
            for shot in next_storyboard["shots"]
        ],
    }
    next_storyboard["review_versions"] = [*versions, snapshot][-20:]
    return next_storyboard


def review_summary(storyboard: dict[str, Any]) -> dict[str, int]:
    summary = {"pending": 0, "approved": 0, "rejected": 0, "revise": 0}
    for shot in storyboard.get("shots", []):
        status = normalize_review_status(shot.get("review_status", "pending"))
        summary[status] += 1
    return summary


def normalize_review_status(value: Any) -> str:
    status = str(value or "pending").strip().lower()
    return status if status in REVIEW_STATUSES else "pending"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_reference_bindings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        reference_id = str(item or "").strip()
        if reference_id and reference_id not in result:
            result.append(reference_id)
    return result
