# Batch Job Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local persisted batch-production job queue so selected project episodes can run storyboard, image, and video production in order without blocking the UI or accidentally consuming real image API credits.

**Architecture:** Add a JSON-backed `anime_workflow/jobs/` package with a focused store and a single-worker runner. The launcher exposes `/api/jobs*` endpoints and starts the runner after job creation. The React UI adds episode selection, queue creation controls, OpenAI confirmation, and queue status polling inside the existing workbench.

**Tech Stack:** Python standard library, `unittest`, local JSON files, `ThreadingHTTPServer`, React, TypeScript, Vite, existing launcher APIs and production helpers.

---

## File Structure

Create:

- `anime_workflow/jobs/__init__.py` - package exports.
- `anime_workflow/jobs/models.py` - job defaults, validation, timestamps, slug checks.
- `anime_workflow/jobs/store.py` - JSON job repository under `data/jobs`.
- `anime_workflow/jobs/runner.py` - single-worker job execution logic.
- `tests/test_job_queue.py` - unit tests for job store and runner.

Modify:

- `anime_workflow/launcher/server.py` - add `/api/jobs*` endpoints and process-local runner wiring.
- `tests/test_launcher_server.py` - HTTP tests for job APIs.
- `frontend/src/api.ts` - add job types and API functions.
- `frontend/src/App.tsx` - add selected episode checkboxes, batch queue controls, queue panel, and polling.

Keep:

- Existing synchronous `/api/projects/{project_id}/episodes/{episode_id}/storyboard|images|video` endpoints.
- Existing project library JSON layout under `data/projects`.
- Existing output listing under `/api/outputs`.

---

### Task 1: Job Models And Store

**Files:**

- Create: `anime_workflow/jobs/__init__.py`
- Create: `anime_workflow/jobs/models.py`
- Create: `anime_workflow/jobs/store.py`
- Test: `tests/test_job_queue.py`

- [ ] **Step 1: Write failing tests for job creation, validation, full-step expansion, cancellation, and retry**

Create `tests/test_job_queue.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from anime_workflow.jobs.store import JobStore


class JobQueueStoreTest(unittest.TestCase):
    def test_create_job_writes_json_and_lists_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "jobs")

            first = store.create_job(
                {
                    "project_id": "demo_drama",
                    "episode_ids": ["episode_001"],
                    "steps": ["storyboard"],
                    "provider": "mock",
                }
            )
            second = store.create_job(
                {
                    "project_id": "demo_drama",
                    "episode_ids": ["episode_002"],
                    "steps": ["full"],
                    "provider": "mock",
                }
            )

            self.assertTrue(first["job_id"].startswith("job_"))
            self.assertEqual(first["status"], "queued")
            self.assertEqual(first["total_steps"], 1)
            self.assertEqual(second["steps"], ["storyboard", "images", "video"])
            self.assertEqual(second["total_steps"], 3)
            self.assertTrue((Path(tmp) / f"jobs/{first['job_id']}.json").exists())
            self.assertEqual([item["job_id"] for item in store.list_jobs()], [second["job_id"], first["job_id"]])

    def test_create_job_rejects_invalid_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "jobs")

            with self.assertRaisesRegex(ValueError, "project_id is required"):
                store.create_job({"project_id": "", "episode_ids": ["episode_001"], "steps": ["storyboard"], "provider": "mock"})
            with self.assertRaisesRegex(ValueError, "episode_ids is required"):
                store.create_job({"project_id": "demo", "episode_ids": [], "steps": ["storyboard"], "provider": "mock"})
            with self.assertRaisesRegex(ValueError, "provider must be mock or openai"):
                store.create_job({"project_id": "demo", "episode_ids": ["episode_001"], "steps": ["storyboard"], "provider": "bad"})
            with self.assertRaisesRegex(ValueError, "invalid step"):
                store.create_job({"project_id": "demo", "episode_ids": ["episode_001"], "steps": ["bad"], "provider": "mock"})

    def test_update_progress_cancel_and_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "jobs")
            job = store.create_job(
                {
                    "project_id": "demo_drama",
                    "episode_ids": ["episode_001", "episode_002"],
                    "steps": ["storyboard", "images"],
                    "provider": "mock",
                }
            )

            running = store.update_job(
                job["job_id"],
                {
                    "status": "running",
                    "current_episode_id": "episode_001",
                    "current_step": "images",
                    "completed_steps": 1,
                    "progress": 25,
                    "started_at": "2026-06-04T00:00:00+00:00",
                },
            )
            cancelled = store.request_cancel(job["job_id"])
            failed = store.update_job(job["job_id"], {"status": "failed", "error": "boom"})
            retried = store.retry_job(job["job_id"])

            self.assertEqual(running["current_step"], "images")
            self.assertTrue(cancelled["cancel_requested"])
            self.assertEqual(failed["status"], "failed")
            self.assertNotEqual(retried["job_id"], job["job_id"])
            self.assertEqual(retried["status"], "queued")
            self.assertEqual(retried["episode_ids"], ["episode_001", "episode_002"])
            self.assertEqual(retried["steps"], ["storyboard", "images"])

    def test_get_job_rejects_non_object_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            job_path = Path(tmp) / "jobs/job_bad.json"
            job_path.parent.mkdir(parents=True)
            job_path.write_text(json.dumps([]), encoding="utf-8")
            store = JobStore(Path(tmp) / "jobs")

            with self.assertRaisesRegex(ValueError, "job json must be an object"):
                store.get_job("job_bad")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m unittest tests.test_job_queue -v
```

Expected: fail with `ModuleNotFoundError: No module named 'anime_workflow.jobs'`.

- [ ] **Step 3: Implement job models**

Create `anime_workflow/jobs/__init__.py`:

```python
from anime_workflow.jobs.runner import JobRunner
from anime_workflow.jobs.store import JobStore

__all__ = ["JobRunner", "JobStore"]
```

Create `anime_workflow/jobs/models.py`:

```python
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from anime_workflow.projects.models import slug


VALID_STEPS = {"storyboard", "images", "video"}
VALID_STATUSES = {"queued", "running", "completed", "failed", "cancelled"}
VALID_PROVIDERS = {"mock", "openai"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"job_{stamp}_{secrets.token_hex(3)}"


def normalize_steps(values: Any) -> list[str]:
    raw = values if isinstance(values, list) else []
    if not raw:
        raise ValueError("steps is required")
    if "full" in raw:
        if len(raw) != 1:
            raise ValueError("full must be the only step when used")
        return ["storyboard", "images", "video"]
    steps = [str(item).strip() for item in raw]
    invalid = [item for item in steps if item not in VALID_STEPS]
    if invalid:
        raise ValueError(f"invalid step: {invalid[0]}")
    return steps


def normalize_episode_ids(values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ValueError("episode_ids is required")
    episode_ids: list[str] = []
    for item in values:
        episode_id = str(item or "").strip()
        if not episode_id:
            raise ValueError("episode_id is required")
        if episode_id != slug(episode_id, ""):
            raise ValueError("episode_id is invalid")
        episode_ids.append(episode_id)
    return episode_ids


def job_from(values: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    project_id = str(values.get("project_id") or existing.get("project_id") or "").strip()
    if not project_id:
        raise ValueError("project_id is required")
    if project_id != slug(project_id, ""):
        raise ValueError("project_id is invalid")
    episode_ids = normalize_episode_ids(values.get("episode_ids", existing.get("episode_ids", [])))
    steps = normalize_steps(values.get("steps", existing.get("steps", [])))
    provider = str(values.get("provider") or existing.get("provider") or "mock").strip().lower()
    if provider not in VALID_PROVIDERS:
        raise ValueError("provider must be mock or openai")
    status = str(values.get("status") or existing.get("status") or "queued").strip()
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid job status: {status}")
    total_steps = len(episode_ids) * len(steps)
    completed_steps = clamp_int(values.get("completed_steps", existing.get("completed_steps", 0)), 0, total_steps, 0)
    progress = clamp_int(values.get("progress", existing.get("progress", 0)), 0, 100, 0)
    created_at = existing.get("created_at") or values.get("created_at") or now_iso()
    return {
        "job_id": str(existing.get("job_id") or values.get("job_id") or job_id()),
        "project_id": project_id,
        "episode_ids": episode_ids,
        "steps": steps,
        "provider": provider,
        "status": status,
        "current_episode_id": str(values.get("current_episode_id", existing.get("current_episode_id", ""))),
        "current_step": str(values.get("current_step", existing.get("current_step", ""))),
        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "progress": progress,
        "error": str(values.get("error", existing.get("error", ""))),
        "created_at": created_at,
        "started_at": str(values.get("started_at", existing.get("started_at", ""))),
        "finished_at": str(values.get("finished_at", existing.get("finished_at", ""))),
        "cancel_requested": bool(values.get("cancel_requested", existing.get("cancel_requested", False))),
        "updated_at": now_iso(),
    }


def clamp_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))
```

- [ ] **Step 4: Implement job store**

Create `anime_workflow/jobs/store.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from anime_workflow.jobs.models import job_from, now_iso
from anime_workflow.projects.models import slug


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    item = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(item, dict):
        raise ValueError(f"{label} json must be an object: {path}")
    return item


class JobStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def job_path(self, job_id: str) -> Path:
        return self.root / f"{slug(job_id, 'job')}.json"

    def create_job(self, values: dict[str, Any]) -> dict[str, Any]:
        job = job_from(values)
        self._write_job(job)
        return job

    def get_job(self, job_id: str) -> dict[str, Any]:
        path = self.job_path(job_id)
        if not path.exists():
            raise FileNotFoundError(f"job not found: {slug(job_id, 'job')}")
        return load_json_object(path, "job")

    def list_jobs(self) -> list[dict[str, Any]]:
        jobs = [load_json_object(path, "job") for path in self.root.glob("job_*.json")]
        return sorted(jobs, key=lambda item: item.get("created_at", ""), reverse=True)

    def queued_jobs_oldest_first(self) -> list[dict[str, Any]]:
        jobs = [item for item in self.list_jobs() if item.get("status") == "queued" and not item.get("cancel_requested")]
        return sorted(jobs, key=lambda item: item.get("created_at", ""))

    def update_job(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        existing = self.get_job(job_id)
        merged = dict(existing)
        merged.update(updates)
        merged["job_id"] = existing["job_id"]
        job = job_from(merged, existing)
        if job["status"] in {"completed", "failed", "cancelled"} and not job["finished_at"]:
            job["finished_at"] = now_iso()
        self._write_job(job)
        return job

    def request_cancel(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        if job["status"] == "queued":
            return self.update_job(job_id, {"status": "cancelled", "cancel_requested": True, "progress": job["progress"]})
        return self.update_job(job_id, {"cancel_requested": True})

    def retry_job(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        if job["status"] not in {"failed", "cancelled"}:
            raise ValueError("only failed or cancelled jobs can be retried")
        return self.create_job(
            {
                "project_id": job["project_id"],
                "episode_ids": job["episode_ids"],
                "steps": job["steps"],
                "provider": job["provider"],
            }
        )

    def _write_job(self, job: dict[str, Any]) -> None:
        path = self.job_path(job["job_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 5: Run store tests and verify they pass**

Run:

```bash
.venv/bin/python -m unittest tests.test_job_queue -v
```

Expected: 4 tests pass.

---

### Task 2: Job Runner

**Files:**

- Modify: `anime_workflow/jobs/runner.py`
- Test: `tests/test_job_queue.py`

- [ ] **Step 1: Add failing tests for runner success, OpenAI missing key, and cancellation**

Append to `tests/test_job_queue.py`:

```python
from anime_workflow.jobs.runner import JobRunner
from anime_workflow.projects.store import ProjectStore


class JobRunnerTest(unittest.TestCase):
    def create_project_with_episode(self, root: Path) -> tuple[JobStore, ProjectStore]:
        project_store = ProjectStore(root / "projects")
        project_store.save_project(
            {
                "project_id": "demo_drama",
                "name": "雨夜侦探",
                "genre": "悬疑",
                "premise": "匿名信",
                "default_duration_seconds": 3,
                "default_shot_count": 1,
                "default_style_id": "clean_anime_drama",
            }
        )
        project_store.save_character("demo_drama", {"character_id": "hero", "name": "林夏"})
        project_store.save_style("demo_drama", {"style_id": "clean_anime_drama", "name": "干净动漫", "base_prompt": "clean anime"})
        project_store.save_episode("demo_drama", {"episode_id": "episode_001", "episode_no": 1})
        return JobStore(root / "jobs"), project_store

    def test_runner_completes_mock_full_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_store, project_store = self.create_project_with_episode(root)
            job = job_store.create_job(
                {
                    "project_id": "demo_drama",
                    "episode_ids": ["episode_001"],
                    "steps": ["full"],
                    "provider": "mock",
                }
            )

            def fake_generate_images(storyboard, provider, source_dir, output_dir, metadata_dir):
                updated = dict(storyboard)
                updated["shots"] = [dict(shot) for shot in storyboard["shots"]]
                image = root / "image.png"
                image.write_bytes(b"image")
                updated["shots"][0]["anime_image"] = str(image)
                return updated

            def fake_export_video(storyboard, output_dir):
                video = Path(output_dir) / f"{storyboard['project_id']}-{storyboard['episode_id']}.mp4"
                video.parent.mkdir(parents=True, exist_ok=True)
                video.write_bytes(b"video")
                return video

            runner = JobRunner(
                job_store=job_store,
                project_store=project_store,
                storyboard_dir=root / "storyboards",
                source_dir=root / "source",
                image_dir=root / "images",
                metadata_dir=root / "metadata",
                output_dir=root / "exports",
                config_loader=lambda: {"openai_api_key": "", "openai_image_model": "gpt-image-2", "openai_base_url": "https://example.invalid"},
                generate_images=fake_generate_images,
                export_video=fake_export_video,
            )

            runner.run_next_job()

            completed = job_store.get_job(job["job_id"])
            episode = project_store.get_episode("demo_drama", "episode_001")
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["completed_steps"], 3)
            self.assertEqual(completed["progress"], 100)
            self.assertEqual(episode["status"], "exported")
            self.assertTrue(episode["video_path"].endswith("demo_drama-episode_001.mp4"))

    def test_runner_fails_openai_without_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_store, project_store = self.create_project_with_episode(root)
            job = job_store.create_job(
                {
                    "project_id": "demo_drama",
                    "episode_ids": ["episode_001"],
                    "steps": ["storyboard", "images"],
                    "provider": "openai",
                }
            )
            runner = JobRunner(
                job_store=job_store,
                project_store=project_store,
                storyboard_dir=root / "storyboards",
                source_dir=root / "source",
                image_dir=root / "images",
                metadata_dir=root / "metadata",
                output_dir=root / "exports",
                config_loader=lambda: {"openai_api_key": "", "openai_image_model": "gpt-image-2", "openai_base_url": "https://example.invalid"},
            )

            runner.run_next_job()

            failed = job_store.get_job(job["job_id"])
            episode = project_store.get_episode("demo_drama", "episode_001")
            self.assertEqual(failed["status"], "failed")
            self.assertIn("OpenAI API Key is not configured", failed["error"])
            self.assertEqual(episode["status"], "failed")

    def test_runner_respects_cancel_request_between_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_store, project_store = self.create_project_with_episode(root)
            job = job_store.create_job(
                {
                    "project_id": "demo_drama",
                    "episode_ids": ["episode_001"],
                    "steps": ["storyboard", "images"],
                    "provider": "mock",
                }
            )

            def cancel_after_storyboard(job_id: str) -> None:
                job_store.request_cancel(job_id)

            runner = JobRunner(
                job_store=job_store,
                project_store=project_store,
                storyboard_dir=root / "storyboards",
                source_dir=root / "source",
                image_dir=root / "images",
                metadata_dir=root / "metadata",
                output_dir=root / "exports",
                config_loader=lambda: {"openai_api_key": "", "openai_image_model": "gpt-image-2", "openai_base_url": "https://example.invalid"},
                after_step=cancel_after_storyboard,
            )

            runner.run_next_job()

            cancelled = job_store.get_job(job["job_id"])
            self.assertEqual(cancelled["status"], "cancelled")
            self.assertEqual(cancelled["completed_steps"], 1)
```

- [ ] **Step 2: Run runner tests and verify they fail**

Run:

```bash
.venv/bin/python -m unittest tests.test_job_queue.JobRunnerTest -v
```

Expected: fail with `ModuleNotFoundError` or missing `anime_workflow.jobs.runner`.

- [ ] **Step 3: Implement job runner**

Create `anime_workflow/jobs/runner.py`:

```python
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable

from anime_workflow.jobs.models import now_iso
from anime_workflow.jobs.store import JobStore
from anime_workflow.projects.store import ProjectStore
from anime_workflow.services.anime_api_adapter import MockAnimeProvider, OpenAIImageProvider
from anime_workflow.story.episode_runner import export_episode_video, generate_episode_images
from anime_workflow.story.storyboard import generate_storyboard, load_storyboard, save_storyboard, storyboard_path


class JobRunner:
    def __init__(
        self,
        job_store: JobStore,
        project_store: ProjectStore,
        storyboard_dir: Path,
        source_dir: Path,
        image_dir: Path,
        metadata_dir: Path,
        output_dir: Path,
        config_loader: Callable[[], dict[str, Any]],
        generate_images: Callable[..., dict[str, Any]] = generate_episode_images,
        export_video: Callable[..., Path] = export_episode_video,
        after_step: Callable[[str], None] | None = None,
    ) -> None:
        self.job_store = job_store
        self.project_store = project_store
        self.storyboard_dir = Path(storyboard_dir)
        self.source_dir = Path(source_dir)
        self.image_dir = Path(image_dir)
        self.metadata_dir = Path(metadata_dir)
        self.output_dir = Path(output_dir)
        self.config_loader = config_loader
        self.generate_images = generate_images
        self.export_video = export_video
        self.after_step = after_step
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def ensure_running(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self.run_until_idle, daemon=True)
            self._thread.start()

    def run_until_idle(self) -> None:
        while self.run_next_job():
            continue

    def run_next_job(self) -> bool:
        queued = self.job_store.queued_jobs_oldest_first()
        if not queued:
            return False
        job = queued[0]
        self._run_job(job["job_id"])
        return True

    def _run_job(self, job_id: str) -> None:
        job = self.job_store.update_job(job_id, {"status": "running", "started_at": now_iso(), "error": ""})
        try:
            self._raise_if_cancelled(job)
            for episode_id in job["episode_ids"]:
                for step in job["steps"]:
                    job = self.job_store.get_job(job_id)
                    self._raise_if_cancelled(job)
                    self.job_store.update_job(job_id, {"current_episode_id": episode_id, "current_step": step})
                    self._run_step(job, episode_id, step)
                    updated = self.job_store.get_job(job_id)
                    completed_steps = int(updated["completed_steps"]) + 1
                    progress = round(completed_steps / max(1, int(updated["total_steps"])) * 100)
                    self.job_store.update_job(job_id, {"completed_steps": completed_steps, "progress": progress})
                    if self.after_step:
                        self.after_step(job_id)
            self.job_store.update_job(
                job_id,
                {
                    "status": "completed",
                    "current_episode_id": "",
                    "current_step": "",
                    "progress": 100,
                    "finished_at": now_iso(),
                },
            )
        except JobCancelled:
            self.job_store.update_job(job_id, {"status": "cancelled", "current_step": "", "finished_at": now_iso()})
        except Exception as exc:
            failed = self.job_store.get_job(job_id)
            self._mark_episode_failed(failed.get("project_id", ""), failed.get("current_episode_id", ""), exc)
            self.job_store.update_job(job_id, {"status": "failed", "error": str(exc), "finished_at": now_iso()})

    def _run_step(self, job: dict[str, Any], episode_id: str, step: str) -> None:
        project_id = job["project_id"]
        if step == "storyboard":
            values = self.project_store.build_storyboard_values(project_id, episode_id)
            storyboard = generate_storyboard(values)
            path = save_storyboard(storyboard, self.storyboard_dir)
            self.project_store.update_episode(project_id, episode_id, {"status": "storyboarded", "storyboard_path": str(path), "error": ""})
            return
        if step == "images":
            storyboard = load_storyboard(storyboard_path(self.storyboard_dir, project_id, episode_id))
            provider = self._provider_for(job["provider"])
            updated = self.generate_images(
                storyboard=storyboard,
                provider=provider,
                source_dir=self.source_dir,
                output_dir=self.image_dir,
                metadata_dir=self.metadata_dir,
            )
            path = save_storyboard(updated, self.storyboard_dir)
            self.project_store.update_episode(project_id, episode_id, {"status": "imaged", "storyboard_path": str(path), "error": ""})
            return
        if step == "video":
            storyboard = load_storyboard(storyboard_path(self.storyboard_dir, project_id, episode_id))
            video = self.export_video(storyboard, self.output_dir)
            storyboard["video_path"] = str(video)
            save_storyboard(storyboard, self.storyboard_dir)
            self.project_store.update_episode(project_id, episode_id, {"status": "exported", "video_path": str(video), "error": ""})
            return
        raise ValueError(f"invalid step: {step}")

    def _provider_for(self, provider_name: str) -> Any:
        if provider_name != "openai":
            return MockAnimeProvider()
        config = self.config_loader()
        api_key = config.get("openai_api_key", "")
        if not api_key:
            raise ValueError("OpenAI API Key is not configured")
        return OpenAIImageProvider(
            api_key=api_key,
            model=config.get("openai_image_model", "gpt-image-2"),
            endpoint=config.get("openai_base_url", "https://aigate.zhixingjidian.cn"),
        )

    def _raise_if_cancelled(self, job: dict[str, Any]) -> None:
        if job.get("cancel_requested"):
            raise JobCancelled()

    def _mark_episode_failed(self, project_id: str, episode_id: str, exc: Exception) -> None:
        if not project_id or not episode_id:
            return
        try:
            self.project_store.update_episode(project_id, episode_id, {"status": "failed", "error": str(exc)})
        except Exception:
            return


class JobCancelled(Exception):
    pass
```

- [ ] **Step 4: Run job queue tests and verify they pass**

Run:

```bash
.venv/bin/python -m unittest tests.test_job_queue -v
```

Expected: store and runner tests pass.

---

### Task 3: Launcher Job API

**Files:**

- Modify: `anime_workflow/launcher/server.py`
- Modify: `tests/test_launcher_server.py`

- [ ] **Step 1: Add failing HTTP tests for job API**

Append these tests to `LauncherServerTest` in `tests/test_launcher_server.py`:

```python
    def test_jobs_api_creates_lists_cancels_and_retries_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, thread = self.with_server(Path(tmp) / "projects")
            server.jobs_dir = Path(tmp) / "jobs"
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "示例项目"})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})

                status, created = self.request_json(
                    server,
                    "/api/jobs",
                    {
                        "project_id": "demo",
                        "episode_ids": ["episode_001"],
                        "steps": ["full"],
                        "provider": "mock",
                    },
                )
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(created["ok"])
                self.assertEqual(created["job"]["steps"], ["storyboard", "images", "video"])

                status, jobs = self.request_json(server, "/api/jobs")
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(jobs["jobs"][0]["job_id"], created["job"]["job_id"])

                status, cancelled = self.request_json(server, f"/api/jobs/{created['job']['job_id']}/cancel", {})
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(cancelled["job"]["status"], "cancelled")

                status, retried = self.request_json(server, f"/api/jobs/{created['job']['job_id']}/retry", {})
                self.assertEqual(status, HTTPStatus.OK)
                self.assertNotEqual(retried["job"]["job_id"], created["job"]["job_id"])
                self.assertEqual(retried["job"]["status"], "queued")
            finally:
                self.stop_server(server, thread)

    def test_jobs_api_rejects_missing_episode(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, thread = self.with_server(Path(tmp) / "projects")
            server.jobs_dir = Path(tmp) / "jobs"
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "示例项目"})

                status, payload = self.request_json(
                    server,
                    "/api/jobs",
                    {
                        "project_id": "demo",
                        "episode_ids": ["episode_999"],
                        "steps": ["storyboard"],
                        "provider": "mock",
                    },
                )

                self.assertEqual(status, HTTPStatus.NOT_FOUND)
                self.assertFalse(payload["ok"])
                self.assertIn("episode not found", payload["error"])
            finally:
                self.stop_server(server, thread)
```

- [ ] **Step 2: Run launcher tests and verify they fail**

Run:

```bash
.venv/bin/python -m unittest tests.test_launcher_server.LauncherServerTest.test_jobs_api_creates_lists_cancels_and_retries_job tests.test_launcher_server.LauncherServerTest.test_jobs_api_rejects_missing_episode -v
```

Expected: fail with 404 because `/api/jobs` does not exist.

- [ ] **Step 3: Wire job store and runner in launcher**

Modify imports in `anime_workflow/launcher/server.py`:

```python
from anime_workflow.jobs.runner import JobRunner
from anime_workflow.jobs.store import JobStore
```

Add constants near existing path constants:

```python
JOBS_DIR = PROJECT_ROOT / "data/jobs"
```

Add properties to `LauncherRequestHandler`:

```python
    @property
    def job_store(self) -> JobStore:
        return JobStore(Path(getattr(self.server, "jobs_dir", JOBS_DIR)))

    @property
    def job_runner(self) -> JobRunner:
        runner = getattr(self.server, "job_runner", None)
        if runner is None:
            runner = JobRunner(
                job_store=self.job_store,
                project_store=self.project_store,
                storyboard_dir=STORYBOARD_DIR,
                source_dir=PROJECT_ROOT / "data/assets/source_frames",
                image_dir=PROJECT_ROOT / "data/assets/anime_frames",
                metadata_dir=PROJECT_ROOT / "data/assets/api_metadata",
                output_dir=configured_output_dir(self.config_store.load()),
                config_loader=self.config_store.load,
            )
            self.server.job_runner = runner
        return runner
```

Add GET route before static handling:

```python
        if parsed.path == "/api/jobs":
            self._handle_jobs_list()
            return
```

Add POST routes before project routes:

```python
        if parsed.path == "/api/jobs":
            self._handle_jobs_create()
            return
        if parsed.path.startswith("/api/jobs/"):
            self._handle_jobs_post(parsed.path)
            return
```

Add handler methods:

```python
    def _handle_jobs_list(self) -> None:
        try:
            self._json({"ok": True, "jobs": self.job_store.list_jobs()})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)

    def _handle_jobs_create(self) -> None:
        try:
            body = self._read_json()
            project_id = str(body.get("project_id") or "")
            self.project_store.get_project(project_id)
            for episode_id in body.get("episode_ids", []):
                self.project_store.get_episode(project_id, str(episode_id))
            job = self.job_store.create_job(body)
            self.job_runner.ensure_running()
            self._json({"ok": True, "job": job})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _handle_jobs_post(self, path: str) -> None:
        try:
            job_id, action = job_action_from_api_path(path)
            if action == "cancel":
                self._json({"ok": True, "job": self.job_store.request_cancel(job_id)})
                return
            if action == "retry":
                job = self.job_store.retry_job(job_id)
                self.job_runner.ensure_running()
                self._json({"ok": True, "job": job})
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)
```

Add helper near other route helpers:

```python
def job_action_from_api_path(path: str) -> tuple[str, str]:
    parts = [unquote(part) for part in path.split("/") if part]
    if len(parts) != 4 or parts[0] != "api" or parts[1] != "jobs":
        raise ValueError("job action path is invalid")
    job_id = parts[2].strip()
    action = parts[3].strip()
    if not job_id:
        raise ValueError("job_id is required")
    if job_id != project_slug(job_id, ""):
        raise ValueError("job_id is invalid")
    if action not in {"cancel", "retry"}:
        raise ValueError("job action is invalid")
    return job_id, action
```

- [ ] **Step 4: Prevent tests from accidentally running background worker**

In `test_jobs_api_creates_lists_cancels_and_retries_job`, before making requests, attach a no-op runner:

```python
class NoopRunner:
    def ensure_running(self) -> None:
        return None

server.job_runner = NoopRunner()
```

Add this directly after `server.jobs_dir = Path(tmp) / "jobs"` so create/retry does not race with cancellation.

- [ ] **Step 5: Run launcher tests and verify they pass**

Run:

```bash
.venv/bin/python -m unittest tests.test_launcher_server -v
```

Expected: all launcher server tests pass.

---

### Task 4: Frontend Job API Types

**Files:**

- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add job types**

Add below `ProjectEpisodeProductionResponse`:

```typescript
export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export type Job = {
  job_id: string;
  project_id: string;
  episode_ids: string[];
  steps: Array<"storyboard" | "images" | "video">;
  provider: "mock" | "openai";
  status: JobStatus;
  current_episode_id: string;
  current_step: string;
  total_steps: number;
  completed_steps: number;
  progress: number;
  error: string;
  created_at: string;
  started_at: string;
  finished_at: string;
  cancel_requested: boolean;
  updated_at: string;
};

export type CreateJobRequest = {
  project_id: string;
  episode_ids: string[];
  steps: Array<"storyboard" | "images" | "video" | "full">;
  provider: "mock" | "openai";
};
```

- [ ] **Step 2: Add API functions**

Add to `api`:

```typescript
  listJobs: () => request<{ ok: boolean; jobs: Job[] }>("/api/jobs"),
  createJob: (payload: CreateJobRequest) =>
    request<{ ok: boolean; job: Job }>("/api/jobs", { method: "POST", body: JSON.stringify(payload) }),
  cancelJob: (jobId: string) =>
    request<{ ok: boolean; job: Job }>(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST", body: "{}" }),
  retryJob: (jobId: string) =>
    request<{ ok: boolean; job: Job }>(`/api/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST", body: "{}" }),
```

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: TypeScript and Vite build pass.

---

### Task 5: Frontend Queue UI

**Files:**

- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Import job types**

Modify the API import block in `frontend/src/App.tsx`:

```typescript
  CreateJobRequest,
  Job,
```

- [ ] **Step 2: Add job and selection state**

Add near existing project queue state:

```typescript
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedEpisodeIds, setSelectedEpisodeIds] = useState<string[]>([]);
  const [jobSteps, setJobSteps] = useState<CreateJobRequest["steps"]>(["full"]);
  const [jobProvider, setJobProvider] = useState<"mock" | "openai">("mock");
```

- [ ] **Step 3: Add job refresh and polling helpers**

Add functions near `refreshProjectLibrary`:

```typescript
  const refreshJobs = async () => {
    const data = await api.listJobs();
    setJobs(data.jobs);
    return data.jobs;
  };

  const hasActiveJobs = jobs.some((job) => job.status === "queued" || job.status === "running");
```

Add polling effect after existing config effect:

```typescript
  useEffect(() => {
    refreshJobs().catch((error: Error) => setNotice(error.message));
  }, []);

  useEffect(() => {
    if (!hasActiveJobs) return;
    const timer = window.setInterval(() => {
      refreshJobs()
        .then((latestJobs) => {
          if (latestJobs.every((job) => job.status !== "queued" && job.status !== "running")) {
            return Promise.all([refreshProjectLibrary(currentProjectId), api.getEpisode(episodeForm.project_id, episodeForm.episode_id).catch(() => null)]);
          }
          return null;
        })
        .then((result) => {
          const episodeResult = Array.isArray(result) ? result[1] : null;
          if (episodeResult?.storyboard) setEpisode(episodeResult.storyboard);
        })
        .catch((error: Error) => setNotice(error.message));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [hasActiveJobs, currentProjectId, episodeForm.project_id, episodeForm.episode_id]);
```

- [ ] **Step 4: Add selection and job creation handlers**

Add near `createBatchEpisodes`:

```typescript
  const toggleEpisodeSelection = (episodeId: string) => {
    setSelectedEpisodeIds((current) =>
      current.includes(episodeId) ? current.filter((item) => item !== episodeId) : [...current, episodeId],
    );
  };

  const selectAllProjectEpisodes = () => {
    setSelectedEpisodeIds(projectEpisodes.map((item) => item.episode_id));
  };

  const clearSelectedEpisodes = () => {
    setSelectedEpisodeIds([]);
  };

  const estimatedImageCount = projectEpisodes
    .filter((item) => selectedEpisodeIds.includes(item.episode_id))
    .reduce((total, item) => total + item.shot_count, 0);

  const createSelectedEpisodesJob = () =>
    runBusy("job-create", async () => {
      if (!selectedEpisodeIds.length) throw new Error("请先选择要批量生产的剧集");
      const payload: CreateJobRequest = {
        project_id: currentProjectId,
        episode_ids: selectedEpisodeIds,
        steps: jobSteps,
        provider: jobProvider,
      };
      if (jobProvider === "openai") {
        const ok = window.confirm(
          `将使用 gpt-image-2 为 ${selectedEpisodeIds.length} 集生成约 ${estimatedImageCount} 张图片，可能消耗真实 API 额度。确认加入任务队列？`,
        );
        if (!ok) return;
      }
      await api.createJob(payload);
      setNotice("任务已加入队列");
      await refreshJobs();
    });

  const cancelJob = (job: Job) =>
    runBusy(`job-cancel-${job.job_id}`, async () => {
      await api.cancelJob(job.job_id);
      await refreshJobs();
    });

  const retryJob = (job: Job) =>
    runBusy(`job-retry-${job.job_id}`, async () => {
      await api.retryJob(job.job_id);
      await refreshJobs();
    });
```

- [ ] **Step 5: Add queue controls to the project production panel**

In the `项目级批量生产` panel, after the batch episode creation form and before the episode list, add:

```tsx
                  <div className="mt-3 rounded-ui border border-line bg-slate-50 p-3">
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <div className="text-sm font-semibold">批量任务</div>
                      <div className="flex flex-wrap gap-2">
                        <Button type="button" variant="secondary" size="sm" onClick={selectAllProjectEpisodes}>
                          全选
                        </Button>
                        <Button type="button" variant="secondary" size="sm" onClick={clearSelectedEpisodes}>
                          清空
                        </Button>
                      </div>
                    </div>
                    <div className="grid grid-cols-[1fr_1fr_auto] items-end gap-2 max-[760px]:grid-cols-1">
                      <Field label="执行步骤">
                        <select
                          className="input"
                          value={jobSteps.length === 1 && jobSteps[0] === "full" ? "full" : jobSteps.join(",")}
                          onChange={(event) => {
                            const value = event.target.value;
                            if (value === "full") setJobSteps(["full"]);
                            else setJobSteps(value.split(",") as CreateJobRequest["steps"]);
                          }}
                        >
                          <option value="full">全流程</option>
                          <option value="storyboard">只生成分镜</option>
                          <option value="images">只生成图片</option>
                          <option value="video">只合成视频</option>
                          <option value="storyboard,images">分镜 + 图片</option>
                          <option value="images,video">图片 + 视频</option>
                        </select>
                      </Field>
                      <Field label="图片 Provider">
                        <select className="input" value={jobProvider} onChange={(event) => setJobProvider(event.target.value as "mock" | "openai")}>
                          <option value="mock">mock 占位图</option>
                          <option value="openai">gpt-image-2 API</option>
                        </select>
                      </Field>
                      <Button type="button" onClick={createSelectedEpisodesJob} busy={busyAction === "job-create"} icon={Play}>
                        加入任务队列
                      </Button>
                    </div>
                    <div className="mt-2 font-mono text-xs text-ink-500">
                      已选择 {selectedEpisodeIds.length} 集，预计图片 {estimatedImageCount} 张。
                    </div>
                  </div>
```

- [ ] **Step 6: Add checkboxes to each project episode row**

Modify the `EpisodeRow` props:

```typescript
  selected: boolean;
  onToggleSelected: (episodeId: string) => void;
```

In the `EpisodeRow` JSX, add a checkbox near `E{episode.episode_no}`:

```tsx
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onToggleSelected(episode.episode_id)}
              aria-label={`选择 ${episode.episode_id}`}
              className="h-4 w-4"
            />
```

Update the `EpisodeRow` call:

```tsx
                          selected={selectedEpisodeIds.includes(projectEpisode.episode_id)}
                          onToggleSelected={toggleEpisodeSelection}
```

- [ ] **Step 7: Add queue panel**

After the `项目级批量生产` panel and before the metrics section, add:

```tsx
                <Panel title="任务队列" icon={Play} action={<Button variant="secondary" size="sm" onClick={() => runBusy("jobs-refresh", refreshJobs)} busy={busyAction === "jobs-refresh"} icon={RefreshCw}>刷新</Button>}>
                  {jobs.length ? (
                    <div className="grid gap-2">
                      {jobs.slice(0, 20).map((job) => (
                        <JobRow key={job.job_id} job={job} busyAction={busyAction} onCancel={cancelJob} onRetry={retryJob} />
                      ))}
                    </div>
                  ) : (
                    <EmptyState text="暂无任务。" />
                  )}
                </Panel>
```

Add `JobRow` helper near `EpisodeRow`:

```tsx
function JobRow({
  job,
  busyAction,
  onCancel,
  onRetry,
}: {
  job: Job;
  busyAction: string | null;
  onCancel: (job: Job) => void;
  onRetry: (job: Job) => void;
}) {
  const isActive = job.status === "queued" || job.status === "running";
  const canRetry = job.status === "failed" || job.status === "cancelled";
  return (
    <article className="rounded-ui border border-line bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-ink-500">{job.job_id}</span>
            <span className={clsx("rounded-ui px-2 py-1 text-xs", job.status === "failed" ? "bg-red-50 text-red-700" : "bg-slate-100 text-ink-700")}>
              {job.status}
            </span>
            <span className="rounded-ui bg-blue-50 px-2 py-1 text-xs text-blue-700">{job.provider}</span>
          </div>
          <div className="mt-1 text-sm text-ink-700">
            {job.project_id} / {job.episode_ids.length} 集 / {job.steps.join(" -> ")}
          </div>
          <div className="mt-1 font-mono text-xs text-ink-500">
            {job.completed_steps}/{job.total_steps} · {job.progress}% · {job.current_episode_id || "-"} {job.current_step || ""}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {isActive && (
            <Button type="button" variant="secondary" size="sm" onClick={() => onCancel(job)} busy={busyAction === `job-cancel-${job.job_id}`} icon={Square}>
              取消
            </Button>
          )}
          {canRetry && (
            <Button type="button" variant="secondary" size="sm" onClick={() => onRetry(job)} busy={busyAction === `job-retry-${job.job_id}`} icon={RefreshCw}>
              重试
            </Button>
          )}
        </div>
      </div>
      {job.error && <div className="mt-2 break-all font-mono text-xs leading-5 text-red-700">{job.error}</div>}
    </article>
  );
}
```

- [ ] **Step 8: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: TypeScript and Vite build pass.

---

### Task 6: End-To-End Verification

**Files:**

- Verify only; no planned source edits.

- [ ] **Step 1: Run all backend tests**

Run:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Expected: all tests pass. The expected count will be higher than 51 after adding job queue tests.

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: TypeScript and Vite build pass. The known `/fonts/msyh.ttc` runtime-resolution warning is acceptable.

- [ ] **Step 3: Restart launcher**

Run:

```bash
.venv/bin/python - <<'PY'
import os, signal, subprocess, time
from pathlib import Path

root = Path.cwd()
current = os.getpid()
for line in subprocess.run(["pgrep", "-af", "scripts/start_launcher.py"], text=True, capture_output=True).stdout.splitlines():
    pid = int(line.split()[0])
    if pid != current:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
for _ in range(30):
    live = [line for line in subprocess.run(["pgrep", "-af", "scripts/start_launcher.py"], text=True, capture_output=True).stdout.splitlines() if int(line.split()[0]) != current]
    if not live:
        break
    time.sleep(0.2)
log = root / "work/launcher.log"
log.parent.mkdir(parents=True, exist_ok=True)
stdout = log.open("a", encoding="utf-8")
process = subprocess.Popen([str(root / ".venv/bin/python"), str(root / "scripts/start_launcher.py")], cwd=str(root), stdout=stdout, stderr=subprocess.STDOUT, start_new_session=True)
print(process.pid)
PY
```

Expected: prints a new launcher PID.

- [ ] **Step 4: Smoke test job APIs**

Run:

```bash
curl -sS http://127.0.0.1:7860/api/jobs
```

Expected:

```json
{"ok": true, "jobs": []}
```

If prior jobs exist, the response should still have `ok: true` and a `jobs` array.

- [ ] **Step 5: Manual UI test with mock provider**

In `http://127.0.0.1:7860`:

1. Open `剧集生产`.
2. Select one existing episode checkbox.
3. Keep provider as `mock`.
4. Choose `全流程`.
5. Click `加入任务队列`.
6. Verify `任务队列` shows `queued` then `running` then `completed`.
7. Verify the selected episode becomes `exported`.
8. Open `成品库` and verify the new `.mp4` appears.

- [ ] **Step 6: Manual UI test for OpenAI confirmation**

In `剧集生产`:

1. Select one existing episode checkbox.
2. Change provider to `gpt-image-2 API`.
3. Click `加入任务队列`.
4. Verify the browser confirmation appears and includes estimated image count.
5. Click cancel.
6. Verify no new OpenAI job is created.

---

## Execution Notes

- The workspace is not a git repository in the current local setup. Skip commit steps and report changed files plus verification output instead.
- Do not call the real image API in automated tests.
- Keep default provider as `mock` in UI.
- Keep worker concurrency at 1.
