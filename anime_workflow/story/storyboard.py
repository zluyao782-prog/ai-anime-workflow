from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DEFAULT_BEATS = [
    ("开场钩子", "用强烈画面交代事件，制造悬念"),
    ("主角登场", "突出主角身份、处境和第一反应"),
    ("冲突升级", "让线索、误会或危险更明确"),
    ("关键发现", "给出推动下一幕的信息"),
    ("情绪爆点", "放大表情、动作和戏剧张力"),
    ("结尾反转", "留下下一集钩子"),
]


def generate_storyboard(values: dict[str, Any]) -> dict[str, Any]:
    project_id = slug(values.get("project_id") or "demo_project")
    episode_id = slug(values.get("episode_id") or "episode_001")
    shot_count = clamp_int(values.get("shot_count", 6), 1, 24)
    duration_seconds = clamp_int(values.get("duration_seconds", shot_count * 3), shot_count, 180)
    genre = str(values.get("genre") or "悬疑")
    premise = str(values.get("premise") or "主角遇到改变命运的事件")
    protagonist = str(values.get("protagonist") or "年轻主角")
    style_preset = str(values.get("style_preset") or "clean_anime_drama")
    platform = str(values.get("platform") or "douyin")
    title = str(values.get("title") or f"{premise[:16]}").strip()
    durations = split_duration(duration_seconds, shot_count)

    shots: list[dict[str, Any]] = []
    for index in range(shot_count):
        beat_name, beat_goal = DEFAULT_BEATS[index % len(DEFAULT_BEATS)]
        shot_no = index + 1
        camera = camera_for(index)
        emotion = emotion_for(index, genre)
        scene = f"{beat_name}：{premise}。{beat_goal}。"
        image_prompt = (
            f"{style_preset}, {genre} anime short drama frame, {platform} vertical composition, "
            f"{protagonist}, {premise}, beat: {beat_name}, camera: {camera}, emotion: {emotion}, "
            "consistent character design, cinematic lighting, clean linework, high clarity"
        )
        shots.append(
            {
                "shot_id": f"shot_{shot_no:03d}",
                "duration": durations[index],
                "scene": scene,
                "dialogue": dialogue_for(index, genre, premise),
                "image_prompt": image_prompt,
                "camera": camera,
                "emotion": emotion,
                "source_image": "",
                "anime_image": "",
                "reference_bindings": [],
                "workflow_template": "mock_image",
                "rerun_history": [],
                "review_status": "pending",
                "review_note": "",
                "reviewed_at": "",
            }
        )

    return {
        "project_id": project_id,
        "episode_id": episode_id,
        "title": title,
        "genre": genre,
        "premise": premise,
        "protagonist": protagonist,
        "style_preset": style_preset,
        "platform": platform,
        "duration_seconds": duration_seconds,
        "shot_count": shot_count,
        "shots": shots,
        "review_versions": [],
    }


def save_storyboard(storyboard: dict[str, Any], root: Path) -> Path:
    path = storyboard_path(root, storyboard["project_id"], storyboard["episode_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_storyboard(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def storyboard_path(root: Path, project_id: str, episode_id: str) -> Path:
    return Path(root) / slug(project_id) / slug(episode_id) / "storyboard.json"


def split_duration(total: int, count: int) -> list[int]:
    base = total // count
    remainder = total % count
    return [base + (1 if index < remainder else 0) for index in range(count)]


def slug(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "item"


def clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(maximum, parsed))


def camera_for(index: int) -> str:
    cameras = ["establishing shot", "medium close-up", "over shoulder", "low angle", "close-up", "wide ending shot"]
    return cameras[index % len(cameras)]


def emotion_for(index: int, genre: str) -> str:
    if "甜" in genre:
        emotions = ["curious", "warm", "hesitant", "surprised", "tender", "hopeful"]
    elif "逆袭" in genre:
        emotions = ["suppressed", "determined", "tense", "focused", "explosive", "confident"]
    else:
        emotions = ["mysterious", "alert", "tense", "shocked", "urgent", "suspenseful"]
    return emotions[index % len(emotions)]


def dialogue_for(index: int, genre: str, premise: str) -> str:
    lines = [
        f"这件事，和{premise}有关。",
        "等等，线索不对。",
        "如果是真的，我们已经来不及了。",
        "我知道下一步该去哪了。",
        "你从一开始就在骗我？",
        "下一集，真相会更危险。",
    ]
    if "甜" in genre:
        lines = ["你怎么会在这里？", "我只是刚好路过。", "别再一个人扛着了。", "你相信我一次。", "这句话，我等了很久。", "明天，我们还会见面吗？"]
    return lines[index % len(lines)]
