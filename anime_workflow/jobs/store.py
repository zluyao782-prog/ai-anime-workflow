from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from anime_workflow.jobs.models import job_from, now_iso, step_sequence_from
from anime_workflow.projects.models import slug


class JobStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._lock = threading.RLock()

    def job_path(self, job_id: str) -> Path:
        return self.root / f"{slug(job_id, 'job')}.json"

    def create_job(self, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            provider = str(values.get("provider") or "mock").strip().lower()
            if provider == "openai" and values.get("confirm_openai") is not True:
                raise ValueError("openai provider requires confirmation")
            job = job_from(values)
            self._write_job(job)
            return job

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            path = self.job_path(job_id)
            if not path.exists():
                raise FileNotFoundError(f"job not found: {slug(job_id, 'job')}")
            return self._read_job_path(path)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            if not self.root.exists():
                return []
            jobs: list[dict[str, Any]] = []
            for path in self.root.glob("job_*.json"):
                try:
                    jobs.append(self._read_job_path(path))
                except (json.JSONDecodeError, OSError, ValueError):
                    continue
            return sorted(jobs, key=lambda item: str(item.get("created_at", "")), reverse=True)

    def next_queued_job(self) -> dict[str, Any] | None:
        with self._lock:
            queued = [job for job in self.list_jobs() if job.get("status") == "queued"]
            if not queued:
                return None
            return sorted(queued, key=lambda item: str(item.get("created_at", "")))[0]

    def update_job(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            existing = self.get_job(job_id)
            merged = dict(existing)
            merged.update(updates)
            merged["job_id"] = existing["job_id"]
            job = job_from(merged, existing)
            self._write_job(job)
            return job

    def request_cancel(self, job_id: str) -> dict[str, Any]:
        return self.update_job(job_id, {"cancel_requested": True})

    def set_item_running(self, job_id: str, episode_id: str, step: str) -> dict[str, Any]:
        return self._update_item(
            job_id,
            episode_id,
            step,
            {"status": "running", "error": "", "started_at": now_iso(), "finished_at": ""},
        )

    def set_item_completed(self, job_id: str, episode_id: str, step: str, output_path: str) -> dict[str, Any]:
        return self._update_item(
            job_id,
            episode_id,
            step,
            {"status": "completed", "error": "", "output_path": output_path, "finished_at": now_iso()},
        )

    def set_item_failed(self, job_id: str, episode_id: str, step: str, error: str) -> dict[str, Any]:
        return self._update_item(
            job_id,
            episode_id,
            step,
            {"status": "failed", "error": error, "finished_at": now_iso()},
        )

    def cancel_pending_items(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self.get_job(job_id)
            items = []
            for item in job["items"]:
                next_item = dict(item)
                if next_item["status"] in {"pending", "running"}:
                    next_item["status"] = "cancelled"
                    next_item["finished_at"] = now_iso()
                items.append(next_item)
            return self.update_job(job_id, {"items": items})

    def retry_job(self, job_id: str, confirm_openai: bool = False) -> dict[str, Any]:
        with self._lock:
            existing = self.get_job(job_id)
            if existing.get("provider") == "openai" and not confirm_openai:
                raise ValueError("openai provider requires confirmation")
            return self.create_job(
                {
                    "project_id": existing["project_id"],
                    "episode_ids": existing["episode_ids"],
                    "steps": existing["steps"],
                    "provider": existing["provider"],
                    "confirm_openai": confirm_openai,
                }
            )

    def create_failed_retry_job(self, job_id: str, confirm_openai: bool = False) -> dict[str, Any]:
        with self._lock:
            existing = self.get_job(job_id)
            failed_items = [item for item in existing["items"] if item["status"] == "failed"]
            if not failed_items:
                raise ValueError("job has no failed items")
            episode_ids = self._ordered_unique([item["episode_id"] for item in failed_items])
            steps = self._merged_retry_steps([item["step"] for item in failed_items])
            return self._create_retry_job(existing, episode_ids, steps, confirm_openai)

    def create_episode_retry_job(self, job_id: str, episode_id: str, confirm_openai: bool = False) -> dict[str, Any]:
        with self._lock:
            existing = self.get_job(job_id)
            if episode_id not in existing["episode_ids"]:
                raise FileNotFoundError(f"episode not found in job: {episode_id}")
            return self._create_retry_job(existing, [episode_id], existing["steps"], confirm_openai)

    def create_episode_step_retry_job(
        self,
        job_id: str,
        episode_id: str,
        step: str,
        confirm_openai: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            existing = self.get_job(job_id)
            if episode_id not in existing["episode_ids"]:
                raise FileNotFoundError(f"episode not found in job: {episode_id}")
            steps = [item for item in step_sequence_from(step) if item in existing["steps"]]
            if not steps:
                raise ValueError(f"invalid step: {step}")
            return self._create_retry_job(existing, [episode_id], steps, confirm_openai)

    def recover_interrupted_jobs(self) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        with self._lock:
            for job in self.list_jobs():
                if job.get("status") == "running":
                    recovered.append(
                        self.update_job(
                            job["job_id"],
                            {
                                "status": "queued",
                                "current_episode_id": "",
                                "current_step": "",
                                "error": "任务在上次服务退出时中断，已重新排队",
                            },
                        )
                    )
            return recovered

    def has_queued_jobs(self) -> bool:
        return self.next_queued_job() is not None

    def _read_job_path(self, path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("job json must be an object")
        normalized = job_from(data, data)
        if "updated_at" in data:
            normalized["updated_at"] = str(data.get("updated_at") or "")
        return normalized

    def _update_item(self, job_id: str, episode_id: str, step: str, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            job = self.get_job(job_id)
            items = []
            matched = False
            for item in job["items"]:
                next_item = dict(item)
                if next_item["episode_id"] == episode_id and next_item["step"] == step:
                    next_item.update(updates)
                    matched = True
                items.append(next_item)
            if not matched:
                raise ValueError("job item not found")
            return self.update_job(job_id, {"items": items})

    def _create_retry_job(
        self,
        existing: dict[str, Any],
        episode_ids: list[str],
        steps: list[str],
        confirm_openai: bool,
    ) -> dict[str, Any]:
        if existing.get("provider") == "openai" and not confirm_openai:
            raise ValueError("openai provider requires confirmation")
        return self.create_job(
            {
                "project_id": existing["project_id"],
                "episode_ids": episode_ids,
                "steps": steps,
                "provider": existing["provider"],
                "confirm_openai": confirm_openai,
            }
        )

    @staticmethod
    def _ordered_unique(values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            if value not in result:
                result.append(value)
        return result

    @staticmethod
    def _merged_retry_steps(failed_steps: list[str]) -> list[str]:
        rank = {"storyboard": 0, "images": 1, "video": 2}
        earliest = min(rank[step] for step in failed_steps)
        return ["storyboard", "images", "video"][earliest:]

    def _write_job(self, job: dict[str, Any]) -> None:
        job = dict(job)
        job["updated_at"] = now_iso()
        path = self.job_path(job["job_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
        tmp_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)
