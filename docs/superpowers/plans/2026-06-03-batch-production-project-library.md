# Batch Production Project Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first project-library version of the local AI anime workbench so one short-drama project can manage characters, style templates, episode outlines, and exported outputs.

**Architecture:** Keep the current Python launcher and React/Vite frontend. Add a focused local JSON repository under `anime_workflow/projects/` and expose project-scoped APIs from the existing launcher server without replacing the current single-episode endpoints. The first version uses synchronous per-action production and leaves full background queues for a later phase.

**Tech Stack:** Python standard library, `unittest`, React, TypeScript, Vite, Tailwind, existing launcher API, local JSON files.

---

## File Structure

Create:

- `anime_workflow/projects/__init__.py` - package exports.
- `anime_workflow/projects/models.py` - typed constructors, defaults, validation helpers, slug normalization.
- `anime_workflow/projects/store.py` - local JSON repository for projects, characters, styles, episodes, and output summaries.
- `tests/test_project_library.py` - backend tests for project data, batch episode creation, status updates, and output listing.

Modify:

- `anime_workflow/launcher/server.py` - add `/api/projects*` and `/api/outputs` endpoints.
- `anime_workflow/story/storyboard.py` - allow project/character/style enriched storyboard inputs without breaking current single-episode API.
- `anime_workflow/story/episode_runner.py` - return episode status data after image/video generation.
- `frontend/src/api.ts` - add project library types and API functions.
- `frontend/src/App.tsx` - add `项目库`, `角色库`, `风格模板`, `成品库` tabs and project-scoped production flow.
- `frontend/src/styles.css` - no planned change; reuse existing `input`, button, panel, and Tailwind utility classes.

Keep:

- Current `/api/episode/*` endpoints for compatibility.
- Existing `data/storyboards`, `data/assets`, and `data/exports` paths.

---

### Task 1: Project Library Models And Store

**Files:**

- Create: `anime_workflow/projects/__init__.py`
- Create: `anime_workflow/projects/models.py`
- Create: `anime_workflow/projects/store.py`
- Test: `tests/test_project_library.py`

- [ ] **Step 1: Write failing tests for project CRUD and defaults**

Add this to `tests/test_project_library.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from anime_workflow.projects.store import ProjectStore


class ProjectLibraryTest(unittest.TestCase):
    def test_create_project_writes_project_json_and_lists_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")

            project = store.save_project(
                {
                    "project_id": "Rain Detective",
                    "name": "雨夜侦探",
                    "genre": "悬疑",
                    "platform": "douyin",
                    "premise": "雨夜匿名信引发的连续失踪案",
                    "default_duration_seconds": 30,
                    "default_shot_count": 6,
                    "default_style_id": "clean_anime_drama",
                }
            )

            self.assertEqual(project["project_id"], "rain_detective")
            self.assertEqual(project["name"], "雨夜侦探")
            self.assertEqual(project["status"], "active")
            self.assertTrue((Path(tmp) / "projects/rain_detective/project.json").exists())
            self.assertEqual([item["project_id"] for item in store.list_projects()], ["rain_detective"])

    def test_project_validation_rejects_empty_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")

            with self.assertRaisesRegex(ValueError, "name is required"):
                store.save_project({"project_id": "demo", "name": ""})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m unittest tests.test_project_library -v
```

Expected: fail with `ModuleNotFoundError: No module named 'anime_workflow.projects'`.

- [ ] **Step 3: Implement models and store**

Create `anime_workflow/projects/__init__.py`:

```python
from anime_workflow.projects.store import ProjectStore

__all__ = ["ProjectStore"]
```

Create `anime_workflow/projects/models.py`:

```python
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


def project_from(values: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    name = str(values.get("name") or existing.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    project_id = slug(values.get("project_id") or existing.get("project_id") or name, "project")
    created_at = existing.get("created_at") or now_iso()
    return {
        "project_id": project_id,
        "name": name,
        "genre": str(values.get("genre") or existing.get("genre") or "悬疑"),
        "platform": str(values.get("platform") or existing.get("platform") or "douyin"),
        "premise": str(values.get("premise") or existing.get("premise") or ""),
        "default_duration_seconds": clamp_int(
            values.get("default_duration_seconds", existing.get("default_duration_seconds", 30)), 3, 180, 30
        ),
        "default_shot_count": clamp_int(values.get("default_shot_count", existing.get("default_shot_count", 6)), 1, 24, 6),
        "default_style_id": slug(values.get("default_style_id") or existing.get("default_style_id") or "clean_anime_drama"),
        "status": str(values.get("status") or existing.get("status") or "active"),
        "created_at": created_at,
        "updated_at": now_iso(),
    }
```

Create `anime_workflow/projects/store.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from anime_workflow.projects.models import project_from, slug


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
        return json.loads(path.read_text(encoding="utf-8"))

    def list_projects(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*/project.json")):
            items.append(json.loads(path.read_text(encoding="utf-8")))
        return items
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
.venv/bin/python -m unittest tests.test_project_library -v
```

Expected: 2 tests pass.

---

### Task 2: Characters, Styles, Episodes

**Files:**

- Modify: `anime_workflow/projects/models.py`
- Modify: `anime_workflow/projects/store.py`
- Test: `tests/test_project_library.py`

- [ ] **Step 1: Add failing tests for characters, styles, and batch episodes**

Add these tests inside `ProjectLibraryTest`:

```python
    def test_create_character_and_style_under_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project({"project_id": "demo", "name": "示例项目"})

            character = store.save_character(
                "demo",
                {
                    "character_id": "hero",
                    "name": "林夏",
                    "role": "年轻侦探",
                    "appearance": "黑发，冷静，蓝色风衣",
                    "personality": "敏锐但克制",
                    "costume": "蓝色风衣",
                },
            )
            style = store.save_style(
                "demo",
                {
                    "style_id": "dark_suspense",
                    "name": "暗色悬疑",
                    "base_prompt": "dark suspense anime, cinematic lighting",
                    "negative_prompt": "low quality, blurry",
                    "aspect_ratio": "9:16",
                },
            )

            self.assertEqual(character["character_id"], "hero")
            self.assertEqual(style["style_id"], "dark_suspense")
            self.assertEqual(store.list_characters("demo")[0]["name"], "林夏")
            self.assertEqual(store.list_styles("demo")[0]["name"], "暗色悬疑")

    def test_create_batch_episodes_uses_project_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project(
                {
                    "project_id": "demo",
                    "name": "示例项目",
                    "genre": "悬疑",
                    "premise": "匿名信连环案",
                    "default_duration_seconds": 30,
                    "default_shot_count": 6,
                }
            )

            episodes = store.create_episode_batch("demo", {"count": 3, "direction": "每集一个线索，结尾反转"})

            self.assertEqual([item["episode_no"] for item in episodes], [1, 2, 3])
            self.assertEqual(episodes[0]["episode_id"], "episode_001")
            self.assertEqual(episodes[0]["status"], "draft")
            self.assertIn("第1集", episodes[0]["title"])
            self.assertEqual(store.list_episodes("demo")[2]["episode_id"], "episode_003")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m unittest tests.test_project_library -v
```

Expected: fail with missing `save_character`, `save_style`, or `create_episode_batch`.

- [ ] **Step 3: Implement model helpers**

Append to `anime_workflow/projects/models.py`:

```python
def character_from(project_id: str, values: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    name = str(values.get("name") or existing.get("name") or "").strip()
    if not name:
        raise ValueError("character name is required")
    character_id = slug(values.get("character_id") or existing.get("character_id") or name, "character")
    return {
        "character_id": character_id,
        "project_id": slug(project_id, "project"),
        "name": name,
        "role": str(values.get("role") or existing.get("role") or ""),
        "appearance": str(values.get("appearance") or existing.get("appearance") or ""),
        "personality": str(values.get("personality") or existing.get("personality") or ""),
        "costume": str(values.get("costume") or existing.get("costume") or ""),
        "reference_image": str(values.get("reference_image") or existing.get("reference_image") or ""),
        "prompt_fragment": str(values.get("prompt_fragment") or existing.get("prompt_fragment") or ""),
        "created_at": existing.get("created_at") or now_iso(),
        "updated_at": now_iso(),
    }


def style_from(project_id: str, values: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    name = str(values.get("name") or existing.get("name") or "").strip()
    if not name:
        raise ValueError("style name is required")
    style_id = slug(values.get("style_id") or existing.get("style_id") or name, "style")
    return {
        "style_id": style_id,
        "project_id": slug(project_id, "project"),
        "name": name,
        "base_prompt": str(values.get("base_prompt") or existing.get("base_prompt") or ""),
        "negative_prompt": str(values.get("negative_prompt") or existing.get("negative_prompt") or ""),
        "aspect_ratio": str(values.get("aspect_ratio") or existing.get("aspect_ratio") or "9:16"),
        "palette": str(values.get("palette") or existing.get("palette") or ""),
        "camera_style": str(values.get("camera_style") or existing.get("camera_style") or ""),
        "provider": str(values.get("provider") or existing.get("provider") or "openai"),
        "created_at": existing.get("created_at") or now_iso(),
        "updated_at": now_iso(),
    }
```

- [ ] **Step 4: Implement store methods**

Modify imports in `anime_workflow/projects/store.py`:

```python
from anime_workflow.projects.models import character_from, clamp_int, now_iso, project_from, slug, style_from
```

Append methods to `ProjectStore`:

```python
    def _json_path(self, project_id: str, collection: str, item_id: str) -> Path:
        return self.project_dir(project_id) / collection / f"{slug(item_id, 'item')}.json"

    def _list_collection(self, project_id: str, collection: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted((self.project_dir(project_id) / collection).glob("*.json")):
            items.append(json.loads(path.read_text(encoding="utf-8")))
        return items

    def save_character(self, project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self.get_project(project_id)
        character_id = slug(values.get("character_id") or values.get("name"), "character")
        path = self._json_path(project_id, "characters", character_id)
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
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
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
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
        episode_no = clamp_int(values.get("episode_no"), 1, 999, 1)
        episode_id = slug(values.get("episode_id") or f"episode_{episode_no:03d}", "episode")
        path = self._json_path(project_id, "episodes", episode_id)
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        episode = {
            "episode_id": episode_id,
            "project_id": project["project_id"],
            "episode_no": episode_no,
            "title": str(values.get("title") or existing.get("title") or f"第{episode_no}集"),
            "premise": str(values.get("premise") or existing.get("premise") or project.get("premise", "")),
            "duration_seconds": clamp_int(values.get("duration_seconds", existing.get("duration_seconds", project["default_duration_seconds"])), 3, 180, project["default_duration_seconds"]),
            "shot_count": clamp_int(values.get("shot_count", existing.get("shot_count", project["default_shot_count"])), 1, 24, project["default_shot_count"]),
            "status": str(values.get("status") or existing.get("status") or "draft"),
            "storyboard_path": str(values.get("storyboard_path") or existing.get("storyboard_path") or ""),
            "video_path": str(values.get("video_path") or existing.get("video_path") or ""),
            "error": str(values.get("error") or ""),
            "created_at": existing.get("created_at") or now_iso(),
            "updated_at": now_iso(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
        return episode

    def list_episodes(self, project_id: str) -> list[dict[str, Any]]:
        self.get_project(project_id)
        return sorted(self._list_collection(project_id, "episodes"), key=lambda item: item["episode_no"])

    def create_episode_batch(self, project_id: str, values: dict[str, Any]) -> list[dict[str, Any]]:
        project = self.get_project(project_id)
        count = clamp_int(values.get("count"), 1, 50, 10)
        direction = str(values.get("direction") or "每集推进一个冲突，结尾留下钩子")
        existing_count = len(self.list_episodes(project_id))
        episodes: list[dict[str, Any]] = []
        for offset in range(count):
            episode_no = existing_count + offset + 1
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
```

- [ ] **Step 5: Run tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_project_library -v
```

Expected: all project library tests pass.

---

### Task 3: Project-Scoped Production Bridge

**Files:**

- Modify: `anime_workflow/projects/store.py`
- Modify: `anime_workflow/story/storyboard.py`
- Test: `tests/test_project_library.py`

- [ ] **Step 1: Add failing test for storyboard input composition**

Add this test:

```python
    def test_build_storyboard_input_combines_project_character_style_episode(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project(
                {
                    "project_id": "demo",
                    "name": "雨夜侦探",
                    "genre": "悬疑",
                    "platform": "douyin",
                    "premise": "匿名信连环案",
                    "default_style_id": "dark_suspense",
                }
            )
            store.save_character("demo", {"character_id": "hero", "name": "林夏", "role": "年轻侦探", "appearance": "黑发蓝色风衣"})
            store.save_style("demo", {"style_id": "dark_suspense", "name": "暗色悬疑", "base_prompt": "dark suspense anime"})
            episode = store.save_episode("demo", {"episode_no": 1, "premise": "林夏收到第一封匿名信"})

            values = store.build_storyboard_values("demo", episode["episode_id"])

            self.assertEqual(values["project_id"], "demo")
            self.assertEqual(values["episode_id"], "episode_001")
            self.assertIn("匿名信连环案", values["premise"])
            self.assertIn("林夏", values["protagonist"])
            self.assertIn("dark_suspense_anime", values["style_preset"])
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_project_library.ProjectLibraryTest.test_build_storyboard_input_combines_project_character_style_episode -v
```

Expected: fail with missing `build_storyboard_values`.

- [ ] **Step 3: Implement storyboard input builder**

Append to `ProjectStore`:

```python
    def get_episode(self, project_id: str, episode_id: str) -> dict[str, Any]:
        path = self._json_path(project_id, "episodes", episode_id)
        if not path.exists():
            raise FileNotFoundError(f"episode not found: {slug(episode_id, 'episode')}")
        return json.loads(path.read_text(encoding="utf-8"))

    def build_storyboard_values(self, project_id: str, episode_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        episode = self.get_episode(project_id, episode_id)
        characters = self.list_characters(project_id)
        styles = self.list_styles(project_id)
        style = next((item for item in styles if item["style_id"] == project["default_style_id"]), styles[0] if styles else {})
        protagonist = "；".join(
            part
            for part in [
                characters[0].get("name", "") if characters else "",
                characters[0].get("role", "") if characters else "",
                characters[0].get("appearance", "") if characters else "",
                characters[0].get("prompt_fragment", "") if characters else "",
            ]
            if part
        )
        style_preset = style.get("style_id") or project.get("default_style_id") or "clean_anime_drama"
        style_prompt = style.get("base_prompt", "")
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
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_project_library -v
```

Expected: pass.

---

### Task 4: Project API Endpoints

**Files:**

- Modify: `anime_workflow/launcher/server.py`
- Test: `tests/test_launcher_server.py` or `tests/test_project_library.py`

- [ ] **Step 1: Add failing route-helper test**

Modify the import in `tests/test_launcher_server.py`:

```python
from anime_workflow.launcher.server import project_id_from_api_path, static_file_for_request
```

Add this method inside `LauncherServerTest`:

```python
    def test_project_id_from_api_path_extracts_nested_resource(self):
        self.assertEqual(project_id_from_api_path("/api/projects/demo/characters"), "demo")
        self.assertEqual(project_id_from_api_path("/api/projects/demo/episodes/episode_001/video"), "demo")
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_launcher_server -v
```

Expected: fail because `project_id_from_api_path` does not exist.

- [ ] **Step 3: Add routing helper and store path**

Modify `anime_workflow/launcher/server.py` imports:

```python
from anime_workflow.projects.store import ProjectStore
```

Add constants and helper:

```python
PROJECTS_DIR = PROJECT_ROOT / "data/projects"


def project_id_from_api_path(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if len(parts) < 3 or parts[0] != "api" or parts[1] != "projects":
        return ""
    return unquote(parts[2])
```

Add property to `LauncherRequestHandler`:

```python
    @property
    def project_store(self) -> ProjectStore:
        return ProjectStore(PROJECTS_DIR)
```

- [ ] **Step 4: Implement GET endpoints**

In `do_GET`, before static file handling:

```python
        if parsed.path == "/api/projects":
            self._json({"ok": True, "projects": self.project_store.list_projects()})
            return
        if parsed.path.startswith("/api/projects/"):
            self._handle_project_get(parsed.path)
            return
        if parsed.path == "/api/outputs":
            self._json({"ok": True, "outputs": self.project_store.list_outputs(PROJECT_ROOT / "data/exports")})
            return
```

Add method:

```python
    def _handle_project_get(self, path: str) -> None:
        project_id = project_id_from_api_path(path)
        suffix = path.split(f"/api/projects/{project_id}", 1)[1].strip("/")
        if suffix == "":
            self._json({"ok": True, "project": self.project_store.get_project(project_id)})
            return
        if suffix == "characters":
            self._json({"ok": True, "characters": self.project_store.list_characters(project_id)})
            return
        if suffix == "styles":
            self._json({"ok": True, "styles": self.project_store.list_styles(project_id)})
            return
        if suffix == "episodes":
            self._json({"ok": True, "episodes": self.project_store.list_episodes(project_id)})
            return
        self.send_error(HTTPStatus.NOT_FOUND)
```

- [ ] **Step 5: Implement POST endpoints**

In `do_POST`, before existing `/api/episode/*` handlers:

```python
        if parsed.path == "/api/projects":
            self._handle_project_save()
            return
        if parsed.path.startswith("/api/projects/"):
            self._handle_project_post(parsed.path)
            return
```

Add methods:

```python
    def _handle_project_save(self) -> None:
        try:
            self._json({"ok": True, "project": self.project_store.save_project(self._read_json())})
        except Exception as exc:
            self._json_error(exc)

    def _handle_project_post(self, path: str) -> None:
        try:
            body = self._read_json()
            project_id = project_id_from_api_path(path)
            suffix = path.split(f"/api/projects/{project_id}", 1)[1].strip("/")
            if suffix == "":
                payload = dict(body)
                payload["project_id"] = project_id
                self._json({"ok": True, "project": self.project_store.save_project(payload)})
                return
            if suffix == "characters":
                self._json({"ok": True, "character": self.project_store.save_character(project_id, body)})
                return
            if suffix == "styles":
                self._json({"ok": True, "style": self.project_store.save_style(project_id, body)})
                return
            if suffix == "episodes/batch":
                self._json({"ok": True, "episodes": self.project_store.create_episode_batch(project_id, body)})
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._json_error(exc)
```

- [ ] **Step 6: Run server tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_launcher_server tests.test_project_library -v
```

Expected: pass.

---

### Task 5: Project-Scoped Production Endpoints

**Files:**

- Modify: `anime_workflow/launcher/server.py`
- Modify: `anime_workflow/projects/store.py`
- Test: `tests/test_project_library.py`

- [ ] **Step 1: Add store status update tests**

Add:

```python
    def test_update_episode_status_preserves_existing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project({"project_id": "demo", "name": "示例项目"})
            episode = store.save_episode("demo", {"episode_no": 1})

            updated = store.update_episode("demo", episode["episode_id"], {"status": "exported", "video_path": "data/exports/demo.mp4"})

            self.assertEqual(updated["episode_no"], 1)
            self.assertEqual(updated["status"], "exported")
            self.assertEqual(updated["video_path"], "data/exports/demo.mp4")
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_project_library.ProjectLibraryTest.test_update_episode_status_preserves_existing_fields -v
```

Expected: fail with missing `update_episode`.

- [ ] **Step 3: Implement status update**

Append to `ProjectStore`:

```python
    def update_episode(self, project_id: str, episode_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        existing = self.get_episode(project_id, episode_id)
        merged = dict(existing)
        merged.update(updates)
        merged["episode_id"] = existing["episode_id"]
        merged["episode_no"] = existing["episode_no"]
        return self.save_episode(project_id, merged)
```

- [ ] **Step 4: Add production POST routes**

Extend `_handle_project_post` in `anime_workflow/launcher/server.py` before the final 404:

```python
            if suffix.startswith("episodes/") and suffix.endswith("/storyboard"):
                episode_id = suffix.split("/")[1]
                values = self.project_store.build_storyboard_values(project_id, episode_id)
                storyboard = generate_storyboard(values)
                path = save_storyboard(storyboard, STORYBOARD_DIR)
                episode = self.project_store.update_episode(project_id, episode_id, {"status": "storyboarded", "storyboard_path": str(path), "error": ""})
                self._json({"ok": True, "storyboard": storyboard, "episode": episode, "storyboard_path": str(path)})
                return
            if suffix.startswith("episodes/") and suffix.endswith("/images"):
                episode_id = suffix.split("/")[1]
                storyboard_file = storyboard_path(STORYBOARD_DIR, project_id, episode_id)
                storyboard = load_storyboard(storyboard_file)
                provider = MockAnimeProvider() if str(body.get("provider") or "mock").lower() != "openai" else OpenAIImageProvider(
                    api_key=self.config_store.load().get("openai_api_key", ""),
                    model=self.config_store.load().get("openai_image_model", "gpt-image-2"),
                    endpoint=self.config_store.load().get("openai_base_url", "https://aigate.zhixingjidian.cn"),
                )
                updated = generate_episode_images(
                    storyboard=storyboard,
                    provider=provider,
                    source_dir=PROJECT_ROOT / "data/assets/source_frames",
                    output_dir=PROJECT_ROOT / "data/assets/anime_frames",
                    metadata_dir=PROJECT_ROOT / "data/assets/api_metadata",
                )
                saved = save_storyboard(updated, STORYBOARD_DIR)
                episode = self.project_store.update_episode(project_id, episode_id, {"status": "imaged", "storyboard_path": str(saved), "error": ""})
                self._json({"ok": True, "storyboard": updated, "episode": episode, "storyboard_path": str(saved), "provider": provider.name})
                return
            if suffix.startswith("episodes/") and suffix.endswith("/video"):
                episode_id = suffix.split("/")[1]
                storyboard = load_storyboard(storyboard_path(STORYBOARD_DIR, project_id, episode_id))
                video = export_episode_video(storyboard, PROJECT_ROOT / "data/exports")
                storyboard["video_path"] = str(video)
                save_storyboard(storyboard, STORYBOARD_DIR)
                episode = self.project_store.update_episode(project_id, episode_id, {"status": "exported", "video_path": str(video), "error": ""})
                self._json({"ok": True, "video_path": str(video), "storyboard": storyboard, "episode": episode})
                return
```

- [ ] **Step 5: Run tests**

Run:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Expected: all tests pass.

---

### Task 6: Outputs Summary

**Files:**

- Modify: `anime_workflow/projects/store.py`
- Test: `tests/test_project_library.py`

- [ ] **Step 1: Add failing output listing test**

Add:

```python
    def test_list_outputs_returns_exported_videos(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exports = root / "exports"
            exports.mkdir()
            video = exports / "demo-episode_001.mp4"
            video.write_bytes(b"video")
            store = ProjectStore(root / "projects")

            outputs = store.list_outputs(exports)

            self.assertEqual(outputs[0]["filename"], "demo-episode_001.mp4")
            self.assertEqual(outputs[0]["video_path"], str(video))
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_project_library.ProjectLibraryTest.test_list_outputs_returns_exported_videos -v
```

Expected: fail with missing `list_outputs`.

- [ ] **Step 3: Implement output listing**

Append to `ProjectStore`:

```python
    def list_outputs(self, exports_dir: Path) -> list[dict[str, Any]]:
        exports_dir = Path(exports_dir)
        outputs: list[dict[str, Any]] = []
        for path in sorted(exports_dir.glob("*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True):
            outputs.append(
                {
                    "filename": path.name,
                    "video_path": str(path),
                    "size_bytes": path.stat().st_size,
                    "updated_at": path.stat().st_mtime,
                }
            )
        return outputs
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_project_library -v
```

Expected: pass.

---

### Task 7: Frontend API Types

**Files:**

- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add project library types**

Add below `EpisodeResponse`:

```typescript
export type Project = {
  project_id: string;
  name: string;
  genre: string;
  platform: string;
  premise: string;
  default_duration_seconds: number;
  default_shot_count: number;
  default_style_id: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Character = {
  character_id: string;
  project_id: string;
  name: string;
  role: string;
  appearance: string;
  personality: string;
  costume: string;
  reference_image: string;
  prompt_fragment: string;
};

export type StyleTemplate = {
  style_id: string;
  project_id: string;
  name: string;
  base_prompt: string;
  negative_prompt: string;
  aspect_ratio: string;
  palette: string;
  camera_style: string;
  provider: string;
};

export type ProjectEpisode = {
  episode_id: string;
  project_id: string;
  episode_no: number;
  title: string;
  premise: string;
  duration_seconds: number;
  shot_count: number;
  status: "draft" | "storyboarded" | "imaged" | "exported" | "failed";
  storyboard_path: string;
  video_path: string;
  error: string;
};

export type OutputItem = {
  filename: string;
  video_path: string;
  size_bytes: number;
  updated_at: number;
};
```

- [ ] **Step 2: Improve error parsing**

Replace the `if (!response.ok)` block in `request<T>` with:

```typescript
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const data = (await response.json()) as { error?: string };
      if (data.error) detail = data.error;
    } catch {
      // Keep the HTTP status text when the response is not JSON.
    }
    throw new Error(detail);
  }
```

- [ ] **Step 3: Add API functions**

Add to `api`:

```typescript
  listProjects: () => request<{ ok: boolean; projects: Project[] }>("/api/projects"),
  saveProject: (project: Partial<Project>) =>
    request<{ ok: boolean; project: Project }>("/api/projects", { method: "POST", body: JSON.stringify(project) }),
  listCharacters: (projectId: string) =>
    request<{ ok: boolean; characters: Character[] }>(`/api/projects/${encodeURIComponent(projectId)}/characters`),
  saveCharacter: (projectId: string, character: Partial<Character>) =>
    request<{ ok: boolean; character: Character }>(`/api/projects/${encodeURIComponent(projectId)}/characters`, {
      method: "POST",
      body: JSON.stringify(character),
    }),
  listStyles: (projectId: string) =>
    request<{ ok: boolean; styles: StyleTemplate[] }>(`/api/projects/${encodeURIComponent(projectId)}/styles`),
  saveStyle: (projectId: string, style: Partial<StyleTemplate>) =>
    request<{ ok: boolean; style: StyleTemplate }>(`/api/projects/${encodeURIComponent(projectId)}/styles`, {
      method: "POST",
      body: JSON.stringify(style),
    }),
  listProjectEpisodes: (projectId: string) =>
    request<{ ok: boolean; episodes: ProjectEpisode[] }>(`/api/projects/${encodeURIComponent(projectId)}/episodes`),
  createEpisodeBatch: (projectId: string, count: number, direction: string) =>
    request<{ ok: boolean; episodes: ProjectEpisode[] }>(`/api/projects/${encodeURIComponent(projectId)}/episodes/batch`, {
      method: "POST",
      body: JSON.stringify({ count, direction }),
    }),
  listOutputs: () => request<{ ok: boolean; outputs: OutputItem[] }>("/api/outputs"),
```

- [ ] **Step 4: Run frontend typecheck**

Run:

```bash
cd frontend && npm run build
```

Expected: build succeeds.

---

### Task 8: Frontend Project Library UI

**Files:**

- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add navigation entries**

Update `navItems`:

```typescript
const navItems = [
  { value: "overview", label: "总览", icon: Activity },
  { value: "projects", label: "项目库", icon: Clapperboard },
  { value: "characters", label: "角色库", icon: Bot },
  { value: "styles", label: "风格模板", icon: Image },
  { value: "episode-studio", label: "剧集生产", icon: Clapperboard },
  { value: "outputs", label: "成品库", icon: Video },
  { value: "services", label: "服务启动", icon: Server },
  { value: "config", label: "API 配置", icon: KeyRound },
  { value: "image-test", label: "图片测试", icon: Image },
  { value: "video-test", label: "视频测试", icon: Video },
] as const;
```

- [ ] **Step 2: Add project state**

Import new types from `api.ts` and add state:

```typescript
const [projects, setProjects] = useState<Project[]>([]);
const [currentProjectId, setCurrentProjectId] = useState("demo_drama");
const [characters, setCharacters] = useState<Character[]>([]);
const [styles, setStyles] = useState<StyleTemplate[]>([]);
const [projectEpisodes, setProjectEpisodes] = useState<ProjectEpisode[]>([]);
const [outputs, setOutputs] = useState<OutputItem[]>([]);
const [projectDraft, setProjectDraft] = useState({
  project_id: "demo_drama",
  name: "雨夜侦探",
  genre: "悬疑",
  platform: "douyin",
  premise: "雨夜主角收到匿名信，发现失踪案和自己有关",
  default_duration_seconds: 30,
  default_shot_count: 6,
  default_style_id: "clean_anime_drama",
});
const [characterDraft, setCharacterDraft] = useState({
  character_id: "hero",
  name: "林夏",
  role: "年轻侦探",
  appearance: "黑发，蓝色风衣，冷静敏锐",
  personality: "克制、观察力强",
  costume: "蓝色风衣",
});
const [styleDraft, setStyleDraft] = useState({
  style_id: "clean_anime_drama",
  name: "干净动漫短剧",
  base_prompt: "clean anime drama, cinematic lighting, vertical composition",
  negative_prompt: "low quality, blurry, inconsistent character",
  aspect_ratio: "9:16",
});
const [batchCount, setBatchCount] = useState(10);
const [batchDirection, setBatchDirection] = useState("每集一个线索，结尾留下反转");
```

- [ ] **Step 3: Add refresh helpers**

Add:

```typescript
const refreshProjectLibrary = async (projectId = currentProjectId) => {
  const [projectData, outputData] = await Promise.all([api.listProjects(), api.listOutputs()]);
  setProjects(projectData.projects);
  setOutputs(outputData.outputs);
  if (projectId) {
    const [characterData, styleData, episodeData] = await Promise.all([
      api.listCharacters(projectId).catch(() => ({ characters: [] })),
      api.listStyles(projectId).catch(() => ({ styles: [] })),
      api.listProjectEpisodes(projectId).catch(() => ({ episodes: [] })),
    ]);
    setCharacters(characterData.characters);
    setStyles(styleData.styles);
    setProjectEpisodes(episodeData.episodes);
  }
};
```

Call it in the initial `useEffect` after `refreshStatus()`:

```typescript
refreshProjectLibrary().catch(() => undefined);
```

- [ ] **Step 4: Add action handlers**

Add:

```typescript
const saveProjectDraft = () =>
  runBusy("project-save", async () => {
    const result = await api.saveProject(projectDraft);
    setCurrentProjectId(result.project.project_id);
    setNotice("项目已保存");
    await refreshProjectLibrary(result.project.project_id);
  });

const saveCharacterDraft = () =>
  runBusy("character-save", async () => {
    await api.saveCharacter(currentProjectId, characterDraft);
    setNotice("角色已保存");
    await refreshProjectLibrary(currentProjectId);
  });

const saveStyleDraft = () =>
  runBusy("style-save", async () => {
    await api.saveStyle(currentProjectId, styleDraft);
    setNotice("风格模板已保存");
    await refreshProjectLibrary(currentProjectId);
  });

const createBatchEpisodes = () =>
  runBusy("episode-batch", async () => {
    await api.createEpisodeBatch(currentProjectId, batchCount, batchDirection);
    setNotice("剧集大纲已创建");
    await refreshProjectLibrary(currentProjectId);
  });
```

- [ ] **Step 5: Add tab content**

Add these `Tabs.Content` blocks before the existing `episode-studio` content. Adjust only field wiring if local state names differ from Step 2:

```tsx
          <Tabs.Content value="projects">
            <section className="grid grid-cols-[380px_minmax(0,1fr)] gap-3 max-[980px]:grid-cols-1">
              <Panel title="项目设置" icon={Clapperboard}>
                <div className="grid gap-3">
                  <Field label="项目 ID">
                    <input className="input" value={projectDraft.project_id} onChange={(event) => setProjectDraft({ ...projectDraft, project_id: event.target.value })} />
                  </Field>
                  <Field label="项目名称">
                    <input className="input" value={projectDraft.name} onChange={(event) => setProjectDraft({ ...projectDraft, name: event.target.value })} />
                  </Field>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="题材">
                      <input className="input" value={projectDraft.genre} onChange={(event) => setProjectDraft({ ...projectDraft, genre: event.target.value })} />
                    </Field>
                    <Field label="平台">
                      <select className="input" value={projectDraft.platform} onChange={(event) => setProjectDraft({ ...projectDraft, platform: event.target.value })}>
                        <option value="douyin">抖音</option>
                        <option value="bilibili">B站</option>
                      </select>
                    </Field>
                  </div>
                  <Field label="系列设定">
                    <textarea className="input min-h-[96px] resize-y py-2 leading-6" value={projectDraft.premise} onChange={(event) => setProjectDraft({ ...projectDraft, premise: event.target.value })} />
                  </Field>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="默认时长">
                      <input className="input" type="number" value={projectDraft.default_duration_seconds} onChange={(event) => setProjectDraft({ ...projectDraft, default_duration_seconds: Number(event.target.value) })} />
                    </Field>
                    <Field label="默认分镜">
                      <input className="input" type="number" value={projectDraft.default_shot_count} onChange={(event) => setProjectDraft({ ...projectDraft, default_shot_count: Number(event.target.value) })} />
                    </Field>
                  </div>
                  <Button type="button" onClick={saveProjectDraft} busy={busyAction === "project-save"} icon={Save}>
                    保存项目
                  </Button>
                </div>
              </Panel>
              <Panel title="项目列表" icon={FileText}>
                <div className="grid gap-2">
                  {projects.map((project) => (
                    <button key={project.project_id} type="button" className="rounded-ui border border-line bg-white p-3 text-left hover:bg-slate-50" onClick={() => { setCurrentProjectId(project.project_id); refreshProjectLibrary(project.project_id); }}>
                      <div className="text-sm font-semibold">{project.name}</div>
                      <div className="mt-1 font-mono text-xs text-ink-500">{project.project_id} / {project.genre} / {project.platform}</div>
                    </button>
                  ))}
                </div>
              </Panel>
            </section>
          </Tabs.Content>

          <Tabs.Content value="characters">
            <section className="grid grid-cols-[380px_minmax(0,1fr)] gap-3 max-[980px]:grid-cols-1">
              <Panel title="角色设定" icon={Bot}>
                <div className="grid gap-3">
                  <Field label="角色 ID"><input className="input" value={characterDraft.character_id} onChange={(event) => setCharacterDraft({ ...characterDraft, character_id: event.target.value })} /></Field>
                  <Field label="姓名"><input className="input" value={characterDraft.name} onChange={(event) => setCharacterDraft({ ...characterDraft, name: event.target.value })} /></Field>
                  <Field label="身份"><input className="input" value={characterDraft.role} onChange={(event) => setCharacterDraft({ ...characterDraft, role: event.target.value })} /></Field>
                  <Field label="外观"><textarea className="input min-h-[80px] resize-y py-2 leading-6" value={characterDraft.appearance} onChange={(event) => setCharacterDraft({ ...characterDraft, appearance: event.target.value })} /></Field>
                  <Field label="性格"><textarea className="input min-h-[80px] resize-y py-2 leading-6" value={characterDraft.personality} onChange={(event) => setCharacterDraft({ ...characterDraft, personality: event.target.value })} /></Field>
                  <Button type="button" onClick={saveCharacterDraft} busy={busyAction === "character-save"} icon={Save}>保存角色</Button>
                </div>
              </Panel>
              <Panel title="当前项目角色" icon={FileText}>
                <div className="grid gap-2">
                  {characters.map((character) => (
                    <article key={character.character_id} className="rounded-ui border border-line bg-white p-3">
                      <div className="text-sm font-semibold">{character.name}</div>
                      <div className="mt-1 text-xs text-ink-500">{character.role}</div>
                      <div className="mt-2 text-sm leading-6">{character.appearance}</div>
                    </article>
                  ))}
                </div>
              </Panel>
            </section>
          </Tabs.Content>

          <Tabs.Content value="styles">
            <section className="grid grid-cols-[380px_minmax(0,1fr)] gap-3 max-[980px]:grid-cols-1">
              <Panel title="风格模板" icon={Image}>
                <div className="grid gap-3">
                  <Field label="模板 ID"><input className="input" value={styleDraft.style_id} onChange={(event) => setStyleDraft({ ...styleDraft, style_id: event.target.value })} /></Field>
                  <Field label="名称"><input className="input" value={styleDraft.name} onChange={(event) => setStyleDraft({ ...styleDraft, name: event.target.value })} /></Field>
                  <Field label="基础 Prompt"><textarea className="input min-h-[96px] resize-y py-2 leading-6" value={styleDraft.base_prompt} onChange={(event) => setStyleDraft({ ...styleDraft, base_prompt: event.target.value })} /></Field>
                  <Field label="负面 Prompt"><textarea className="input min-h-[80px] resize-y py-2 leading-6" value={styleDraft.negative_prompt} onChange={(event) => setStyleDraft({ ...styleDraft, negative_prompt: event.target.value })} /></Field>
                  <Button type="button" onClick={saveStyleDraft} busy={busyAction === "style-save"} icon={Save}>保存模板</Button>
                </div>
              </Panel>
              <Panel title="当前项目模板" icon={FileText}>
                <div className="grid gap-2">
                  {styles.map((style) => (
                    <article key={style.style_id} className="rounded-ui border border-line bg-white p-3">
                      <div className="text-sm font-semibold">{style.name}</div>
                      <div className="mt-1 font-mono text-xs text-ink-500">{style.style_id} / {style.aspect_ratio}</div>
                      <div className="mt-2 break-all font-mono text-xs leading-5 text-ink-600">{style.base_prompt}</div>
                    </article>
                  ))}
                </div>
              </Panel>
            </section>
          </Tabs.Content>

          <Tabs.Content value="outputs">
            <Panel title="成品库" icon={Video}>
              <div className="grid gap-2">
                {outputs.map((item) => (
                  <article key={item.video_path} className="rounded-ui border border-line bg-white p-3">
                    <div className="text-sm font-semibold">{item.filename}</div>
                    <div className="mt-1 break-all font-mono text-xs text-ink-500">{item.video_path}</div>
                  </article>
                ))}
              </div>
            </Panel>
          </Tabs.Content>
```

- [ ] **Step 6: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: build succeeds and `web/launcher` updates.

---

### Task 9: Manual End-To-End Verification

**Files:**

- No code changes unless verification finds a defect.

- [ ] **Step 1: Start launcher**

Run:

```bash
.venv/bin/python scripts/start_launcher.py
```

Expected: service available at `http://127.0.0.1:7860`.

- [ ] **Step 2: Verify backend API manually**

Run:

```bash
curl -sS http://127.0.0.1:7860/api/status
curl -sS -X POST http://127.0.0.1:7860/api/projects -H 'Content-Type: application/json' -d '{"project_id":"demo_drama","name":"雨夜侦探","genre":"悬疑","platform":"douyin","premise":"匿名信连环案"}'
curl -sS http://127.0.0.1:7860/api/projects
```

Expected:

- `/api/status` returns JSON.
- Project POST returns `"ok": true`.
- Project list includes `demo_drama`.

- [ ] **Step 3: Verify browser flow**

Open `http://127.0.0.1:7860` and verify:

- `项目库` can save a project.
- `角色库` can save a character for current project.
- `风格模板` can save a style for current project.
- `剧集生产` can create 3 draft episodes.
- Existing single-episode generation still works.
- `成品库` lists exported MP4 files.

- [ ] **Step 4: Run full verification**

Run:

```bash
.venv/bin/python -m unittest discover -s tests -v
cd frontend && npm run build
```

Expected:

- Python tests pass.
- Frontend build passes.

---

## Self-Review Checklist

- Spec coverage: project library, character library, style templates, episode list, batch creation, output library, local JSON storage, and project-scoped APIs are covered.
- Deferred scope: automatic publishing, crawler resources, ComfyUI video workflows, and background queues stay out of first implementation.
- Compatibility: current `/api/episode/*` and existing output paths remain intact.
- Testing: backend TDD is explicit; frontend verification uses TypeScript build plus manual browser flow.
- Current workspace note: this directory is not a git repository. Skip commit steps unless a git repository is initialized before implementation.
