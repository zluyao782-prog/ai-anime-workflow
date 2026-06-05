from __future__ import annotations

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

SHOT_EDITABLE = {"duration", "scene", "dialogue", "image_prompt", "camera", "emotion"}


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
                shot[key] = int(value) if key == "duration" else str(value)
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
    copied["shots"] = [dict(shot) for shot in storyboard["shots"]]
    return copied
