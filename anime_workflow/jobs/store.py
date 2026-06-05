from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from anime_workflow.jobs.models import job_from, now_iso
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
        return data

    def _write_job(self, job: dict[str, Any]) -> None:
        job = dict(job)
        job["updated_at"] = now_iso()
        path = self.job_path(job["job_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
        tmp_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)
