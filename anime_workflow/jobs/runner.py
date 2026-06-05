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
        config_loader: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.job_store = job_store
        self.project_store = project_store
        self.storyboard_dir = Path(storyboard_dir)
        self.source_dir = Path(source_dir)
        self.image_dir = Path(image_dir)
        self.metadata_dir = Path(metadata_dir)
        self.output_dir = Path(output_dir)
        self.config_loader = config_loader or (lambda: {})
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._thread = threading.Thread(target=self.run_until_idle, daemon=True)
            self._thread.start()
            return True

    def run_until_idle(self) -> None:
        while self.run_next() is not None:
            continue

    def run_next(self) -> dict[str, Any] | None:
        job = self.job_store.next_queued_job()
        if not job:
            return None
        try:
            return self._run_job(job)
        except Exception as exc:
            return self.job_store.update_job(
                job["job_id"],
                {"status": "failed", "error": str(exc), "finished_at": now_iso()},
            )

    def _run_job(self, job: dict[str, Any]) -> dict[str, Any]:
        if job.get("cancel_requested"):
            return self.job_store.update_job(
                job["job_id"],
                {"status": "cancelled", "progress": 0, "finished_at": now_iso()},
            )
        self.job_store.update_job(job["job_id"], {"status": "running", "started_at": now_iso(), "error": ""})
        completed_steps = 0
        total_steps = int(job["total_steps"])
        for episode_id in job["episode_ids"]:
            for step in job["steps"]:
                if self.job_store.get_job(job["job_id"]).get("cancel_requested"):
                    return self.job_store.update_job(
                        job["job_id"],
                        {
                            "status": "cancelled",
                            "completed_steps": completed_steps,
                            "progress": self._progress(completed_steps, total_steps),
                            "finished_at": now_iso(),
                        },
                    )
                self.job_store.update_job(
                    job["job_id"],
                    {
                        "current_episode_id": episode_id,
                        "current_step": step,
                        "completed_steps": completed_steps,
                        "progress": self._progress(completed_steps, total_steps),
                    },
                )
                self._run_step(job, episode_id, step)
                completed_steps += 1
                self.job_store.update_job(
                    job["job_id"],
                    {
                        "completed_steps": completed_steps,
                        "progress": self._progress(completed_steps, total_steps),
                    },
                )

        return self.job_store.update_job(
            job["job_id"],
            {
                "status": "completed",
                "progress": 100,
                "completed_steps": total_steps,
                "current_episode_id": "",
                "current_step": "",
                "finished_at": now_iso(),
            },
        )

    def _run_step(self, job: dict[str, Any], episode_id: str, step: str) -> None:
        project_id = job["project_id"]
        if step == "storyboard":
            values = self.project_store.build_storyboard_values(project_id, episode_id)
            storyboard = generate_storyboard(values)
            path = save_storyboard(storyboard, self.storyboard_dir)
            self.project_store.update_episode(project_id, episode_id, {"status": "storyboarded", "storyboard_path": str(path), "error": ""})
            return

        if step == "images":
            provider = self._provider(job["provider"])
            storyboard_file = storyboard_path(self.storyboard_dir, project_id, episode_id)
            storyboard = load_storyboard(storyboard_file)
            updated = generate_episode_images(
                storyboard=storyboard,
                provider=provider,
                source_dir=self.source_dir,
                output_dir=self.image_dir,
                metadata_dir=self.metadata_dir,
            )
            saved = save_storyboard(updated, self.storyboard_dir)
            self.project_store.update_episode(project_id, episode_id, {"status": "imaged", "storyboard_path": str(saved), "error": ""})
            return

        if step == "video":
            storyboard_file = storyboard_path(self.storyboard_dir, project_id, episode_id)
            storyboard = load_storyboard(storyboard_file)
            video = export_episode_video(storyboard, self.output_dir)
            storyboard["video_path"] = str(video)
            save_storyboard(storyboard, self.storyboard_dir)
            self.project_store.update_episode(project_id, episode_id, {"status": "exported", "video_path": str(video), "error": ""})
            return

        raise ValueError(f"invalid step: {step}")

    def _provider(self, provider_name: str):
        if provider_name == "openai":
            config = self.config_loader()
            api_key = str(config.get("openai_api_key") or "")
            if not api_key:
                raise ValueError("OpenAI API Key is not configured")
            return OpenAIImageProvider(
                api_key=api_key,
                model=config.get("openai_image_model", "gpt-image-2"),
                endpoint=config.get("openai_base_url", "https://aigate.zhixingjidian.cn"),
            )
        return MockAnimeProvider()

    @staticmethod
    def _progress(completed_steps: int, total_steps: int) -> int:
        if total_steps <= 0:
            return 0
        return max(0, min(100, round((completed_steps / total_steps) * 100)))
