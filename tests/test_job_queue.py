import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from anime_workflow.jobs.runner import JobRunner
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

    def test_create_job_adds_pending_items_for_each_episode_step(self):
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

            self.assertEqual(
                [(item["episode_id"], item["step"], item["status"]) for item in job["items"]],
                [
                    ("episode_001", "storyboard", "pending"),
                    ("episode_001", "images", "pending"),
                    ("episode_002", "storyboard", "pending"),
                    ("episode_002", "images", "pending"),
                ],
            )
            self.assertTrue(all(item["error"] == "" for item in job["items"]))
            self.assertTrue(all(item["output_path"] == "" for item in job["items"]))

    def test_get_job_derives_items_for_legacy_json_without_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            root.mkdir(parents=True)
            job_path = root / "job_legacy.json"
            job_path.write_text(
                json.dumps(
                    {
                        "job_id": "job_legacy",
                        "project_id": "demo_drama",
                        "episode_ids": ["episode_001"],
                        "steps": ["storyboard", "images"],
                        "provider": "mock",
                        "status": "queued",
                        "progress": 0,
                        "completed_steps": 0,
                        "total_steps": 2,
                        "current_episode_id": "",
                        "current_step": "",
                        "error": "",
                        "cancel_requested": False,
                        "created_at": "2026-06-04T00:00:00+00:00",
                        "updated_at": "2026-06-04T00:00:00+00:00",
                        "started_at": "",
                        "finished_at": "",
                    }
                ),
                encoding="utf-8",
            )
            store = JobStore(root)

            job = store.get_job("job_legacy")

            self.assertEqual(
                [(item["episode_id"], item["step"], item["status"]) for item in job["items"]],
                [("episode_001", "storyboard", "pending"), ("episode_001", "images", "pending")],
            )

    def test_get_job_preserves_stored_updated_at_when_normalizing_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            root.mkdir(parents=True)
            updated_at = "2026-06-04T00:00:00+00:00"
            (root / "job_legacy.json").write_text(
                json.dumps(
                    {
                        "job_id": "job_legacy",
                        "project_id": "demo_drama",
                        "episode_ids": ["episode_001"],
                        "steps": ["storyboard"],
                        "provider": "mock",
                        "status": "completed",
                        "progress": 100,
                        "completed_steps": 1,
                        "total_steps": 1,
                        "current_episode_id": "",
                        "current_step": "",
                        "error": "",
                        "cancel_requested": False,
                        "created_at": "2026-06-04T00:00:00+00:00",
                        "updated_at": updated_at,
                        "started_at": "2026-06-04T00:00:00+00:00",
                        "finished_at": "2026-06-04T00:01:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            store = JobStore(root)

            job = store.get_job("job_legacy")

            self.assertEqual(job["updated_at"], updated_at)

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
            with self.assertRaisesRegex(ValueError, "openai provider requires confirmation"):
                store.create_job({"project_id": "demo", "episode_ids": ["episode_001"], "steps": ["storyboard"], "provider": "openai"})

    def test_openai_job_requires_confirmation_for_create_and_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "jobs")
            job = store.create_job(
                {
                    "project_id": "demo",
                    "episode_ids": ["episode_001"],
                    "steps": ["storyboard"],
                    "provider": "openai",
                    "confirm_openai": True,
                }
            )

            with self.assertRaisesRegex(ValueError, "openai provider requires confirmation"):
                store.retry_job(job["job_id"])

            retried = store.retry_job(job["job_id"], confirm_openai=True)

            self.assertEqual(retried["provider"], "openai")
            self.assertEqual(retried["status"], "queued")

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

    def test_list_jobs_skips_corrupt_job_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            store = JobStore(root)
            valid = store.create_job({"project_id": "demo", "episode_ids": ["episode_001"], "steps": ["storyboard"], "provider": "mock"})
            (root / "job_corrupt.json").write_text("{", encoding="utf-8")

            self.assertEqual([job["job_id"] for job in store.list_jobs()], [valid["job_id"]])

    def test_recover_interrupted_jobs_marks_running_as_queued(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "jobs")
            queued = store.create_job({"project_id": "demo", "episode_ids": ["episode_001"], "steps": ["storyboard"], "provider": "mock"})
            running = store.update_job(queued["job_id"], {"status": "running", "progress": 25})

            recovered = store.recover_interrupted_jobs()

            self.assertEqual([job["job_id"] for job in recovered], [running["job_id"]])
            self.assertEqual(store.get_job(running["job_id"])["status"], "queued")

    def test_retry_payloads_scope_failed_episode_and_step_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "jobs")
            job = store.create_job(
                {
                    "project_id": "demo_drama",
                    "episode_ids": ["episode_001", "episode_002"],
                    "steps": ["storyboard", "images", "video"],
                    "provider": "mock",
                }
            )
            store.set_item_completed(job["job_id"], "episode_001", "storyboard", "/tmp/storyboard.json")
            store.set_item_failed(job["job_id"], "episode_001", "images", "image failed")
            store.set_item_failed(job["job_id"], "episode_002", "video", "video failed")

            failed_retry = store.create_failed_retry_job(job["job_id"])
            episode_retry = store.create_episode_retry_job(job["job_id"], "episode_002")
            step_retry = store.create_episode_step_retry_job(job["job_id"], "episode_001", "images")

            self.assertEqual(failed_retry["episode_ids"], ["episode_001", "episode_002"])
            self.assertEqual(failed_retry["steps"], ["images", "video"])
            self.assertEqual(episode_retry["episode_ids"], ["episode_002"])
            self.assertEqual(episode_retry["steps"], ["storyboard", "images", "video"])
            self.assertEqual(step_retry["episode_ids"], ["episode_001"])
            self.assertEqual(step_retry["steps"], ["images", "video"])

    def test_openai_targeted_retries_require_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "jobs")
            job = store.create_job(
                {
                    "project_id": "demo",
                    "episode_ids": ["episode_001"],
                    "steps": ["storyboard", "images", "video"],
                    "provider": "openai",
                    "confirm_openai": True,
                }
            )
            store.set_item_failed(job["job_id"], "episode_001", "images", "boom")

            with self.assertRaisesRegex(ValueError, "openai provider requires confirmation"):
                store.create_failed_retry_job(job["job_id"])
            with self.assertRaisesRegex(ValueError, "openai provider requires confirmation"):
                store.create_episode_retry_job(job["job_id"], "episode_001")
            with self.assertRaisesRegex(ValueError, "openai provider requires confirmation"):
                store.create_episode_step_retry_job(job["job_id"], "episode_001", "images")

            retried = store.create_failed_retry_job(job["job_id"], confirm_openai=True)

            self.assertEqual(retried["provider"], "openai")
            self.assertEqual(retried["steps"], ["images", "video"])


class JobRunnerTest(unittest.TestCase):
    def test_run_next_processes_full_mock_job_and_updates_episode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = JobStore(root / "jobs")
            project_store = build_project_store(root)
            job = store.create_job(
                {
                    "project_id": "demo",
                    "episode_ids": ["episode_001"],
                    "steps": ["full"],
                    "provider": "mock",
                }
            )
            video_path = root / "exports/demo-episode_001.mp4"

            def fake_images(storyboard, provider, source_dir, output_dir, metadata_dir):
                updated = dict(storyboard)
                updated["shots"] = [dict(shot) for shot in storyboard["shots"]]
                updated["shots"][0]["anime_image"] = str(root / "frame.png")
                return updated

            with mock.patch("anime_workflow.jobs.runner.generate_episode_images", fake_images), mock.patch(
                "anime_workflow.jobs.runner.export_episode_video", lambda storyboard, output_dir: video_path
            ):
                completed = JobRunner(
                    job_store=store,
                    project_store=project_store,
                    storyboard_dir=root / "storyboards",
                    source_dir=root / "source",
                    image_dir=root / "images",
                    metadata_dir=root / "metadata",
                    output_dir=root / "exports",
                ).run_next()

            episode = project_store.get_episode("demo", "episode_001")
            self.assertEqual(completed["job_id"], job["job_id"])
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["progress"], 100)
            self.assertEqual(episode["status"], "exported")
            self.assertEqual(episode["video_path"], str(video_path))
            stored = store.get_job(job["job_id"])
            self.assertEqual(
                [(item["step"], item["status"]) for item in stored["items"]],
                [("storyboard", "completed"), ("images", "completed"), ("video", "completed")],
            )
            self.assertTrue(stored["items"][0]["output_path"].endswith("storyboard.json"))
            self.assertTrue(stored["items"][1]["output_path"].endswith("storyboard.json"))
            self.assertEqual(stored["items"][2]["output_path"], str(video_path))

    def test_openai_job_without_api_key_fails_before_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = JobStore(root / "jobs")
            project_store = build_project_store(root)
            job = store.create_job(
                {
                    "project_id": "demo",
                    "episode_ids": ["episode_001"],
                    "steps": ["images"],
                    "provider": "openai",
                    "confirm_openai": True,
                }
            )

            failed = JobRunner(
                job_store=store,
                project_store=project_store,
                storyboard_dir=root / "storyboards",
                source_dir=root / "source",
                image_dir=root / "images",
                metadata_dir=root / "metadata",
                output_dir=root / "exports",
                config_loader=lambda: {"openai_api_key": ""},
            ).run_next()

            self.assertEqual(failed["job_id"], job["job_id"])
            self.assertEqual(failed["status"], "failed")
            self.assertIn("OpenAI API Key is not configured", failed["error"])
            stored = store.get_job(job["job_id"])
            self.assertEqual(stored["items"][0]["status"], "failed")
            self.assertIn("OpenAI API Key is not configured", stored["items"][0]["error"])

    def test_cancel_requested_before_run_marks_cancelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = JobStore(root / "jobs")
            project_store = build_project_store(root)
            job = store.create_job({"project_id": "demo", "episode_ids": ["episode_001"], "steps": ["storyboard"], "provider": "mock"})
            store.request_cancel(job["job_id"])

            cancelled = JobRunner(
                job_store=store,
                project_store=project_store,
                storyboard_dir=root / "storyboards",
                source_dir=root / "source",
                image_dir=root / "images",
                metadata_dir=root / "metadata",
                output_dir=root / "exports",
            ).run_next()

            self.assertEqual(cancelled["status"], "cancelled")
            self.assertEqual(cancelled["progress"], 0)
            self.assertEqual(store.get_job(job["job_id"])["items"][0]["status"], "cancelled")

    def test_cancel_during_run_marks_pending_items_cancelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = JobStore(root / "jobs")
            project_store = build_project_store(root)
            job = store.create_job({"project_id": "demo", "episode_ids": ["episode_001"], "steps": ["storyboard", "images"], "provider": "mock"})

            original_run_step = JobRunner._run_step

            def run_step_and_cancel(runner, running_job, episode_id, step):
                output = original_run_step(runner, running_job, episode_id, step)
                store.request_cancel(running_job["job_id"])
                return output

            with mock.patch.object(JobRunner, "_run_step", run_step_and_cancel):
                cancelled = JobRunner(
                    job_store=store,
                    project_store=project_store,
                    storyboard_dir=root / "storyboards",
                    source_dir=root / "source",
                    image_dir=root / "images",
                    metadata_dir=root / "metadata",
                    output_dir=root / "exports",
                ).run_next()

            self.assertEqual(cancelled["status"], "cancelled")
            stored = store.get_job(job["job_id"])
            self.assertEqual([(item["step"], item["status"]) for item in stored["items"]], [("storyboard", "completed"), ("images", "cancelled")])


def build_project_store(root: Path):
    from anime_workflow.projects.store import ProjectStore

    store = ProjectStore(root / "projects")
    store.save_project(
        {
            "project_id": "demo",
            "name": "示例项目",
            "genre": "悬疑",
            "premise": "匿名信",
            "default_shot_count": 1,
            "default_duration_seconds": 3,
        }
    )
    store.create_episode_batch("demo", {"count": 1})
    return store


if __name__ == "__main__":
    unittest.main()
