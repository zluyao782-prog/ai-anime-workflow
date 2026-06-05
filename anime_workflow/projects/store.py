from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from anime_workflow.projects.models import character_from, clamp_int, now_iso, project_from, slug, style_from, value_from


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    item = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(item, dict):
        raise ValueError(f"{label} json must be an object: {path}")
    return item


def load_project_json(path: Path) -> dict[str, Any]:
    return load_json_object(path, "project")


class ProjectStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def project_dir(self, project_id: str) -> Path:
        return self.root / slug(project_id, "project")

    def project_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "project.json"

    def save_project(self, values: dict[str, Any]) -> dict[str, Any]:
        project_id = slug(values.get("project_id") or values.get("name"), "project")
        existing = self.get_project(project_id) if self.project_path(project_id).exists() else None
        project = project_from(values, existing)
        path = self.project_path(project["project_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
        return project

    def get_project(self, project_id: str) -> dict[str, Any]:
        path = self.project_path(project_id)
        if not path.exists():
            raise FileNotFoundError(f"project not found: {slug(project_id, 'project')}")
        return load_project_json(path)

    def list_projects(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*/project.json")):
            items.append(load_project_json(path))
        return items

    def _json_path(self, project_id: str, collection: str, item_id: str) -> Path:
        return self.project_dir(project_id) / collection / f"{slug(item_id, 'item')}.json"

    def _list_collection(self, project_id: str, collection: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted((self.project_dir(project_id) / collection).glob("*.json")):
            items.append(load_json_object(path, collection))
        return items

    def save_character(self, project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self.get_project(project_id)
        character_id = slug(values.get("character_id") or values.get("name"), "character")
        path = self._json_path(project_id, "characters", character_id)
        existing = load_json_object(path, "character") if path.exists() else None
        character = character_from(project_id, values, existing)
        path = self._json_path(project_id, "characters", character["character_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(character, ensure_ascii=False, indent=2), encoding="utf-8")
        return character

    def list_characters(self, project_id: str) -> list[dict[str, Any]]:
        self.get_project(project_id)
        return self._list_collection(project_id, "characters")

    def save_style(self, project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self.get_project(project_id)
        style_id = slug(values.get("style_id") or values.get("name"), "style")
        path = self._json_path(project_id, "styles", style_id)
        existing = load_json_object(path, "style") if path.exists() else None
        style = style_from(project_id, values, existing)
        path = self._json_path(project_id, "styles", style["style_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(style, ensure_ascii=False, indent=2), encoding="utf-8")
        return style

    def list_styles(self, project_id: str) -> list[dict[str, Any]]:
        self.get_project(project_id)
        return self._list_collection(project_id, "styles")

    def save_episode(self, project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        project = self.get_project(project_id)
        requested_episode_no = clamp_int(values.get("episode_no"), 1, 999, 1)
        episode_id = slug(values.get("episode_id") or f"episode_{requested_episode_no:03d}", "episode")
        path = self._json_path(project_id, "episodes", episode_id)
        existing = load_json_object(path, "episode") if path.exists() else {}
        episode_no = clamp_int(value_from(values, existing, "episode_no", requested_episode_no), 1, 999, requested_episode_no)
        episode = {
            "episode_id": episode_id,
            "project_id": project["project_id"],
            "episode_no": episode_no,
            "title": str(value_from(values, existing, "title", f"第{episode_no}集")),
            "premise": str(value_from(values, existing, "premise", project.get("premise", ""))),
            "duration_seconds": clamp_int(
                value_from(values, existing, "duration_seconds", project["default_duration_seconds"]),
                3,
                180,
                project["default_duration_seconds"],
            ),
            "shot_count": clamp_int(
                value_from(values, existing, "shot_count", project["default_shot_count"]),
                1,
                24,
                project["default_shot_count"],
            ),
            "status": str(value_from(values, existing, "status", "draft")),
            "storyboard_path": str(value_from(values, existing, "storyboard_path", "")),
            "video_path": str(value_from(values, existing, "video_path", "")),
            "error": str(value_from(values, existing, "error", "")),
            "source_excerpt": str(value_from(values, existing, "source_excerpt", "")),
            "created_at": existing.get("created_at") or now_iso(),
            "updated_at": now_iso(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
        return episode

    def get_episode(self, project_id: str, episode_id: str) -> dict[str, Any]:
        path = self._json_path(project_id, "episodes", episode_id)
        if not path.exists():
            raise FileNotFoundError(f"episode not found: {slug(episode_id, 'episode')}")
        return load_json_object(path, "episode")

    def update_episode(self, project_id: str, episode_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        existing = self.get_episode(project_id, episode_id)
        merged = dict(existing)
        merged.update(updates)
        merged["episode_id"] = existing["episode_id"]
        merged["episode_no"] = existing["episode_no"]
        return self.save_episode(project_id, merged)

    def list_episodes(self, project_id: str) -> list[dict[str, Any]]:
        self.get_project(project_id)
        return sorted(self._list_collection(project_id, "episodes"), key=lambda item: item["episode_no"])

    def build_storyboard_values(self, project_id: str, episode_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        episode = self.get_episode(project_id, episode_id)
        characters = self.list_characters(project_id)
        styles = self.list_styles(project_id)
        default_style_id = str(project.get("default_style_id") or "")
        style = next((item for item in styles if item.get("style_id") == default_style_id), {})
        character = characters[0] if characters else {}
        protagonist = "；".join(
            part
            for part in [
                character.get("name", ""),
                character.get("role", ""),
                character.get("appearance", ""),
                character.get("prompt_fragment", ""),
            ]
            if part
        )
        style_preset = style.get("style_id") or default_style_id or "clean_anime_drama"
        style_prompt = str(style.get("base_prompt") or "")
        return {
            "project_id": project["project_id"],
            "episode_id": episode["episode_id"],
            "title": episode["title"],
            "genre": project["genre"],
            "platform": project["platform"],
            "premise": f"{project.get('premise', '')}。{episode.get('premise', '')}".strip("。"),
            "protagonist": protagonist or "年轻主角",
            "style_preset": f"{style_preset}, {style_prompt}".strip(", "),
            "duration_seconds": episode["duration_seconds"],
            "shot_count": episode["shot_count"],
        }

    def create_episode_batch(self, project_id: str, values: dict[str, Any]) -> list[dict[str, Any]]:
        project = self.get_project(project_id)
        count = clamp_int(values.get("count"), 1, 50, 10)
        direction = str(values.get("direction") or "每集推进一个冲突，结尾留下钩子")
        next_episode_no = max((item["episode_no"] for item in self.list_episodes(project_id)), default=0) + 1
        episodes: list[dict[str, Any]] = []
        for offset in range(count):
            episode_no = next_episode_no + offset
            episodes.append(
                self.save_episode(
                    project_id,
                    {
                        "episode_no": episode_no,
                        "episode_id": f"episode_{episode_no:03d}",
                        "title": f"第{episode_no}集：{project['name']}",
                        "premise": f"{project.get('premise', '')}。{direction}。这是第{episode_no}集。",
                        "status": "draft",
                    },
                )
            )
        return episodes

    def list_outputs(self, exports_dir: Path) -> list[dict[str, Any]]:
        exports_dir = Path(exports_dir)
        outputs: list[dict[str, Any]] = []
        for path in sorted(exports_dir.glob("*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True):
            stat = path.stat()
            outputs.append(
                {
                    "filename": path.name,
                    "video_path": str(path),
                    "size_bytes": stat.st_size,
                    "updated_at": stat.st_mtime,
                }
            )
        return outputs
